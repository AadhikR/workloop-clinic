from __future__ import annotations

import os
from pathlib import Path

from alembic.config import Config

from alembic import command as alembic_command
from app.db import cloud_bootstrap, cloud_seed

ALEMBIC_CONFIG = Path(__file__).resolve().parents[2] / "alembic.ini"


def upgrade_schema() -> None:
    alembic_command.upgrade(Config(str(ALEMBIC_CONFIG)), "head")


def workloop_admin_url() -> str:
    value = os.environ.get("CLOUD_ADMIN_WORKLOOP_DATABASE_URL")
    if not value:
        raise RuntimeError("CLOUD_ADMIN_WORKLOOP_DATABASE_URL is required")
    return value


def main() -> int:
    cloud_bootstrap.main()
    upgrade_schema()
    cloud_bootstrap.harden_migrated_schema(workloop_admin_url())
    cloud_seed.main()
    print("Shared-development ownership, schema, and synthetic identity are ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
