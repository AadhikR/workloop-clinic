#!/usr/bin/env python3

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT / "backend/alembic/versions/b2d4f6a8c0e5_add_phase11f_letter_requests.py"
PREDECESSOR = "a1c3e5f7b9d4"
CURRENT_HEAD = "e8a1c3f5b7d9"


def require(path: Path, *fragments: str) -> str:
    if not path.is_file():
        raise AssertionError(f"missing Phase 11F file: {path.relative_to(ROOT)}")
    source = path.read_text(encoding="utf-8")
    for fragment in fragments:
        if fragment not in source:
            raise AssertionError(
                f"{path.relative_to(ROOT)} is missing required boundary: {fragment}"
            )
    return source


def verify_static() -> None:
    migration = require(
        REVISION,
        'revision: str = "b2d4f6a8c0e5"',
        'down_revision: str | Sequence[str] | None = "a1c3e5f7b9d4"',
        "employee_name_snapshot",
        "basic_salary_snapshot",
        "letter_submitted",
        "letter_completed",
        "letter_rejected",
        "letter_request",
        "_append_audit_event_phase11f_prior",
    )
    ast.parse(migration)
    require(
        ROOT / "backend/app/letter_request_api.py",
        'prefix="/api/v1/requests"',
        'operation_id="submit_letter_request"',
        'operation_id="complete_letter_request"',
        'operation_id="reject_letter_request"',
        'operation_id="get_letter_request_print_source"',
    )
    require(
        ROOT / "backend/app/services/letter_requests.py",
        "FOR UPDATE",
        "FOR SHARE OF employee",
        "basic_salary_snapshot",
        "pending_to_completed",
        "pending_to_rejected",
    )
    require(
        ROOT / "migration/src/letterRequestsApi.js",
        "/api/v1/requests/self",
        "/print-source",
        "Invalid request print source",
    )
    require(
        ROOT / "tests/phase-11f-legacy-freeze.test.js",
        "legacy request storage reads and writes fail closed",
        "legacy employee submission RPCs are frozen",
    )


def verify_database(mode: str) -> None:
    from sqlalchemy import create_engine, inspect, text

    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("letter_requests", schema="public")
        }
        if mode == "predecessor":
            assert version == PREDECESSOR
            assert "employee_name_snapshot" not in columns
            assert "updated_at" not in columns
        elif mode == "head":
            assert version == CURRENT_HEAD
            assert {
                "employee_name_snapshot",
                "job_title_snapshot",
                "department_snapshot",
                "employment_start_date_snapshot",
                "branch_name_snapshot",
                "basic_salary_snapshot",
                "allowance_snapshot",
                "updated_at",
            } <= columns
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_catalog.pg_trigger WHERE NOT tgisinternal "
                        "AND tgname='trg_letter_requests_set_updated_at'"
                    )
                ).scalar_one()
                == 1
            )
        else:
            raise ValueError("mode must be predecessor or head")
    engine.dispose()


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) == 2 else "static"
    if mode == "static":
        verify_static()
    elif mode in {"predecessor", "head"}:
        verify_database(mode)
    else:
        raise SystemExit("usage: verify-phase-11f-revision.py [static|predecessor|head]")
    print(f"Phase 11F revision {mode} check passed")


if __name__ == "__main__":
    main()
