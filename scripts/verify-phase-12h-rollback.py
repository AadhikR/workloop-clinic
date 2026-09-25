#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path("/workspace") if Path("/workspace").is_dir() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.seed import constants as seed  # noqa: E402
from app.db.seed.fixtures import build_rows  # noqa: E402
from app.db.seed.runner import apply_rows, validate  # noqa: E402
from app.db.seed.runner import clean as clean_seed  # noqa: E402

HEAD = "e8a1c3f5b7d9"
PREDECESSOR = "d6f8a0c2e4b7"
RENDERER = "phase12h-rollback-v1"


def marker_count(connection: object) -> int:
    return int(
        connection.scalar(
            text(
                "SELECT count(*) FROM public.audit_events "
                "WHERE action='report_pdf_exported' "
                "AND metadata->>'rendererVersion'=:renderer"
            ),
            {"renderer": RENDERER},
        )
    )


def prepare() -> None:
    migration = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    runtime = create_engine(os.environ["DATABASE_URL"])
    rows = build_rows()
    try:
        with migration.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            clean_seed(connection, rows)
            apply_rows(connection, rows)
            validate(connection, rows)
        with runtime.begin() as connection:
            connection.execute(
                text(
                    "SELECT set_config('workloop.identity_issuer',:issuer,true),"
                    "set_config('workloop.identity_subject','hr.admin@horizon.test',true),"
                    "set_config('workloop.app_user_id',:actor,true),"
                    "set_config('workloop.role','admin',true),"
                    "set_config('workloop.company_id',:company,true),"
                    "set_config('workloop.employee_id','',true),"
                    "set_config('workloop.branch_id',:branch,true),"
                    "set_config('workloop.actor_kind','human',true),"
                    "set_config('workloop.actor_key','',true),"
                    "set_config('workloop.business_date','2026-09-25',true)"
                ),
                {
                    "issuer": seed.SEED_ISSUER,
                    "actor": str(seed.ADMIN_APP_USER[seed.HORIZON]),
                    "company": str(seed.COMPANY_ID[seed.HORIZON]),
                    "branch": str(seed.BRANCH_DXB),
                },
            )
            connection.execute(
                text(
                    "SELECT public.append_phase12_output_audit("
                    "'report_pdf_exported','report',:branch,'pdf',:digest,:digest,"
                    ":renderer,1,64,'succeeded')"
                ),
                {
                    "branch": str(seed.BRANCH_DXB),
                    "digest": "sha256:" + "a" * 64,
                    "renderer": RENDERER,
                },
            )
        with migration.connect() as connection:
            assert marker_count(connection) == 1
    finally:
        runtime.dispose()
        migration.dispose()


def verify(expected: str) -> None:
    migration = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with migration.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == expected
            assert marker_count(connection) == 1
    finally:
        migration.dispose()


def cleanup() -> None:
    migration = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    try:
        with migration.begin() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            assert marker_count(connection) == 1
            connection.execute(
                text(
                    "DELETE FROM public.audit_events WHERE action='report_pdf_exported' "
                    "AND metadata->>'rendererVersion'=:renderer"
                ),
                {"renderer": RENDERER},
            )
            clean_seed(connection, rows)
            assert marker_count(connection) == 0
    finally:
        migration.dispose()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "predecessor", "head", "cleanup"}:
        raise SystemExit(
            "usage: verify-phase-12h-rollback.py [prepare|predecessor|head|cleanup]"
        )
    mode = sys.argv[1]
    if mode == "prepare":
        prepare()
    elif mode == "predecessor":
        verify(PREDECESSOR)
    elif mode == "head":
        verify(HEAD)
    else:
        cleanup()
    print(f"Phase 12H rollback evidence {mode} check passed")


if __name__ == "__main__":
    main()
