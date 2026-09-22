from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from contextlib import suppress

import boto3
import httpx

from app.storage.base import StorageConflictError
from app.storage.recovery import (
    RecoveryObject,
    SnapshotError,
    create_encrypted_snapshot,
    restore_encrypted_snapshot,
)
from app.storage.spaces import SpacesObjectStorage


async def verify() -> None:
    endpoint = os.environ["PHASE11B_S3_ENDPOINT"]
    access_key = os.environ["PHASE11B_S3_ACCESS_KEY"]
    secret_key = os.environ["PHASE11B_S3_SECRET_KEY"]
    source_bucket = f"workloop-phase11b-source-{uuid.uuid4().hex[:8]}"
    target_bucket = f"workloop-phase11b-target-{uuid.uuid4().hex[:8]}"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    for attempt in range(30):
        try:
            client.list_buckets()
            break
        except Exception:
            if attempt == 29:
                raise
            await asyncio.sleep(1)
    client.create_bucket(Bucket=source_bucket)
    client.create_bucket(Bucket=target_bucket)
    source = SpacesObjectStorage(
        endpoint_url=endpoint,
        region="us-east-1",
        bucket=source_bucket,
        access_key=access_key,
        secret_key=secret_key,
        addressing_style="path",
    )
    target = SpacesObjectStorage(
        endpoint_url=endpoint,
        region="us-east-1",
        bucket=target_bucket,
        access_key=access_key,
        secret_key=secret_key,
        addressing_style="path",
    )
    objects: list[RecoveryObject] = []
    fixtures = (
        ("leave_attachment", "leave-attachments/v1/scope/one", b"%PDF-1.7\none\n%%EOF\n"),
        ("expense_receipt", "expense-receipts/v1/scope/two", b"%PDF-1.7\ntwo\n%%EOF\n"),
        ("employee_document", "employee-documents/v1/scope/three", b"%PDF-1.7\nthree\n%%EOF\n"),
    )
    started = time.monotonic()
    try:
        for index, (entity_type, key, body) in enumerate(fixtures, start=1):
            digest = hashlib.sha256(body).hexdigest()
            await source.put_object(
                key=key,
                body=body,
                content_type="application/pdf",
                sha256=digest,
                if_absent=True,
            )
            with suppress(StorageConflictError):
                await source.put_object(
                    key=key,
                    body=body,
                    content_type="application/pdf",
                    sha256=digest,
                    if_absent=True,
                )
                raise AssertionError("conditional create replaced an S3 object")
            objects.append(
                RecoveryObject(
                    entity_type=entity_type,
                    entity_id=f"00000000-0000-4000-8000-{index:012d}",
                    object_key=key,
                    content_type="application/pdf",
                    size_bytes=len(body),
                    sha256=digest,
                )
            )

        async with httpx.AsyncClient(timeout=5) as http:
            public_list = await http.get(f"{endpoint}/{source_bucket}")
        assert public_list.status_code in {401, 403}

        signed = await source.create_download_url(
            key=objects[0].object_key,
            expires_in_seconds=300,
            download_name="synthetic-proof.pdf",
            content_type="application/pdf",
        )
        async with httpx.AsyncClient(timeout=5) as http:
            download = await http.get(signed.url)
        assert download.status_code == 200
        assert download.content == fixtures[0][2]
        assert download.headers.get("cache-control") == "private, no-store"

        snapshot = await create_encrypted_snapshot(
            source,
            objects=objects,
            scan_rows=[{"id": "scan-1", "status": "clean"}],
            operation_rows=[{"id": "operation-1", "status": "succeeded"}],
            encryption_key=b"r" * 32,
            key_id="11b00001",
        )
        restored = await restore_encrypted_snapshot(
            target,
            payload=snapshot.payload,
            encryption_keys={"11b00001": b"r" * 32},
        )
        assert restored.object_count == len(objects)
        assert restored.manifest_digest == snapshot.manifest_digest
        for item, (_entity_type, _key, expected_body) in zip(objects, fixtures, strict=True):
            stored = await target.get_object(key=item.object_key)
            assert stored.body == expected_body
            assert stored.metadata.sha256 == item.sha256

        rotated = await create_encrypted_snapshot(
            source,
            objects=objects,
            scan_rows=[{"id": "scan-1", "status": "clean"}],
            operation_rows=[{"id": "operation-1", "status": "succeeded"}],
            encryption_key=b"n" * 32,
            key_id="11b00002",
        )
        with suppress(SnapshotError):
            await restore_encrypted_snapshot(
                target,
                payload=rotated.payload,
                encryption_keys={"11b00001": b"r" * 32},
            )
            raise AssertionError("old recovery key opened the rotated snapshot")
        assert time.monotonic() - started < 900
    finally:
        await source.close()
        await target.close()
        for bucket in (source_bucket, target_bucket):
            with suppress(Exception):
                response = client.list_objects_v2(Bucket=bucket)
                for item in response.get("Contents", []):
                    client.delete_object(Bucket=bucket, Key=item["Key"])
                client.delete_bucket(Bucket=bucket)
        client.close()
    print("Phase 11B local S3 privacy, signing, backup, restore, and rotation checks passed")


if __name__ == "__main__":
    asyncio.run(verify())
