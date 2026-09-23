#!/usr/bin/env python3
"""Exercise Phase 10B authority, replay, RLS, and database constraints."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from typing import Any

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import DataResponse
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.attendance_configuration import (
    AttendanceSettingsUpdateRequest,
    ShiftAssignmentCreateRequest,
    ShiftCreateRequest,
    ShiftUpdateRequest,
)
from app.services.attendance_configuration import AttendanceConfigurationService
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import (
    IdempotencyCommand,
    IdempotencyCoordinator,
    IdempotentResponse,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
EMPLOYEE = "ravi.employee@horizon.test"
COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
SETTINGS_KEY = uuid.UUID("10b00000-0000-4000-8000-000000000001")
SHIFT_KEY = uuid.UUID("10b00000-0000-4000-8000-000000000002")
ASSIGNMENT_KEY = uuid.UUID("10b00000-0000-4000-8000-000000000003")


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
            "b2d4f6a8c0e5"
        )
        apply_rows(connection, rows)
        validate(connection, rows)
        business_date = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        assert isinstance(business_date, date)

    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD")
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine,
        issuer=seed.SEED_ISSUER,
        timeout_seconds=5,
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    principals = {
        subject: await resolver.resolve(issuer=seed.SEED_ISSUER, subject=subject)
        for subject in (ADMIN, MANAGER, EMPLOYEE)
    }
    codec = EmployeeCursorCodec(b"b" * 32)
    created_ids: list[uuid.UUID] = []

    async def run_service(
        subject: str,
        callback: Callable[
            [AttendanceConfigurationService, AuthorizationPrincipal], Awaitable[Any]
        ],
        *,
        branch_id: uuid.UUID | None = None,
    ) -> Any:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(
                AttendanceConfigurationService(connection, codec),
                principal,
            )

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=branch_id if subject == ADMIN else None,
            operation=invoke,
        )

    async def run_idempotent(
        *,
        key: uuid.UUID,
        operation_id: str,
        resource_kind: str,
        body: object,
        mutation: Callable[
            [AttendanceConfigurationService, AuthorizationPrincipal], Awaitable[Any]
        ],
    ) -> IdempotentResponse:
        principal = principals[ADMIN]
        body_values = body.model_dump(mode="json", by_alias=True)
        command = IdempotencyCommand(
            key=key,
            operation_id=operation_id,
            method="POST",
            route_parameters={},
            fingerprint=request_fingerprint(
                operation_id=operation_id,
                method="POST",
                route_parameters={},
                effective_query_parameters={},
                body=body_values,
            ),
            branch_id=BRANCH_ID,
        )

        async def invoke(connection: AsyncConnection) -> IdempotentResponse:
            service = AttendanceConfigurationService(connection, codec)

            async def apply() -> IdempotentResponse:
                item = await mutation(service, principal)
                created_ids.append(item.id)
                return IdempotentResponse(
                    status=200,
                    body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                    location=None,
                    resource_kind=resource_kind,
                    resource_id=item.id,
                )

            return await IdempotencyCoordinator(
                IdempotencyRepository(connection)
            ).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, BRANCH_ID, kind, resource_id
                ),
                mutation=apply,
            )

        return await executor.execute(
            claims=claims(ADMIN),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID,
            operation=invoke,
        )

    try:
        settings = await run_service(
            ADMIN,
            lambda service, principal: service.get_settings(principal, BRANCH_ID),
            branch_id=BRANCH_ID,
        )
        assert not hasattr(settings, "biometric_api_key")
        assert settings.biometric_api_key_configured is True
        await expect_code(
            "operation_not_permitted",
            run_service(
                MANAGER,
                lambda service, principal: service.get_settings(principal, BRANCH_ID),
            ),
        )
        await expect_code(
            "operation_not_permitted",
            run_service(
                EMPLOYEE,
                lambda service, principal: service.get_settings(principal, BRANCH_ID),
            ),
        )

        settings_body = AttendanceSettingsUpdateRequest.model_validate(
            {
                "workingDays": settings.working_days,
                "weekendDays": settings.weekend_days,
                "defaultHoursPerDay": settings.default_hours_per_day,
                "lateGraceMinutes": settings.late_grace_minutes,
                "earlyDepartureGraceMinutes": settings.early_departure_grace_minutes,
                "overtimeRequiresApproval": settings.overtime_requires_approval,
                "maxDailyOvertimeHours": settings.max_daily_overtime_hours,
                "lateDeductionPolicy": settings.late_deduction_policy,
                "lateDeductionAmount": settings.late_deduction_amount,
                "wfhEnabled": not settings.wfh_enabled,
                "regularisationMaxDaysPerMonth": (
                    settings.regularisation_max_days_per_month
                ),
                "regularisationWindowDays": settings.regularisation_window_days,
                "biometricApiEnabled": False,
                "biometricApiKey": None,
                "expectedUpdatedAt": settings.updated_at,
            }
        )
        first_settings = await run_idempotent(
            key=SETTINGS_KEY,
            operation_id="verify_phase10b_settings",
            resource_kind="attendance_settings",
            body=settings_body,
            mutation=lambda service, principal: service.update_settings(
                principal, BRANCH_ID, settings_body
            ),
        )
        replayed_settings = await run_idempotent(
            key=SETTINGS_KEY,
            operation_id="verify_phase10b_settings",
            resource_kind="attendance_settings",
            body=settings_body,
            mutation=lambda service, principal: service.update_settings(
                principal, BRANCH_ID, settings_body
            ),
        )
        assert first_settings.replayed is False and replayed_settings.replayed is True
        assert "biometricApiKey" not in first_settings.body["data"]

        shift_body = ShiftCreateRequest.model_validate(
            {
                "name": "Phase 10B Verification",
                "shiftType": "fixed",
                "startTime": "07:00:00",
                "endTime": "16:00:00",
                "breakMinutes": 60,
                "expectedHours": "8.00",
                "lateGraceMinutes": 10,
                "earlyDepartureGraceMinutes": 10,
                "splitStartTime": None,
                "splitEndTime": None,
                "isOvernight": False,
                "minHoursFlexible": None,
                "color": "#123ABC",
                "code": "P10BVERIFY",
                "shiftCategory": "morning",
                "minStaff": 1,
            }
        )
        first_shift = await run_idempotent(
            key=SHIFT_KEY,
            operation_id="verify_phase10b_shift",
            resource_kind="shift",
            body=shift_body,
            mutation=lambda service, principal: service.create_shift(
                principal, BRANCH_ID, shift_body
            ),
        )
        replayed_shift = await run_idempotent(
            key=SHIFT_KEY,
            operation_id="verify_phase10b_shift",
            resource_kind="shift",
            body=shift_body,
            mutation=lambda service, principal: service.create_shift(
                principal, BRANCH_ID, shift_body
            ),
        )
        shift_id = uuid.UUID(first_shift.body["data"]["id"])
        assert first_shift.replayed is False and replayed_shift.replayed is True

        assignment_body = ShiftAssignmentCreateRequest.model_validate(
            {
                "employeeId": EMPLOYEE_ID,
                "shiftId": shift_id,
                "effectiveFrom": business_date + timedelta(days=10),
                "expectedCurrentAssignmentId": None,
                "expectedCurrentAssignmentUpdatedAt": None,
            }
        )
        first_assignment = await run_idempotent(
            key=ASSIGNMENT_KEY,
            operation_id="verify_phase10b_assignment",
            resource_kind="shift_assignment",
            body=assignment_body,
            mutation=lambda service, principal: service.assign_shift(
                principal, BRANCH_ID, assignment_body
            ),
        )
        replayed_assignment = await run_idempotent(
            key=ASSIGNMENT_KEY,
            operation_id="verify_phase10b_assignment",
            resource_kind="shift_assignment",
            body=assignment_body,
            mutation=lambda service, principal: service.assign_shift(
                principal, BRANCH_ID, assignment_body
            ),
        )
        assignment_id = uuid.UUID(first_assignment.body["data"]["id"])
        assert (
            first_assignment.replayed is False and replayed_assignment.replayed is True
        )

        await expect_code(
            "retained_shift",
            run_service(
                ADMIN,
                lambda service, principal: service.update_shift(
                    principal,
                    BRANCH_ID,
                    shift_id,
                    ShiftUpdateRequest.model_validate(
                        {
                            "expectedUpdatedAt": first_shift.body["data"]["updatedAt"],
                            "name": "Forbidden rewrite",
                        }
                    ),
                ),
                branch_id=BRANCH_ID,
            ),
        )
        await expect_code(
            "retained_shift",
            run_service(
                ADMIN,
                lambda service, principal: service.deactivate_shift(
                    principal,
                    BRANCH_ID,
                    shift_id,
                    datetime.fromisoformat(
                        first_shift.body["data"]["updatedAt"].replace("Z", "+00:00")
                    ),
                ),
                branch_id=BRANCH_ID,
            ),
        )

        async def forbidden_write(connection: AsyncConnection) -> object:
            return (
                await connection.execute(
                    text(
                        "UPDATE public.shifts SET color=color WHERE id=:id RETURNING id"
                    ),
                    {"id": shift_id},
                )
            ).one_or_none()

        for subject in (MANAGER, EMPLOYEE):
            result = await executor.execute(
                claims=claims(subject),
                principal=principals[subject],
                operation=forbidden_write,
            )
            assert result is None

        with migration_engine.begin() as connection:
            audit_counts = dict(
                connection.execute(
                    text(
                        "SELECT action,count(*) FROM public.audit_events "
                        "WHERE entity_id=ANY(:ids) GROUP BY action"
                    ),
                    {"ids": [settings.id, shift_id, assignment_id]},
                ).all()
            )
            assert audit_counts["attendance_settings_changed"] == 1
            assert audit_counts["shift_created"] == 1
            assert audit_counts["shift_assigned"] == 1

            try:
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "INSERT INTO public.shift_assignments"
                            "(id,company_id,branch_id,employee_id,shift_id,effective_from) "
                            "VALUES(:id,:company,:branch,:employee,:shift,:start)"
                        ),
                        {
                            "id": uuid.UUID("10b00000-0000-4000-8000-000000000099"),
                            "company": COMPANY_ID,
                            "branch": BRANCH_ID,
                            "employee": EMPLOYEE_ID,
                            "shift": shift_id,
                            "start": assignment_body.effective_from + timedelta(days=1),
                        },
                    )
            except IntegrityError:
                pass
            else:
                raise AssertionError("overlapping assignment was accepted")

            try:
                with connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE public.attendance_settings "
                            "SET biometric_api_enabled=true,biometric_api_key='short' "
                            "WHERE id=:id"
                        ),
                        {"id": settings.id},
                    )
            except IntegrityError:
                pass
            else:
                raise AssertionError("short enabled biometric secret was accepted")
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM public.idempotency_records "
                    "WHERE idempotency_key=ANY(:keys)"
                ),
                {"keys": [SETTINGS_KEY, SHIFT_KEY, ASSIGNMENT_KEY]},
            )
            connection.execute(
                text(
                    "DELETE FROM public.audit_events WHERE action IN "
                    "('attendance_settings_changed','shift_created','shift_changed',"
                    "'shift_deactivated','shift_assigned')"
                )
            )
            connection.execute(
                text(
                    "DELETE FROM public.shift_assignments "
                    "WHERE id=:assignment OR shift_id IN "
                    "(SELECT id FROM public.shifts WHERE code='P10BVERIFY')"
                ),
                {"assignment": uuid.UUID("10b00000-0000-4000-8000-000000000099")},
            )
            connection.execute(
                text("DELETE FROM public.shifts WHERE code='P10BVERIFY'")
            )
            clean(connection, rows)
        migration_engine.dispose()
    print("Phase 10B database authority verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
