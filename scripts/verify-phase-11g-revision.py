#!/usr/bin/env python3

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT / "backend/alembic/versions/c3e5a7b9d1f6_add_phase11g_offboarding_settlement.py"
REVISION_ID = "c3e5a7b9d1f6"
PREDECESSOR = "b2d4f6a8c0e5"
CURRENT_HEAD = "e8a1c3f5b7d9"


def require(path: Path, *fragments: str) -> str:
    if not path.is_file():
        raise AssertionError(f"missing Phase 11G file: {path.relative_to(ROOT)}")
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
        'revision: str = "c3e5a7b9d1f6"',
        'down_revision: str | Sequence[str] | None = "b2d4f6a8c0e5"',
        "settlement_policy_versions",
        "final_settlements",
        "source_snapshot",
        "_append_audit_event_phase11g_prior",
        "read_offboarding_payroll_source",
        "offboarding_checklist",
    )
    ast.parse(migration)
    require(
        ROOT / "backend/app/offboarding_api.py",
        'prefix="/api/v1/offboarding"',
        'operation_id="initialize_offboarding_checklist"',
        'operation_id="preview_final_settlement"',
        'operation_id="complete_offboarding"',
        'operation_id="get_offboarding_letter_source"',
    )
    require(
        ROOT / "backend/app/services/offboarding.py",
        "ROUND_HALF_UP",
        "FOR UPDATE",
        "record_advance_repayment",
        "archive_employee",
        "expected_source_digest",
    )
    require(
        ROOT / "migration/src/offboardingApi.js",
        "/api/v1/offboarding",
        "/settlement/preview",
        "Invalid settlement preview",
    )
    require(
        ROOT / "tests/phase-11g-legacy-freeze.test.js",
        "legacy offboarding storage reads and writes fail closed",
        "migration offboarding paths contain no Supabase",
    )


def verify_database(mode: str) -> None:
    from sqlalchemy import create_engine, inspect, text

    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        tables = set(inspect(connection).get_table_names(schema="public"))
        task_columns = {
            column["name"]
            for column in inspect(connection).get_columns("offboarding_tasks", schema="public")
        }
        if mode == "predecessor":
            assert version == PREDECESSOR
            assert "source" not in task_columns
            assert "final_settlements" not in tables
        elif mode == "head":
            assert version == CURRENT_HEAD
            assert {"source", "template_id", "updated_at"} <= task_columns
            assert {"settlement_policy_versions", "final_settlements"} <= tables
            assert (
                connection.execute(
                    text("SELECT count(*) FROM settlement_policy_versions")
                ).scalar_one()
                == 1
            )
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.role_table_grants "
                        "WHERE grantee='workloop_runtime' AND table_name='final_settlements' "
                        "AND privilege_type IN ('UPDATE','DELETE')"
                    )
                ).scalar_one()
                == 0
            )
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_proc procedure "
                        "JOIN pg_namespace namespace ON namespace.oid=procedure.pronamespace "
                        "WHERE namespace.nspname='public' "
                        "AND procedure.proname='read_offboarding_payroll_source' "
                        "AND procedure.prosecdef"
                    )
                ).scalar_one()
                == 1
            )
            assert (
                connection.execute(
                    text(
                        "SELECT has_function_privilege('workloop_runtime', "
                        "'public.read_offboarding_payroll_source(uuid,text)', 'EXECUTE')"
                    )
                ).scalar_one()
                is True
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
        raise SystemExit("usage: verify-phase-11g-revision.py [static|predecessor|head]")
    print(f"Phase 11G revision {mode} check passed")


if __name__ == "__main__":
    main()
