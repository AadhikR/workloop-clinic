#!/usr/bin/env python3
"""Exercise Phase 9C advance and repayment boundaries through the runtime role."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
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
from app.schemas.advance import (
    AdminAdvanceCreateRequest,
    AdvanceCreateRequest,
    AdvanceDecisionRequest,
    AdvanceRepaymentRequest,
    AdvanceScheduleRequest,
    AdvanceVersionRequest,
)
from app.services.advances import AdvanceListQuery, AdvanceService
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
ADMIN = "hr.admin@horizon.test"
SECOND_ADMIN = "phase9c.second.admin@horizon.test"
RAVI = "ravi.employee@horizon.test"
MARIA = "maria.employee@horizon.test"
RAVI_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
MARIA_ID = uuid.UUID("21000000-0000-4000-8000-000000000003")
SECOND_ADMIN_ID = uuid.UUID("9c000000-0000-4000-8000-000000000001")
PAYROLL_RUN_ID = uuid.UUID("9c000000-0000-4000-8000-000000000002")
KEYS = [uuid.UUID(f"9c000000-0000-4000-8000-{value:012d}") for value in range(101, 151)]


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
            "d8f0a2c4e6b1"
        )
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "INSERT INTO public.app_users(id,identity_issuer,identity_subject,status) "
                "VALUES(:id,:issuer,:subject,'active')"
            ),
            {"id": SECOND_ADMIN_ID, "issuer": seed.SEED_ISSUER, "subject": SECOND_ADMIN},
        )
        connection.execute(
            text(
                "INSERT INTO public.user_profiles(app_user_id,company_id,employee_id,role) "
                "VALUES(:id,:company_id,NULL,'admin')"
            ),
            {"id": SECOND_ADMIN_ID, "company_id": COMPANY_ID},
        )
        business_date = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        assert isinstance(business_date, date)
    start_period = business_date.strftime("%Y-%m")

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
        for subject in (ADMIN, SECOND_ADMIN, RAVI, MARIA)
    }
    codec = EmployeeCursorCodec(b"9" * 32)
    generated_ids: list[uuid.UUID] = []

    async def run(subject: str, callback: object, *, branch_id: uuid.UUID | None = None) -> object:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> object:
            return await callback(AdvanceService(connection, codec), principal)  # type: ignore[operator]

        selected = branch_id if subject in {ADMIN, SECOND_ADMIN} else None
        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=selected,
            operation=invoke,
        )

    async def idempotent(
        subject: str,
        *,
        branch_id: uuid.UUID,
        key: uuid.UUID,
        operation_id: str,
        method: str,
        route_parameters: dict[str, object],
        body: object,
        callback: object,
    ) -> IdempotentResponse:
        principal = principals[subject]
        body_values = body.model_dump(mode="json", by_alias=True)  # type: ignore[attr-defined]
        command = IdempotencyCommand(
            key=key,
            operation_id=operation_id,
            method=method,
            route_parameters=route_parameters,
            fingerprint=request_fingerprint(
                operation_id=operation_id,
                method=method,
                route_parameters=route_parameters,
                effective_query_parameters={},
                body=body_values,
            ),
            branch_id=branch_id,
        )

        async def invoke(connection: AsyncConnection) -> IdempotentResponse:
            service = AdvanceService(connection, codec)

            async def mutate() -> IdempotentResponse:
                result = await callback(service, principal, key)  # type: ignore[operator]
                return IdempotentResponse(
                    status=200,
                    body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
                    location=None,
                    resource_kind="salary_advance",
                    resource_id=result.id,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, branch_id, kind, resource_id
                ),
                mutation=mutate,
            )

        selected = branch_id if subject in {ADMIN, SECOND_ADMIN} else None
        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=selected,
            operation=invoke,
        )

    async def create_self(subject: str, key: uuid.UUID, amount: str, reason: str) -> object:
        principal = principals[subject]
        assert principal.branch_id is not None
        body = AdvanceCreateRequest(
            amount=amount,
            reason=reason,
            installment_count=3,
            repayment_start_period=start_period,
        )
        outcome = await idempotent(
            subject,
            branch_id=principal.branch_id,
            key=key,
            operation_id="create_self_advance",
            method="POST",
            route_parameters={},
            body=body,
            callback=lambda service, actor, _key: service.create(
                actor, principal.branch_id, body, admin=False
            ),
        )
        assert outcome.body is not None
        advance_id = uuid.UUID(outcome.body["data"]["id"])  # type: ignore[index]
        generated_ids.append(advance_id)
        items, _ = await run(
            subject,
            lambda service, actor: service.list_self(actor, AdvanceListQuery(limit=100)),
        )
        return next(item for item in items if item.id == advance_id)  # type: ignore[union-attr]

    first_body = AdvanceCreateRequest(
        amount="1000.00",
        reason="Phase 9C replay",
        installment_count=3,
        repayment_start_period=start_period,
    )
    ravi_principal = principals[RAVI]
    assert ravi_principal.branch_id is not None
    first = await idempotent(
        RAVI,
        branch_id=ravi_principal.branch_id,
        key=KEYS[0],
        operation_id="create_self_advance",
        method="POST",
        route_parameters={},
        body=first_body,
        callback=lambda service, actor, _key: service.create(
            actor, ravi_principal.branch_id, first_body, admin=False
        ),
    )
    replay = await idempotent(
        RAVI,
        branch_id=ravi_principal.branch_id,
        key=KEYS[0],
        operation_id="create_self_advance",
        method="POST",
        route_parameters={},
        body=first_body,
        callback=lambda service, actor, _key: service.create(
            actor, ravi_principal.branch_id, first_body, admin=False
        ),
    )
    assert first.body == replay.body and replay.replayed
    assert first.body is not None
    first_id = uuid.UUID(first.body["data"]["id"])  # type: ignore[index]
    generated_ids.append(first_id)
    await expect_code(
        "idempotency_conflict",
        idempotent(
            RAVI,
            branch_id=ravi_principal.branch_id,
            key=KEYS[0],
            operation_id="create_self_advance",
            method="POST",
            route_parameters={},
            body=first_body.model_copy(update={"reason": "Changed replay"}),
            callback=lambda service, actor, _key: service.create(
                actor,
                ravi_principal.branch_id,
                first_body.model_copy(update={"reason": "Changed replay"}),
                admin=False,
            ),
        ),
    )

    maria_items, _ = await run(
        MARIA, lambda service, actor: service.list_self(actor, AdvanceListQuery(limit=100))
    )
    assert first_id not in {item.id for item in maria_items}  # type: ignore[union-attr]
    other_branch, _ = await run(
        ADMIN,
        lambda service, actor: service.list_admin(
            actor, OTHER_BRANCH_ID, AdvanceListQuery(limit=100)
        ),
        branch_id=OTHER_BRANCH_ID,
    )
    assert first_id not in {item.id for item in other_branch}  # type: ignore[union-attr]
    first_self = next(
        item
        for item in (
            await run(
                RAVI,
                lambda service, actor: service.list_self(actor, AdvanceListQuery(limit=100)),
            )
        )[0]
        if item.id == first_id
    )
    await expect_code(
        "resource_not_found",
        run(
            ADMIN,
            lambda service, actor: service.decide(
                actor,
                OTHER_BRANCH_ID,
                first_id,
                AdvanceDecisionRequest(expected_updated_at=first_self.updated_at),
                approve=True,
            ),
            branch_id=OTHER_BRANCH_ID,
        ),
    )

    withdrawn = await create_self(MARIA, KEYS[1], "500.00", "Withdrawal case")
    await expect_code(
        "stale_financial_state",
        run(
            MARIA,
            lambda service, actor: service.withdraw(
                actor,
                BRANCH_ID,
                withdrawn.id,  # type: ignore[attr-defined]
                AdvanceVersionRequest(
                    expected_updated_at=withdrawn.updated_at - timedelta(seconds=1)  # type: ignore[attr-defined]
                ),
            ),
        ),
    )
    withdrawn_result = await run(
        MARIA,
        lambda service, actor: service.withdraw(
            actor,
            BRANCH_ID,
            withdrawn.id,  # type: ignore[attr-defined]
            AdvanceVersionRequest(expected_updated_at=withdrawn.updated_at),  # type: ignore[attr-defined]
        ),
    )
    assert withdrawn_result.status == "cancelled"  # type: ignore[union-attr]
    await expect_code(
        "stale_financial_state",
        run(
            ADMIN,
            lambda service, actor: service.schedule(
                actor,
                BRANCH_ID,
                withdrawn_result.id,  # type: ignore[union-attr]
                AdvanceScheduleRequest(
                    expected_updated_at=withdrawn_result.updated_at,  # type: ignore[union-attr]
                    amount="500.00",
                    installment_count=3,
                    repayment_start_period=start_period,
                ),
            ),
            branch_id=BRANCH_ID,
        ),
    )

    rejected = await create_self(MARIA, KEYS[2], "600.00", "Rejection case")
    rejected_result = await run(
        ADMIN,
        lambda service, actor: service.decide(
            actor,
            BRANCH_ID,
            rejected.id,  # type: ignore[attr-defined]
            AdvanceDecisionRequest(
                expected_updated_at=rejected.updated_at,  # type: ignore[attr-defined]
                reason="Synthetic rejection",
            ),
            approve=False,
        ),
        branch_id=BRANCH_ID,
    )
    assert rejected_result.status == "cancelled"  # type: ignore[union-attr]

    admin_body = AdminAdvanceCreateRequest(
        employee_id=RAVI_ID,
        amount="1500.00",
        reason="Administrator-created case",
        installment_count=3,
        repayment_start_period=start_period,
    )
    admin_created = await run(
        ADMIN,
        lambda service, actor: service.create(actor, BRANCH_ID, admin_body, admin=True),
        branch_id=BRANCH_ID,
    )
    generated_ids.append(admin_created.id)  # type: ignore[union-attr]
    scheduled = await run(
        ADMIN,
        lambda service, actor: service.schedule(
            actor,
            BRANCH_ID,
            admin_created.id,  # type: ignore[union-attr]
            AdvanceScheduleRequest(
                expected_updated_at=admin_created.updated_at,  # type: ignore[union-attr]
                amount="1000.00",
                installment_count=3,
                repayment_start_period=start_period,
            ),
        ),
        branch_id=BRANCH_ID,
    )
    assert [row.scheduled_amount for row in scheduled.schedule] == [  # type: ignore[union-attr]
        "333.33",
        "333.33",
        "333.34",
    ]
    await expect_code(
        "resource_not_found",
        run(
            ADMIN,
            lambda service, actor: service.decide(
                actor,
                BRANCH_ID,
                scheduled.id,  # type: ignore[union-attr]
                AdvanceDecisionRequest(expected_updated_at=scheduled.updated_at),  # type: ignore[union-attr]
                approve=True,
            ),
            branch_id=BRANCH_ID,
        ),
    )
    await expect_code(
        "operation_not_permitted",
        run(
            RAVI,
            lambda service, actor: service.decide(
                actor,
                BRANCH_ID,
                scheduled.id,  # type: ignore[union-attr]
                AdvanceDecisionRequest(expected_updated_at=scheduled.updated_at),  # type: ignore[union-attr]
                approve=True,
            ),
        ),
    )
    active = await run(
        SECOND_ADMIN,
        lambda service, actor: service.decide(
            actor,
            BRANCH_ID,
            scheduled.id,  # type: ignore[union-attr]
            AdvanceDecisionRequest(expected_updated_at=scheduled.updated_at),  # type: ignore[union-attr]
            approve=True,
        ),
        branch_id=BRANCH_ID,
    )

    repayment_body = AdvanceRepaymentRequest(
        expected_updated_at=active.updated_at,
        amount="333.33",  # type: ignore[union-attr]
    )
    repayment_params = {"advanceId": str(active.id)}  # type: ignore[union-attr]
    repayment = await idempotent(
        ADMIN,
        branch_id=BRANCH_ID,
        key=KEYS[3],
        operation_id="record_advance_repayment",
        method="POST",
        route_parameters=repayment_params,
        body=repayment_body,
        callback=lambda service, actor, key: service.repay(
            actor,
            BRANCH_ID,
            active.id,  # type: ignore[union-attr]
            repayment_body,
            idempotency_key=key,
            settle=False,
        ),
    )
    replayed_repayment = await idempotent(
        ADMIN,
        branch_id=BRANCH_ID,
        key=KEYS[3],
        operation_id="record_advance_repayment",
        method="POST",
        route_parameters=repayment_params,
        body=repayment_body,
        callback=lambda service, actor, key: service.repay(
            actor,
            BRANCH_ID,
            active.id,  # type: ignore[union-attr]
            repayment_body,
            idempotency_key=key,
            settle=False,
        ),
    )
    assert repayment.body == replayed_repayment.body and replayed_repayment.replayed
    assert repayment.body is not None
    after_first = repayment.body["data"]  # type: ignore[index]
    assert after_first["outstandingBalance"] == "666.67"
    await expect_code(
        "idempotency_conflict",
        idempotent(
            ADMIN,
            branch_id=BRANCH_ID,
            key=KEYS[3],
            operation_id="record_advance_repayment",
            method="POST",
            route_parameters=repayment_params,
            body=repayment_body.model_copy(update={"amount": "300.00"}),
            callback=lambda service, actor, key: service.repay(
                actor,
                BRANCH_ID,
                active.id,  # type: ignore[union-attr]
                repayment_body.model_copy(update={"amount": "300.00"}),
                idempotency_key=key,
                settle=False,
            ),
        ),
    )
    current = next(
        item
        for item in (
            await run(
                ADMIN,
                lambda service, actor: service.list_admin(
                    actor,
                    BRANCH_ID,
                    AdvanceListQuery(limit=100, employee_id=RAVI_ID),
                ),
                branch_id=BRANCH_ID,
            )
        )[0]
        if item.id == active.id  # type: ignore[union-attr]
    )
    second_body = AdvanceRepaymentRequest(expected_updated_at=current.updated_at, amount="333.33")
    second = await run(
        ADMIN,
        lambda service, actor: service.repay(
            actor,
            BRANCH_ID,
            current.id,
            second_body,
            idempotency_key=KEYS[4],
            settle=False,
        ),
        branch_id=BRANCH_ID,
    )
    assert second.outstanding_balance == "333.34"  # type: ignore[union-attr]
    settled = await run(
        ADMIN,
        lambda service, actor: service.repay(
            actor,
            BRANCH_ID,
            second.id,  # type: ignore[union-attr]
            AdvanceVersionRequest(expected_updated_at=second.updated_at),  # type: ignore[union-attr]
            idempotency_key=KEYS[5],
            settle=True,
        ),
        branch_id=BRANCH_ID,
    )
    assert settled.status == "settled" and settled.outstanding_balance == "0.00"  # type: ignore[union-attr]
    assert settled.repayments[-1].amount == "333.34"  # type: ignore[union-attr]
    await expect_code(
        "stale_financial_state",
        run(
            ADMIN,
            lambda service, actor: service.repay(
                actor,
                BRANCH_ID,
                settled.id,  # type: ignore[union-attr]
                AdvanceRepaymentRequest(
                    expected_updated_at=settled.updated_at,
                    amount="1.00",  # type: ignore[union-attr]
                ),
                idempotency_key=KEYS[12],
                settle=False,
            ),
            branch_id=BRANCH_ID,
        ),
    )

    concurrent_pending = await create_self(RAVI, KEYS[6], "800.00", "Concurrent repayment")
    concurrent_active = await run(
        ADMIN,
        lambda service, actor: service.decide(
            actor,
            BRANCH_ID,
            concurrent_pending.id,  # type: ignore[attr-defined]
            AdvanceDecisionRequest(expected_updated_at=concurrent_pending.updated_at),  # type: ignore[attr-defined]
            approve=True,
        ),
        branch_id=BRANCH_ID,
    )
    concurrent_body = AdvanceRepaymentRequest(
        expected_updated_at=concurrent_active.updated_at,
        amount="100.00",  # type: ignore[union-attr]
    )
    concurrent = await asyncio.gather(
        run(
            ADMIN,
            lambda service, actor: service.repay(
                actor,
                BRANCH_ID,
                concurrent_active.id,  # type: ignore[union-attr]
                concurrent_body,
                idempotency_key=KEYS[7],
                settle=False,
            ),
            branch_id=BRANCH_ID,
        ),
        run(
            SECOND_ADMIN,
            lambda service, actor: service.repay(
                actor,
                BRANCH_ID,
                concurrent_active.id,  # type: ignore[union-attr]
                concurrent_body,
                idempotency_key=KEYS[8],
                settle=False,
            ),
            branch_id=BRANCH_ID,
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(item, BaseException) for item in concurrent) == 1
    concurrent_failure = next(item for item in concurrent if isinstance(item, BaseException))
    assert isinstance(concurrent_failure, ServiceExecutionError)
    assert concurrent_failure.code == "stale_financial_state"

    payroll_pending = await create_self(RAVI, KEYS[9], "900.00", "Payroll uniqueness")
    payroll_active = await run(
        ADMIN,
        lambda service, actor: service.decide(
            actor,
            BRANCH_ID,
            payroll_pending.id,  # type: ignore[attr-defined]
            AdvanceDecisionRequest(expected_updated_at=payroll_pending.updated_at),  # type: ignore[attr-defined]
            approve=True,
        ),
        branch_id=BRANCH_ID,
    )
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO public.payroll_runs(id,company_id,branch_id,period) "
                "VALUES(:id,:company_id,:branch_id,'2098-01')"
            ),
            {"id": PAYROLL_RUN_ID, "company_id": COMPANY_ID, "branch_id": BRANCH_ID},
        )

    async def payroll_repayment(key: uuid.UUID) -> object:
        principal = principals[ADMIN]

        async def invoke(connection: AsyncConnection) -> object:
            return await connection.scalar(
                text(
                    "SELECT public.record_advance_repayment("
                    ":advance_id,:run_id,:key,100.00,public.workloop_business_date())"
                ),
                {"advance_id": payroll_active.id, "run_id": PAYROLL_RUN_ID, "key": key},  # type: ignore[union-attr]
            )

        return await executor.execute(
            claims=claims(ADMIN),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID,
            operation=invoke,
        )

    first_payroll = await payroll_repayment(KEYS[10])
    assert first_payroll["newBalance"] == 800  # type: ignore[index]
    try:
        await payroll_repayment(KEYS[11])
    except DBAPIError as error:
        assert "advance_repayment_payroll_conflict" in str(error.orig)
    else:
        raise AssertionError("second repayment for one advance and payroll run succeeded")

    with migration_engine.begin() as connection:
        assert (
            connection.scalar(
                text("SELECT outstanding_balance FROM public.salary_advances WHERE id=:id"),
                {"id": payroll_active.id},  # type: ignore[union-attr]
            )
            == 800
        )
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM public.advance_repayments "
                    "WHERE advance_id=:id AND payroll_run_id=:run_id"
                ),
                {"id": payroll_active.id, "run_id": PAYROLL_RUN_ID},  # type: ignore[union-attr]
            )
            == 1
        )
        actions = set(
            connection.execute(
                text(
                    "SELECT action FROM public.audit_events "
                    "WHERE entity_type='salary_advance' AND entity_id=ANY(:ids)"
                ),
                {"ids": generated_ids},
            ).scalars()
        )
        assert {
            "salary_advance_requested",
            "salary_advance_schedule_changed",
            "salary_advance_withdrawn",
            "salary_advance_approved",
            "salary_advance_rejected",
            "salary_advance_repayment_recorded",
            "salary_advance_settled",
        } <= actions
        connection.execute(
            text(
                "DELETE FROM public.audit_events "
                "WHERE entity_type='salary_advance' AND entity_id=ANY(:ids)"
            ),
            {"ids": generated_ids},
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE idempotency_key=ANY(:keys)"),
            {"keys": KEYS},
        )
        connection.execute(
            text("DELETE FROM public.advance_repayments WHERE advance_id=ANY(:ids)"),
            {"ids": generated_ids},
        )
        connection.execute(
            text("DELETE FROM public.salary_advances WHERE id=ANY(:ids)"),
            {"ids": generated_ids},
        )
        connection.execute(
            text("DELETE FROM public.payroll_runs WHERE id=:id"), {"id": PAYROLL_RUN_ID}
        )
        connection.execute(
            text("DELETE FROM public.user_profiles WHERE app_user_id=:id"),
            {"id": SECOND_ADMIN_ID},
        )
        connection.execute(
            text("DELETE FROM public.app_users WHERE id=:id"), {"id": SECOND_ADMIN_ID}
        )
    await runtime_engine.dispose()
    with migration_engine.begin() as connection:
        clean(connection, rows)
    migration_engine.dispose()
    print("Phase 9C advance database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
