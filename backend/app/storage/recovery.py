from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.storage.base import ObjectStorage, StorageError, StorageNotFoundError
from app.storage.malware import ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE

MAGIC = b"WLSNP1\0"
KEY_ID = re.compile(r"[0-9a-f]{8}")
SHA256 = re.compile(r"[0-9a-f]{64}")


class SnapshotError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class RecoveryObject:
    entity_type: str
    entity_id: str
    object_key: str
    content_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class EncryptedSnapshot:
    payload: bytes
    manifest_digest: str
    object_count: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RestoreResult:
    manifest_digest: str
    object_count: int
    scan_rows: tuple[Mapping[str, object], ...]
    operation_rows: tuple[Mapping[str, object], ...]


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _validate_recovery_object(item: RecoveryObject) -> None:
    try:
        UUID(item.entity_id)
    except ValueError:
        raise SnapshotError("invalid entity identity") from None
    if (
        re.fullmatch(r"[a-z][a-z0-9_]{0,63}", item.entity_type) is None
        or item.content_type not in ALLOWED_CONTENT_TYPES
        or not 1 <= item.size_bytes <= MAX_FILE_SIZE
        or SHA256.fullmatch(item.sha256) is None
        or not item.object_key
    ):
        raise SnapshotError("invalid object manifest")


async def create_encrypted_snapshot(
    storage: ObjectStorage,
    *,
    objects: Sequence[RecoveryObject],
    scan_rows: Sequence[Mapping[str, object]],
    operation_rows: Sequence[Mapping[str, object]],
    encryption_key: bytes,
    key_id: str,
    created_at: datetime | None = None,
) -> EncryptedSnapshot:
    if len(encryption_key) != 32 or KEY_ID.fullmatch(key_id) is None:
        raise SnapshotError("invalid snapshot key")
    resolved_time = created_at or datetime.now(UTC)
    if resolved_time.tzinfo is None or resolved_time.utcoffset() != timedelta(0):
        raise SnapshotError("snapshot time must use UTC")
    ordered = sorted(objects, key=lambda item: (item.object_key, item.entity_type, item.entity_id))
    if len({item.object_key for item in ordered}) != len(ordered):
        raise SnapshotError("duplicate object key")

    stored_objects: list[dict[str, object]] = []
    for item in ordered:
        _validate_recovery_object(item)
        try:
            stored = await storage.get_object(key=item.object_key)
        except StorageError:
            raise SnapshotError("snapshot source is unavailable") from None
        if (
            len(stored.body) != item.size_bytes
            or stored.metadata.size_bytes != item.size_bytes
            or stored.metadata.content_type != item.content_type
            or stored.metadata.sha256 != item.sha256
            or hashlib.sha256(stored.body).hexdigest() != item.sha256
        ):
            raise SnapshotError("snapshot source metadata mismatch")
        stored_objects.append(
            {
                **asdict(item),
                "body": base64.b64encode(stored.body).decode("ascii"),
            }
        )

    manifest = {
        "createdAt": resolved_time.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "objectCount": len(stored_objects),
        "objects": [asdict(item) for item in ordered],
        "operationRows": list(operation_rows),
        "scanRows": list(scan_rows),
        "version": 1,
    }
    manifest_digest = hashlib.sha256(_canonical(manifest)).hexdigest()
    plaintext = _canonical(
        {
            "manifest": manifest,
            "manifestDigest": manifest_digest,
            "storedObjects": stored_objects,
        }
    )
    nonce = os.urandom(12)
    header = MAGIC + key_id.encode("ascii")
    payload = header + nonce + AESGCM(encryption_key).encrypt(nonce, plaintext, header)
    return EncryptedSnapshot(
        payload=payload,
        manifest_digest=f"sha256:{manifest_digest}",
        object_count=len(stored_objects),
        created_at=resolved_time,
    )


async def restore_encrypted_snapshot(
    storage: ObjectStorage,
    *,
    payload: bytes,
    encryption_keys: Mapping[str, bytes],
) -> RestoreResult:
    header_size = len(MAGIC) + 8
    if len(payload) <= header_size + 12 or not payload.startswith(MAGIC):
        raise SnapshotError("invalid snapshot envelope")
    key_id = payload[len(MAGIC) : header_size].decode("ascii", errors="ignore")
    encryption_key = encryption_keys.get(key_id)
    if encryption_key is None or len(encryption_key) != 32:
        raise SnapshotError("snapshot key is unavailable")
    header = payload[:header_size]
    nonce = payload[header_size : header_size + 12]
    try:
        plaintext = AESGCM(encryption_key).decrypt(nonce, payload[header_size + 12 :], header)
        decoded = cast(dict[str, object], json.loads(plaintext))
    except (InvalidTag, UnicodeDecodeError, ValueError, TypeError):
        raise SnapshotError("snapshot authentication failed") from None
    if set(decoded) != {"manifest", "manifestDigest", "storedObjects"}:
        raise SnapshotError("invalid snapshot document")
    manifest = cast(dict[str, object], decoded["manifest"])
    manifest_digest = decoded["manifestDigest"]
    if (
        not isinstance(manifest_digest, str)
        or not hmac.compare_digest(
            hashlib.sha256(_canonical(manifest)).hexdigest(), manifest_digest
        )
        or manifest.get("version") != 1
    ):
        raise SnapshotError("snapshot manifest mismatch")
    raw_objects_value = decoded["storedObjects"]
    if not isinstance(raw_objects_value, list):
        raise SnapshotError("snapshot object count mismatch")
    raw_objects = cast(list[object], raw_objects_value)
    if manifest.get("objectCount") != len(raw_objects):
        raise SnapshotError("snapshot object count mismatch")

    restored_objects: list[tuple[RecoveryObject, bytes]] = []
    keys: set[str] = set()
    for raw in raw_objects:
        if not isinstance(raw, dict):
            raise SnapshotError("invalid stored object")
        item_data = cast(dict[str, object], raw)
        if set(item_data) != {
            "entity_type",
            "entity_id",
            "object_key",
            "content_type",
            "size_bytes",
            "sha256",
            "body",
        }:
            raise SnapshotError("invalid stored object")
        entity_type = item_data["entity_type"]
        entity_id = item_data["entity_id"]
        object_key = item_data["object_key"]
        content_type = item_data["content_type"]
        size_bytes = item_data["size_bytes"]
        sha256 = item_data["sha256"]
        encoded_body = item_data["body"]
        if (
            not isinstance(entity_type, str)
            or not isinstance(entity_id, str)
            or not isinstance(object_key, str)
            or not isinstance(content_type, str)
            or not isinstance(size_bytes, int)
            or not isinstance(sha256, str)
            or not isinstance(encoded_body, str)
        ):
            raise SnapshotError("invalid stored object")
        try:
            item = RecoveryObject(
                entity_type=entity_type,
                entity_id=entity_id,
                object_key=object_key,
                content_type=content_type,
                size_bytes=size_bytes,
                sha256=sha256,
            )
            body = base64.b64decode(encoded_body, validate=True)
        except (ValueError, TypeError):
            raise SnapshotError("invalid stored object") from None
        _validate_recovery_object(item)
        if (
            item.object_key in keys
            or len(body) != item.size_bytes
            or hashlib.sha256(body).hexdigest() != item.sha256
        ):
            raise SnapshotError("stored object integrity mismatch")
        keys.add(item.object_key)
        restored_objects.append((item, body))

    manifest_objects = manifest.get("objects")
    if manifest_objects != [asdict(item) for item, _body in restored_objects]:
        raise SnapshotError("stored objects do not match manifest")
    for item, _body in restored_objects:
        try:
            await storage.head_object(key=item.object_key)
        except StorageNotFoundError:
            continue
        except StorageError:
            raise SnapshotError("restore target is unavailable") from None
        raise SnapshotError("restore target is not empty")

    written: list[str] = []
    try:
        for item, body in restored_objects:
            await storage.put_object(
                key=item.object_key,
                body=body,
                content_type=item.content_type,
                sha256=item.sha256,
                if_absent=True,
            )
            written.append(item.object_key)
            metadata = await storage.head_object(key=item.object_key)
            if (
                metadata.size_bytes != item.size_bytes
                or metadata.content_type != item.content_type
                or metadata.sha256 != item.sha256
            ):
                raise SnapshotError("restored object metadata mismatch")
    except (StorageError, SnapshotError):
        for key in reversed(written):
            with suppress(StorageError):
                await storage.delete_object(key=key)
        raise SnapshotError("restore failed") from None

    raw_scans = manifest.get("scanRows")
    raw_operations = manifest.get("operationRows")
    if not isinstance(raw_scans, list) or not isinstance(raw_operations, list):
        raise SnapshotError("snapshot state rows are invalid")
    return RestoreResult(
        manifest_digest=f"sha256:{manifest_digest}",
        object_count=len(restored_objects),
        scan_rows=tuple(cast(list[Mapping[str, object]], raw_scans)),
        operation_rows=tuple(cast(list[Mapping[str, object]], raw_operations)),
    )
