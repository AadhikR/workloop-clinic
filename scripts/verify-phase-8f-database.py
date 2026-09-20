#!/usr/bin/env python3
"""Exercise Phase 8F approval transactions through the runtime database role."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

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
from app.schemas.leave_approval import (
    LeaveApprovalDelegateCreate,
    LeaveApprovalDelegateUpdate,
    LeaveDecisionRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.leave_approval import ApprovalQueueQuery, LeaveApprovalService

COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
RAVI = "ravi.employee@horizon.test"
MARIA = "maria.employee@horizon.test"
AISHA_ID = uuid.UUID("21000000-0000-4000-8000-000000000001")
RAVI_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
MARIA_ID = uuid.UUID("21000000-0000-4000-8000-000000000003")
TYPE_ID = uuid.UUID("8f000000-0000-4000-8000-000000000010")
REQUEST_IDS = [uuid.UUID(f"8f000000-0000-4000-8000-{value:012d}") for value in range(101, 106)]
BALANCE_IDS = [uuid.UUID(f"8f000000-0000-4000-8000-{value:012d}") for value in range(201, 204)]
IDEMPOTENCY_KEY = uuid.UUID("8f000000-0000-4000-8000-000000000301")


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


def decision(action: str, updated_at: datetime, reason: str = "") -> LeaveDecisionRequest:
    return LeaveDecisionRequest.model_validate(
        {"decision": action, "reason": reason, "expectedUpdatedAt": updated_at}
    )


async def expect_code(code: str, operation: object) -> None:
    try:
        await operation  # type: ignore[misc]
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
            "a6c8e0f2b4d7"
        )
        business_date = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        assert isinstance(business_date, date)
        connection.execute(
            text("DELETE FROM public.audit_events WHERE entity_id=ANY(:ids) OR entity_id=:type_id"),
            {"ids": REQUEST_IDS, "type_id": TYPE_ID},
        )
        connection.execute(
            text("DELETE FROM public.leave_audit_log WHERE leave_request_id=ANY(:ids)"),
            {"ids": REQUEST_IDS},
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE idempotency_key=:key"),
            {"key": IDEMPOTENCY_KEY},
        )
        connection.execute(
            text("DELETE FROM public.leave_requests WHERE id=ANY(:ids)"), {"ids": REQUEST_IDS}
        )
        connection.execute(
            text("DELETE FROM public.leave_balances WHERE id=ANY(:ids)"), {"ids": BALANCE_IDS}
        )
        connection.execute(text("DELETE FROM public.leave_types WHERE id=:id"), {"id": TYPE_ID})
        connection.execute(
            text(
                "DELETE FROM public.audit_events WHERE action LIKE 'leave_delegation_%' "
                "AND entity_id IN (SELECT id FROM public.leave_approval_delegates WHERE "
                "approver_employee_id=:approver AND delegate_employee_id=:delegate)"
            ),
            {"approver": AISHA_ID, "delegate": RAVI_ID},
        )
        connection.execute(
            text(
                "DELETE FROM public.leave_approval_delegates WHERE "
                "approver_employee_id=:approver AND delegate_employee_id=:delegate"
            ),
            {"approver": AISHA_ID, "delegate": RAVI_ID},
        )
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "INSERT INTO public.leave_types("
                "id,company_id,branch_id,code,name,is_active,annual_entitlement_days) "
                "VALUES(:id,:company,:branch,'P8F','Phase 8F synthetic',true,30)"
            ),
            {"id": TYPE_ID, "company": COMPANY_ID, "branch": BRANCH_ID},
        )
        for balance_id, employee_id in zip(BALANCE_IDS, (RAVI_ID, MARIA_ID, AISHA_ID), strict=True):
            connection.execute(
                text(
                    "INSERT INTO public.leave_balances("
                    "id,company_id,branch_id,employee_id,leave_type_id,leave_year,"
                    "entitled_days,accrued_days,pending_days,remaining_days) "
                    "VALUES(:id,:company,:branch,:employee,:type_id,2026,30,30,"
                    ":pending,30-:pending)"
                ),
                {
                    "id": balance_id,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": employee_id,
                    "type_id": TYPE_ID,
                    "pending": Decimal("4.00") if employee_id == RAVI_ID else Decimal("1.00"),
                },
            )
        request_values = [
            (REQUEST_IDS[0], RAVI_ID, 1, Decimal("1.00")),
            (REQUEST_IDS[1], MARIA_ID, 2, Decimal("1.00")),
            (REQUEST_IDS[2], RAVI_ID, 2, Decimal("1.00")),
            (REQUEST_IDS[3], RAVI_ID, 1, Decimal("1.00")),
            (REQUEST_IDS[4], RAVI_ID, 1, Decimal("1.00")),
        ]
        for offset, (request_id, employee_id, level, days) in enumerate(request_values):
            start = business_date + timedelta(days=20 + offset)
            connection.execute(
                text(
                    "INSERT INTO public.leave_requests("
                    "id,company_id,branch_id,employee_id,leave_type_id,start_date,end_date,"
                    "days_requested,status,reason,approval_level_required) "
                    "VALUES(:id,:company,:branch,:employee,:type_id,:start,:start,:days,"
                    "'Pending','Phase 8F synthetic request',:level)"
                ),
                {
                    "id": request_id,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": employee_id,
                    "type_id": TYPE_ID,
                    "start": start,
                    "days": days,
                    "level": level,
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
        for subject in (ADMIN, MANAGER, RAVI, MARIA)
    }
    codec = EmployeeCursorCodec(b"8" * 32)

    async def run(subject: str, callback: object, *, admin: bool = False) -> object:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> object:
            service = LeaveApprovalService(connection, codec)
            return await callback(service, principal)  # type: ignore[operator]

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID if admin else None,
            operation=invoke,
        )

    async def run_idempotent_manager_decision(
        request_id: uuid.UUID, body: LeaveDecisionRequest
    ) -> IdempotentResponse:
        principal = principals[MANAGER]
        operation_id = "decide_leave_as_approver"
        route_parameters: dict[str, object] = {"requestId": str(request_id)}
        body_values = body.model_dump(mode="json", by_alias=True)
        command = IdempotencyCommand(
            key=IDEMPOTENCY_KEY,
            operation_id=operation_id,
            method="POST",
            route_parameters=route_parameters,
            fingerprint=request_fingerprint(
                operation_id=operation_id,
                method="POST",
                route_parameters=route_parameters,
                effective_query_parameters={},
                body=body_values,
            ),
            branch_id=BRANCH_ID,
        )

        async def invoke(connection: AsyncConnection) -> IdempotentResponse:
            service = LeaveApprovalService(connection, codec)

            async def mutate() -> IdempotentResponse:
                result = await service.decide_staff(principal, request_id, body)
                return IdempotentResponse(
                    status=200,
                    body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
                    location=None,
                    resource_kind="leave_request",
                    resource_id=request_id,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, BRANCH_ID, kind, resource_id
                ),
                mutation=mutate,
            )

        return await executor.execute(claims=claims(MANAGER), principal=principal, operation=invoke)

    queue_query = ApprovalQueueQuery(limit=100, cursor=None)
    manager_queue = await run(
        MANAGER, lambda service, principal: service.list_staff_queue(principal, queue_query)
    )
    manager_items = manager_queue[0]  # type: ignore[index]
    assert set(REQUEST_IDS) <= {item.request.id for item in manager_items}
    assert all(
        item.visible_because == "directReport"
        for item in manager_items
        if item.request.id in REQUEST_IDS
    )

    with migration_engine.begin() as connection:
        connection.execute(
            text("UPDATE public.employees SET reporting_manager_id=NULL WHERE id=:employee"),
            {"employee": MARIA_ID},
        )
    changed_scope = await run(
        MANAGER, lambda service, principal: service.list_staff_queue(principal, queue_query)
    )
    assert REQUEST_IDS[1] not in {item.request.id for item in changed_scope[0]}  # type: ignore[index]
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE public.employees SET reporting_manager_id=:manager WHERE id=:employee"
            ),
            {"manager": AISHA_ID, "employee": MARIA_ID},
        )
    restored_scope = await run(
        MANAGER, lambda service, principal: service.list_staff_queue(principal, queue_query)
    )
    assert REQUEST_IDS[1] in {item.request.id for item in restored_scope[0]}  # type: ignore[index]

    delegation = await run(
        ADMIN,
        lambda service, principal: service.create_delegation(
            principal,
            BRANCH_ID,
            LeaveApprovalDelegateCreate(
                approver_employee_id=AISHA_ID,
                delegate_employee_id=RAVI_ID,
                from_date=business_date,
                to_date=business_date + timedelta(days=2),
            ),
        ),
        admin=True,
    )
    delegate_queue = await run(
        RAVI, lambda service, principal: service.list_staff_queue(principal, queue_query)
    )
    delegate_items = delegate_queue[0]  # type: ignore[index]
    assert [item.request.id for item in delegate_items] == [REQUEST_IDS[1]]
    assert delegate_items[0].visible_because == "activeDelegation"

    future_delegation = await run(
        ADMIN,
        lambda service, principal: service.create_delegation(
            principal,
            BRANCH_ID,
            LeaveApprovalDelegateCreate(
                approver_employee_id=AISHA_ID,
                delegate_employee_id=RAVI_ID,
                from_date=business_date + timedelta(days=10),
                to_date=business_date + timedelta(days=12),
            ),
        ),
        admin=True,
    )
    updated_future_delegation = await run(
        ADMIN,
        lambda service, principal: service.update_delegation(
            principal,
            BRANCH_ID,
            future_delegation.id,  # type: ignore[union-attr]
            LeaveApprovalDelegateUpdate(
                approver_employee_id=AISHA_ID,
                delegate_employee_id=RAVI_ID,
                from_date=business_date + timedelta(days=11),
                to_date=business_date + timedelta(days=13),
                expected_updated_at=future_delegation.updated_at,  # type: ignore[union-attr]
            ),
        ),
        admin=True,
    )
    await run(
        ADMIN,
        lambda service, principal: service.delete_delegation(
            principal,
            BRANCH_ID,
            updated_future_delegation.id,  # type: ignore[union-attr]
            updated_future_delegation.updated_at,  # type: ignore[union-attr]
        ),
        admin=True,
    )

    direct = next(item for item in manager_items if item.request.id == REQUEST_IDS[0])
    direct_decision = decision("approve", direct.request.updated_at)
    approved_outcome = await run_idempotent_manager_decision(direct.request.id, direct_decision)
    replayed_outcome = await run_idempotent_manager_decision(direct.request.id, direct_decision)
    assert approved_outcome.body is not None
    assert approved_outcome.body["data"]["status"] == "Approved"  # type: ignore[index]
    assert replayed_outcome.replayed and replayed_outcome.body == approved_outcome.body
    await expect_code(
        "idempotency_conflict",
        run_idempotent_manager_decision(
            direct.request.id,
            decision("approve", direct.request.updated_at, "Changed replay payload"),
        ),
    )

    delegated = delegate_items[0]
    manager_approved = await run(
        RAVI,
        lambda service, principal: service.decide_staff(
            principal,
            delegated.request.id,
            decision("approve", delegated.request.updated_at, "Cover arranged"),
        ),
    )
    assert manager_approved.status == "ManagerApproved"  # type: ignore[attr-defined]
    finalized = await run(
        ADMIN,
        lambda service, principal: service.decide_admin(
            principal,
            BRANCH_ID,
            manager_approved.id,  # type: ignore[attr-defined]
            decision("approve", manager_approved.updated_at),  # type: ignore[attr-defined]
        ),
        admin=True,
    )
    assert finalized.status == "Approved"  # type: ignore[attr-defined]

    refreshed_queue = await run(
        MANAGER, lambda service, principal: service.list_staff_queue(principal, queue_query)
    )
    reject_item = next(item for item in refreshed_queue[0] if item.request.id == REQUEST_IDS[2])  # type: ignore[index]
    rejected = await run(
        MANAGER,
        lambda service, principal: service.decide_staff(
            principal,
            reject_item.request.id,
            decision("reject", reject_item.request.updated_at, "Coverage unavailable"),
        ),
    )
    assert rejected.status == "ManagerRejected"  # type: ignore[attr-defined]
    await expect_code(
        "state_conflict",
        run(
            MANAGER,
            lambda service, principal: service.decide_staff(
                principal,
                reject_item.request.id,
                decision("approve", reject_item.request.updated_at),
            ),
        ),
    )

    admin_queue = await run(
        ADMIN,
        lambda service, principal: service.list_admin_queue(principal, BRANCH_ID, queue_query),
        admin=True,
    )
    admin_item = next(item for item in admin_queue[0] if item.request.id == REQUEST_IDS[3])  # type: ignore[index]
    await expect_code(
        "validation_failed",
        run(
            ADMIN,
            lambda service, principal: service.decide_admin(
                principal,
                BRANCH_ID,
                admin_item.request.id,
                decision("approve", admin_item.request.updated_at),
            ),
            admin=True,
        ),
    )
    admin_rejected = await run(
        ADMIN,
        lambda service, principal: service.decide_admin(
            principal,
            BRANCH_ID,
            admin_item.request.id,
            decision("reject", admin_item.request.updated_at, "Policy override denied"),
        ),
        admin=True,
    )
    assert admin_rejected.status == "Rejected"  # type: ignore[attr-defined]

    concurrent_item = next(item for item in admin_queue[0] if item.request.id == REQUEST_IDS[4])  # type: ignore[index]
    concurrent = await asyncio.gather(
        run(
            ADMIN,
            lambda service, principal: service.decide_admin(
                principal,
                BRANCH_ID,
                concurrent_item.request.id,
                decision("approve", concurrent_item.request.updated_at, "Urgent coverage"),
            ),
            admin=True,
        ),
        run(
            MANAGER,
            lambda service, principal: service.decide_staff(
                principal,
                concurrent_item.request.id,
                decision("reject", concurrent_item.request.updated_at, "Coverage unavailable"),
            ),
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(item, BaseException) for item in concurrent) == 1
    failure = next(item for item in concurrent if isinstance(item, BaseException))
    assert isinstance(failure, ServiceExecutionError)
    assert failure.code in {"resource_not_found", "state_conflict"}

    owner_audit = await run(
        MARIA,
        lambda service, principal: service.list_audit(principal, BRANCH_ID, REQUEST_IDS[1]),
    )
    assert [entry.action for entry in owner_audit] == ["manager_approved", "approved"]
    manager_audit = await run(
        MANAGER,
        lambda service, principal: service.list_audit(principal, BRANCH_ID, REQUEST_IDS[0]),
    )
    assert manager_audit[-1].new_status == "Approved"

    await expect_code(
        "resource_not_found",
        run(
            ADMIN,
            lambda service, principal: service.delete_delegation(
                principal,
                BRANCH_ID,
                delegation.id,  # type: ignore[union-attr]
                delegation.updated_at,  # type: ignore[union-attr]
            ),
            admin=True,
        ),
    )

    with migration_engine.begin() as connection:
        decisions = (
            connection.execute(
                text(
                    "SELECT action FROM public.audit_events WHERE entity_id=ANY(:ids) "
                    "ORDER BY occurred_at,id"
                ),
                {"ids": REQUEST_IDS},
            )
            .scalars()
            .all()
        )
        assert "leave_request_manager_approved" in decisions
        assert "leave_request_manager_rejected" in decisions
        assert "leave_request_approved" in decisions
        assert "leave_request_rejected" in decisions
        balances = connection.execute(
            text(
                "SELECT employee_id,pending_days,used_days,remaining_days "
                "FROM public.leave_balances WHERE id=ANY(:ids) ORDER BY employee_id"
            ),
            {"ids": BALANCE_IDS},
        ).all()
        assert all(
            row.pending_days >= 0 and row.used_days >= 0 and row.remaining_days >= 0
            for row in balances
        )
        connection.execute(
            text(
                "DELETE FROM public.audit_events WHERE entity_id=ANY(:ids) "
                "OR entity_id IN (:delegate,:future_delegate)"
            ),
            {
                "ids": REQUEST_IDS,
                "delegate": delegation.id,  # type: ignore[union-attr]
                "future_delegate": future_delegation.id,  # type: ignore[union-attr]
            },
        )
        connection.execute(
            text("DELETE FROM public.leave_audit_log WHERE leave_request_id=ANY(:ids)"),
            {"ids": REQUEST_IDS},
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE idempotency_key=:key"),
            {"key": IDEMPOTENCY_KEY},
        )
        connection.execute(
            text("DELETE FROM public.leave_requests WHERE id=ANY(:ids)"), {"ids": REQUEST_IDS}
        )
        connection.execute(
            text("DELETE FROM public.leave_balances WHERE id=ANY(:ids)"), {"ids": BALANCE_IDS}
        )
        connection.execute(
            text("DELETE FROM public.leave_approval_delegates WHERE id=:id"),
            {"id": delegation.id},  # type: ignore[union-attr]
        )
        connection.execute(text("DELETE FROM public.leave_types WHERE id=:id"), {"id": TYPE_ID})
    await runtime_engine.dispose()
    with migration_engine.begin() as connection:
        clean(connection, rows)
    migration_engine.dispose()
    print("Phase 8F approval database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
