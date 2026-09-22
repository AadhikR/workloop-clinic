#!/usr/bin/env python3
"""Prove Phase 11B S3 objects and scan state survive a stack restart."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid
from contextlib import suppress

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text

from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.storage.spaces import SpacesObjectStorage

BODY = b"%PDF-1.7\nPhase 11B restart proof\n%%EOF\n"
CONTENT_TYPE = "application/pdf"
BUCKET = "workloop-phase11b-restart"
KEY = "verification/phase11b/restart-proof"
SCAN_ID = uuid.UUID("11b00000-0000-4000-8000-000000000001")
ENTITY_ID = uuid.UUID("11b00000-0000-4000-8000-000000000002")


def s3_client() -> object:
    return boto3.client(
        "s3",
        endpoint_url=os.environ["PHASE11B_S3_ENDPOINT"],
        region_name="us-east-1",
        aws_access_key_id=os.environ["PHASE11B_S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["PHASE11B_S3_SECRET_KEY"],
    )


def storage() -> SpacesObjectStorage:
    return SpacesObjectStorage(
        endpoint_url=os.environ["PHASE11B_S3_ENDPOINT"],
        region="us-east-1",
        bucket=BUCKET,
        access_key=os.environ["PHASE11B_S3_ACCESS_KEY"],
        secret_key=os.environ["PHASE11B_S3_SECRET_KEY"],
        addressing_style="path",
    )


async def prepare() -> None:
    client = s3_client()
    with suppress(ClientError):
        client.create_bucket(Bucket=BUCKET)  # type: ignore[attr-defined]
    object_storage = storage()
    digest = hashlib.sha256(BODY).hexdigest()
    with suppress(Exception):
        await object_storage.delete_object(key=KEY)
    await object_storage.put_object(
        key=KEY,
        body=BODY,
        content_type=CONTENT_TYPE,
        sha256=digest,
        if_absent=True,
    )
    await object_storage.close()

    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    with engine.begin() as connection:
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text("DELETE FROM public.file_security_scans WHERE id=:id"),
            {"id": SCAN_ID},
        )
        connection.execute(
            text(
                "INSERT INTO public.file_security_scans("
                "id,company_id,branch_id,created_by_app_user_id,entity_type,entity_id,"
                "object_key,content_type,size_bytes,sha256,status,scanner_name,"
                "scanner_definition,result_signature,attempt_count,scanned_at,valid_until) "
                "VALUES(:id,:company_id,:branch_id,:creator,'employee_document',:entity_id,"
                ":object_key,:content_type,:size_bytes,:sha256,'clean','synthetic',"
                "'synthetic-v1',:signature,1,statement_timestamp(),"
                "statement_timestamp()+interval '30 days')"
            ),
            {
                "id": SCAN_ID,
                "company_id": seed.COMPANY_ID[seed.HORIZON],
                "branch_id": seed.BRANCH_DXB,
                "creator": seed.ADMIN_APP_USER[seed.HORIZON],
                "entity_id": ENTITY_ID,
                "object_key": KEY,
                "content_type": CONTENT_TYPE,
                "size_bytes": len(BODY),
                "sha256": digest,
                "signature": "b" * 64,
            },
        )
    engine.dispose()
    print(f"Phase 11B restart state prepared: {digest}")


async def verify() -> None:
    digest = hashlib.sha256(BODY).hexdigest()
    object_storage = storage()
    stored = await object_storage.get_object(key=KEY)
    assert stored.body == BODY
    assert stored.metadata.content_type == CONTENT_TYPE
    assert stored.metadata.sha256 == digest

    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    with engine.begin() as connection:
        scan = connection.execute(
            text(
                "SELECT status,scanner_name,scanner_definition,result_signature,sha256 "
                "FROM public.file_security_scans WHERE id=:id"
            ),
            {"id": SCAN_ID},
        ).one()
        assert scan == ("clean", "synthetic", "synthetic-v1", "b" * 64, digest)
        connection.execute(
            text("DELETE FROM public.file_security_scans WHERE id=:id"),
            {"id": SCAN_ID},
        )
        clean(connection, rows)
    engine.dispose()

    await object_storage.delete_object(key=KEY)
    await object_storage.close()
    s3_client().delete_bucket(Bucket=BUCKET)  # type: ignore[attr-defined]
    print("Phase 11B S3 object and scan state persisted across restart")


async def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "verify"}:
        raise SystemExit("usage: verify-phase-11b-restart.py prepare|verify")
    if sys.argv[1] == "prepare":
        await prepare()
    else:
        await verify()


if __name__ == "__main__":
    asyncio.run(main())
