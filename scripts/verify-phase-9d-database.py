#!/usr/bin/env python3
"""Exercise Phase 9D payroll draft boundaries through the runtime role."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date

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
from app.schemas.payroll import (
    PayrollAdjustmentRequest,
    PayrollCreateRequest,
    PayrollEntriesRequest,
    PayrollEntrySaveRequest,
    PayrollRepeatRequest,
    PayrollVersionRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.payroll import (
    PayrollService,
    _preview,
    calculate_entry,
    is_automatic_adjustment,
)

COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
ADMIN = "hr.admin@horizon.test"
KEY = uuid.UUID("9d000000-0000-4000-8000-000000000001")


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


def claims() -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=seed.SEED_ISSUER,
        subject=ADMIN,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def previous_period(value: date) -> tuple[str, date]:
    index = value.year * 12 + value.month - 1 - 8
    year = index // 12
    month = index % 12 + 1
    return f"{year:04d}-{month:02d}", date(year, month, 25)


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
    fixture_run_ids = [row.values["id"] for row in rows if row.table == "payroll_runs"]
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "d0f6b8e2a753"
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE replay_resource_kind='payroll_run'")
        )
        connection.execute(
            text(
                "DELETE FROM public.audit_events WHERE entity_type='payroll_run' "
                "AND action IN ('payroll_draft_created','payroll_draft_refreshed',"
                "'payroll_inputs_refreshed',"
                "'payroll_entries_replaced','payroll_draft_deleted')"
            )
        )
        connection.execute(
            text(
                "DELETE FROM public.payroll_entries AS entry USING public.payroll_runs AS run "
                "WHERE entry.payroll_run_id=run.id AND run.company_id=:company_id "
                "AND run.branch_id=:branch_id "
                "AND NOT (run.id=ANY(CAST(:fixture_run_ids AS uuid[])))"
            ),
            {
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "fixture_run_ids": fixture_run_ids,
            },
        )
        connection.execute(
            text(
                "DELETE FROM public.payroll_runs WHERE company_id=:company_id "
                "AND branch_id=:branch_id "
                "AND NOT (id=ANY(CAST(:fixture_run_ids AS uuid[])))"
            ),
            {
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "fixture_run_ids": fixture_run_ids,
            },
        )
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        business_date = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        assert isinstance(business_date, date)
        connection.execute(
            text(
                "UPDATE public.employees SET basic_salary=10000,housing_allowance=0,"
                "transport_allowance=0,allowance=0,employment_start_date=:start_date,"
                "termination_date=NULL,employment_status='Active',active=true "
                "WHERE company_id=:company_id AND branch_id=:branch_id"
            ),
            {
                "start_date": date(2020, 1, 1),
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
            },
        )

    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD")
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine, issuer=seed.SEED_ISSUER, timeout_seconds=5
    )
    principal = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=ADMIN)
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    codec = EmployeeCursorCodec(b"9" * 32)

    async def run(callback: object, branch_id: uuid.UUID = BRANCH_ID) -> object:
        async def invoke(connection: AsyncConnection) -> object:
            return await callback(PayrollService(connection, codec))  # type: ignore[operator]

        return await executor.execute(
            claims=claims(),
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=invoke,
        )

    source_period, source_payment = previous_period(business_date)
    create_body = PayrollCreateRequest(period=source_period, payment_date=source_payment)

    async def idempotent_create(body: PayrollCreateRequest) -> IdempotentResponse:
        operation_id = "create_payroll_run"
        body_values = body.model_dump(mode="json", by_alias=True)
        command = IdempotencyCommand(
            key=KEY,
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
            service = PayrollService(connection, codec)

            async def mutate() -> IdempotentResponse:
                result = await service.create(principal, BRANCH_ID, body)
                return IdempotentResponse(
                    status=201,
                    body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
                    location=f"/api/v1/payroll-runs/{result.id}",
                    resource_kind="payroll_run",
                    resource_id=result.id,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, BRANCH_ID, kind, resource_id
                ),
                mutation=mutate,
            )

        return await executor.execute(
            claims=claims(),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID,
            operation=invoke,
        )

    first = await idempotent_create(create_body)
    replay = await idempotent_create(create_body)
    assert replay.replayed and replay.body == first.body
    changed = PayrollCreateRequest(
        period=source_period, payment_date=date.fromisoformat(source_period + "-24")
    )
    await expect_code("idempotency_conflict", idempotent_create(changed))
    assert first.body is not None
    source_id = uuid.UUID(first.body["data"]["id"])  # type: ignore[index]
    source = await run(lambda service: service.detail(principal, BRANCH_ID, source_id))
    assert source.sequence == "0001"  # type: ignore[union-attr]
    assert source.source_warnings == [  # type: ignore[union-attr]
        "attendance_input_not_ready",
        "roster_input_not_ready",
    ]
    assert source.entries and all(item.net_pay == "10000.00" for item in source.entries)  # type: ignore[union-attr]
    await expect_code(
        "resource_not_found",
        run(lambda service: service.detail(principal, OTHER_BRANCH_ID, source_id), OTHER_BRANCH_ID),
    )

    first_entry = source.entries[0]  # type: ignore[union-attr]
    recurring = PayrollAdjustmentRequest(
        id=uuid.UUID("9d000000-0000-4000-8000-000000000010"),
        code="SHIFT_ALLOWANCE",
        label="Shift allowance",
        amount="250.25",
        recurrence="recurring",
        note=None,
    )
    one_time = PayrollAdjustmentRequest(
        id=uuid.UUID("9d000000-0000-4000-8000-000000000011"),
        code="PROJECT_BONUS",
        label="Project bonus",
        amount="499.75",
        recurrence="one_time",
        note=None,
    )

    def save_item(
        item: object, *, additions: list[PayrollAdjustmentRequest] | None = None
    ) -> PayrollEntrySaveRequest:
        manual_additions = additions or []
        automatic_additions = [
            value.model_dump(mode="json")
            for value in item.additional_allowances  # type: ignore[attr-defined]
            if is_automatic_adjustment(value.model_dump(mode="json"))
        ]
        automatic_deductions = [
            value.model_dump(mode="json")
            for value in item.deductions  # type: ignore[attr-defined]
            if is_automatic_adjustment(value.model_dump(mode="json"))
        ]
        values = calculate_entry(
            basic_salary=item.basic_salary,  # type: ignore[attr-defined]
            housing_allowance=item.housing_allowance,  # type: ignore[attr-defined]
            transport_allowance=item.transport_allowance,  # type: ignore[attr-defined]
            fixed_allowance=item.fixed_allowance,  # type: ignore[attr-defined]
            increment=item.increment,  # type: ignore[attr-defined]
            bonus=item.bonus,  # type: ignore[attr-defined]
            other_pay=item.other_pay,  # type: ignore[attr-defined]
            variable_allowance=item.variable_allowance,  # type: ignore[attr-defined]
            leave_deduction=item.leave_deduction,  # type: ignore[attr-defined]
            additional_allowances=[
                value.model_dump(mode="json") for value in manual_additions
            ]
            + automatic_additions,
            deductions=automatic_deductions,
        )
        return PayrollEntrySaveRequest(
            employee_id=item.employee_id,  # type: ignore[attr-defined]
            increment=item.increment,  # type: ignore[attr-defined]
            bonus=item.bonus,  # type: ignore[attr-defined]
            other_pay=item.other_pay,  # type: ignore[attr-defined]
            variable_allowance=item.variable_allowance,  # type: ignore[attr-defined]
            additional_allowances=manual_additions,
            deductions=[],
            excluded=item.excluded,  # type: ignore[attr-defined]
            preview=_preview(values),
        )

    source_items = [
        save_item(item, additions=[recurring, one_time] if item.id == first_entry.id else None)
        for item in source.entries  # type: ignore[union-attr]
    ]
    saved = await run(
        lambda service: service.save_entries(
            principal,
            BRANCH_ID,
            source_id,
            PayrollEntriesRequest(expected_updated_at=source.updated_at, entries=source_items),  # type: ignore[union-attr]
        )
    )
    assert saved.entries[0].gross_pay == "10750.00"  # type: ignore[union-attr]

    target_period = business_date.strftime("%Y-%m")
    target_payment = business_date.replace(day=min(25, business_date.day))
    repeated = await run(
        lambda service: service.repeat(
            principal,
            BRANCH_ID,
            source_id,
            PayrollRepeatRequest(
                period=target_period,
                payment_date=target_payment,
                expected_updated_at=saved.updated_at,  # type: ignore[union-attr]
            ),
        )
    )
    repeated_first = next(
        item for item in repeated.entries if item.employee_id == first_entry.employee_id
    )  # type: ignore[union-attr]
    assert repeated_first.gross_pay == "10250.25"
    assert [item.code for item in repeated_first.additional_allowances] == ["SHIFT_ALLOWANCE"]

    stale = PayrollVersionRequest(expected_updated_at=saved.updated_at)  # type: ignore[union-attr]
    await expect_code(
        "stale_financial_state",
        run(lambda service: service.refresh(principal, BRANCH_ID, repeated.id, stale)),  # type: ignore[union-attr]
    )

    current = repeated
    current_items = [save_item(item) for item in current.entries]  # type: ignore[union-attr]
    save_request = PayrollEntriesRequest(
        expected_updated_at=current.updated_at,  # type: ignore[union-attr]
        entries=current_items,
    )

    async def concurrent_save() -> object:
        try:
            return await run(
                lambda service: service.save_entries(
                    principal,
                    BRANCH_ID,
                    current.id,
                    save_request,  # type: ignore[union-attr]
                )
            )
        except ServiceExecutionError as error:
            return error.code

    concurrent = await asyncio.gather(concurrent_save(), concurrent_save())
    assert sum(item == "stale_financial_state" for item in concurrent) == 1, concurrent
    updated = next(item for item in concurrent if item != "stale_financial_state")

    invalid_items = list(current_items)
    invalid_items[0] = invalid_items[0].model_copy(
        update={"preview": invalid_items[0].preview.model_copy(update={"net_pay": "9999.99"})}
    )
    await expect_code(
        "validation_failed",
        run(
            lambda service: service.save_entries(
                principal,
                BRANCH_ID,
                updated.id,  # type: ignore[union-attr]
                PayrollEntriesRequest(
                    expected_updated_at=updated.updated_at,  # type: ignore[union-attr]
                    entries=invalid_items,
                ),
            )
        ),
    )
    unchanged = await run(lambda service: service.detail(principal, BRANCH_ID, updated.id))  # type: ignore[union-attr]
    assert unchanged.updated_at == updated.updated_at  # type: ignore[union-attr]

    await run(
        lambda service: service.delete(
            principal,
            BRANCH_ID,
            source_id,
            PayrollVersionRequest(expected_updated_at=saved.updated_at),  # type: ignore[union-attr]
        )
    )
    await run(
        lambda service: service.delete(
            principal,
            BRANCH_ID,
            updated.id,  # type: ignore[union-attr]
            PayrollVersionRequest(expected_updated_at=updated.updated_at),  # type: ignore[union-attr]
        )
    )

    with migration_engine.begin() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM public.audit_events WHERE entity_type='payroll_run' "
                    "AND action IN ('payroll_draft_created','payroll_draft_refreshed',"
                    "'payroll_inputs_refreshed',"
                    "'payroll_entries_replaced','payroll_draft_deleted')"
                )
            )
            >= 8
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE replay_resource_kind='payroll_run'")
        )
        connection.execute(
            text(
                "DELETE FROM public.audit_events WHERE entity_type='payroll_run' "
                "AND action IN ('payroll_draft_created','payroll_draft_refreshed',"
                "'payroll_inputs_refreshed',"
                "'payroll_entries_replaced','payroll_draft_deleted')"
            )
        )
        clean(connection, rows)
    await runtime_engine.dispose()
    migration_engine.dispose()
    print("Phase 9D payroll database verification passed")


if __name__ == "__main__":
    asyncio.run(main())
