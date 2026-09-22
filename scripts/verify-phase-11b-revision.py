#!/usr/bin/env python3
"""Verify the Phase 11B revision and its exact predecessor boundary."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

REVISION = "d8f0a2c4e6b1"
PREDECESSOR = "c6e8a1b3d927"


def verify_static(repository: Path) -> None:
    migration = (
        repository
        / "backend"
        / "alembic"
        / "versions"
        / "d8f0a2c4e6b1_add_phase11b_file_security.py"
    ).read_text(encoding="utf-8")
    worker = (repository / "backend" / "app" / "storage" / "scanner_worker.py").read_text(
        encoding="utf-8"
    )
    required_migration = (
        f'revision: str = "{REVISION}"',
        f'down_revision: str | Sequence[str] | None = "{PREDECESSOR}"',
        "file_security_scans",
        "workloop_file_scanner",
        "file_security_scan_id",
        "append_file_security_audit",
        "requeue_file_security_scan",
        "append_storage_recovery_audit",
        "file_security_scan_allows_download",
        "storage_manual_requeue",
        "interval '30 days'",
    )
    for value in required_migration:
        assert value in migration, value
    for value in (
        "FOR UPDATE SKIP LOCKED",
        "retry_exhausted",
        "object_missing",
        "manual_requeue",
    ):
        assert value in worker, value


def verify_database(mode: str) -> None:
    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        inspector = inspect(connection)
        tables = set(inspector.get_table_names(schema="public"))
        leave_columns = {
            column["name"] for column in inspector.get_columns("leave_attachments", schema="public")
        }
        receipt_columns = {
            column["name"] for column in inspector.get_columns("expense_receipts", schema="public")
        }
        actor_key = connection.execute(
            text("SELECT pg_get_functiondef('public.workloop_actor_key()'::regprocedure)")
        ).scalar_one()
        if mode == "predecessor":
            assert version == PREDECESSOR
            assert "file_security_scans" not in tables
            assert "file_security_scan_id" not in leave_columns
            assert "file_security_scan_id" not in receipt_columns
            assert "file_security_scan" not in actor_key
        elif mode == "head":
            assert version == REVISION
            assert "file_security_scans" in tables
            assert "file_security_scan_id" in leave_columns
            assert "file_security_scan_id" in receipt_columns
            assert "file_security_scan" in actor_key
            indexes = {item["name"] for item in inspector.get_indexes("file_security_scans")}
            assert {
                "ix_file_security_scans_claim",
                "ix_file_security_scans_entity",
                "ix_file_security_scans_expiry",
            } <= indexes
        else:
            raise ValueError("mode must be predecessor or head")
    engine.dispose()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"static", "predecessor", "head"}:
        raise SystemExit("usage: verify-phase-11b-revision.py static|predecessor|head")
    mode = sys.argv[1]
    if mode == "static":
        verify_static(Path(os.environ.get("WORKLOOP_REPOSITORY", "/repo")))
    else:
        verify_database(mode)
    print(f"Phase 11B revision {mode} check passed")


if __name__ == "__main__":
    main()
