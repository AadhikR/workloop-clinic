from __future__ import annotations

from pathlib import Path

from alembic.config import Config

from alembic import command as alembic_command
from app.db import cloud_bootstrap, cloud_seed

ALEMBIC_CONFIG = Path(__file__).resolve().parents[2] / "alembic.ini"


def upgrade_schema() -> None:
    alembic_command.upgrade(Config(str(ALEMBIC_CONFIG)), "head")


def main() -> int:
    cloud_bootstrap.main()
    upgrade_schema()
    cloud_seed.main()
    print("Phase 6G ownership, schema, and synthetic identity are ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
