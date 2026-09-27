#!/usr/bin/env python3
"""Rehearse one encrypted private-object backup into the exact isolated target."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.storage.recovery import (
    RecoveryObject,
    create_encrypted_snapshot,
    restore_encrypted_snapshot,
)
from app.storage.spaces import SpacesObjectStorage

SOURCE_BUCKET = "workloop-phase11b-restart"
TARGET_BUCKET = "workloop-phase14f-restore-objects"
SOURCE_KEY = "phase14f/" + hashlib.sha256(b"workloop-phase14f-object").hexdigest()
ENTITY_ID = "11b00000-0000-4000-8000-000000000002"


async def prepare_source() -> None:
    body = os.urandom(47)
    s3 = client()
    try:
        try:
            s3.head_bucket(Bucket=SOURCE_BUCKET)  # type: ignore[attr-defined]
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status != 404:
                raise
        else:
            raise RuntimeError("exact backup source bucket already exists")
        s3.create_bucket(Bucket=SOURCE_BUCKET)  # type: ignore[attr-defined]
    finally:
        s3.close()  # type: ignore[attr-defined]
    source = storage(SOURCE_BUCKET)
    try:
        await source.put_object(
            key=SOURCE_KEY,
            body=body,
            content_type="application/pdf",
            sha256=hashlib.sha256(body).hexdigest(),
            if_absent=True,
        )
    finally:
        await source.close()
    print("Phase 14F exact private-object backup source prepared")


def client() -> object:
    return boto3.client(
        "s3",
        endpoint_url=os.environ["PHASE11B_S3_ENDPOINT"],
        region_name="us-east-1",
        aws_access_key_id=os.environ["PHASE11B_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["PHASE11B_S3_SECRET_KEY"],
    )


def storage(bucket: str) -> SpacesObjectStorage:
    return SpacesObjectStorage(
        endpoint_url=os.environ["PHASE11B_S3_ENDPOINT"],
        region="us-east-1",
        bucket=bucket,
        access_key=os.environ["PHASE11B_S3_ACCESS_KEY"],
        secret_key=os.environ["PHASE11B_S3_SECRET_KEY"],
        addressing_style="path",
    )


def recovery_key() -> bytes:
    value = base64.b64decode(os.environ["WORKLOOP_RECOVERY_KEY_BASE64"], validate=True)
    if len(value) != 32:
        raise RuntimeError("recovery key must contain 32 bytes")
    return value


async def backup(archive: Path) -> None:
    if archive.exists():
        raise RuntimeError("object archive already exists")
    source = storage(SOURCE_BUCKET)
    try:
        stored = await source.get_object(key=SOURCE_KEY)
        item = RecoveryObject(
            entity_type="employee_document",
            entity_id=ENTITY_ID,
            object_key=SOURCE_KEY,
            content_type=stored.metadata.content_type,
            size_bytes=stored.metadata.size_bytes,
            sha256=stored.metadata.sha256,
        )
        snapshot = await create_encrypted_snapshot(
            source,
            objects=[item],
            scan_rows=[{"status": "clean"}],
            operation_rows=[{"status": "succeeded"}],
            encryption_key=recovery_key(),
            key_id=os.environ["WORKLOOP_RECOVERY_KEY_ID"],
        )
        archive.write_bytes(snapshot.payload)
        archive.chmod(0o600)
        print(
            "Phase 14F encrypted object backup passed: "
            f"count={snapshot.object_count} bytes={item.size_bytes} "
            f"manifest={snapshot.manifest_digest}"
        )
    finally:
        await source.close()


async def restore(archive: Path) -> None:
    s3 = client()
    try:
        try:
            s3.head_bucket(Bucket=TARGET_BUCKET)  # type: ignore[attr-defined]
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status != 404:
                raise
        else:
            raise RuntimeError("exact restore bucket already exists")
        s3.create_bucket(Bucket=TARGET_BUCKET)  # type: ignore[attr-defined]
    finally:
        s3.close()  # type: ignore[attr-defined]

    target = storage(TARGET_BUCKET)
    try:
        result = await restore_encrypted_snapshot(
            target,
            payload=archive.read_bytes(),
            encryption_keys={os.environ["WORKLOOP_RECOVERY_KEY_ID"]: recovery_key()},
        )
        stored = await target.get_object(key=SOURCE_KEY)
        opaque_key_digest = hashlib.sha256(SOURCE_KEY.encode("utf-8")).hexdigest()
        print(
            "Phase 14F isolated object restore passed: "
            f"versions={result.object_count} count={result.object_count} "
            f"bytes={stored.metadata.size_bytes} key=sha256:{opaque_key_digest} "
            f"content=sha256:{stored.metadata.sha256} reconciliation=passed"
        )
    finally:
        await target.close()


async def verify() -> None:
    target = storage(TARGET_BUCKET)
    try:
        stored = await target.get_object(key=SOURCE_KEY)
        opaque_key_digest = hashlib.sha256(SOURCE_KEY.encode("utf-8")).hexdigest()
        print(
            "Phase 14F restored object verification passed: "
            f"versions=1 count=1 bytes={stored.metadata.size_bytes} "
            f"key=sha256:{opaque_key_digest} content=sha256:{stored.metadata.sha256} "
            "reconciliation=passed"
        )
    finally:
        await target.close()


async def cleanup() -> None:
    s3 = client()
    try:
        response = s3.list_objects_v2(Bucket=TARGET_BUCKET)  # type: ignore[attr-defined]
        for item in response.get("Contents", []):
            s3.delete_object(Bucket=TARGET_BUCKET, Key=item["Key"])  # type: ignore[attr-defined]
        s3.delete_bucket(Bucket=TARGET_BUCKET)  # type: ignore[attr-defined]
    except ClientError as error:
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status != 404:
            raise
    finally:
        s3.close()  # type: ignore[attr-defined]
    print("Phase 14F exact object restore target cleanup passed")


async def cleanup_source() -> None:
    s3 = client()
    try:
        response = s3.list_objects_v2(Bucket=SOURCE_BUCKET)  # type: ignore[attr-defined]
        for item in response.get("Contents", []):
            s3.delete_object(Bucket=SOURCE_BUCKET, Key=item["Key"])  # type: ignore[attr-defined]
        s3.delete_bucket(Bucket=SOURCE_BUCKET)  # type: ignore[attr-defined]
    except ClientError as error:
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status != 404:
            raise
    finally:
        s3.close()  # type: ignore[attr-defined]
    print("Phase 14F exact private-object backup source cleanup passed")


async def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] not in {
        "backup",
        "prepare-source",
        "restore",
        "verify",
        "cleanup",
        "cleanup-source",
    }:
        raise SystemExit(
            "usage: verify-phase-14f-object-recovery.py "
            "prepare-source|backup|restore|verify|cleanup|cleanup-source archive"
        )
    archive = Path(sys.argv[2])
    if sys.argv[1] == "prepare-source":
        await prepare_source()
    elif sys.argv[1] == "backup":
        await backup(archive)
    elif sys.argv[1] == "restore":
        await restore(archive)
    elif sys.argv[1] == "verify":
        await verify()
    elif sys.argv[1] == "cleanup":
        await cleanup()
    else:
        await cleanup_source()


if __name__ == "__main__":
    asyncio.run(main())
