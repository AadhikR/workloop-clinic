#!/usr/bin/env python3
"""Exercise the Phase 9G lifecycle through runtime authorization context."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.wps import (
    ComplianceOverrideRequest,
    NafisReplaceRequest,
    WpsEntryRejectRequest,
    WpsEntryVersionRequest,
    WpsSubmitRequest,
    WpsVersionRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.wps import WpsService

COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
RUN_ID = uuid.UUID("9a000000-0000-4000-8000-000000000010")
ENTRY_IDS = tuple(
    uuid.UUID(value)
    for value in (
        "9a000000-0000-4000-8000-000000000011",
        "9a000000-0000-4000-8000-000000000012",
        "9a000000-0000-4000-8000-000000000013",
    )
)
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


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=seed.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def clean_phase_9g(connection: object) -> None:
    execute = connection.execute  # type: ignore[attr-defined]
    execute(
        text(
            "DELETE FROM audit_events WHERE entity_id=:run "
            "OR entity_id=ANY(CAST(:entries AS uuid[])) "
            "OR action IN ('compliance_override_created','nafis_snapshot_replaced')"
        ),
        {"run": RUN_ID, "entries": list(ENTRY_IDS)},
    )
    execute(
        text("DELETE FROM compliance_overrides WHERE payroll_run_id=:run"),
        {"run": RUN_ID},
    )
    execute(
        text("DELETE FROM nafis_reports WHERE company_id=:company AND branch_id=:branch"),
        {"company": COMPANY_ID, "branch": BRANCH_ID},
    )
    execute(text("DELETE FROM payroll_entries WHERE payroll_run_id=:run"), {"run": RUN_ID})
    execute(text("DELETE FROM payroll_runs WHERE id=:run"), {"run": RUN_ID})


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
            "f4b8d2e6a901"
        )
        clean_phase_9g(connection)
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        employees = list(
            connection.execute(
                text(
                    "SELECT id,mol_id FROM employees WHERE company_id=:company "
                    "AND branch_id=:branch AND mol_id<>'' AND bank_routing_code<>'' AND iban<>'' "
                    "ORDER BY mol_id,id LIMIT 3"
                ),
                {"company": COMPANY_ID, "branch": BRANCH_ID},
            ).mappings()
        )
        assert len(employees) == 3
        admin_id = seed.ADMIN_APP_USER[seed.HORIZON]
        connection.execute(
            text(
                """
INSERT INTO payroll_runs(
 id,company_id,branch_id,period,payment_date,sequence_no,scr_bank_routing_code,
 description,status,run_by_app_user_id,total_disbursed,employee_count,wps_status,
 approval_status,submitted_for_approval_at,submitted_by_app_user_id,
 approved_by_app_user_id,approved_at,source_snapshot_digest)
VALUES(:id,:company,:branch,:period,'2026-04-25','0001','999000001','Phase 9G',
 'generated',:actor,23439.46,3,'draft','approved',statement_timestamp(),:actor,
 :actor,statement_timestamp(),:digest)
"""
            ),
            {
                "id": RUN_ID,
                "company": COMPANY_ID,
                "branch": BRANCH_ID,
                "period": PERIOD,
                "actor": admin_id,
                "digest": "a" * 64,
            },
        )
        values = (
            (Decimal("1000.50"), Decimal("200.50")),
            (Decimal("12000.00"), Decimal("5238.46")),
            (Decimal("5000.00"), Decimal("0.00")),
        )
        for entry_id, employee, (basic, variable) in zip(ENTRY_IDS, employees, values, strict=True):
            connection.execute(
                text(
                    """
INSERT INTO payroll_entries(
 id,payroll_run_id,company_id,branch_id,employee_id,basic_salary,variable_allowance,
 additional_allowances,deductions,source_snapshot,excluded,wps_payment_status)
VALUES(:id,:run,:company,:branch,:employee,:basic,:variable,'[]','[]',
 CAST(:snapshot AS jsonb),false,'pending')
"""
                ),
                {
                    "id": entry_id,
                    "run": RUN_ID,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": employee["id"],
                    "basic": basic,
                    "variable": variable,
                    "snapshot": json.dumps({"eligibleDays": 30}),
                },
            )

    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD"), pool_size=5
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine, issuer=seed.SEED_ISSUER, timeout_seconds=5
    )
    admin = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=ADMIN)
    manager = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=MANAGER)
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    codec = EmployeeCursorCodec(b"g" * 32)

    async def run(
        principal: AuthorizationPrincipal,
        callback: object,
        *,
        selected: uuid.UUID | None = BRANCH_ID,
    ) -> object:
        async def invoke(connection: AsyncConnection) -> object:
            return await callback(WpsService(connection, codec))  # type: ignore[operator]

        subject = ADMIN if principal.app_user_id == admin.app_user_id else MANAGER
        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=selected,
            operation=invoke,
        )

    await expect_code(
        "operation_not_permitted",
        run(
            manager,
            lambda service: service.get_wps(manager, BRANCH_ID, RUN_ID),
            selected=None,
        ),
    )
    await expect_code(
        "resource_not_found",
        run(
            admin,
            lambda service: service.get_wps(admin, OTHER_BRANCH_ID, RUN_ID),
            selected=OTHER_BRANCH_ID,
        ),
    )

    wps = await run(admin, lambda service: service.get_wps(admin, BRANCH_ID, RUN_ID))
    full = await run(admin, lambda service: service.sif_input(admin, BRANCH_ID, RUN_ID))
    assert [item.total_pay for item in full.entries] == [1202, 17238, 5000]  # type: ignore[attr-defined]
    assert full.header.total_integer_pay == 23440  # type: ignore[attr-defined]
    assert [item.employee_mol_id for item in full.entries] == sorted(  # type: ignore[attr-defined]
        item.employee_mol_id
        for item in full.entries  # type: ignore[attr-defined]
    )
    wps = await run(
        admin,
        lambda service: service.record_sif_projection(
            admin,
            BRANCH_ID,
            RUN_ID,
            WpsVersionRequest(expected_updated_at=wps.updated_at),  # type: ignore[attr-defined]
        ),
    )
    wps = await run(
        admin,
        lambda service: service.submit(
            admin,
            BRANCH_ID,
            RUN_ID,
            WpsSubmitRequest(
                expected_updated_at=wps.updated_at,
                reference_number="BANK-FULL",  # type: ignore[attr-defined]
            ),
        ),
    )

    first = wps.entries[0]  # type: ignore[attr-defined]
    concurrent = await asyncio.gather(
        run(
            admin,
            lambda service: service.mark_entry_paid(
                admin,
                BRANCH_ID,
                RUN_ID,
                first.id,
                WpsEntryVersionRequest(expected_updated_at=first.updated_at),
            ),
        ),
        run(
            admin,
            lambda service: service.mark_entry_paid(
                admin,
                BRANCH_ID,
                RUN_ID,
                first.id,
                WpsEntryVersionRequest(expected_updated_at=first.updated_at),
            ),
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(item, Exception) for item in concurrent) == 1
    denied = next(item for item in concurrent if isinstance(item, Exception))
    assert isinstance(denied, ServiceExecutionError) and denied.code == "stale_financial_state"
    wps = next(item for item in concurrent if not isinstance(item, Exception))

    second = wps.entries[1]  # type: ignore[attr-defined]
    wps = await run(
        admin,
        lambda service: service.mark_entry_paid(
            admin,
            BRANCH_ID,
            RUN_ID,
            second.id,
            WpsEntryVersionRequest(expected_updated_at=second.updated_at),
        ),
    )
    rejected = wps.entries[2]  # type: ignore[attr-defined]
    stale_timestamp = rejected.updated_at
    wps = await run(
        admin,
        lambda service: service.reject_entry(
            admin,
            BRANCH_ID,
            RUN_ID,
            rejected.id,
            WpsEntryRejectRequest(
                expected_updated_at=rejected.updated_at,
                reason="Synthetic bank rejection",
            ),
        ),
    )
    assert wps.status == "partial_rejection"  # type: ignore[attr-defined]
    await expect_code(
        "stale_financial_state",
        run(
            admin,
            lambda service: service.mark_entry_paid(
                admin,
                BRANCH_ID,
                RUN_ID,
                rejected.id,
                WpsEntryVersionRequest(expected_updated_at=stale_timestamp),
            ),
        ),
    )
    correction = await run(
        admin,
        lambda service: service.sif_input(admin, BRANCH_ID, RUN_ID, "rejected"),
    )
    assert len(correction.entries) == 1  # type: ignore[attr-defined]
    assert correction.entries[0].total_pay == 5000  # type: ignore[attr-defined]
    assert correction.digest != full.digest  # type: ignore[attr-defined]
    wps = await run(
        admin,
        lambda service: service.record_sif_projection(
            admin,
            BRANCH_ID,
            RUN_ID,
            WpsVersionRequest(expected_updated_at=wps.updated_at),  # type: ignore[attr-defined]
        ),
    )
    assert [item.payment_status for item in wps.entries] == [  # type: ignore[attr-defined]
        "paid",
        "paid",
        "pending",
    ]
    wps = await run(
        admin,
        lambda service: service.submit(
            admin,
            BRANCH_ID,
            RUN_ID,
            WpsSubmitRequest(
                expected_updated_at=wps.updated_at,
                reference_number="BANK-CORRECTED",  # type: ignore[attr-defined]
            ),
        ),
    )
    pending = wps.entries[2]  # type: ignore[attr-defined]
    wps = await run(
        admin,
        lambda service: service.mark_entry_paid(
            admin,
            BRANCH_ID,
            RUN_ID,
            pending.id,
            WpsEntryVersionRequest(expected_updated_at=pending.updated_at),
        ),
    )
    wps = await run(
        admin,
        lambda service: service.confirm(
            admin,
            BRANCH_ID,
            RUN_ID,
            WpsVersionRequest(expected_updated_at=wps.updated_at),  # type: ignore[attr-defined]
        ),
    )
    assert wps.status == "confirmed"  # type: ignore[attr-defined]

    override = await run(
        admin,
        lambda service: service.create_compliance_override(
            admin,
            BRANCH_ID,
            RUN_ID,
            ComplianceOverrideRequest(
                rule_code="passport_expired",
                reason="Synthetic compliance evidence reviewed",
                payroll_entry_id=None,
            ),
        ),
    )
    assert override.rule_code == "passport_expired"  # type: ignore[attr-defined]

    first_snapshot = await run(
        admin,
        lambda service: service.replace_nafis_snapshot(
            admin, BRANCH_ID, PERIOD, NafisReplaceRequest()
        ),
    )
    second_snapshot = await run(
        admin,
        lambda service: service.replace_nafis_snapshot(
            admin,
            BRANCH_ID,
            PERIOD,
            NafisReplaceRequest(expected_generated_at=first_snapshot.generated_at),  # type: ignore[attr-defined]
        ),
    )
    assert second_snapshot.source_version == first_snapshot.source_version  # type: ignore[attr-defined]
    assert second_snapshot.emirati_count == first_snapshot.emirati_count  # type: ignore[attr-defined]
    assert second_snapshot.qualifying_wage_total == first_snapshot.qualifying_wage_total  # type: ignore[attr-defined]

    with migration_engine.begin() as connection:
        changed_employee = connection.scalar(
            text(
                "SELECT id FROM employees WHERE company_id=:company AND branch_id=:branch "
                "AND nationality<>'United Arab Emirates' ORDER BY id LIMIT 1"
            ),
            {"company": COMPANY_ID, "branch": BRANCH_ID},
        )
        assert changed_employee is not None
        connection.execute(
            text(
                "UPDATE employees SET nationality='United Arab Emirates',"
                "updated_at=statement_timestamp() WHERE id=:id"
            ),
            {"id": changed_employee},
        )
    changed_snapshot = await run(
        admin,
        lambda service: service.replace_nafis_snapshot(
            admin,
            BRANCH_ID,
            PERIOD,
            NafisReplaceRequest(expected_generated_at=second_snapshot.generated_at),  # type: ignore[attr-defined]
        ),
    )
    assert changed_snapshot.source_version != second_snapshot.source_version  # type: ignore[attr-defined]
    assert changed_snapshot.emirati_count == second_snapshot.emirati_count + 1  # type: ignore[attr-defined]

    with migration_engine.begin() as connection:
        actions = set(
            connection.scalars(
                text(
                    "SELECT action FROM audit_events WHERE entity_id=:run "
                    "OR entity_id=ANY(CAST(:entries AS uuid[])) "
                    "OR action IN ('compliance_override_created','nafis_snapshot_replaced')"
                ),
                {"run": RUN_ID, "entries": list(ENTRY_IDS)},
            )
        )
        assert {
            "sif_projection_recorded",
            "payroll_wps_changed",
            "wps_entry_paid",
            "wps_entry_rejected",
            "compliance_override_created",
            "nafis_snapshot_replaced",
        } <= actions
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM payroll_entries WHERE payroll_run_id=:run "
                    "AND wps_payment_status='paid'"
                ),
                {"run": RUN_ID},
            )
            == 3
        )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM compliance_overrides WHERE payroll_run_id=:run"),
                {"run": RUN_ID},
            )
            == 1
        )
        clean_phase_9g(connection)
        clean(connection, rows)
    await runtime_engine.dispose()
    migration_engine.dispose()
    print("Phase 9G WPS and Nafis lifecycle verification passed")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "cleanup":
        cleanup_engine = create_engine(
            database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
        )
        with cleanup_engine.begin() as cleanup_connection:
            clean_phase_9g(cleanup_connection)
        cleanup_engine.dispose()
        print("Phase 9G synthetic lifecycle rows removed")
    else:
        asyncio.run(main())
