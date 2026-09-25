#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path("/workspace") if Path("/workspace").is_dir() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.auth.application_user import AuthorizationPrincipal  # noqa: E402
from app.models.identity import AccountStatus, AppRole  # noqa: E402
from app.repositories.tasks import SqlTaskRepository  # noqa: E402
from app.services.tasks import TASK_CATEGORY_REGISTRY  # noqa: E402

COMPANY_ID = uuid.UUID("c4000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("c4000000-0000-4000-8000-000000000002")
APP_USER_ID = uuid.UUID("c4000000-0000-4000-8000-000000000003")
EMPLOYEE_ID = uuid.UUID("c4000000-0000-4000-8000-000000000004")


def principal(role: AppRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=APP_USER_ID,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=None if role is AppRole.ADMIN else EMPLOYEE_ID,
        branch_id=None if role is AppRole.ADMIN else BRANCH_ID,
    )


async def verify() -> None:
    url = os.environ["MIGRATION_DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql+psycopg_async://", 1
    )
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            head = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert head == "e8a1c3f5b7d9"
            repository = SqlTaskRepository(connection)
            executed: list[str] = []
            for role in (AppRole.ADMIN, AppRole.MANAGER, AppRole.EMPLOYEE):
                actor = principal(role)
                for spec in TASK_CATEGORY_REGISTRY:
                    if role not in spec.roles:
                        continue
                    await repository.read_category(
                        code=spec.code,
                        principal=actor,
                        branch_id=BRANCH_ID,
                        business_date=date(2026, 9, 24),
                    )
                    executed.append(f"{role.value}:{spec.code}")
            assert len(executed) == sum(len(spec.roles) for spec in TASK_CATEGORY_REGISTRY)
    finally:
        await engine.dispose()

    print("Phase 12C database query verification passed")


if __name__ == "__main__":
    asyncio.run(verify())
