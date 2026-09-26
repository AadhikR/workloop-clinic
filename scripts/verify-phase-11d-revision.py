#!/usr/bin/env python3

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = (
    ROOT / "backend/alembic/versions/f0b2c4d6e8a3_add_phase11d_development_assets.py"
)
REVISION_ID = "f0b2c4d6e8a3"
PREDECESSOR = "e9a1b3d5f7c2"
CURRENT_HEAD = "e8a1c3f5b7d9"


def require(path: Path, *fragments: str) -> str:
    if not path.is_file():
        raise AssertionError(f"missing Phase 11D file: {path.relative_to(ROOT)}")
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
        'revision: str = "f0b2c4d6e8a3"',
        'down_revision: str | Sequence[str] | None = "e9a1b3d5f7c2"',
        '"content_type"',
        '"sha256"',
        '"file_security_scan_id"',
        '"created_by_app_user_id"',
        '"updated_at"',
        "phase11d_assets_select_runtime",
        "phase11d_training_records_delete_runtime",
        "phase11d_training_records_insert_runtime",
        "phase11d_certifications_delete_runtime",
        "phase11d_cme_requirements_select_runtime",
        "training_evidence_uploaded",
        "certification_verified",
        "cme_requirement_saved",
        "resolve_workloop_principal",
        "lock_development_direct_report",
    )
    ast.parse(migration)
    require(
        ROOT / "backend/app/asset_api.py",
        'prefix="/api/v1/assets"',
        'operation_id="list_self_assets"',
        'operation_id="assign_asset"',
        'operation_id="return_asset"',
    )
    require(
        ROOT / "backend/app/development_api.py",
        'prefix="/api/v1/training-records"',
        'prefix="/api/v1/certifications"',
        'prefix="/api/v1/cme"',
        'operation_id="complete_training_record"',
        'operation_id="verify_certification"',
        'operation_id="read_self_cme"',
    )
    require(
        ROOT / "backend/app/evidence_api.py",
        'prefix="/api/v1/training-files"',
        'prefix="/api/v1/certification-files"',
        'operation_id="upload_training_evidence"',
        'operation_id="download_certification_evidence"',
    )
    require(
        ROOT / "backend/app/main.py",
        "asset_router",
        "training_router",
        "certification_router",
        "cme_router",
        "training_file_router",
        "certification_file_router",
    )
    require(
        ROOT / "src/developmentAssetsApi.js",
        "/api/v1/assets",
        "/api/v1/training-records",
        "/api/v1/certifications",
        "/api/v1/cme",
    )
    if (ROOT / "tests/phase-11d-legacy-freeze.test.js").exists():
        fail("retired Phase 11D legacy freeze test was restored")


def verify_database(mode: str) -> None:
    from sqlalchemy import create_engine, inspect, text

    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        inspector = inspect(connection)
        training_columns = {
            column["name"]
            for column in inspector.get_columns("training_records", schema="public")
        }
        certification_columns = {
            column["name"]
            for column in inspector.get_columns("certifications", schema="public")
        }
        asset_columns = {
            column["name"]
            for column in inspector.get_columns("assets", schema="public")
        }
        phase11d_columns = {
            "updated_at",
            "content_type",
            "size_bytes",
            "sha256",
            "file_security_scan_id",
            "created_by_app_user_id",
        }
        if mode == "predecessor":
            assert version == PREDECESSOR
            assert "updated_at" not in asset_columns
            assert not phase11d_columns.intersection(training_columns)
            assert not phase11d_columns.intersection(certification_columns)
        elif mode == "head":
            assert version == CURRENT_HEAD
            assert "updated_at" in asset_columns
            assert phase11d_columns <= training_columns
            assert phase11d_columns <= certification_columns
            policies = set(
                connection.execute(
                    text(
                        "SELECT policyname FROM pg_catalog.pg_policies "
                        "WHERE schemaname='public' AND policyname LIKE 'phase11d_%'"
                    )
                ).scalars()
            )
            assert policies == {
                "phase11d_assets_select_runtime",
                "phase11d_training_records_delete_runtime",
                "phase11d_training_records_insert_runtime",
                "phase11d_certifications_delete_runtime",
                "phase11d_cme_requirements_select_runtime",
            }
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_catalog.pg_trigger WHERE NOT tgisinternal "
                        "AND tgname IN ('trg_assets_set_updated_at',"
                        "'trg_training_records_set_updated_at',"
                        "'trg_certifications_set_updated_at')"
                    )
                ).scalar_one()
                == 3
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
        raise SystemExit(
            "usage: verify-phase-11d-revision.py [static|predecessor|head]"
        )
    print(f"Phase 11D revision {mode} check passed")


if __name__ == "__main__":
    main()
