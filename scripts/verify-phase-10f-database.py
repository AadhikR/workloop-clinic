#!/usr/bin/env python3
"""Exercise Phase 10F close versions and payroll projection against PostgreSQL."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.repositories.attendance_exceptions import SqlAttendanceExceptionRepository
from app.repositories.attendance_periods import AttendancePeriodRepository
from app.repositories.payroll import PayrollRepository
from app.schemas.attendance_calculation import AttendanceCalculationRequest
from app.schemas.attendance_exceptions import AbsenceResolutionRequest, OvertimeApprovalRequest
from app.schemas.attendance_periods import AttendancePeriodCloseRequest
from app.services.attendance_exceptions import AttendanceExceptionService
from app.services.attendance_periods import AttendancePeriodService
from app.services.attendance_records import AttendanceRecordService
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError

ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
TARGET_EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
VERIFY_SHIFT_ID = uuid.UUID("a10f0000-0000-4000-8000-000000000001")
VERIFY_ASSIGNMENT_ID = uuid.UUID("a10f0000-0000-4000-8000-000000000002")
PREFIX = "Phase 10F verification"


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


def instant(day: date, local_hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(local_hour - 4, minute), tzinfo=UTC)


def cleanup_verification_state(connection: Any, *, today: date, period: str) -> None:
    protected_tables = (
        "attendance_period_audit_log",
        "attendance_period_record_snapshots",
        "attendance_period_versions",
    )
    for table in protected_tables:
        connection.execute(text(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY"))
    connection.execute(
        text(
            "DROP TRIGGER IF EXISTS trg_phase10f_verify_reject_audit "
            "ON public.attendance_period_audit_log"
        )
    )
    connection.execute(text("DROP FUNCTION IF EXISTS public.phase10f_verify_reject_audit()"))
    period_ids = list(
        connection.execute(
            text(
                "SELECT id FROM public.attendance_periods WHERE company_id=:company "
                "AND branch_id=:branch AND period=:period"
            ),
            {"company": COMPANY_ID, "branch": BRANCH_ID, "period": period},
        ).scalars()
    )
    if period_ids:
        version_ids = list(
            connection.execute(
                text(
                    "SELECT id FROM public.attendance_period_versions "
                    "WHERE attendance_period_id=ANY(:period_ids)"
                ),
                {"period_ids": period_ids},
            ).scalars()
        )
        connection.execute(
            text(
                "UPDATE public.attendance_periods SET payroll_ready=false,version=0,"
                "current_version_id=NULL,source_version=NULL WHERE id=ANY(:period_ids)"
            ),
            {"period_ids": period_ids},
        )
        if version_ids:
            for table in protected_tables:
                key = "period_version_id" if table != "attendance_period_versions" else "id"
                connection.execute(
                    text(f"DELETE FROM public.{table} WHERE {key}=ANY(:version_ids)"),
                    {"version_ids": version_ids},
                )
        connection.execute(
            text("DELETE FROM public.attendance_periods WHERE id=ANY(:period_ids)"),
            {"period_ids": period_ids},
        )
    first_day = today - timedelta(days=3)
    connection.execute(
        text(
            "DELETE FROM public.attendance_audit_log WHERE company_id=:company "
            "AND branch_id=:branch AND attendance_date BETWEEN :first_day AND :today"
        ),
        {
            "company": COMPANY_ID,
            "branch": BRANCH_ID,
            "first_day": first_day,
            "today": today,
        },
    )
    connection.execute(
        text(
            "UPDATE public.attendance_records SET period_closed=false WHERE company_id=:company "
            "AND branch_id=:branch AND date BETWEEN :first_day AND :today"
        ),
        {
            "company": COMPANY_ID,
            "branch": BRANCH_ID,
            "first_day": first_day,
            "today": today,
        },
    )
    connection.execute(
        text(
            "DELETE FROM public.attendance_records WHERE company_id=:company "
            "AND branch_id=:branch AND date BETWEEN :first_day AND :today"
        ),
        {
            "company": COMPANY_ID,
            "branch": BRANCH_ID,
            "first_day": first_day,
            "today": today,
        },
    )
    connection.execute(
        text("DELETE FROM public.clock_events WHERE notes LIKE :prefix"),
        {"prefix": f"{PREFIX}%"},
    )
    connection.execute(
        text("DELETE FROM public.shift_assignments WHERE id=:id"),
        {"id": VERIFY_ASSIGNMENT_ID},
    )
    connection.execute(
        text("DELETE FROM public.shifts WHERE id=:id"),
        {"id": VERIFY_SHIFT_ID},
    )
    for table in protected_tables:
        connection.execute(text(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))
        connection.execute(text(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY"))


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    rows = build_rows()
    added_event_ids: list[uuid.UUID] = []
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "c3e5a7b9d1f6"
        )
        raw_today = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        today = raw_today if isinstance(raw_today, date) else date.fromisoformat(str(raw_today))
        period = today.strftime("%Y-%m")
        cleanup_verification_state(connection, today=today, period=period)
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        absence_date = today - timedelta(days=3)
        late_date = today - timedelta(days=2)
        overtime_date = today - timedelta(days=1)
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        today_name = today.strftime("%a")
        other_weekend = day_names[(day_names.index(today_name) + 1) % len(day_names)]
        weekend_days = [today_name, other_weekend]
        working_days = [value for value in day_names if value not in weekend_days]
        active_ids = list(
            connection.execute(
                text(
                    "SELECT id FROM public.employees WHERE company_id=:company "
                    "AND branch_id=:branch AND active "
                    "AND employment_status IN ('Active','Probation','On Leave') ORDER BY id"
                ),
                {"company": COMPANY_ID, "branch": BRANCH_ID},
            ).scalars()
        )
        assert TARGET_EMPLOYEE_ID in active_ids
        connection.execute(
            text(
                "UPDATE public.employees SET employment_start_date=:today,updated_at=now() "
                "WHERE id=ANY(:employees)"
            ),
            {"today": today, "employees": active_ids},
        )
        connection.execute(
            text(
                "UPDATE public.employees SET employment_start_date=:start,basic_salary=12000.00,"
                "updated_at=now() WHERE id=:employee"
            ),
            {"start": absence_date, "employee": TARGET_EMPLOYEE_ID},
        )
        connection.execute(
            text(
                "UPDATE public.attendance_settings SET working_days=:working,"
                "weekend_days=:weekend,late_deduction_policy='per_minute',"
                "late_deduction_amount=1.25,overtime_requires_approval=true,"
                "max_daily_overtime_hours=4.00,updated_at=now() "
                "WHERE company_id=:company AND branch_id=:branch"
            ),
            {
                "working": working_days,
                "weekend": weekend_days,
                "company": COMPANY_ID,
                "branch": BRANCH_ID,
            },
        )
        connection.execute(
            text(
                "INSERT INTO public.shifts"
                "(id,company_id,branch_id,name,code,shift_type,start_time,end_time,"
                "break_minutes,expected_hours,late_grace_minutes,"
                "early_departure_grace_minutes,is_overnight,shift_category,color) "
                "VALUES (:id,:company,:branch,:name,'P10F','fixed','08:00','17:00',"
                "60,8,10,10,false,'morning','#2563EB')"
            ),
            {
                "id": VERIFY_SHIFT_ID,
                "company": COMPANY_ID,
                "branch": BRANCH_ID,
                "name": f"{PREFIX} fixed shift",
            },
        )
        connection.execute(
            text(
                "INSERT INTO public.shift_assignments"
                "(id,company_id,branch_id,employee_id,shift_id,effective_from,effective_to) "
                "VALUES (:id,:company,:branch,:employee,:shift,:start,:today)"
            ),
            {
                "id": VERIFY_ASSIGNMENT_ID,
                "company": COMPANY_ID,
                "branch": BRANCH_ID,
                "employee": TARGET_EMPLOYEE_ID,
                "shift": VERIFY_SHIFT_ID,
                "start": absence_date,
                "today": today,
            },
        )
        event_rows = (
            (late_date, "CLOCK_IN", instant(late_date, 8, 16)),
            (late_date, "CLOCK_OUT", instant(late_date, 17)),
            (overtime_date, "CLOCK_IN", instant(overtime_date, 8)),
            (overtime_date, "CLOCK_OUT", instant(overtime_date, 19)),
        )
        for event_day, event_type, event_time in event_rows:
            event_id = uuid.uuid4()
            added_event_ids.append(event_id)
            connection.execute(
                text(
                    "INSERT INTO public.clock_events"
                    "(id,company_id,branch_id,employee_id,event_type,event_time,method,notes) "
                    "VALUES (:id,:company,:branch,:employee,:event_type,:event_time,'WEB',:notes)"
                ),
                {
                    "id": event_id,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": TARGET_EMPLOYEE_ID,
                    "event_type": event_type,
                    "event_time": event_time,
                    "notes": f"{PREFIX} {event_day}",
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
        deadline_seconds=30,
    )
    principals = {
        subject: await resolver.resolve(issuer=seed.SEED_ISSUER, subject=subject)
        for subject in (ADMIN, MANAGER)
    }
    codec = EmployeeCursorCodec(b"f" * 32)

    async def run(
        subject: str,
        callback: Callable[[AsyncConnection, AuthorizationPrincipal], Awaitable[Any]],
        *,
        branch_id: uuid.UUID | None = None,
    ) -> Any:
        principal = principals[subject]
        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=branch_id if subject == ADMIN else None,
            operation=lambda connection: callback(connection, principal),
        )

    async def calculate(employee_id: uuid.UUID, attendance_date: date) -> Any:
        async def invoke(connection: AsyncConnection, principal: AuthorizationPrincipal) -> Any:
            return await AttendanceRecordService(connection, codec).calculate_one(
                principal,
                BRANCH_ID,
                AttendanceCalculationRequest(
                    employee_id=employee_id, attendance_date=attendance_date
                ),
            )

        return await run(ADMIN, invoke, branch_id=BRANCH_ID)

    async def close(expected_version: int, reason: str | None = None) -> Any:
        async def invoke(connection: AsyncConnection, principal: AuthorizationPrincipal) -> Any:
            return await AttendancePeriodService(
                AttendancePeriodRepository(connection), codec
            ).close(
                principal,
                BRANCH_ID,
                period,
                AttendancePeriodCloseRequest(
                    expected_version=expected_version, amendment_reason=reason
                ),
            )

        return await run(ADMIN, invoke, branch_id=BRANCH_ID)

    try:
        target_records = {
            day: await calculate(TARGET_EMPLOYEE_ID, day)
            for day in (absence_date, late_date, overtime_date, today)
        }
        for employee_id in active_ids:
            if employee_id != TARGET_EMPLOYEE_ID:
                record = await calculate(employee_id, today)
                assert record.status == "WEEKEND"
        assert target_records[absence_date].status == "UNEXPLAINED_ABSENCE"
        assert target_records[late_date].late_minutes == 6
        assert target_records[overtime_date].overtime_hours == 2

        async def readiness(connection: AsyncConnection, principal: AuthorizationPrincipal) -> Any:
            return await AttendancePeriodService(
                AttendancePeriodRepository(connection), codec
            ).detail(principal, BRANCH_ID, period)

        open_period = await run(ADMIN, readiness, branch_id=BRANCH_ID)
        blocker_codes = {item.code for item in open_period.blockers}
        assert blocker_codes == {"unapproved_overtime", "unresolved_absences"}
        await expect_code("attendance_period_not_ready", close(0))
        await expect_code(
            "operation_not_permitted",
            run(MANAGER, readiness),
        )
        await expect_code(
            "resource_not_found",
            run(ADMIN, readiness, branch_id=OTHER_BRANCH_ID),
        )

        async def resolve(connection: AsyncConnection, principal: AuthorizationPrincipal) -> Any:
            return await AttendanceExceptionService(
                SqlAttendanceExceptionRepository(connection), codec
            ).resolve_absence(
                principal,
                BRANCH_ID,
                target_records[absence_date].id,
                AbsenceResolutionRequest(
                    expected_calculation_version=target_records[absence_date].calculation_version,
                    resolution_type="UNAUTHORISED",
                    reason="Unapproved absence confirmed",
                ),
            )

        resolved = await run(ADMIN, resolve, branch_id=BRANCH_ID)
        assert resolved.resolution_type == "UNAUTHORISED"

        async def approve_overtime(
            connection: AsyncConnection, principal: AuthorizationPrincipal
        ) -> Any:
            return await AttendanceExceptionService(
                SqlAttendanceExceptionRepository(connection), codec
            ).approve_overtime(
                principal,
                BRANCH_ID,
                target_records[overtime_date].id,
                OvertimeApprovalRequest(
                    expected_calculation_version=target_records[overtime_date].calculation_version
                ),
            )

        approved = await run(ADMIN, approve_overtime, branch_id=BRANCH_ID)
        assert approved.overtime_approved

        first, competing = await asyncio.gather(close(0), close(0))
        assert first.source_version == competing.source_version
        assert first.version == competing.version == 1
        assert first.payroll_ready and first.blocker_count == 0
        with migration_engine.connect() as connection:
            first_version_id = connection.scalar(
                text(
                    "SELECT current_version_id FROM public.attendance_periods "
                    "WHERE company_id=:company AND branch_id=:branch AND period=:period"
                ),
                {"company": COMPANY_ID, "branch": BRANCH_ID, "period": period},
            )
        assert isinstance(first_version_id, uuid.UUID)

        async def projection(
            connection: AsyncConnection, _principal: AuthorizationPrincipal
        ) -> Any:
            return await PayrollRepository(connection).attendance_input_projection(
                company_id=COMPANY_ID, branch_id=BRANCH_ID, period=period
            )

        payroll_rows = await run(ADMIN, projection, branch_id=BRANCH_ID)
        if payroll_rows is None:

            async def projection_diagnostic(
                connection: AsyncConnection, _principal: AuthorizationPrincipal
            ) -> Any:
                row = (
                    (
                        await connection.execute(
                            text(
                                "SELECT period_row.current_version_id,period_row.source_version,"
                                "version.source_canonical,version.record_count,"
                                "(SELECT count(*) FROM public.attendance_period_record_snapshots "
                                "WHERE period_version_id=version.id) snapshot_count,"
                                "public.phase10f_lock_period_evidence("
                                "period_row.company_id,period_row.branch_id,version.id) "
                                "evidence_locked "
                                "FROM public.attendance_periods period_row "
                                "JOIN public.attendance_period_versions version "
                                "ON version.id=period_row.current_version_id "
                                "WHERE period_row.company_id=:company "
                                "AND period_row.branch_id=:branch "
                                "AND period_row.period=:period"
                            ),
                            {"company": COMPANY_ID, "branch": BRANCH_ID, "period": period},
                        )
                    )
                    .mappings()
                    .one()
                )
                return dict(row)

            diagnostic = await run(ADMIN, projection_diagnostic, branch_id=BRANCH_ID)
            diagnostic["computed_version"] = (
                "sha256:" + hashlib.sha256(diagnostic["source_canonical"].encode()).hexdigest()
            )
            raise AssertionError(f"payroll projection not ready: {diagnostic}")
        target = next(row for row in payroll_rows if row["employee_id"] == TARGET_EMPLOYEE_ID)
        assert target["absence_days"] == Decimal("1.00")
        assert target["absence_amount"] == Decimal("400.00")
        assert target["late_minutes"] == 6
        assert target["late_amount"] == Decimal("7.50")
        assert target["standard_overtime_hours"] == Decimal("2.00")
        assert target["standard_overtime_amount"] == Decimal("144.23")
        assert list(target["source_row_ids"]) == sorted(target["source_row_ids"])

        await expect_code(
            "state_conflict",
            calculate(TARGET_EMPLOYEE_ID, late_date),
        )
        await expect_code("state_conflict", close(1, "No new attendance evidence"))

        late_evidence_id = uuid.uuid4()
        added_event_ids.append(late_evidence_id)
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.clock_events"
                    "(id,company_id,branch_id,employee_id,event_type,event_time,method,notes) "
                    "VALUES (:id,:company,:branch,:employee,'CLOCK_OUT',:event_time,'WEB',:notes)"
                ),
                {
                    "id": late_evidence_id,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": TARGET_EMPLOYEE_ID,
                    "event_time": instant(absence_date, 18),
                    "notes": f"{PREFIX} amendment evidence",
                },
            )
            connection.execute(
                text(
                    "CREATE FUNCTION public.phase10f_verify_reject_audit() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced audit failure'; END $$"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_phase10f_verify_reject_audit BEFORE INSERT "
                    "ON public.attendance_period_audit_log FOR EACH ROW "
                    "EXECUTE FUNCTION public.phase10f_verify_reject_audit()"
                )
            )
        try:
            await close(1, "Approved late evidence")
        except DBAPIError:
            pass
        else:
            raise AssertionError("forced audit failure did not roll back amendment")
        with migration_engine.connect() as connection:
            state = connection.execute(
                text(
                    "SELECT version,current_version_id,source_version "
                    "FROM public.attendance_periods "
                    "WHERE company_id=:company AND branch_id=:branch AND period=:period"
                ),
                {"company": COMPANY_ID, "branch": BRANCH_ID, "period": period},
            ).one()
            assert state == (1, first_version_id, first.source_version)
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM public.attendance_period_versions "
                        "WHERE company_id=:company AND branch_id=:branch AND period=:period"
                    ),
                    {"company": COMPANY_ID, "branch": BRANCH_ID, "period": period},
                )
                == 1
            )
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "DROP TRIGGER trg_phase10f_verify_reject_audit "
                    "ON public.attendance_period_audit_log"
                )
            )
            connection.execute(text("DROP FUNCTION public.phase10f_verify_reject_audit()"))

        amended = await close(1, "Approved late evidence")
        assert amended.version == 2 and amended.source_version != first.source_version
        refreshed_rows = await run(ADMIN, projection, branch_id=BRANCH_ID)
        assert refreshed_rows[0]["source_version"] == amended.source_version
        with migration_engine.connect() as connection:
            versions = connection.execute(
                text(
                    "SELECT version,source_version,prior_version_id "
                    "FROM public.attendance_period_versions "
                    "WHERE company_id=:company AND branch_id=:branch "
                    "AND period=:period ORDER BY version"
                ),
                {"company": COMPANY_ID, "branch": BRANCH_ID, "period": period},
            ).all()
            assert versions[0] == (1, first.source_version, None)
            assert versions[1][0] == 2 and versions[1][2] == first_version_id
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM public.attendance_period_audit_log "
                        "WHERE company_id=:company AND branch_id=:branch AND period=:period"
                    ),
                    {"company": COMPANY_ID, "branch": BRANCH_ID, "period": period},
                )
                == 2
            )

        async def tamper(connection: AsyncConnection, _principal: AuthorizationPrincipal) -> None:
            await connection.execute(
                text("UPDATE public.attendance_records SET late_minutes=0 WHERE id=:id"),
                {"id": target_records[late_date].id},
            )

        try:
            await run(ADMIN, tamper, branch_id=BRANCH_ID)
        except DBAPIError:
            pass
        else:
            raise AssertionError("closed attendance record update was not rejected")
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            cleanup_verification_state(connection, today=today, period=period)
            clean(connection, rows)
        migration_engine.dispose()

    print("Phase 10F database close and payroll projection verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
