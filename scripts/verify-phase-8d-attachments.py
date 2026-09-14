#!/usr/bin/env python3
"""Verify the tracked Phase 8D attachment implementation boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Phase 8D attachment check failed: missing {path}")
    return target.read_text(encoding="utf-8")


def require(source: str, markers: tuple[str, ...], name: str) -> None:
    for marker in markers:
        if marker not in source:
            raise SystemExit(f"Phase 8D attachment check failed: {name} lacks {marker}")


def main() -> None:
    proposal = read("docs/migration/phase-8/PART_8D_ATTACHMENT_PROPOSAL.md")
    require(
        proposal,
        (
            "Decision 8A-ATT-1",
            "8D-STO-D1",
            "8D-ATT-D1",
            "8D-HTTP-D1",
            "8D-FILE-D1",
            "8D-AUD-D1",
        ),
        "approved contract",
    )
    storage_revision = read(
        "backend/alembic/versions/4d8a7c2e9f31_add_storage_operations_prerequisite.py"
    )
    require(
        storage_revision,
        (
            'revision: str = "4d8a7c2e9f31"',
            'down_revision: str | Sequence[str] | None = "8f6b2d1a4c70"',
            '"storage_operations"',
            "workloop_storage_reconciler",
            "interval '15 minutes'",
        ),
        "storage prerequisite revision",
    )
    reconciler = read("backend/app/storage/reconciler.py")
    require(
        reconciler,
        ("FOR UPDATE SKIP LOCKED", "retry_exhausted", "interval '90 days'"),
        "storage reconciler",
    )
    restart_check = read("scripts/verify-phase-8d-storage-restart.py")
    require(
        restart_check,
        ("async def prepare", "async def verify", "create_download_url"),
        "storage restart verifier",
    )
    attachment_revision = read(
        "backend/alembic/versions/a83d5e7c1b29_add_leave_attachment_metadata.py"
    )
    require(
        attachment_revision,
        (
            'revision: str = "a83d5e7c1b29"',
            'down_revision: str | Sequence[str] | None = "4d8a7c2e9f31"',
            '"leave_attachments"',
            "leave_attachment_uploaded",
            "leave_attachment_cleanup_requested",
            "_append_audit_event_phase8d_prior",
        ),
        "attachment revision",
    )
    storage = read("backend/app/storage/base.py")
    require(
        storage,
        ("class StorageConflictError", "class SignedDownload", "create_download_url"),
        "storage interface",
    )
    synthetic = read("backend/app/storage/synthetic.py")
    require(
        synthetic,
        ("AESGCM", "hashlib.sha256(key.encode())", "expiresAt", "StorageConflictError"),
        "synthetic provider",
    )
    service = read("backend/app/services/leave_attachment.py")
    require(
        service,
        (
            "wlat1.",
            "hmac.compare_digest",
            "leave-attachments/v1/",
            "Leave attachment uploaded",
            "Leave attachment cleanup requested",
        ),
        "attachment service",
    )
    api = read("backend/app/leave_attachment_api.py")
    require(
        api,
        (
            'operation_id="create_leave_attachment_submission"',
            'operation_id="upload_leave_attachment"',
            'operation_id="create_leave_attachment_download"',
            "if_absent=True",
            "asyncio.timeout(45)",
        ),
        "attachment API",
    )
    model = read("backend/app/models/leave.py")
    require(model, ("class LeaveAttachment", "attachment_url"), "leave models")
    frontend = read("migration/src/leaveAttachmentApi.js")
    require(
        frontend,
        ("crypto.subtle.digest", "new FormData()", "createLeaveAttachmentDownload"),
        "migration frontend",
    )
    if "supabase" in frontend.lower():
        raise SystemExit("Phase 8D attachment check failed: migration frontend uses Supabase")
    legacy = read("src/utils/leaveStorage.js")
    require(
        legacy,
        (
            "export async function uploadLeaveAttachment()",
            "Leave attachments have moved to the migration leave screen.",
        ),
        "legacy attachment freeze",
    )
    if "supabase.storage" in legacy:
        raise SystemExit("Phase 8D attachment check failed: legacy attachment storage remains active")
    workflow = read(".github/workflows/migration-foundation.yml")
    require(
        workflow,
        (
            "verify-phase-8d-storage-restart.py prepare",
            "verify-phase-8d-storage-restart.py verify",
        ),
        "storage restart workflow",
    )
    cutover = json.loads(read("docs/migration/phase-8/cutover/leave-attachments.json"))
    if cutover["status"]["current"] != "completed":
        raise SystemExit("Phase 8D attachment check failed: cutover is not complete")
    authority = cutover["authority"]
    if authority != {
        "readSystem": "migration-fastapi",
        "writeSystem": "migration-fastapi",
        "writableSystems": ["migration-fastapi"],
    }:
        raise SystemExit("Phase 8D attachment check failed: authority is ambiguous")
    print("Phase 8D attachment implementation check passed")


if __name__ == "__main__":
    main()
