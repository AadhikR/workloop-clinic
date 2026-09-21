#!/usr/bin/env python3
"""Exercise the Phase 9F lifecycle through runtime authorization context."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.repositories.payroll import PayrollRepository
from app.schemas.payroll import PayrollVersionRequest
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.payroll import PayrollService, PayslipListQuery

COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
ADMIN_A = "hr.admin@horizon.test"
ADMIN_B = "payroll.approver@horizon.test"
EMPLOYEE = "ravi.employee@horizon.test"
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
ADMIN_B_ID = uuid.UUID("9f000000-0000-4000-8000-000000000010")
RUN_ID = uuid.UUID("9f000000-0000-4000-8000-000000000020")
EXPENSE_ID = uuid.UUID("9f000000-0000-4000-8000-000000000021")
ADVANCE_ID = uuid.UUID("9f000000-0000-4000-8000-000000000022")
PERIOD = "2026-04"


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


class ReadyPayrollRepository(PayrollRepository):
    async def attendance_input_projection(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> list[RowMapping] | None:
        del company_id, branch_id, period
        return []

    async def roster_input_projection(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> list[RowMapping] | None:
        del company_id, branch_id, period
        return []


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=seed.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def clean_phase_9f(connection: object) -> None:
    execute = connection.execute  # type: ignore[attr-defined]
    identifiers = {"run": RUN_ID, "expense": EXPENSE_ID, "advance": ADVANCE_ID}
    execute(
        text("DELETE FROM audit_events WHERE entity_id IN (:run,:expense,:advance)"),
        identifiers,
    )
    execute(text("DELETE FROM payroll_approval_log WHERE payroll_run_id=:run"), identifiers)
    execute(text("DELETE FROM payslips WHERE payroll_run_id=:run"), identifiers)
    execute(text("DELETE FROM advance_repayments WHERE payroll_run_id=:run"), identifiers)
    execute(text("DELETE FROM payroll_entries WHERE payroll_run_id=:run"), identifiers)
    execute(text("DELETE FROM expense_claims WHERE id=:expense"), identifiers)
    execute(text("DELETE FROM salary_advances WHERE id=:advance"), identifiers)
    execute(text("DELETE FROM payroll_runs WHERE id=:run"), identifiers)
    execute(text("DELETE FROM user_profiles WHERE app_user_id=:id"), {"id": ADMIN_B_ID})
    execute(text("DELETE FROM app_users WHERE id=:id"), {"id": ADMIN_B_ID})


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
            "d0f6b8e2a753"
        )
        clean_phase_9f(connection)
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "INSERT INTO public.app_users(id,identity_issuer,identity_subject,status) "
                "VALUES(:id,:issuer,:subject,'active')"
            ),
            {"id": ADMIN_B_ID, "issuer": seed.SEED_ISSUER, "subject": ADMIN_B},
        )
        connection.execute(
            text(
                "INSERT INTO public.user_profiles(app_user_id,company_id,employee_id,role) "
                "VALUES(:id,:company_id,NULL,'admin')"
            ),
            {"id": ADMIN_B_ID, "company_id": COMPANY_ID},
        )
        connection.execute(
            text(
                "INSERT INTO public.expense_claims("
                "id,company_id,branch_id,employee_id,amount,expense_date,description,status,"
                "approved_by_app_user_id,approved_at) VALUES("
                ":id,:company_id,:branch_id,:employee_id,350,'2026-04-12',"
                "'Phase 9F expense','approved',:actor,statement_timestamp())"
            ),
            {
                "id": EXPENSE_ID,
                "company_id": COMPANY_ID,
                "branch_id": BRANCH_ID,
                "employee_id": EMPLOYEE_ID,
                "actor": seed.ADMIN_APP_USER[seed.HORIZON],
            },
        )
        connection.execute(
            text(
                "INSERT INTO public.salary_advances("
                "id,company_id,branch_id,employee_id,amount,disbursed_date,"
                "repayment_start_month,reason,repayment_months,monthly_deduction,"
                "outstanding_balance,status) VALUES("
                ":id,:company_id,:branch_id,:employee_id,500,'2026-04-01','2026-04-01',"
                "'Phase 9F advance',1,500,500,'active')"
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
    admin_a = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=ADMIN_A)
    admin_b = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=ADMIN_B)
    employee = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=EMPLOYEE)
    manager = await resolver.resolve(issuer=seed.SEED_ISSUER, subject="aisha.manager@horizon.test")
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    codec = EmployeeCursorCodec(b"f" * 32)

    async def run(
        principal: AuthorizationPrincipal,
        callback: object,
        *,
        selected: uuid.UUID | None = None,
        ready: bool = True,
    ) -> object:
        async def invoke(connection: AsyncConnection) -> object:
            service = PayrollService(connection, codec)
            if ready:
                service.repository = ReadyPayrollRepository(connection)
            return await callback(service)  # type: ignore[operator]

        return await executor.execute(
            claims=claims(
                ADMIN_A
                if principal.app_user_id == admin_a.app_user_id
                else ADMIN_B
                if principal.app_user_id == admin_b.app_user_id
                else EMPLOYEE
                if principal.app_user_id == employee.app_user_id
                else "aisha.manager@horizon.test"
            ),
            principal=principal,
            selected_admin_branch_id=selected,
            operation=invoke,
        )

    async def create_run(service: PayrollService) -> object:
        await service.repository.create_run(
            run_id=RUN_ID,
            company_id=COMPANY_ID,
            branch_id=BRANCH_ID,
            period=PERIOD,
            payment_date=date(2026, 4, 25),
            sequence="0001",
            routing_code="999000001",
            actor_id=admin_a.app_user_id,
        )
        entries = await service._employee_entries(admin_a, BRANCH_ID, PERIOD, {})
        await service.repository.replace_entries(RUN_ID, entries)
        return await service.detail(admin_a, BRANCH_ID, RUN_ID)

    created = await run(admin_a, create_run, selected=BRANCH_ID)
    assert created.validation_status == "valid"  # type: ignore[attr-defined]
    submitted = await run(
        admin_a,
        lambda service: service.submit(
            admin_a,
            BRANCH_ID,
            RUN_ID,
            PayrollVersionRequest(expected_updated_at=created.updated_at),  # type: ignore[attr-defined]
        ),
        selected=BRANCH_ID,
    )
    await expect_code(
        "operation_not_permitted",
        run(
            admin_a,
            lambda service: service.approve(
                admin_a,
                BRANCH_ID,
                RUN_ID,
                PayrollVersionRequest(expected_updated_at=submitted.updated_at),  # type: ignore[attr-defined]
            ),
            selected=BRANCH_ID,
        ),
    )
    approved = await run(
        admin_b,
        lambda service: service.approve(
            admin_b,
            BRANCH_ID,
            RUN_ID,
            PayrollVersionRequest(expected_updated_at=submitted.updated_at),  # type: ignore[attr-defined]
        ),
        selected=BRANCH_ID,
    )
    generated = await run(
        admin_a,
        lambda service: service.generate(
            admin_a,
            BRANCH_ID,
            RUN_ID,
            PayrollVersionRequest(expected_updated_at=approved.updated_at),  # type: ignore[attr-defined]
        ),
        selected=BRANCH_ID,
    )
    assert generated.run_status == "generated"  # type: ignore[attr-defined]
    history = await run(
        admin_a,
        lambda service: service.approval_history(admin_a, BRANCH_ID, RUN_ID),
        selected=BRANCH_ID,
    )
    history_actions = [item.action for item in history]  # type: ignore[union-attr]
    assert history_actions == ["submitted", "approved"], history_actions
    payslips, _ = await run(
        employee,
        lambda service: service.list_self_payslips(employee, PayslipListQuery()),
        ready=False,
    )
    assert len(payslips) == 1 and payslips[0].employee_name == "Ravi Test"  # type: ignore[arg-type]
    await expect_code(
        "operation_not_permitted",
        run(
            manager,
            lambda service: service.list_self_payslips(manager, PayslipListQuery()),
            ready=False,
        ),
    )

    with migration_engine.begin() as connection:
        assert connection.execute(
            text("SELECT status,payroll_run_id FROM expense_claims WHERE id=:id"),
            {"id": EXPENSE_ID},
        ).one() == ("paid", RUN_ID)
        assert connection.execute(
            text("SELECT status,outstanding_balance FROM salary_advances WHERE id=:id"),
            {"id": ADVANCE_ID},
        ).one() == ("settled", 0)
        assert (
            connection.scalar(
                text("SELECT count(*) FROM payslips WHERE payroll_run_id=:id"), {"id": RUN_ID}
            )
            == generated.employee_count
        )  # type: ignore[attr-defined]
        actions = set(
            connection.scalars(
                text("SELECT action FROM audit_events WHERE entity_id IN (:run,:expense,:advance)"),
                {"run": RUN_ID, "expense": EXPENSE_ID, "advance": ADVANCE_ID},
            )
        )
        assert {
            "payroll_submitted",
            "payroll_approved",
            "payroll_generated",
            "payslips_issued",
            "expense_paid",
            "salary_advance_repayment_recorded",
            "salary_advance_settled",
        } <= actions
        clean_phase_9f(connection)
        clean(connection, rows)
    await runtime_engine.dispose()
    migration_engine.dispose()
    print("Phase 9F lifecycle database verification passed")


if __name__ == "__main__":
    asyncio.run(main())
