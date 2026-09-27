from __future__ import annotations

import json
import os
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command as alembic_command
from app.db import cloud_bootstrap, cloud_seed
from app.db.engine import normalize_psycopg_url

ALEMBIC_CONFIG = Path(__file__).resolve().parents[2] / "alembic.ini"
EXPECTED_ALEMBIC_HEAD = "e8a1c3f5b7d9"


def upgrade_schema() -> None:
    alembic_command.upgrade(Config(str(ALEMBIC_CONFIG)), "head")


def workloop_admin_url() -> str:
    value = os.environ.get("CLOUD_ADMIN_WORKLOOP_DATABASE_URL")
    if not value:
        raise RuntimeError("CLOUD_ADMIN_WORKLOOP_DATABASE_URL is required")
    return value


def migration_url() -> str:
    value = os.environ.get("MIGRATION_DATABASE_URL")
    if not value:
        raise RuntimeError("MIGRATION_DATABASE_URL is required")
    return value


def required_release_head() -> str:
    value = os.environ.get("WORKLOOP_ALEMBIC_HEAD")
    if value != EXPECTED_ALEMBIC_HEAD:
        raise RuntimeError("release manifest has an incompatible Alembic head")
    return value


def current_schema_heads(database_url: str) -> tuple[str, ...]:
    engine = create_engine(normalize_psycopg_url(database_url))
    try:
        with engine.connect() as connection:
            exists = connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
            if exists is None:
                return ()
            rows = connection.execute(
                text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
            )
            return tuple(rows.scalars())
    finally:
        engine.dispose()


def verify_schema_head(database_url: str) -> None:
    heads = current_schema_heads(database_url)
    if heads != (EXPECTED_ALEMBIC_HEAD,):
        raise RuntimeError("migration did not reach the approved single Alembic head")


def main() -> int:
    required_release_head()
    cloud_bootstrap.main()
    database_url = migration_url()
    already_current = current_schema_heads(database_url) == (EXPECTED_ALEMBIC_HEAD,)
    upgrade_schema()
    cloud_bootstrap.harden_migrated_schema(workloop_admin_url())
    verify_schema_head(database_url)
    cloud_seed.main()
    print(
        json.dumps(
            {
                "already_current": already_current,
                "alembic_head": EXPECTED_ALEMBIC_HEAD,
                "status": "ready",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
