#!/usr/bin/env python3
"""Prove synthetic object and signing-key persistence across a stack restart."""

from __future__ import annotations

import asyncio
import hashlib
import sys

from app.core.config import Settings
from app.storage.factory import create_object_storage
from app.storage.synthetic import SyntheticObjectStorage

BODY = b"Workloop Phase 8D restart proof\n"
CONTENT_TYPE = "application/pdf"
DOWNLOAD_NAME = "phase-8d-restart-proof.pdf"
KEY = "verification/phase8d/restart-proof"
TOKEN_FILE = ".phase8d-restart-token"


async def prepare(storage: SyntheticObjectStorage, settings: Settings) -> None:
    token_path = settings.synthetic_storage_path / TOKEN_FILE
    token_path.unlink(missing_ok=True)
    await storage.delete_object(key=KEY)
    digest = hashlib.sha256(BODY).hexdigest()
    await storage.put_object(
        key=KEY,
        body=BODY,
        content_type=CONTENT_TYPE,
        sha256=digest,
        if_absent=True,
    )
    signed = await storage.create_download_url(
        key=KEY,
        expires_in_seconds=300,
        download_name=DOWNLOAD_NAME,
        content_type=CONTENT_TYPE,
    )
    token_path.write_text(signed.url.rsplit("/", 1)[-1], encoding="ascii")
    print(f"Phase 8D storage restart state prepared: {digest}")


async def verify(storage: SyntheticObjectStorage, settings: Settings) -> None:
    token_path = settings.synthetic_storage_path / TOKEN_FILE
    token = token_path.read_text(encoding="ascii")
    stored, download_name = await storage.resolve_download(token)
    assert download_name == DOWNLOAD_NAME
    assert stored.body == BODY
    assert stored.metadata.content_type == CONTENT_TYPE
    assert stored.metadata.sha256 == hashlib.sha256(BODY).hexdigest()
    await storage.delete_object(key=KEY)
    token_path.unlink()
    print("Phase 8D storage volume and signing key persisted across restart")


async def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "verify"}:
        raise SystemExit("usage: verify-phase-8d-storage-restart.py prepare|verify")
    settings = Settings()
    storage = create_object_storage(settings)
    if not isinstance(storage, SyntheticObjectStorage):
        raise RuntimeError("the restart verifier requires synthetic storage")
    try:
        if sys.argv[1] == "prepare":
            await prepare(storage, settings)
        else:
            await verify(storage, settings)
    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
