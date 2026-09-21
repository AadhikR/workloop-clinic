#!/usr/bin/env python3
"""Exercise Phase 10D attendance calculation against PostgreSQL."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.attendance_calculation import (
    AttendanceCalculationBatchRequest,
    AttendanceCalculationRequest,
)
from app.services.attendance_records import AttendanceRecordService, RecordListQuery
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError

ADMIN = "hr.admin@horizon.test"
EMPLOYEE = "ravi.employee@horizon.test"
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
ATTENDANCE_DATE = "2026-08-27"


def database_url(user: str, password_name: str) -> URL:
    password = os.environ.get(password_name)
    if not password:
        raise RuntimeError(f"{password_name} is required")
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=os.environ.get("WORKLOOP_POSTGRES_HOST", "postgres"),
        port=5432,
        database="workloop",
    )


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=seed.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


async def expect_code(code: str, operation: Awaitable[object]) -> None:
    try:
        await operation
    except ServiceExecutionError as error:
        assert error.code == code, error.code
        return
    raise AssertionError(f"expected {code}")


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    rows = build_rows()
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "a1c3e5f7b902"
        )
        connection.execute(text("DELETE FROM public.clock_events WHERE notes LIKE '10D %'"))
        connection.execute(
            text(
                "DELETE FROM public.attendance_records "
                "WHERE employee_id=:employee AND date=:attendance_date"
            ),
            {"employee": EMPLOYEE_ID, "attendance_date": ATTENDANCE_DATE},
        )
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "DELETE FROM public.attendance_records "
                "WHERE employee_id=:employee AND date=:attendance_date"
            ),
            {"employee": EMPLOYEE_ID, "attendance_date": ATTENDANCE_DATE},
        )
        connection.execute(
            text(
                "DELETE FROM public.clock_events WHERE employee_id=:employee "
                "AND event_time >= '2026-08-27T00:00:00Z' "
                "AND event_time < '2026-08-28T00:00:00Z'"
            ),
            {"employee": EMPLOYEE_ID},
        )
        connection.execute(
            text(
                "INSERT INTO public.clock_events"
                "(company_id,branch_id,employee_id,event_type,event_time,method,notes) VALUES "
                "(:company,:branch,:employee,'CLOCK_IN','2026-08-27T04:00:00Z','WEB','10D in'),"
                "(:company,:branch,:employee,'CLOCK_OUT','2026-08-27T12:00:00Z','WEB','10D out')"
            ),
            {
                "company": seed.COMPANY_ID[seed.HORIZON],
                "branch": BRANCH_ID,
                "employee": EMPLOYEE_ID,
            },
        )

    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD")
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine, issuer=seed.SEED_ISSUER, timeout_seconds=5
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    principals = {
        subject: await resolver.resolve(issuer=seed.SEED_ISSUER, subject=subject)
        for subject in (ADMIN, EMPLOYEE)
    }
    codec = EmployeeCursorCodec(b"d" * 32)

    async def run_service(
        subject: str,
        callback: Callable[[AttendanceRecordService, AuthorizationPrincipal], Awaitable[Any]],
        *,
        branch_id: uuid.UUID | None = None,
    ) -> Any:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(AttendanceRecordService(connection, codec), principal)

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=branch_id if subject == ADMIN else None,
            operation=invoke,
        )

    request = AttendanceCalculationRequest.model_validate(
        {"employeeId": str(EMPLOYEE_ID), "attendanceDate": ATTENDANCE_DATE}
    )
    try:
        calculated = await run_service(
            ADMIN,
            lambda service, principal: service.calculate_one(principal, BRANCH_ID, request),
            branch_id=BRANCH_ID,
        )
        assert (calculated.status, calculated.total_hours) == ("PRESENT", 8), (
            calculated.status,
            calculated.total_hours,
            calculated.expected_hours,
            calculated.late_minutes,
            calculated.early_departure_minutes,
            calculated.evidence_flags,
        )
        assert calculated.calculation_version == 1 and not calculated.source_stale
        with migration_engine.connect() as connection:
            persisted = (
                connection.execute(
                    text(
                        "SELECT source_snapshot,source_clock_event_ids,is_ramadan_day "
                        "FROM public.attendance_records "
                        "WHERE employee_id=:employee AND date=:attendance_date"
                    ),
                    {"employee": EMPLOYEE_ID, "attendance_date": ATTENDANCE_DATE},
                )
                .mappings()
                .one()
            )
            assert {
                "employment",
                "attendanceSettings",
                "shift",
                "shiftSource",
                "clockEvents",
                "holiday",
                "approvedLeave",
                "ramadan",
                "priorRequiredAttendance",
            } <= set(persisted["source_snapshot"])
            assert len(persisted["source_clock_event_ids"]) == 2
        await expect_code(
            "state_conflict",
            run_service(
                ADMIN,
                lambda service, principal: service.calculate_one(principal, BRANCH_ID, request),
                branch_id=BRANCH_ID,
            ),
        )
        await expect_code(
            "resource_not_found",
            run_service(
                ADMIN,
                lambda service, principal: service.calculate_one(
                    principal, OTHER_BRANCH_ID, request
                ),
                branch_id=OTHER_BRANCH_ID,
            ),
        )
        versioned = AttendanceCalculationRequest.model_validate(
            {
                "employeeId": str(EMPLOYEE_ID),
                "attendanceDate": ATTENDANCE_DATE,
                "expectedSourceDigest": calculated.source_digest,
                "expectedCalculationVersion": calculated.calculation_version,
            }
        )
        first, second = await asyncio.gather(
            run_service(
                ADMIN,
                lambda service, principal: service.calculate_one(principal, BRANCH_ID, versioned),
                branch_id=BRANCH_ID,
            ),
            run_service(
                ADMIN,
                lambda service, principal: service.calculate_one(principal, BRANCH_ID, versioned),
                branch_id=BRANCH_ID,
            ),
            return_exceptions=True,
        )
        outcomes = (first, second)
        winners = [item for item in outcomes if not isinstance(item, Exception)]
        conflicts = [
            item
            for item in outcomes
            if isinstance(item, ServiceExecutionError) and item.code == "state_conflict"
        ]
        assert len(winners) == len(conflicts) == 1, tuple(repr(item) for item in outcomes)
        assert winners[0].calculation_version == 2

        batch = AttendanceCalculationBatchRequest.model_validate(
            {
                "items": [
                    {
                        "employeeId": str(EMPLOYEE_ID),
                        "attendanceDate": ATTENDANCE_DATE,
                        "expectedSourceDigest": winners[0].source_digest,
                        "expectedCalculationVersion": winners[0].calculation_version,
                    },
                    {
                        "employeeId": "ffffffff-ffff-4fff-8fff-ffffffffffff",
                        "attendanceDate": ATTENDANCE_DATE,
                    },
                ]
            }
        )
        await expect_code(
            "resource_not_found",
            run_service(
                ADMIN,
                lambda service, principal: service.calculate_batch(principal, BRANCH_ID, batch),
                branch_id=BRANCH_ID,
            ),
        )

        listed, _ = await run_service(
            ADMIN,
            lambda service, principal: service.list_admin(
                principal,
                BRANCH_ID,
                RecordListQuery(EMPLOYEE_ID, None, None, 20, None),
            ),
            branch_id=BRANCH_ID,
        )
        assert listed and all(item.employee_id == EMPLOYEE_ID for item in listed)
        target = next(item for item in listed if item.date.isoformat() == ATTENDANCE_DATE)
        assert target.calculation_version == 2
        history, _ = await run_service(
            EMPLOYEE,
            lambda service, principal: service.personal_history(
                principal, RecordListQuery(None, None, None, 20, None)
            ),
        )
        assert all(item.employee_id == EMPLOYEE_ID for item in history)
        today = await run_service(
            EMPLOYEE,
            lambda service, principal: service.personal_today(principal),
        )
        assert today.record is None and today.raw_event_fallback == "self_only"

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.clock_events"
                    "(company_id,branch_id,employee_id,event_type,event_time,method,notes) "
                    "VALUES (:company,:branch,:employee,'CLOCK_OUT',"
                    "'2026-08-27T13:05:00Z','WEB','10D late event')"
                ),
                {
                    "company": seed.COMPANY_ID[seed.HORIZON],
                    "branch": BRANCH_ID,
                    "employee": EMPLOYEE_ID,
                },
            )
            assert connection.scalar(
                text(
                    "SELECT source_stale FROM public.attendance_records "
                    "WHERE employee_id=:employee AND date=:attendance_date"
                ),
                {"employee": EMPLOYEE_ID, "attendance_date": ATTENDANCE_DATE},
            )
            connection.execute(
                text(
                    "INSERT INTO public.attendance_periods"
                    "(company_id,branch_id,period,status,closed_by_app_user_id,closed_at) "
                    "VALUES (:company,:branch,'2026-08','closed',:actor,now()) "
                    "ON CONFLICT (branch_id,period) DO UPDATE SET status='closed',"
                    "closed_by_app_user_id=excluded.closed_by_app_user_id,closed_at=excluded.closed_at"
                ),
                {
                    "company": seed.COMPANY_ID[seed.HORIZON],
                    "branch": BRANCH_ID,
                    "actor": seed.ADMIN_APP_USER[seed.HORIZON],
                },
            )
        await expect_code(
            "state_conflict",
            run_service(
                ADMIN,
                lambda service, principal: service.calculate_one(
                    principal,
                    BRANCH_ID,
                    AttendanceCalculationRequest.model_validate(
                        {
                            "employeeId": str(EMPLOYEE_ID),
                            "attendanceDate": ATTENDANCE_DATE,
                            "expectedSourceDigest": winners[0].source_digest,
                            "expectedCalculationVersion": winners[0].calculation_version,
                        }
                    ),
                ),
                branch_id=BRANCH_ID,
            ),
        )
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            connection.execute(text("DELETE FROM public.clock_events WHERE notes LIKE '10D %'"))
            connection.execute(
                text(
                    "DELETE FROM public.attendance_records "
                    "WHERE employee_id=:employee AND date=:attendance_date"
                ),
                {"employee": EMPLOYEE_ID, "attendance_date": ATTENDANCE_DATE},
            )
            clean(connection, rows)
        migration_engine.dispose()

    print("Phase 10D database calculation and isolation verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
