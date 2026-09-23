#!/usr/bin/env python3

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = (
    ROOT
    / "backend/alembic/versions/a1c3e5f7b9d4_add_phase11e_appraisals_incidents.py"
)
REVISION_ID = "a1c3e5f7b9d4"
PREDECESSOR = "f0b2c4d6e8a3"


def require(path: Path, *fragments: str) -> str:
    if not path.is_file():
        raise AssertionError(f"missing Phase 11E file: {path.relative_to(ROOT)}")
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
        'revision: str = "a1c3e5f7b9d4"',
        'down_revision: str | Sequence[str] | None = "f0b2c4d6e8a3"',
        '"updated_at"',
        '"template_version"',
        "appraisal_cycle_generated",
        "appraisal_section_rated",
        "incident_corrective_action_recorded",
        "incident_type",
        "severity",
        "resolve_workloop_principal",
        "appraisal_cycle','appraisal','incident_report",
    )
    ast.parse(migration)
    require(
        ROOT / "backend/app/appraisal_api.py",
        'prefix="/api/v1/appraisal-cycles"',
        'prefix="/api/v1/appraisals"',
        'operation_id="generate_appraisals"',
        'operation_id="rate_appraisal_section"',
        'operation_id="calibrate_appraisal"',
    )
    require(
        ROOT / "backend/app/incident_api.py",
        'prefix="/api/v1/clinical-incidents"',
        'operation_id="investigate_clinical_incident"',
        'operation_id="record_clinical_incident_corrective_action"',
        'operation_id="close_clinical_incident"',
    )
    require(
        ROOT / "backend/app/services/appraisals.py",
        "ROUND_HALF_UP",
        'Decimal("7.50")',
        "FOR UPDATE",
        "lock_development_direct_report",
    )
    require(
        ROOT / "backend/app/services/incidents.py",
        "resource_not_found",
        "from_status",
        "to_status",
        "incident_type",
        "severity",
    )
    require(
        ROOT / "migration/src/appraisalsIncidentsApi.js",
        "/api/v1/appraisal-cycles",
        "/api/v1/appraisals",
        "/api/v1/clinical-incidents",
    )
    require(
        ROOT / "tests/phase-11e-legacy-freeze.test.js",
        "legacy appraisal functions fail closed",
        "hard delete stays unavailable",
    )


def verify_database(mode: str) -> None:
    from sqlalchemy import create_engine, inspect, text

    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get(
        "DATABASE_URL"
    )
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        inspector = inspect(connection)
        cycle_columns = {
            column["name"]
            for column in inspector.get_columns("appraisal_cycles", schema="public")
        }
        section_columns = {
            column["name"]
            for column in inspector.get_columns("appraisal_sections", schema="public")
        }
        appraisal_columns = {
            column["name"]
            for column in inspector.get_columns("appraisals", schema="public")
        }
        if mode == "predecessor":
            assert version == PREDECESSOR
            assert "updated_at" not in cycle_columns
            assert "updated_at" not in section_columns
            assert "template_version" not in appraisal_columns
        elif mode == "head":
            assert version == REVISION_ID
            assert "updated_at" in cycle_columns
            assert "updated_at" in section_columns
            assert "template_version" in appraisal_columns
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_catalog.pg_trigger WHERE NOT tgisinternal "
                        "AND tgname IN ('trg_appraisal_cycles_set_updated_at',"
                        "'trg_appraisal_sections_set_updated_at')"
                    )
                ).scalar_one()
                == 2
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
        raise SystemExit("usage: verify-phase-11e-revision.py [static|predecessor|head]")
    print(f"Phase 11E revision {mode} check passed")


if __name__ == "__main__":
    main()
