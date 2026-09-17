#!/usr/bin/env python3
"""Exercise Phase 8E request transactions through the runtime database role."""

from __future__ import annotations

import asyncio
import os
import uuid
from decimal import Decimal
from typing import cast

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import DataResponse
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.leave_request import LeaveRequestRepository
from app.schemas.leave_balance import LeaveRequestResponse
from app.schemas.leave_request import LeaveSubmissionRequest
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import (
    IdempotencyCommand,
    IdempotencyCoordinator,
    IdempotentResponse,
)
from app.services.leave_attachment import ClaimedCleanup, LeaveAttachmentService
from app.services.leave_request import LeaveRequestService

BRANCH_ID = seed.BRANCH_DXB
RAVI = "ravi.employee@horizon.test"
MARIA = "maria.employee@horizon.test"
ADMIN = "hr.admin@horizon.test"
RAVI_EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
ANNUAL_BALANCE_ID = uuid.UUID("8e000000-0000-4000-8000-000000000001")
PATERNITY_BALANCE_ID = uuid.UUID("8e000000-0000-4000-8000-000000000002")
ATTACHMENT_ID = uuid.UUID("8e000000-0000-4000-8000-000000000003")


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


def request(type_id: uuid.UUID, start: str, end: str, **changes: object) -> LeaveSubmissionRequest:
    values: dict[str, object] = {
        "leaveTypeId": str(type_id),
        "startDate": start,
        "endDate": end,
        "isHalfDay": False,
        "halfDayPeriod": None,
        "reason": "Phase 8E synthetic request",
        "attachmentId": None,
        "relationship": None,
        "deceasedName": None,
        "dateOfDeath": None,
        "childBirthDate": None,
        "childName": None,
        "expectedDueDate": None,
        "institutionName": None,
        "examDates": None,
        "substituteEmployeeId": None,
    }
    values.update(changes)
    return LeaveSubmissionRequest.model_validate(values)


async def expect_code(code: str, operation: object) -> None:
    try:
        await operation  # type: ignore[misc]
    except ServiceExecutionError as error:
        assert error.code == code
        return
    raise AssertionError(f"expected {code}")


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    rows = build_rows()
    with migration_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM public.audit_events WHERE entity_id=:id"), {"id": ATTACHMENT_ID}
        )
        connection.execute(
            text("DELETE FROM public.storage_operations WHERE entity_id=:id"),
            {"id": ATTACHMENT_ID},
        )
        connection.execute(
            text("DELETE FROM public.leave_attachments WHERE id=:id"), {"id": ATTACHMENT_ID}
        )
        stale_request_ids = list(
            connection.execute(
                text(
                    "SELECT id FROM public.leave_requests WHERE reason='Phase 8E synthetic request'"
                )
            ).scalars()
        )
        if stale_request_ids:
            connection.execute(
                text("DELETE FROM public.audit_events WHERE entity_id=ANY(:ids)"),
                {"ids": stale_request_ids},
            )
            connection.execute(
                text("DELETE FROM public.leave_audit_log WHERE leave_request_id=ANY(:ids)"),
                {"ids": stale_request_ids},
            )
            connection.execute(
                text("DELETE FROM public.leave_requests WHERE id=ANY(:ids)"),
                {"ids": stale_request_ids},
            )
        connection.execute(
            text("DELETE FROM public.leave_balances WHERE id IN (:annual,:paternity)"),
            {"annual": ANNUAL_BALANCE_ID, "paternity": PATERNITY_BALANCE_ID},
        )
        connection.execute(
            text("DELETE FROM public.leave_types WHERE id=:id"),
            {"id": seed.derive("leave_types", seed.HORIZON, "dubai", "none", "paternity")},
        )
        apply_rows(connection, rows)
        validate(connection, rows)
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "d7f1b3c5e9a2"
        )
        type_rows = dict(
            connection.execute(
                text(
                    "SELECT code,id FROM public.leave_types "
                    "WHERE branch_id=:branch_id AND code IN ('ANNUAL','PATERNITY')"
                ),
                {"branch_id": BRANCH_ID},
            ).all()
        )
        annual_type_id = type_rows["ANNUAL"]
        paternity_type_id = type_rows["PATERNITY"]
        connection.execute(
            text(
                "INSERT INTO public.leave_balances("
                "id,company_id,branch_id,employee_id,leave_type_id,leave_year,"
                "entitled_days,accrued_days,remaining_days) VALUES "
                "(:annual,:company,:branch,:employee,:annual_type,2026,30,30,30),"
                "(:paternity,:company,:branch,:employee,:paternity_type,2026,5,5,5)"
            ),
            {
                "annual": ANNUAL_BALANCE_ID,
                "paternity": PATERNITY_BALANCE_ID,
                "company": seed.COMPANY_ID[seed.HORIZON],
                "branch": BRANCH_ID,
                "employee": RAVI_EMPLOYEE_ID,
                "annual_type": annual_type_id,
                "paternity_type": paternity_type_id,
            },
        )
        connection.execute(
            text("UPDATE public.leave_types SET auto_approve=true WHERE id=:id"),
            {"id": paternity_type_id},
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
        for subject in (RAVI, MARIA, ADMIN)
    }

    async def run(subject: str, operation: object, *, admin: bool = False) -> object:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> object:
            return await operation(LeaveRequestService(connection), principal)  # type: ignore[operator]

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID if admin else None,
            operation=invoke,
        )

    async def run_idempotent_submit(
        subject: str,
        submission: LeaveSubmissionRequest,
        *,
        employee_id: uuid.UUID,
        admin: bool,
        key: uuid.UUID,
    ) -> IdempotentResponse:
        principal = principals[subject]
        operation_id = "submit_admin_leave_request" if admin else "submit_employee_leave_request"
        body = cast(dict[str, object], submission.model_dump(mode="json", by_alias=True))
        if admin:
            body = {"employeeId": str(employee_id), **body}
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
                body=body,
            ),
            branch_id=BRANCH_ID,
        )

        async def invoke(connection: AsyncConnection) -> IdempotentResponse:
            service = LeaveRequestService(connection)

            async def mutation() -> IdempotentResponse:
                result = await service.submit(
                    principal,
                    submission,
                    employee_id=employee_id,
                    selected_branch_id=BRANCH_ID if admin else None,
                )
                response_body = cast(
                    dict[str, object],
                    DataResponse(data=result).model_dump(mode="json", by_alias=True),
                )
                return IdempotentResponse(
                    status=201,
                    body=response_body,
                    location=f"/api/v1/leave/requests/{result.id}",
                    resource_kind="leave_request",
                    resource_id=result.id,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, BRANCH_ID, kind, resource_id
                ),
                mutation=mutation,
            )

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID if admin else None,
            operation=invoke,
        )

    async def run_idempotent_cancel(
        subject: str,
        request_id: uuid.UUID,
        *,
        admin: bool,
        key: uuid.UUID,
    ) -> tuple[IdempotentResponse, object | None]:
        principal = principals[subject]
        operation_id = "cancel_admin_leave_request" if admin else "cancel_employee_leave_request"
        route_parameters: dict[str, object] = {"requestId": str(request_id)}
        command = IdempotencyCommand(
            key=key,
            operation_id=operation_id,
            method="POST",
            route_parameters=route_parameters,
            fingerprint=request_fingerprint(
                operation_id=operation_id,
                method="POST",
                route_parameters=route_parameters,
                effective_query_parameters={},
                body={},
            ),
            branch_id=BRANCH_ID,
        )

        async def invoke(
            connection: AsyncConnection,
        ) -> tuple[IdempotentResponse, object | None]:
            service = LeaveRequestService(connection)
            cleanup_claim: object | None = None

            async def mutation() -> IdempotentResponse:
                nonlocal cleanup_claim
                result, cleanup_claim = await service.cancel_with_cleanup(
                    principal,
                    request_id,
                    selected_branch_id=BRANCH_ID if admin else None,
                )
                response_body = cast(
                    dict[str, object],
                    DataResponse(data=result).model_dump(mode="json", by_alias=True),
                )
                return IdempotentResponse(
                    status=200,
                    body=response_body,
                    location=None,
                    resource_kind="leave_request",
                    resource_id=result.id,
                )

            outcome = await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, BRANCH_ID, kind, resource_id
                ),
                mutation=mutation,
            )
            return outcome, cleanup_claim

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID if admin else None,
            operation=invoke,
        )

    async def probe(service: LeaveRequestService, principal: object) -> tuple[bool, bool, bool]:
        repository = LeaveRequestRepository(service.connection)
        return (
            await repository.lock_settings(seed.COMPANY_ID[seed.HORIZON], BRANCH_ID) is not None,
            await repository.lock_employee(
                seed.COMPANY_ID[seed.HORIZON], BRANCH_ID, RAVI_EMPLOYEE_ID
            )
            is not None,
            await repository.lock_type(seed.COMPANY_ID[seed.HORIZON], BRANCH_ID, annual_type_id)
            is not None,
        )

    probed = await run(RAVI, probe)
    assert probed == (True, True, True), probed

    async def audit_probe(service: LeaveRequestService, principal: object) -> tuple[object, ...]:
        repository = LeaveRequestRepository(service.connection)
        savepoint = await service.connection.begin_nested()
        probe_id = await repository.insert_request(
            {
                "company_id": seed.COMPANY_ID[seed.HORIZON],
                "branch_id": BRANCH_ID,
                "employee_id": RAVI_EMPLOYEE_ID,
                "leave_type_id": annual_type_id,
                "start_date": "2026-12-20",
                "end_date": "2026-12-20",
                "days_requested": Decimal("1.00"),
                "status": "Pending",
            }
        )
        values = (
            await service.connection.execute(
                text(
                    "SELECT current_user,session_user,public.workloop_role(),"
                    "public.workloop_app_user_id(),public.workloop_company_id(),"
                    "public.workloop_branch_id(),public.workloop_employee_id(),"
                    "EXISTS(SELECT 1 FROM public.leave_requests WHERE id=:id),"
                    "EXISTS(SELECT 1 FROM public.resolve_workloop_principal() p WHERE "
                    "p.app_user_id=public.workloop_app_user_id() AND p.account_status='active' "
                    "AND p.profile_app_user_id=p.app_user_id AND p.role=public.workloop_role() "
                    "AND p.profile_company_id=public.workloop_company_id() "
                    "AND p.company_id=p.profile_company_id AND p.profile_employee_id="
                    "public.workloop_employee_id() AND p.employee_id=p.profile_employee_id "
                    "AND p.employee_company_id=p.profile_company_id "
                    "AND p.employee_branch_id=public.workloop_branch_id() AND p.employee_active "
                    "AND p.employment_status IN ('Active','Probation','On Leave') "
                    "AND p.branch_id=p.employee_branch_id "
                    "AND p.branch_company_id=p.profile_company_id)"
                ),
                {
                    "id": probe_id,
                },
            )
        ).one()
        await savepoint.rollback()
        return tuple(values)

    audit_context = await run(RAVI, audit_probe)
    assert audit_context == (
        "workloop_runtime",
        "workloop_runtime",
        "employee",
        principals[RAVI].app_user_id,
        seed.COMPANY_ID[seed.HORIZON],
        BRANCH_ID,
        RAVI_EMPLOYEE_ID,
        True,
        True,
    ), audit_context

    annual = await run(
        RAVI,
        lambda service, principal: service.submit(
            principal,
            request(annual_type_id, "2026-09-28", "2026-09-28"),
            employee_id=RAVI_EMPLOYEE_ID,
            selected_branch_id=None,
        ),
    )
    assert annual.status == "Pending" and annual.days_requested == Decimal("1.00")
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO public.leave_attachments("
                "id,company_id,branch_id,employee_id,leave_request_id,"
                "created_by_app_user_id,submission_token_digest,file_name,content_type,"
                "size_bytes,sha256,object_key,status,token_consumed_at,uploaded_at,attached_at) "
                "VALUES(:id,:company,:branch,:employee,:request,:actor,"
                "decode(repeat('11',32),'hex'),'phase-8e-cancel.pdf','application/pdf',"
                "32,repeat('a',64),'verification/phase8e/cancel-proof','attached',"
                "statement_timestamp(),statement_timestamp(),statement_timestamp())"
            ),
            {
                "id": ATTACHMENT_ID,
                "company": seed.COMPANY_ID[seed.HORIZON],
                "branch": BRANCH_ID,
                "employee": RAVI_EMPLOYEE_ID,
                "request": annual.id,
                "actor": principals[RAVI].app_user_id,
            },
        )
    await expect_code(
        "resource_not_found",
        run(
            MARIA,
            lambda service, principal: service.cancel(
                principal, annual.id, selected_branch_id=None
            ),
        ),
    )
    annual_cancelled, annual_cleanup_value = await run_idempotent_cancel(
        RAVI,
        annual.id,
        admin=False,
        key=uuid.uuid4(),
    )
    assert annual_cancelled.body is not None
    assert cast(dict[str, object], annual_cancelled.body["data"])["status"] == "Cancelled"
    annual_cleanup = cast(ClaimedCleanup | None, annual_cleanup_value)
    assert annual_cleanup is not None and annual_cleanup.attachment_id == ATTACHMENT_ID

    async def complete_cleanup(service: LeaveRequestService, principal: object) -> None:
        attachment_service = LeaveAttachmentService(
            service.connection, object_key_hmac_key=b"8" * 32
        )
        await attachment_service.complete_cleanup(annual_cleanup)

    await run(
        RAVI,
        complete_cleanup,
    )
    with migration_engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT concat(attachment.status,'|',operation.status) "
                "FROM public.leave_attachments AS attachment "
                "JOIN public.storage_operations AS operation ON operation.entity_id=attachment.id "
                "WHERE attachment.id=:id"
            ),
            {"id": ATTACHMENT_ID},
        ).scalar_one() == ("removed|succeeded")

    self_auto = await run(
        RAVI,
        lambda service, principal: service.submit(
            principal,
            request(
                paternity_type_id,
                "2026-09-29",
                "2026-09-29",
                childBirthDate="2026-09-15",
            ),
            employee_id=RAVI_EMPLOYEE_ID,
            selected_branch_id=None,
        ),
    )
    assert self_auto.status == "Approved"
    assert self_auto.approval_comment == "Auto-approved by leave type policy"
    self_auto_cancelled = await run(
        ADMIN,
        lambda service, principal: service.cancel(
            principal, self_auto.id, selected_branch_id=BRANCH_ID
        ),
        admin=True,
    )
    assert self_auto_cancelled.status == "Cancelled"

    admin_submission = request(
        paternity_type_id,
        "2026-09-30",
        "2026-09-30",
        childBirthDate="2026-09-15",
    )
    admin_key = uuid.uuid4()
    admin_outcome = await run_idempotent_submit(
        ADMIN,
        admin_submission,
        employee_id=RAVI_EMPLOYEE_ID,
        admin=True,
        key=admin_key,
    )
    assert admin_outcome.body is not None
    admin_auto_data = cast(dict[str, object], admin_outcome.body["data"])
    admin_auto_id = uuid.UUID(cast(str, admin_auto_data["id"]))
    assert admin_auto_data["status"] == "Approved"
    replayed = await run_idempotent_submit(
        ADMIN,
        admin_submission,
        employee_id=RAVI_EMPLOYEE_ID,
        admin=True,
        key=admin_key,
    )
    assert replayed.replayed and replayed.body == admin_outcome.body
    await expect_code(
        "idempotency_conflict",
        run_idempotent_submit(
            ADMIN,
            request(
                paternity_type_id,
                "2026-10-02",
                "2026-10-02",
                childBirthDate="2026-09-15",
            ),
            employee_id=RAVI_EMPLOYEE_ID,
            admin=True,
            key=admin_key,
        ),
    )
    admin_cancelled, admin_cleanup = await run_idempotent_cancel(
        ADMIN,
        admin_auto_id,
        admin=True,
        key=uuid.uuid4(),
    )
    assert admin_cancelled.body is not None
    assert cast(dict[str, object], admin_cancelled.body["data"])["status"] == "Cancelled"
    assert admin_cleanup is None

    race = await asyncio.gather(
        run(
            RAVI,
            lambda service, principal: service.submit(
                principal,
                request(annual_type_id, "2026-10-01", "2026-10-01"),
                employee_id=RAVI_EMPLOYEE_ID,
                selected_branch_id=None,
            ),
        ),
        run(
            RAVI,
            lambda service, principal: service.submit(
                principal,
                request(
                    paternity_type_id,
                    "2026-10-01",
                    "2026-10-01",
                    childBirthDate="2026-09-15",
                ),
                employee_id=RAVI_EMPLOYEE_ID,
                selected_branch_id=None,
            ),
        ),
        return_exceptions=True,
    )
    race_successes = [outcome for outcome in race if not isinstance(outcome, BaseException)]
    race_failures = [outcome for outcome in race if isinstance(outcome, BaseException)]
    assert len(race_successes) == len(race_failures) == 1
    assert isinstance(race_failures[0], ServiceExecutionError)
    assert race_failures[0].code == "state_conflict"
    race_request = race_successes[0]
    cancel_subject = ADMIN if race_request.status == "Approved" else RAVI  # type: ignore[attr-defined]
    cancel_as_admin = cancel_subject == ADMIN
    repeated_cancel = await asyncio.gather(
        run(
            cancel_subject,
            lambda service, principal: service.cancel(
                principal,
                race_request.id,  # type: ignore[attr-defined]
                selected_branch_id=BRANCH_ID if cancel_as_admin else None,
            ),
            admin=cancel_as_admin,
        ),
        run(
            cancel_subject,
            lambda service, principal: service.cancel(
                principal,
                race_request.id,  # type: ignore[attr-defined]
                selected_branch_id=BRANCH_ID if cancel_as_admin else None,
            ),
            admin=cancel_as_admin,
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(outcome, BaseException) for outcome in repeated_cancel) == 1
    cancellation_failure = next(
        outcome for outcome in repeated_cancel if isinstance(outcome, BaseException)
    )
    assert isinstance(cancellation_failure, ServiceExecutionError)
    assert cancellation_failure.code in {"state_conflict", "resource_not_found"}

    request_ids = [annual.id, self_auto.id, admin_auto_id, race_request.id]  # type: ignore[attr-defined]
    with migration_engine.begin() as connection:
        protected = connection.execute(
            text(
                "SELECT action,actor_kind,system_actor_key,initiated_by_app_user_id "
                "FROM public.audit_events WHERE entity_id=ANY(:ids) ORDER BY occurred_at,id"
            ),
            {"ids": request_ids},
        ).all()
        assert sum(event.action == "leave_request_submitted" for event in protected) == 4
        expected_automatic = 2 + int(race_request.status == "Approved")  # type: ignore[attr-defined]
        assert sum(event.action == "leave_request_auto_approved" for event in protected) == (
            expected_automatic
        )
        assert sum(event.action == "leave_request_cancelled" for event in protected) == 4
        automatic = [event for event in protected if event.action == "leave_request_auto_approved"]
        assert all(
            event.actor_kind == "system_rule"
            and event.system_actor_key == "leave_auto_approval"
            and event.initiated_by_app_user_id is not None
            for event in automatic
        )
        balances = connection.execute(
            text(
                "SELECT pending_days,used_days,remaining_days FROM public.leave_balances "
                "WHERE id IN (:annual,:paternity) ORDER BY id"
            ),
            {"annual": ANNUAL_BALANCE_ID, "paternity": PATERNITY_BALANCE_ID},
        ).all()
        assert balances == [
            (Decimal("0.00"), Decimal("0.00"), Decimal("30.00")),
            (Decimal("0.00"), Decimal("0.00"), Decimal("5.00")),
        ]
        connection.execute(
            text("DELETE FROM public.audit_events WHERE company_id=:company"),
            {"company": seed.COMPANY_ID[seed.HORIZON]},
        )
        connection.execute(
            text("DELETE FROM public.storage_operations WHERE entity_id=:id"),
            {"id": ATTACHMENT_ID},
        )
        connection.execute(
            text("DELETE FROM public.leave_attachments WHERE id=:id"), {"id": ATTACHMENT_ID}
        )
        connection.execute(
            text("DELETE FROM public.leave_audit_log WHERE leave_request_id=ANY(:ids)"),
            {"ids": request_ids},
        )
        connection.execute(
            text("DELETE FROM public.leave_requests WHERE id=ANY(:ids)"), {"ids": request_ids}
        )
        connection.execute(
            text("DELETE FROM public.leave_balances WHERE id IN (:annual,:paternity)"),
            {"annual": ANNUAL_BALANCE_ID, "paternity": PATERNITY_BALANCE_ID},
        )
        connection.execute(
            text("DELETE FROM public.leave_types WHERE id=:id"), {"id": paternity_type_id}
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE company_id=:company"),
            {"company": seed.COMPANY_ID[seed.HORIZON]},
        )
        apply_rows(connection, rows)

    await runtime_engine.dispose()
    with migration_engine.begin() as connection:
        clean(connection, rows)
    migration_engine.dispose()
    print("Phase 8E request database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
