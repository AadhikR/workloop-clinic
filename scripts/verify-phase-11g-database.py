#!/usr/bin/env python3
"""Exercise the Phase 11G offboarding and final-settlement boundary."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.offboarding import (
    OffboardingTaskUpdateRequest,
    SettlementCompleteRequest,
    SettlementInputs,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.offboarding import OffboardingService

ADMIN = "hr.admin@horizon.test"
REVIEWER = "settlement.reviewer@horizon.test"
BRANCH_ID = seed.BRANCH_DXB
REVIEWER_ID = uuid.UUID("10000000-0000-4000-8000-000000000099")
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000099")
RUN_ID = uuid.UUID("41000000-0000-4000-8000-000000000099")
PAYSLIP_ID = uuid.UUID("42000000-0000-4000-8000-000000000099")
BALANCE_ID = uuid.UUID("71000000-0000-4000-8000-000000000099")
ADVANCE_ID = uuid.UUID("51000000-0000-4000-8000-000000000099")


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
        assert error.code == code
        return
    raise AssertionError(f"expected {code}")


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    seed_rows = build_rows()
    business_date = datetime.now(ZoneInfo("Asia/Dubai")).date()
    period = business_date.strftime("%Y-%m")
    with migration_engine.begin() as connection:
        apply_rows(connection, seed_rows)
        validate(connection, seed_rows)
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "d6f8a0c2e4b7"
        )
        annual_type_id = connection.execute(
            text(
                "SELECT id FROM leave_types WHERE company_id=:company_id "
                "AND branch_id=:branch_id AND code='ANNUAL'"
            ),
            {"company_id": seed.COMPANY_ID[seed.HORIZON], "branch_id": BRANCH_ID},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO app_users(id,identity_issuer,identity_subject,status) "
                "VALUES(:id,:issuer,:subject,'active')"
            ),
            {"id": REVIEWER_ID, "issuer": seed.SEED_ISSUER, "subject": REVIEWER},
        )
        connection.execute(
            text(
                "INSERT INTO user_profiles(app_user_id,company_id,role) "
                "VALUES(:id,:company_id,'admin')"
            ),
            {"id": REVIEWER_ID, "company_id": seed.COMPANY_ID[seed.HORIZON]},
        )
        connection.execute(
            text(
                """
INSERT INTO employees(
 id,company_id,branch_id,emp_no,name,mol_id,work_email,nationality,
 employment_start_date,basic_salary,employment_status,active,visa_type,work_location_type)
VALUES(:id,:company_id,:branch_id,'H-DXB-099','Settlement Golden Employee',
 '90000000000099','settlement.employee@horizon.test','India',:start_date,
 10000.00,'Active',true,'Exempt','Mainland')
"""
            ),
            {
                "id": EMPLOYEE_ID,
                "company_id": seed.COMPANY_ID[seed.HORIZON],
                "branch_id": BRANCH_ID,
                "start_date": business_date.replace(year=business_date.year - 6),
            },
        )
        connection.execute(
            text(
                """
INSERT INTO payroll_runs(
 id,company_id,branch_id,period,status,approval_status,approved_by_app_user_id,
 approved_at,submitted_by_app_user_id,submitted_for_approval_at)
VALUES(:id,:company_id,:branch_id,:period,'generated','approved',:admin,
 statement_timestamp(),:admin,statement_timestamp())
"""
            ),
            {
                "id": RUN_ID,
                "company_id": seed.COMPANY_ID[seed.HORIZON],
                "branch_id": BRANCH_ID,
                "period": period,
                "admin": seed.ADMIN_APP_USER[seed.HORIZON],
            },
        )
        connection.execute(
            text(
                "INSERT INTO payslips(id,company_id,branch_id,payroll_run_id,employee_id,period,"
                "gross_pay,net_pay) VALUES(:id,:company_id,:branch_id,:run_id,:employee_id,"
                ":period,12500.00,12500.00)"
            ),
            {
                "id": PAYSLIP_ID,
                "company_id": seed.COMPANY_ID[seed.HORIZON],
                "branch_id": BRANCH_ID,
                "run_id": RUN_ID,
                "employee_id": EMPLOYEE_ID,
                "period": period,
            },
        )
        connection.execute(
            text(
                "INSERT INTO leave_balances(id,company_id,branch_id,employee_id,leave_type_id,"
                "leave_year,entitled_days,accrued_days,remaining_days) VALUES("
                ":id,:company_id,:branch_id,:employee_id,:type_id,:year,30.00,30.00,7.50)"
            ),
            {
                "id": BALANCE_ID,
                "company_id": seed.COMPANY_ID[seed.HORIZON],
                "branch_id": BRANCH_ID,
                "employee_id": EMPLOYEE_ID,
                "type_id": annual_type_id,
                "year": business_date.year,
            },
        )
        connection.execute(
            text(
                "INSERT INTO salary_advances(id,company_id,branch_id,employee_id,amount,"
                "repayment_start_month,reason,repayment_months,monthly_deduction,"
                "outstanding_balance,status,disbursed_date) VALUES("
                ":id,:company_id,:branch_id,:employee_id,333.34,date_trunc('month',CURRENT_DATE),"
                "'Synthetic settlement balance',1,333.34,333.34,'active',CURRENT_DATE)"
            ),
            {
                "id": ADVANCE_ID,
                "company_id": seed.COMPANY_ID[seed.HORIZON],
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
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    admin = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=ADMIN)
    reviewer = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=REVIEWER)
    cursor_codec = EmployeeCursorCodec(b"phase11g-settlement-verifier-key")

    async def run(principal: object, subject: str, operation: object):
        return await executor.execute(
            claims=claims(subject),
            principal=principal,  # type: ignore[arg-type]
            selected_admin_branch_id=BRANCH_ID,
            operation=operation,  # type: ignore[arg-type]
        )

    checklist = await run(
        admin,
        ADMIN,
        lambda connection: OffboardingService(connection, cursor_codec).initialize(
            admin, BRANCH_ID, EMPLOYEE_ID
        ),
    )
    replay = await run(
        admin,
        ADMIN,
        lambda connection: OffboardingService(connection, cursor_codec).initialize(
            admin, BRANCH_ID, EMPLOYEE_ID
        ),
    )
    assert replay.id == checklist.id and len(checklist.tasks) == 4

    for task in checklist.tasks:
        checklist = await run(
            admin,
            ADMIN,
            lambda connection, task=task, checklist=checklist: OffboardingService(
                connection, cursor_codec
            ).update_task(
                admin,
                BRANCH_ID,
                checklist.id,
                task.id,
                OffboardingTaskUpdateRequest(
                    expected_checklist_updated_at=checklist.updated_at,
                    expected_task_updated_at=task.updated_at,
                    notes="Synthetic clearance complete",
                ),
                complete=True,
            ),
        )

    inputs = SettlementInputs(expected_checklist_updated_at=checklist.updated_at)
    preview = await run(
        admin,
        ADMIN,
        lambda connection: OffboardingService(connection, cursor_codec).preview(
            admin, BRANCH_ID, checklist.id, inputs
        ),
    )
    assert preview.final_salary == Decimal("12500.00")
    assert preview.leave_encashment == Decimal("2500.00")
    assert preview.advance_deduction == Decimal("333.34")
    complete_request = SettlementCompleteRequest(
        expected_checklist_updated_at=checklist.updated_at,
        expected_source_digest=preview.source_digest,
        termination_reason="Synthetic completed offboarding",
    )
    await expect_code(
        "offboarding_blocked",
        run(
            admin,
            ADMIN,
            lambda connection: OffboardingService(connection, cursor_codec).complete(
                admin, BRANCH_ID, checklist.id, complete_request
            ),
        ),
    )
    settlement = await run(
        reviewer,
        REVIEWER,
        lambda connection: OffboardingService(connection, cursor_codec).complete(
            reviewer, BRANCH_ID, checklist.id, complete_request
        ),
    )
    assert settlement.source_digest == preview.source_digest
    assert settlement.net_amount == preview.net_amount

    with migration_engine.connect() as connection:
        state = connection.execute(
            text(
                "SELECT employee.employment_status,employee.active,advance.status,"
                "advance.outstanding_balance,checklist.status,settlement.source_digest "
                "FROM employees employee JOIN salary_advances advance "
                "ON advance.employee_id=employee.id "
                "JOIN offboarding_checklists checklist ON checklist.employee_id=employee.id "
                "JOIN final_settlements settlement ON settlement.id=checklist.final_settlement_id "
                "WHERE employee.id=:id"
            ),
            {"id": EMPLOYEE_ID},
        ).one()
        assert state[:5] == ("Terminated", False, "settled", Decimal("0.00"), "completed")
        assert state.source_digest == preview.source_digest
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE entity_id IN (:checklist,:settlement) "
                    "AND action IN ('offboarding_initialized','offboarding_task_completed',"
                    "'final_settlement_completed','offboarding_completed')"
                ),
                {"checklist": checklist.id, "settlement": settlement.id},
            ).scalar_one()
            == 7
        )

    with migration_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM audit_events WHERE company_id=:company_id"),
            {"company_id": seed.COMPANY_ID[seed.HORIZON]},
        )
        connection.execute(
            text("DELETE FROM idempotency_records WHERE company_id=:company_id"),
            {"company_id": seed.COMPANY_ID[seed.HORIZON]},
        )
        connection.execute(
            text(
                "UPDATE offboarding_checklists SET final_settlement_id=NULL WHERE employee_id=:id"
            ),
            {"id": EMPLOYEE_ID},
        )
        connection.execute(
            text("DELETE FROM final_settlements WHERE employee_id=:id"), {"id": EMPLOYEE_ID}
        )
        connection.execute(
            text(
                "DELETE FROM offboarding_tasks WHERE checklist_id IN "
                "(SELECT id FROM offboarding_checklists WHERE employee_id=:id)"
            ),
            {"id": EMPLOYEE_ID},
        )
        connection.execute(
            text("DELETE FROM offboarding_checklists WHERE employee_id=:id"), {"id": EMPLOYEE_ID}
        )
        connection.execute(
            text("DELETE FROM advance_repayments WHERE advance_id=:id"), {"id": ADVANCE_ID}
        )
        connection.execute(text("DELETE FROM salary_advances WHERE id=:id"), {"id": ADVANCE_ID})
        connection.execute(text("DELETE FROM leave_balances WHERE id=:id"), {"id": BALANCE_ID})
        connection.execute(text("DELETE FROM payslips WHERE id=:id"), {"id": PAYSLIP_ID})
        connection.execute(text("DELETE FROM payroll_runs WHERE id=:id"), {"id": RUN_ID})
        connection.execute(
            text("DELETE FROM employee_job_history WHERE employee_id=:id"), {"id": EMPLOYEE_ID}
        )
        connection.execute(text("DELETE FROM employees WHERE id=:id"), {"id": EMPLOYEE_ID})
        connection.execute(
            text("DELETE FROM user_profiles WHERE app_user_id=:id"), {"id": REVIEWER_ID}
        )
        connection.execute(text("DELETE FROM app_users WHERE id=:id"), {"id": REVIEWER_ID})
        clean(connection, seed_rows)

    await runtime_engine.dispose()
    migration_engine.dispose()
    print("Phase 11G offboarding and final-settlement database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
