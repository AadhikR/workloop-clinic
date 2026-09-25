#!/usr/bin/env python3

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT / "backend/alembic/versions/e8a1c3f5b7d9_extend_phase12g_output_audit.py"
REVISION_ID = "e8a1c3f5b7d9"
PREDECESSOR = "d6f8a0c2e4b7"
SIGNATURE = "public.append_phase12_output_audit(text,text,uuid,text,text,text,text,integer,bigint,text)"


def require(path: Path, *fragments: str) -> str:
    if not path.is_file():
        raise AssertionError(f"missing Phase 12G file: {path.relative_to(ROOT)}")
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
        'revision: str = "e8a1c3f5b7d9"',
        'down_revision: str | Sequence[str] | None = "d6f8a0c2e4b7"',
        "PART_12F_ALLOWLIST",
        "PART_12G_ALLOWLIST",
        "SECURITY DEFINER",
        "SET search_path TO pg_catalog, public",
        "REVOKE ALL ON FUNCTION",
        "GRANT EXECUTE ON FUNCTION",
        "PAYSLIP_HUMAN_CONTEXT",
        "_replace_payslip_policy(include_admin=True)",
        "_replace_payslip_policy(include_admin=False)",
    )
    ast.parse(migration)
    require(
        ROOT / "backend/app/rendered_output_api.py",
        '"/{report_id}.pdf"',
        '"/{run_id}/payslips.zip"',
        '"/{request_id}/letter.pdf"',
        '"/{checklist_id}/final-settlement.pdf"',
    )
    require(
        ROOT / "backend/app/services/rendered_outputs.py",
        "MAX_PDF_PAGES",
        "MAX_ZIP_ENTRIES",
        "PDF_RENDERER_VERSION",
        "ZIP_RENDERER_VERSION",
    )


def verify_database(mode: str) -> None:
    from sqlalchemy import create_engine, text

    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        properties = (
            connection.execute(
                text(
                    """
SELECT owner.rolname AS owner,procedure.prosecdef,procedure.proconfig,
 pg_catalog.pg_get_functiondef(procedure.oid) AS definition,
 has_function_privilege('workloop_runtime',procedure.oid,'EXECUTE') runtime_executes,
 EXISTS (SELECT 1 FROM pg_catalog.aclexplode(procedure.proacl) permission
         WHERE permission.grantee=0 AND permission.privilege_type='EXECUTE') public_executes
FROM pg_proc procedure
JOIN pg_namespace namespace ON namespace.oid=procedure.pronamespace
JOIN pg_roles owner ON owner.oid=procedure.proowner
WHERE namespace.nspname='public' AND procedure.oid=CAST(:signature AS regprocedure)
"""
                ),
                {"signature": SIGNATURE},
            )
            .mappings()
            .one()
        )
        assert properties["owner"] == "workloop_migration"
        assert properties["prosecdef"] is True
        assert properties["proconfig"] == ["search_path=pg_catalog, public"]
        assert properties["runtime_executes"] is True
        assert properties["public_executes"] is False
        definition = str(properties["definition"])
        payslip_policy = connection.execute(
            text(
                "SELECT pg_catalog.pg_get_expr(policy.polqual,policy.polrelid) "
                "FROM pg_catalog.pg_policy policy "
                "JOIN pg_catalog.pg_class relation ON relation.oid=policy.polrelid "
                "JOIN pg_catalog.pg_namespace namespace ON namespace.oid=relnamespace "
                "WHERE namespace.nspname='public' AND relation.relname='payslips' "
                "AND policy.polname='phase5f_payslips_select_runtime'"
            )
        ).scalar_one()
        assert "report_csv_exported" in definition
        if mode == "predecessor":
            assert version == PREDECESSOR
            assert "report_pdf_exported" not in definition
            assert "payslip_zip_exported" not in definition
            assert "workloop_role() = 'admin'::text" not in payslip_policy
        elif mode == "head":
            assert version == REVISION_ID
            assert "report_pdf_exported" in definition
            assert "payslip_zip_exported" in definition
            assert "final_settlement_pdf_exported" in definition
            assert "workloop_role() = 'admin'::text" in payslip_policy
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
        raise SystemExit("usage: verify-phase-12g-revision.py [static|predecessor|head]")
    print(f"Phase 12G revision {mode} check passed")


if __name__ == "__main__":
    main()
