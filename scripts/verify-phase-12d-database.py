#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path("/workspace") if Path("/workspace").is_dir() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.expiry_command import CLINICAL_DOCUMENT_TYPES  # noqa: E402
from app.repositories.dashboards import (  # noqa: E402
    ADMIN_SNAPSHOT,
    CLINICAL_SNAPSHOT,
    SELF_SNAPSHOT,
    SqlDashboardRepository,
)

COMPANY_ID = uuid.UUID("c7000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("c7000000-0000-4000-8000-000000000002")
EMPLOYEE_ID = uuid.UUID("c7000000-0000-4000-8000-000000000003")


async def verify() -> None:
    url = os.environ["MIGRATION_DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql+psycopg_async://", 1
    )
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            head = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert head == "d6f8a0c2e4b7"
            await connection.execute(
                text(
                    "SELECT set_config('workloop.company_id',:company,true),"
                    "set_config('workloop.branch_id',:branch,true),"
                    "set_config('workloop.app_user_id',:user_id,true),"
                    "set_config('workloop.actor_kind','human',true),"
                    "set_config('workloop.business_date','2026-09-24',true)"
                ),
                {
                    "branch": str(BRANCH_ID),
                    "company": str(COMPANY_ID),
                    "user_id": str(uuid.UUID("c7000000-0000-4000-8000-000000000004")),
                },
            )
            before = tuple(
                await connection.execute(
                    text(
                        "SELECT (SELECT count(*) FROM public.notifications),"
                        "(SELECT count(*) FROM public.payroll_runs),"
                        "(SELECT count(*) FROM public.roster_publication_versions),"
                        "(SELECT count(*) FROM public.employee_documents)"
                    )
                )
            )[0]
            repository = SqlDashboardRepository(connection, "synthetic-v1")
            common = {
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "employee_id": None,
                "clinical_types": tuple(sorted(CLINICAL_DOCUMENT_TYPES)),
            }
            admin = await repository.snapshot("admin", **common)
            clinical = await repository.snapshot("clinical", **common)
            assert admin["business_date"] is not None and admin["active_headcount"] == 0
            assert clinical["business_date"] is not None and clinical["valid_count"] == 0

            parameters = {
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "employee_id": EMPLOYEE_ID,
                "clinical_types": list(sorted(CLINICAL_DOCUMENT_TYPES)),
                "scanner_definition": "synthetic-v1",
            }
            for statement in (ADMIN_SNAPSHOT, CLINICAL_SNAPSHOT, SELF_SNAPSHOT):
                await connection.execute(
                    text("EXPLAIN " + statement.text),
                    parameters,
                )
            after = tuple(
                await connection.execute(
                    text(
                        "SELECT (SELECT count(*) FROM public.notifications),"
                        "(SELECT count(*) FROM public.payroll_runs),"
                        "(SELECT count(*) FROM public.roster_publication_versions),"
                        "(SELECT count(*) FROM public.employee_documents)"
                    )
                )
            )[0]
            assert after == before
    finally:
        await engine.dispose()

    print("Phase 12D database snapshot and no-write verification passed")


if __name__ == "__main__":
    asyncio.run(verify())
