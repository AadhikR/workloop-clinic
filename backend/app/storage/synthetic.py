from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.storage.base import (
    SignedDownload,
    StorageConflictError,
    StorageError,
    StorageNotFoundError,
    StoredObject,
    StoredObjectMetadata,
    validate_object_write,
)

KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9/_-]{0,1023}")


class SyntheticObjectStorage:
    def __init__(self, *, root: Path, signing_key: bytes, base_url: str) -> None:
        self._root = root.resolve()
        self._cipher = AESGCM(signing_key)
        self._base_url = base_url.rstrip("/")
        self._root.mkdir(parents=True, exist_ok=True)

    def _paths(self, key: str) -> tuple[Path, Path]:
        if not KEY_PATTERN.fullmatch(key) or "//" in key or "/../" in f"/{key}/":
            raise StorageError
        name = hashlib.sha256(key.encode()).hexdigest()
        body_path = (self._root / name[:2] / name).resolve()
        return body_path, body_path.with_suffix(body_path.suffix + ".metadata.json")

    async def put_object(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
        sha256: str,
        if_absent: bool = True,
    ) -> None:
        body_path, metadata_path = self._paths(key)
        validate_object_write(body=body, content_type=content_type, sha256=sha256)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_suffix = f".{os.urandom(8).hex()}.tmp"
        temporary_body = body_path.with_suffix(body_path.suffix + temporary_suffix)
        temporary_metadata = metadata_path.with_suffix(metadata_path.suffix + temporary_suffix)
        try:
            temporary_body.write_bytes(body)
            temporary_metadata.write_text(
                json.dumps(
                    {
                        "contentType": content_type,
                        "sha256": sha256,
                        "sizeBytes": len(body),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            if if_absent:
                body_linked = False
                try:
                    os.link(temporary_body, body_path)
                    body_linked = True
                    os.link(temporary_metadata, metadata_path)
                except FileExistsError:
                    if body_linked:
                        body_path.unlink(missing_ok=True)
                    raise StorageConflictError from None
            else:
                os.replace(temporary_body, body_path)
                os.replace(temporary_metadata, metadata_path)
            temporary_body.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)
        except StorageConflictError:
            temporary_body.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)
            raise
        except OSError:
            temporary_body.unlink(missing_ok=True)
            temporary_metadata.unlink(missing_ok=True)
            raise StorageError from None

    async def get_object(self, *, key: str) -> StoredObject:
        body_path, _ = self._paths(key)
        metadata = await self.head_object(key=key)
        try:
            body = body_path.read_bytes()
        except FileNotFoundError:
            raise StorageNotFoundError from None
        except OSError:
            raise StorageError from None
        if len(body) != metadata.size_bytes or hashlib.sha256(body).hexdigest() != metadata.sha256:
            raise StorageError
        return StoredObject(body=body, metadata=metadata)

    async def head_object(self, *, key: str) -> StoredObjectMetadata:
        body_path, metadata_path = self._paths(key)
        try:
            raw_object: object = json.loads(metadata_path.read_text(encoding="utf-8"))
            size = body_path.stat().st_size
        except FileNotFoundError:
            raise StorageNotFoundError from None
        except (OSError, ValueError, TypeError):
            raise StorageError from None
        if not isinstance(raw_object, dict):
            raise StorageError
        raw = cast(dict[str, object], raw_object)
        size_bytes = raw.get("sizeBytes")
        content_type = raw.get("contentType")
        digest = raw.get("sha256")
        if (
            not isinstance(size_bytes, int)
            or not isinstance(content_type, str)
            or not isinstance(digest, str)
            or size_bytes != size
        ):
            raise StorageError
        return StoredObjectMetadata(
            size_bytes=size_bytes,
            content_type=content_type,
            sha256=digest,
        )

    async def delete_object(self, *, key: str) -> None:
        body_path, metadata_path = self._paths(key)
        try:
            body_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
        except OSError:
            raise StorageError from None

    async def create_download_url(
        self,
        *,
        key: str,
        expires_in_seconds: int,
        download_name: str,
        content_type: str,
    ) -> SignedDownload:
        if not 1 <= expires_in_seconds <= 300:
            raise StorageError
        await self.head_object(key=key)
        payload = json.dumps(
            {
                "contentType": content_type,
                "downloadName": download_name,
                "expiresAt": int(time.time()) + expires_in_seconds,
                "key": key,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        nonce = os.urandom(12)
        token = base64.urlsafe_b64encode(nonce + self._cipher.encrypt(nonce, payload, None)).rstrip(
            b"="
        )
        return SignedDownload(
            url=f"{self._base_url}/_synthetic-storage/v1/{token.decode()}",
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )

    async def resolve_download(self, token: str) -> tuple[StoredObject, str]:
        try:
            encoded = token.encode()
            raw = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
            if base64.urlsafe_b64encode(raw).rstrip(b"=") != encoded:
                raise ValueError
            payload_object: object = json.loads(self._cipher.decrypt(raw[:12], raw[12:], None))
        except Exception:
            raise StorageNotFoundError from None
        if not isinstance(payload_object, dict):
            raise StorageNotFoundError
        payload = cast(dict[str, object], payload_object)
        expires_at = payload.get("expiresAt")
        key = payload.get("key")
        download_name = payload.get("downloadName")
        content_type = payload.get("contentType")
        if (
            not isinstance(expires_at, int)
            or expires_at < int(time.time())
            or not isinstance(key, str)
            or not isinstance(download_name, str)
            or not isinstance(content_type, str)
        ):
            raise StorageNotFoundError
        stored = await self.get_object(key=key)
        if stored.metadata.content_type != content_type:
            raise StorageNotFoundError
        return stored, download_name

    async def close(self) -> None:
        return None
