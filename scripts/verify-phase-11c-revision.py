from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT / "backend/alembic/versions/e9a1b3d5f7c2_add_phase11c_records_benefits.py"
REVISION_ID = "e9a1b3d5f7c2"
PREDECESSOR = "d8f0a2c4e6b1"


def require(path: Path, *fragments: str) -> str:
    if not path.is_file():
        raise AssertionError(f"missing Phase 11C file: {path.relative_to(ROOT)}")
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
        'revision: str = "e9a1b3d5f7c2"',
        'down_revision: str | Sequence[str] | None = "d8f0a2c4e6b1"',
        '"content_type"',
        '"sha256"',
        '"file_security_scan_id"',
        '"created_by_app_user_id"',
        '"updated_at"',
        "employee_document_uploaded",
        "insurance_coverage_replaced",
        "employment_contract_recorded",
        "phase11c_employee_documents_delete_runtime",
    )
    ast.parse(migration)
    require(
        ROOT / "backend/app/employee_document_api.py",
        'prefix="/api/v1/employee-documents"',
        'operation_id="list_self_employee_documents"',
        'operation_id="verify_employee_document"',
        'operation_id="delete_employee_document"',
    )
    require(
        ROOT / "backend/app/insurance_api.py",
        'prefix="/api/v1/insurance"',
        'operation_id="list_insurance_policies"',
        'operation_id="replace_employee_coverage"',
        'operation_id="read_self_insurance"',
    )
    require(
        ROOT / "backend/app/employment_contract_api.py",
        'operation_id="list_employee_contracts"',
        'operation_id="record_new_contract"',
        'operation_id="renew_employee_contract"',
        'operation_id="convert_employee_contract"',
        'operation_id="record_contract_not_renewed"',
    )
    require(
        ROOT / "backend/app/main.py",
        "employee_document_router",
        "insurance_router",
        "employment_contract_router",
    )
    require(
        ROOT / "migration/src/recordsBenefitsApi.js",
        "/api/v1/employee-documents",
        "/api/v1/insurance",
        "/contracts",
    )
    require(
        ROOT / "tests/phase-11c-legacy-freeze.test.js",
        "employee documents",
        "insurance",
        "employment contracts",
    )


def verify_database(mode: str) -> None:
    from sqlalchemy import create_engine, inspect, text

    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        inspector = inspect(connection)
        document_column_definitions = {
            column["name"]: column
            for column in inspector.get_columns("employee_documents", schema="public")
        }
        document_columns = set(document_column_definitions)
        policy_columns = {
            column["name"]
            for column in inspector.get_columns("insurance_policies", schema="public")
        }
        if mode == "predecessor":
            assert version == PREDECESSOR
            assert "content_type" not in document_columns
            assert "updated_at" not in policy_columns
            assert document_column_definitions["file_size"]["default"] is not None
            assert document_column_definitions["storage_path"]["default"] is not None
        elif mode == "head":
            assert version == REVISION_ID
            assert {
                "content_type",
                "sha256",
                "file_security_scan_id",
                "created_by_app_user_id",
                "updated_at",
            } <= document_columns
            assert "updated_at" in policy_columns
            assert document_column_definitions["file_size"]["default"] is None
            assert document_column_definitions["storage_path"]["default"] is None
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_catalog.pg_trigger WHERE NOT tgisinternal "
                        "AND tgname LIKE 'trg_%_set_updated_at'"
                    )
                ).scalar_one()
                >= 4
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
        raise SystemExit("usage: verify-phase-11c-revision.py [static|predecessor|head]")
    print(f"Phase 11C revision {mode} check passed")


if __name__ == "__main__":
    main()
