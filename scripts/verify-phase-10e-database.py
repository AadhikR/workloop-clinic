#!/usr/bin/env python3
"""Exercise Phase 10E exception workflows against PostgreSQL."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta
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
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.attendance_calculation import AttendanceCalculationRequest
from app.schemas.attendance_exceptions import (
    AbsenceResolutionRequest,
    OvertimeApprovalRequest,
    RegularisationDecisionRequest,
    RegularisationSubmitRequest,
)
from app.services.attendance_exceptions import (
    AttendanceAuditListQuery,
    AttendanceExceptionService,
    RegularisationListQuery,
)
from app.services.attendance_records import AttendanceRecordService
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import (
    IdempotencyCommand,
    IdempotencyCoordinator,
    IdempotentResponse,
)

ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
EMPLOYEE = "ravi.employee@horizon.test"
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
PREFIX = "Phase 10E verification"


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


def instant(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    rows = build_rows()
    dynamic_dates: list[date] = []
    dynamic_leave_id = uuid.uuid4()
    idempotency_key = uuid.uuid4()
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "c6e8a1b3d927"
        )
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        raw_today = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        today = raw_today if isinstance(raw_today, date) else date.fromisoformat(str(raw_today))
        raw_working_days = connection.scalar(
            text(
                "SELECT working_days FROM public.attendance_settings "
                "WHERE company_id=:company AND branch_id=:branch"
            ),
            {"company": COMPANY_ID, "branch": BRANCH_ID},
        )
        assert isinstance(raw_working_days, list)
        working_days = set(raw_working_days)
        verification_dates: list[date] = []
        candidate = today - timedelta(days=1)
        while len(verification_dates) < 6:
            if candidate.strftime("%a") in working_days:
                verification_dates.append(candidate)
            candidate -= timedelta(days=1)
        (
            correction_date,
            closed_date,
            unauthorised_date,
            wfh_date,
            leave_date,
            overtime_date,
        ) = verification_dates
        dynamic_dates.extend(
            [
                correction_date,
                closed_date,
                unauthorised_date,
                wfh_date,
                leave_date,
                overtime_date,
            ]
        )
        connection.execute(
            text(
                "UPDATE public.attendance_settings SET wfh_enabled=true "
                "WHERE company_id=:company AND branch_id=:branch"
            ),
            {"company": COMPANY_ID, "branch": BRANCH_ID},
        )
        for day, end_hour, note in (
            (correction_date, 13, "correction"),
            (closed_date, 13, "closed"),
            (overtime_date, 15, "overtime"),
        ):
            connection.execute(
                text(
                    "INSERT INTO public.clock_events"
                    "(company_id,branch_id,employee_id,event_type,event_time,method,notes) VALUES "
                    "(:company,:branch,:employee,'CLOCK_IN',:clock_in,'WEB',:note),"
                    "(:company,:branch,:employee,'CLOCK_OUT',:clock_out,'WEB',:note)"
                ),
                {
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": EMPLOYEE_ID,
                    "clock_in": instant(day, 4),
                    "clock_out": instant(day, end_hour),
                    "note": f"{PREFIX} {note}",
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
        deadline_seconds=20,
    )
    principals = {
        subject: await resolver.resolve(issuer=seed.SEED_ISSUER, subject=subject)
        for subject in (ADMIN, MANAGER, EMPLOYEE)
    }
    codec = EmployeeCursorCodec(b"e" * 32)

    async def run(
        subject: str,
        callback: Callable[
            [AttendanceExceptionService, AuthorizationPrincipal], Awaitable[Any]
        ],
        *,
        branch_id: uuid.UUID | None = None,
    ) -> Any:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> Any:
            service = AttendanceExceptionService(
                SqlAttendanceExceptionRepository(connection), codec
            )
            return await callback(service, principal)

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=branch_id if subject == ADMIN else None,
            operation=invoke,
        )

    async def calculate(day: date) -> Any:
        principal = principals[ADMIN]

        async def invoke(connection: AsyncConnection) -> Any:
            return await AttendanceRecordService(connection, codec).calculate_one(
                principal,
                BRANCH_ID,
                AttendanceCalculationRequest.model_validate(
                    {"employeeId": str(EMPLOYEE_ID), "attendanceDate": day.isoformat()}
                ),
            )

        return await executor.execute(
            claims=claims(ADMIN),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID,
            operation=invoke,
        )

    try:
        (
            corrected_record,
            _closed_record,
            absence_record,
            wfh_record,
            leave_record,
            overtime_record,
        ) = (
            await calculate(correction_date),
            await calculate(closed_date),
            await calculate(unauthorised_date),
            await calculate(wfh_date),
            await calculate(leave_date),
            await calculate(overtime_date),
        )
        absence_statuses = (
            absence_record.status,
            wfh_record.status,
            leave_record.status,
        )
        assert absence_statuses == (
            "UNEXPLAINED_ABSENCE",
            "UNEXPLAINED_ABSENCE",
            "UNEXPLAINED_ABSENCE",
        ), absence_statuses
        assert overtime_record.status == "OVERTIME" and overtime_record.overtime_hours > 0

        submit_body = RegularisationSubmitRequest.model_validate(
            {
                "attendanceDate": correction_date.isoformat(),
                "correctClockIn": instant(correction_date, 4, 5).isoformat(),
                "correctClockOut": instant(correction_date, 13, 5).isoformat(),
                "reason": f"{PREFIX} corrected punches",
            }
        )

        async def idempotent_submit(fingerprint: str) -> IdempotentResponse:
            principal = principals[EMPLOYEE]

            async def invoke(connection: AsyncConnection) -> IdempotentResponse:
                service = AttendanceExceptionService(
                    SqlAttendanceExceptionRepository(connection), codec
                )

                async def mutation() -> IdempotentResponse:
                    item = await service.submit(principal, submit_body)
                    return IdempotentResponse(
                        status=201,
                        body={"data": {"id": str(item.id)}},
                        location=f"/api/v1/attendance/regularisations/{item.id}",
                        resource_kind="regularisation_request",
                        resource_id=item.id,
                    )

                return await IdempotencyCoordinator(
                    IdempotencyRepository(connection)
                ).execute(
                    principal=principal,
                    command=IdempotencyCommand(
                        key=idempotency_key,
                        operation_id="submit_attendance_regularisation",
                        method="POST",
                        route_parameters={},
                        fingerprint=fingerprint,
                        branch_id=BRANCH_ID,
                    ),
                    authorize_replay=lambda kind, resource_id: service.authorize_replay(
                        principal, kind, resource_id
                    ),
                    mutation=mutation,
                )

            return await executor.execute(
                claims=claims(EMPLOYEE), principal=principal, operation=invoke
            )

        submitted = await idempotent_submit("a" * 64)
        replayed = await idempotent_submit("a" * 64)
        assert submitted.resource_id == replayed.resource_id and replayed.replayed
        await expect_code("idempotency_conflict", idempotent_submit("b" * 64))
        request_id = submitted.resource_id
        assert request_id is not None

        personal, cursor = await run(
            EMPLOYEE,
            lambda service, principal: service.personal(
                principal,
                RegularisationListQuery(None, None, None, None, 1, None),
            ),
        )
        assert personal and personal[0].employee_id == EMPLOYEE_ID
        if cursor is not None:
            second_page, _ = await run(
                EMPLOYEE,
                lambda service, principal: service.personal(
                    principal,
                    RegularisationListQuery(None, None, None, None, 1, cursor),
                ),
            )
            assert all(item.id != personal[0].id for item in second_page)
        await expect_code(
            "operation_not_permitted",
            run(
                MANAGER,
                lambda service, principal: service.queue(
                    principal,
                    BRANCH_ID,
                    RegularisationListQuery(None, "Pending", None, None, 50, None),
                ),
            ),
        )
        other_queue, _ = await run(
            ADMIN,
            lambda service, principal: service.queue(
                principal,
                OTHER_BRANCH_ID,
                RegularisationListQuery(None, "Pending", None, None, 50, None),
            ),
            branch_id=OTHER_BRANCH_ID,
        )
        assert not other_queue

        decision = RegularisationDecisionRequest.model_validate({"expectedVersion": 1})
        outcomes = await asyncio.gather(
            run(
                ADMIN,
                lambda service, principal: service.decide(
                    principal, BRANCH_ID, request_id, "approve", decision
                ),
                branch_id=BRANCH_ID,
            ),
            run(
                ADMIN,
                lambda service, principal: service.decide(
                    principal, BRANCH_ID, request_id, "approve", decision
                ),
                branch_id=BRANCH_ID,
            ),
            return_exceptions=True,
        )
        winners = [item for item in outcomes if not isinstance(item, Exception)]
        conflicts = [
            item
            for item in outcomes
            if isinstance(item, ServiceExecutionError) and item.code == "state_conflict"
        ]
        assert len(winners) == len(conflicts) == 1, tuple(repr(item) for item in outcomes)
        assert winners[0].status == "Approved" and winners[0].version == 2

        with migration_engine.connect() as connection:
            approval = (
                connection.execute(
                    text(
                        "SELECT count(*) FILTER (WHERE is_superseded),"
                        "count(*) FILTER (WHERE NOT is_superseded),"
                        "count(*) FILTER (WHERE method='MANUAL') "
                        "FROM public.clock_events WHERE employee_id=:employee "
                        "AND event_time >= :start AND event_time < :end"
                    ),
                    {
                        "employee": EMPLOYEE_ID,
                        "start": instant(correction_date, 0),
                        "end": instant(correction_date + timedelta(days=1), 0),
                    },
                )
            ).one()
            assert approval == (2, 2, 2), approval
            saved = connection.execute(
                text(
                    "SELECT clock_in_time,clock_out_time,calculation_version "
                    "FROM public.attendance_records WHERE id=:id"
                ),
                {"id": corrected_record.id},
            ).one()
            assert saved.clock_in_time == instant(correction_date, 4, 5)
            assert saved.clock_out_time == instant(correction_date, 13, 5)
            assert saved.calculation_version == corrected_record.calculation_version + 1
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM public.attendance_audit_log "
                    "WHERE action='REGULARISATION_APPROVED' AND attendance_date=:day"
                ),
                {"day": correction_date},
            ) == 1

        unauthorised = await run(
            ADMIN,
            lambda service, principal: service.resolve_absence(
                principal,
                BRANCH_ID,
                absence_record.id,
                AbsenceResolutionRequest.model_validate(
                    {
                        "expectedCalculationVersion": absence_record.calculation_version,
                        "resolutionType": "UNAUTHORISED",
                        "reason": f"{PREFIX} unauthorised",
                    }
                ),
            ),
            branch_id=BRANCH_ID,
        )
        assert unauthorised.status == "UNEXPLAINED_ABSENCE"
        assert unauthorised.absence_deduction > 0

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.clock_events"
                    "(company_id,branch_id,employee_id,event_type,event_time,method,notes) VALUES "
                    "(:company,:branch,:employee,'CLOCK_IN',:clock_in,'WEB',:note),"
                    "(:company,:branch,:employee,'CLOCK_OUT',:clock_out,'WEB',:note)"
                ),
                {
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": EMPLOYEE_ID,
                    "clock_in": instant(wfh_date, 4),
                    "clock_out": instant(wfh_date, 13),
                    "note": f"{PREFIX} wfh evidence",
                },
            )
        wfh = await run(
            ADMIN,
            lambda service, principal: service.resolve_absence(
                principal,
                BRANCH_ID,
                wfh_record.id,
                AbsenceResolutionRequest.model_validate(
                    {
                        "expectedCalculationVersion": wfh_record.calculation_version,
                        "resolutionType": "WFH",
                        "reason": f"{PREFIX} remote work confirmed",
                    }
                ),
            ),
            branch_id=BRANCH_ID,
        )
        assert wfh.status == "PRESENT_REMOTE" and wfh.absence_deduction == 0

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.leave_requests"
                    "(id,company_id,branch_id,employee_id,leave_type_id,start_date,end_date,"
                    "days_requested,status,reason,approved_by_app_user_id,approved_at) "
                    "SELECT :id,:company,:branch,:employee,id,:day,:day,1,'Approved',:reason,"
                    ":actor,now() FROM public.leave_types "
                    "WHERE company_id=:company AND branch_id=:branch AND code='ANNUAL'"
                ),
                {
                    "id": dynamic_leave_id,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": EMPLOYEE_ID,
                    "day": leave_date,
                    "reason": f"{PREFIX} approved leave",
                    "actor": seed.ADMIN_APP_USER[seed.HORIZON],
                },
            )
        linked = await run(
            ADMIN,
            lambda service, principal: service.resolve_absence(
                principal,
                BRANCH_ID,
                leave_record.id,
                AbsenceResolutionRequest.model_validate(
                    {
                        "expectedCalculationVersion": leave_record.calculation_version,
                        "resolutionType": "LEAVE_LINKED",
                        "reason": f"{PREFIX} linked approved leave",
                    }
                ),
            ),
            branch_id=BRANCH_ID,
        )
        assert linked.status == "ON_LEAVE" and linked.absence_deduction == 0

        overtime = await run(
            ADMIN,
            lambda service, principal: service.approve_overtime(
                principal,
                BRANCH_ID,
                overtime_record.id,
                OvertimeApprovalRequest.model_validate(
                    {"expectedCalculationVersion": overtime_record.calculation_version}
                ),
            ),
            branch_id=BRANCH_ID,
        )
        assert overtime.overtime_approved
        assert overtime.overtime_approval_source_digest is not None
        assert overtime.overtime_approved_at is not None
        await expect_code(
            "state_conflict",
            run(
                ADMIN,
                lambda service, principal: service.approve_overtime(
                    principal,
                    BRANCH_ID,
                    overtime_record.id,
                    OvertimeApprovalRequest.model_validate(
                        {"expectedCalculationVersion": overtime_record.calculation_version}
                    ),
                ),
                branch_id=BRANCH_ID,
            ),
        )

        manager_request = await run(
            MANAGER,
            lambda service, principal: service.submit(
                principal,
                RegularisationSubmitRequest.model_validate(
                    {
                        "attendanceDate": correction_date.isoformat(),
                        "correctClockIn": instant(correction_date, 4).isoformat(),
                        "correctClockOut": instant(correction_date, 13).isoformat(),
                        "reason": f"{PREFIX} manager self request",
                    }
                ),
            ),
        )
        rejected = await run(
            ADMIN,
            lambda service, principal: service.decide(
                principal,
                BRANCH_ID,
                manager_request.id,
                "reject",
                RegularisationDecisionRequest.model_validate(
                    {"expectedVersion": 1, "rejectionReason": "Evidence does not match"}
                ),
            ),
            branch_id=BRANCH_ID,
        )
        assert rejected.status == "Rejected" and rejected.version == 2

        forced_request = await run(
            EMPLOYEE,
            lambda service, principal: service.submit(
                principal,
                RegularisationSubmitRequest.model_validate(
                    {
                        "attendanceDate": closed_date.isoformat(),
                        "correctClockIn": instant(closed_date, 4, 10).isoformat(),
                        "correctClockOut": instant(closed_date, 13, 10).isoformat(),
                        "reason": f"{PREFIX} forced rollback",
                    }
                ),
            ),
        )
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE FUNCTION public.phase10e_verify_reject_audit() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced audit failure'; END $$"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_phase10e_verify_reject_audit BEFORE INSERT "
                    "ON public.attendance_audit_log FOR EACH ROW "
                    "EXECUTE FUNCTION public.phase10e_verify_reject_audit()"
                )
            )
        try:
            try:
                await run(
                    ADMIN,
                    lambda service, principal: service.decide(
                        principal,
                        BRANCH_ID,
                        forced_request.id,
                        "reject",
                        RegularisationDecisionRequest.model_validate(
                            {"expectedVersion": 1, "rejectionReason": "Forced rollback"}
                        ),
                    ),
                    branch_id=BRANCH_ID,
                )
            except DBAPIError:
                pass
            else:
                raise AssertionError("forced audit failure did not abort the decision")
        finally:
            with migration_engine.begin() as connection:
                connection.execute(
                    text(
                        "DROP TRIGGER IF EXISTS trg_phase10e_verify_reject_audit "
                        "ON public.attendance_audit_log"
                    )
                )
                connection.execute(
                    text("DROP FUNCTION IF EXISTS public.phase10e_verify_reject_audit()")
                )
        with migration_engine.connect() as connection:
            state = connection.execute(
                text(
                    "SELECT status,version FROM public.regularisation_requests WHERE id=:id"
                ),
                {"id": forced_request.id},
            ).one()
            assert state == ("Pending", 1)

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.attendance_periods"
                    "(company_id,branch_id,period,status,closed_by_app_user_id,closed_at) "
                    "VALUES (:company,:branch,:period,'closed',:actor,now()) "
                    "ON CONFLICT (branch_id,period) DO UPDATE SET status='closed',"
                    "closed_by_app_user_id=EXCLUDED.closed_by_app_user_id,"
                    "closed_at=EXCLUDED.closed_at"
                ),
                {
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "period": closed_date.strftime("%Y-%m"),
                    "actor": seed.ADMIN_APP_USER[seed.HORIZON],
                },
            )
        await expect_code(
            "state_conflict",
            run(
                ADMIN,
                lambda service, principal: service.decide(
                    principal,
                    BRANCH_ID,
                    forced_request.id,
                    "approve",
                    RegularisationDecisionRequest.model_validate({"expectedVersion": 1}),
                ),
                branch_id=BRANCH_ID,
            ),
        )

        audit, audit_cursor = await run(
            ADMIN,
            lambda service, principal: service.audit(
                principal,
                BRANCH_ID,
                AttendanceAuditListQuery(None, None, None, None, 2, None),
            ),
            branch_id=BRANCH_ID,
        )
        assert len(audit) == 2 and audit_cursor is not None
        assert {item.action for item in audit} <= {
            "REGULARISATION_APPROVED",
            "REGULARISATION_REJECTED",
            "ABSENCE_RESOLVED",
            "OVERTIME_APPROVED",
        }
        with migration_engine.connect() as connection:
            audit_id = connection.scalar(
                text(
                    "SELECT id FROM public.attendance_audit_log "
                    "WHERE reason LIKE :prefix ORDER BY id LIMIT 1"
                ),
                {"prefix": f"{PREFIX}%"},
            )

        async def attempt_audit_update(connection: AsyncConnection) -> int:
            result = await connection.execute(
                text("UPDATE public.attendance_audit_log SET reason='tampered' WHERE id=:id"),
                {"id": audit_id},
            )
            return result.rowcount

        try:
            changed = await executor.execute(
                claims=claims(ADMIN),
                principal=principals[ADMIN],
                selected_admin_branch_id=BRANCH_ID,
                operation=attempt_audit_update,
            )
        except DBAPIError:
            pass
        else:
            assert changed == 0
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "DROP TRIGGER IF EXISTS trg_phase10e_verify_reject_audit "
                    "ON public.attendance_audit_log"
                )
            )
            connection.execute(
                text("DROP FUNCTION IF EXISTS public.phase10e_verify_reject_audit()")
            )
            connection.execute(
                text(
                    "DELETE FROM public.attendance_audit_log "
                    "WHERE attendance_date=ANY(:dates)"
                ),
                {"dates": dynamic_dates},
            )
            connection.execute(
                text(
                    "DELETE FROM public.idempotency_records WHERE idempotency_key=:key"
                ),
                {"key": idempotency_key},
            )
            connection.execute(
                text(
                    "DELETE FROM public.clock_events WHERE employee_id=:employee "
                    "AND (event_time AT TIME ZONE 'UTC')::date=ANY(:dates)"
                ),
                {"employee": EMPLOYEE_ID, "dates": dynamic_dates},
            )
            connection.execute(
                text("DELETE FROM public.regularisation_requests WHERE reason LIKE :prefix"),
                {"prefix": f"{PREFIX}%"},
            )
            connection.execute(
                text(
                    "DELETE FROM public.attendance_records "
                    "WHERE employee_id=:employee AND date=ANY(:dates)"
                ),
                {"employee": EMPLOYEE_ID, "dates": dynamic_dates},
            )
            connection.execute(
                text("DELETE FROM public.leave_requests WHERE id=:id"),
                {"id": dynamic_leave_id},
            )
            connection.execute(
                text(
                    "DELETE FROM public.attendance_periods "
                    "WHERE company_id=:company AND branch_id=:branch AND period=:period"
                ),
                {
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "period": closed_date.strftime("%Y-%m"),
                },
            )
            clean(connection, rows)
        migration_engine.dispose()

    print("Phase 10E database exception and isolation verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
