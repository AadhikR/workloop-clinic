#!/usr/bin/env python3
"""Exercise Phase 9E payroll inputs through the runtime role."""

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
    PayrollEntriesRequest,
    PayrollEntrySaveRequest,
    PayrollVersionRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.payroll import PayrollService, _preview, calculate_entry

COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
ADMIN = "hr.admin@horizon.test"
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
PERIOD = "2026-04"
PAYMENT_DATE = date(2026, 4, 25)
RUN_ID = uuid.UUID("9e000000-0000-4000-8000-000000000100")
LEAVE_ID = uuid.UUID("9e000000-0000-4000-8000-000000000101")
EXPENSE_ID = uuid.UUID("9e000000-0000-4000-8000-000000000102")
ADVANCE_ID = uuid.UUID("9e000000-0000-4000-8000-000000000103")
OTHER_EXPENSE_ID = uuid.UUID("9e000000-0000-4000-8000-000000000104")
REFRESH_KEY = uuid.UUID("9e000000-0000-4000-8000-000000000105")


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


async def expect_code(code: str, operation: object) -> None:
    try:
        await operation  # type: ignore[misc]
    except ServiceExecutionError as error:
        assert error.code == code, error.code
        return
    raise AssertionError(f"expected {code}")


def manual_save(detail: object) -> PayrollEntriesRequest:
    items: list[PayrollEntrySaveRequest] = []
    for entry in detail.entries:  # type: ignore[attr-defined]
        bonus = "1000.00" if entry.employee_id == EMPLOYEE_ID else entry.bonus
        additions = [item.model_dump(mode="json") for item in entry.additional_allowances]
        deductions = [item.model_dump(mode="json") for item in entry.deductions]
        values = calculate_entry(
            basic_salary=entry.basic_salary,
            housing_allowance=entry.housing_allowance,
            transport_allowance=entry.transport_allowance,
            fixed_allowance=entry.fixed_allowance,
            increment=entry.increment,
            bonus=bonus,
            other_pay=entry.other_pay,
            variable_allowance=entry.variable_allowance,
            leave_deduction=entry.leave_deduction,
            additional_allowances=additions,
            deductions=deductions,
        )
        items.append(
            PayrollEntrySaveRequest(
                employee_id=entry.employee_id,
                increment=entry.increment,
                bonus=bonus,
                other_pay=entry.other_pay,
                variable_allowance=entry.variable_allowance,
                additional_allowances=[],
                deductions=[],
                excluded=entry.excluded,
                preview=_preview(values),
            )
        )
    return PayrollEntriesRequest(expected_updated_at=detail.updated_at, entries=items)  # type: ignore[attr-defined]


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    rows = build_rows()
    fixture_run_ids = [row.values["id"] for row in rows if row.table == "payroll_runs"]
    unpaid_type_id = seed.derive("leave_types", seed.HORIZON, "dubai", "none", "unpaid")
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "a1c3e5f7b9d4"
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE replay_resource_kind='payroll_run'")
        )
        connection.execute(text("DELETE FROM public.audit_events WHERE entity_type='payroll_run'"))
        connection.execute(
            text(
                "DELETE FROM public.payroll_entries AS entry USING public.payroll_runs AS run "
                "WHERE entry.payroll_run_id=run.id AND run.company_id=:company_id "
                "AND NOT (run.id=ANY(CAST(:fixture_run_ids AS uuid[])))"
            ),
            {"company_id": COMPANY_ID, "fixture_run_ids": fixture_run_ids},
        )
        connection.execute(
            text(
                "DELETE FROM public.payroll_runs WHERE company_id=:company_id "
                "AND NOT (id=ANY(CAST(:fixture_run_ids AS uuid[])))"
            ),
            {"company_id": COMPANY_ID, "fixture_run_ids": fixture_run_ids},
        )
        connection.execute(text("DELETE FROM public.leave_requests WHERE id=:id"), {"id": LEAVE_ID})
        connection.execute(
            text("DELETE FROM public.expense_claims WHERE id IN (:first,:second)"),
            {"first": EXPENSE_ID, "second": OTHER_EXPENSE_ID},
        )
        connection.execute(
            text("DELETE FROM public.salary_advances WHERE id=:id"), {"id": ADVANCE_ID}
        )
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "INSERT INTO public.leave_requests("
                "id,company_id,branch_id,employee_id,leave_type_id,start_date,end_date,"
                "days_requested,status,approved_by_app_user_id,approved_at) VALUES("
                ":id,:company_id,:branch_id,:employee_id,:leave_type_id,'2026-04-10',"
                "'2026-04-10',1,'Approved',:actor,statement_timestamp())"
            ),
            {
                "id": LEAVE_ID,
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "employee_id": EMPLOYEE_ID,
                "leave_type_id": unpaid_type_id,
                "actor": seed.ADMIN_APP_USER[seed.HORIZON],
            },
        )
        connection.execute(
            text(
                "INSERT INTO public.expense_claims("
                "id,company_id,branch_id,employee_id,amount,expense_date,description,status,"
                "approved_by_app_user_id,approved_at) VALUES("
                ":id,:company_id,:branch_id,:employee_id,350,'2026-04-12','Phase 9E input',"
                "'approved',:actor,statement_timestamp())"
            ),
            {
                "id": EXPENSE_ID,
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "employee_id": EMPLOYEE_ID,
                "actor": seed.ADMIN_APP_USER[seed.HORIZON],
            },
        )
        other_employee = connection.scalar(
            text(
                "SELECT id FROM public.employees WHERE company_id=:company_id "
                "AND branch_id=:branch_id ORDER BY id LIMIT 1"
            ),
            {"company_id": COMPANY_ID, "branch_id": OTHER_BRANCH_ID},
        )
        connection.execute(
            text(
                "INSERT INTO public.expense_claims("
                "id,company_id,branch_id,employee_id,amount,expense_date,description,status,"
                "approved_by_app_user_id,approved_at) VALUES("
                ":id,:company_id,:branch_id,:employee_id,999,'2026-04-12','Other branch',"
                "'approved',:actor,statement_timestamp())"
            ),
            {
                "id": OTHER_EXPENSE_ID,
                "company_id": COMPANY_ID,
                "branch_id": OTHER_BRANCH_ID,
                "employee_id": other_employee,
                "actor": seed.ADMIN_APP_USER[seed.HORIZON],
            },
        )
        connection.execute(
            text(
                "INSERT INTO public.salary_advances("
                "id,company_id,branch_id,employee_id,amount,disbursed_date,"
                "repayment_start_month,reason,repayment_months,monthly_deduction,"
                "outstanding_balance,status) VALUES("
                ":id,:company_id,:branch_id,:employee_id,1500,'2026-04-01','2026-04-01',"
                "'Phase 9E input',3,500,1500,'active')"
            ),
            {
                "id": ADVANCE_ID,
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "employee_id": EMPLOYEE_ID,
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
    codec = EmployeeCursorCodec(b"e" * 32)

    async def run(callback: object, branch_id: uuid.UUID = BRANCH_ID) -> object:
        async def invoke(connection: AsyncConnection) -> object:
            return await callback(PayrollService(connection, codec))  # type: ignore[operator]

        return await executor.execute(
            claims=claims(),
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=invoke,
        )

    async def create_fixed_id(service: PayrollService) -> object:
        await service.repository.create_run(
            run_id=RUN_ID,
            company_id=COMPANY_ID,
            branch_id=BRANCH_ID,
            period=PERIOD,
            payment_date=PAYMENT_DATE,
            sequence="0001",
            routing_code="999000001",
            actor_id=principal.app_user_id,
        )
        entries = await service._employee_entries(principal, BRANCH_ID, PERIOD, {})
        await service.repository.replace_entries(RUN_ID, entries)
        from app.db.audit import append_audit_event

        await append_audit_event(
            service.connection,
            action="payroll_inputs_refreshed",
            entity_type="payroll_run",
            entity_id=RUN_ID,
            changed_fields=[
                "source_snapshot_digest",
                "employee_count",
                "total_disbursed",
                "updated_at",
            ],
            reason="Payroll inputs refreshed",
            metadata={
                "counts": {
                    "leave": 1,
                    "attendance": 0,
                    "roster": 0,
                    "expense": 1,
                    "advance": 1,
                },
                "digests": {
                    name: "0" * 64
                    for name in ("leave", "attendance", "roster", "expense", "advance")
                },
            },
        )
        return await service.detail(principal, BRANCH_ID, RUN_ID)

    created = await run(create_fixed_id)
    target = next(item for item in created.entries if item.employee_id == EMPLOYEE_ID)  # type: ignore[attr-defined]
    assert target.leave_deduction == "400.00"
    assert target.gross_pay == "16850.00" and target.total_deductions == "900.00"
    assert target.net_pay == "15950.00"
    assert [item.amount for item in target.additional_allowances] == ["350.00"]
    assert [item.amount for item in target.deductions] == ["500.00"]
    assert created.source_warnings == [  # type: ignore[attr-defined]
        "attendance_input_not_ready",
        "roster_input_not_ready",
    ]
    assert created.validation_status == "blocking"  # type: ignore[attr-defined]
    assert len(target.source_explanations) == 3
    await expect_code(
        "resource_not_found",
        run(lambda service: service.detail(principal, OTHER_BRANCH_ID, RUN_ID), OTHER_BRANCH_ID),
    )

    async def idempotent_refresh(expected: object, *, changed: bool = False) -> IdempotentResponse:
        body = {"expectedUpdatedAt": expected.updated_at.isoformat()}  # type: ignore[attr-defined]
        if changed:
            body["changed"] = True
        command = IdempotencyCommand(
            key=REFRESH_KEY,
            operation_id="refresh_payroll_run",
            method="POST",
            route_parameters={"runId": str(RUN_ID)},
            fingerprint=request_fingerprint(
                operation_id="refresh_payroll_run",
                method="POST",
                route_parameters={"runId": str(RUN_ID)},
                effective_query_parameters={},
                body=body,
            ),
            branch_id=BRANCH_ID,
        )

        async def invoke(connection: AsyncConnection) -> IdempotentResponse:
            service = PayrollService(connection, codec)

            async def mutate() -> IdempotentResponse:
                detail = await service.refresh(
                    principal,
                    BRANCH_ID,
                    RUN_ID,
                    PayrollVersionRequest(expected_updated_at=expected.updated_at),  # type: ignore[attr-defined]
                )
                return IdempotentResponse(
                    status=200,
                    body=DataResponse(data=detail).model_dump(mode="json", by_alias=True),
                    location=None,
                    resource_kind="payroll_run",
                    resource_id=RUN_ID,
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

    first_refresh = await idempotent_refresh(created)
    replay = await idempotent_refresh(created)
    assert replay.replayed and replay.body == first_refresh.body
    await expect_code("idempotency_conflict", idempotent_refresh(created, changed=True))
    current = await run(lambda service: service.detail(principal, BRANCH_ID, RUN_ID))
    saved = await run(
        lambda service: service.save_entries(principal, BRANCH_ID, RUN_ID, manual_save(current))
    )
    target = next(item for item in saved.entries if item.employee_id == EMPLOYEE_ID)  # type: ignore[attr-defined]
    assert target.bonus == "1000.00" and target.net_pay == "16950.00"
    assert len(target.additional_allowances) == 1 and len(target.deductions) == 1

    refresh_request = PayrollVersionRequest(expected_updated_at=saved.updated_at)  # type: ignore[attr-defined]

    async def concurrent_refresh() -> object:
        try:
            return await run(
                lambda service: service.refresh(principal, BRANCH_ID, RUN_ID, refresh_request)
            )
        except ServiceExecutionError as error:
            return error.code

    concurrent = await asyncio.gather(concurrent_refresh(), concurrent_refresh())
    assert sum(item == "stale_financial_state" for item in concurrent) == 1
    refreshed = next(item for item in concurrent if item != "stale_financial_state")
    target = next(item for item in refreshed.entries if item.employee_id == EMPLOYEE_ID)  # type: ignore[attr-defined]
    assert target.bonus == "1000.00" and target.net_pay == "16950.00"
    old_fingerprint = target.source_fingerprint

    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE public.expense_claims SET amount=360,updated_at=statement_timestamp() "
                "WHERE id=:id"
            ),
            {"id": EXPENSE_ID},
        )
    changed = await run(
        lambda service: service.refresh(
            principal,
            BRANCH_ID,
            RUN_ID,
            PayrollVersionRequest(expected_updated_at=refreshed.updated_at),  # type: ignore[attr-defined]
        )
    )
    target = next(item for item in changed.entries if item.employee_id == EMPLOYEE_ID)  # type: ignore[attr-defined]
    assert target.net_pay == "16960.00" and target.source_fingerprint != old_fingerprint

    with migration_engine.begin() as connection:
        audit = connection.execute(
            text(
                "SELECT metadata FROM public.audit_events WHERE entity_type='payroll_run' "
                "AND entity_id=:run_id AND action='payroll_inputs_refreshed' "
                "ORDER BY occurred_at DESC,id DESC LIMIT 1"
            ),
            {"run_id": RUN_ID},
        ).scalar_one()
        assert audit["counts"] == {
            "leave": 1,
            "attendance": 0,
            "roster": 0,
            "expense": 1,
            "advance": 1,
        }
        assert all(len(value) == 64 for value in audit["digests"].values())
        source_snapshot = connection.execute(
            text(
                "SELECT source_snapshot FROM public.payroll_entries "
                "WHERE payroll_run_id=:run_id AND employee_id=:employee_id"
            ),
            {"run_id": RUN_ID, "employee_id": EMPLOYEE_ID},
        ).scalar_one()
        inputs = source_snapshot["automaticInputs"]
        assert [item["sourceType"] for item in inputs] == ["leave", "expense", "advance"]
        assert {item["sourceId"] for item in inputs} == {
            str(LEAVE_ID),
            str(EXPENSE_ID),
            str(ADVANCE_ID),
        }
        assert str(OTHER_EXPENSE_ID) not in {item["sourceId"] for item in inputs}
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE idempotency_key=:key"),
            {"key": REFRESH_KEY},
        )
        connection.execute(
            text(
                "DELETE FROM public.audit_events WHERE entity_type='payroll_run' "
                "AND entity_id=:run_id"
            ),
            {"run_id": RUN_ID},
        )
        connection.execute(
            text("DELETE FROM public.payroll_entries WHERE payroll_run_id=:id"), {"id": RUN_ID}
        )
        connection.execute(text("DELETE FROM public.payroll_runs WHERE id=:id"), {"id": RUN_ID})
        connection.execute(text("DELETE FROM public.leave_requests WHERE id=:id"), {"id": LEAVE_ID})
        connection.execute(
            text("DELETE FROM public.expense_claims WHERE id IN (:first,:second)"),
            {"first": EXPENSE_ID, "second": OTHER_EXPENSE_ID},
        )
        connection.execute(
            text("DELETE FROM public.salary_advances WHERE id=:id"), {"id": ADVANCE_ID}
        )
        clean(connection, rows)
    await runtime_engine.dispose()
    migration_engine.dispose()
    print("Phase 9E payroll input database verification passed")


if __name__ == "__main__":
    asyncio.run(main())
