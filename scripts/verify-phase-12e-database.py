#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ROOT = Path("/workspace") if Path("/workspace").is_dir() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.repositories.reports import REPORT_QUERIES, SqlReportRepository  # noqa: E402

COMPANY_ID = uuid.UUID("ca000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("ca000000-0000-4000-8000-000000000002")

SOURCE_TABLES = (
    "attendance_records",
    "compliance_overrides",
    "employee_documents",
    "employee_job_history",
    "employees",
    "leave_balances",
    "leave_requests",
    "nafis_reports",
    "payroll_entries",
    "payroll_runs",
    "roster_months",
    "settlement_policy_versions",
)


async def counts(connection: AsyncConnection) -> tuple[int, ...]:
    statement = "SELECT " + ",".join(
        f"(SELECT count(*) FROM public.{table_name})" for table_name in SOURCE_TABLES
    )
    result = await connection.execute(text(statement))
    return tuple(result.one())


async def verify() -> None:
    url = os.environ["MIGRATION_DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql+psycopg_async://", 1
    )
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            head = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert head == "e8a1c3f5b7d9"
            await connection.execute(
                text(
                    "SELECT set_config('workloop.company_id',:company,true),"
                    "set_config('workloop.branch_id',:branch,true),"
                    "set_config('workloop.app_user_id',:user_id,true),"
                    "set_config('workloop.actor_kind','human',true),"
                    "set_config('workloop.business_date','2026-09-25',true)"
                ),
                {
                    "branch": str(BRANCH_ID),
                    "company": str(COMPANY_ID),
                    "user_id": str(uuid.UUID("ca000000-0000-4000-8000-000000000003")),
                },
            )
            before = await counts(connection)
            repository = SqlReportRepository(connection)
            filters: dict[str, object] = {
                "date_from": None,
                "date_to": None,
                "period": None,
                "status": None,
                "employee_id": None,
                "department": None,
            }
            for report_id in REPORT_QUERIES:
                as_of, rows = await repository.read(
                    report_id,
                    company_id=COMPANY_ID,
                    branch_id=BRANCH_ID,
                    filters=filters,
                )
                assert as_of is not None
                assert rows == []
            assert not await repository.resolve_employee(
                COMPANY_ID, BRANCH_ID, uuid.UUID("ca000000-0000-4000-8000-000000000004")
            )
            assert (
                await repository.resolve_department(
                    COMPANY_ID,
                    BRANCH_ID,
                    uuid.UUID("ca000000-0000-4000-8000-000000000005"),
                )
                is None
            )
            for statement in REPORT_QUERIES.values():
                await connection.execute(
                    text("EXPLAIN " + statement),
                    {"company_id": COMPANY_ID, "branch_id": BRANCH_ID, **filters},
                )
            after = await counts(connection)
            assert after == before
    finally:
        await engine.dispose()

    print("Phase 12E report source and no-write verification passed")


if __name__ == "__main__":
    asyncio.run(verify())
