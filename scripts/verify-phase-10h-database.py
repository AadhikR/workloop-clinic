#!/usr/bin/env python3
"""Exercise Phase 10H roster publication and payroll projection against PostgreSQL."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
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
from app.repositories.payroll import PayrollRepository
from app.repositories.roster_publication import RosterPublicationRepository
from app.schemas.roster_publication import (
    RosterActualHoursRequest,
    RosterOvertimeApprovalRequest,
    RosterPublishRequest,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.roster_publication import RosterPublicationService

ADMIN = "hr.admin@horizon.test"
RAVI = "ravi.employee@horizon.test"
MARIA = "maria.employee@horizon.test"
COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
RAVI_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
MARIA_ID = uuid.UUID("21000000-0000-4000-8000-000000000003")
SHIFT_ID = seed.derive("shifts", seed.HORIZON, "dubai", None, "M")
PERIOD = "2026-12"
DAY = "2026-12-03"
PREFIX = "Phase 10H verification"


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
    assignments = [uuid.uuid4(), uuid.uuid4()]
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "b4d7f9a2c816"
        )
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "DELETE FROM public.roster_assignments WHERE notes LIKE :prefix"
            ),
            {"prefix": f"{PREFIX}%"},
        )
        connection.execute(
            text(
                "INSERT INTO public.roster_assignments("
                "id,company_id,branch_id,employee_id,shift_id,date,published,"
                "planned_hours,notes) VALUES "
                "(:ravi,:company,:branch,:ravi_employee,:shift,:day,false,8,:ravi_note),"
                "(:maria,:company,:branch,:maria_employee,:shift,:day,false,8,:maria_note)"
            ),
            {
                "ravi": assignments[0],
                "maria": assignments[1],
                "company": COMPANY_ID,
                "branch": BRANCH_ID,
                "ravi_employee": RAVI_ID,
                "maria_employee": MARIA_ID,
                "shift": SHIFT_ID,
                "day": DAY,
                "ravi_note": f"{PREFIX} Ravi",
                "maria_note": f"{PREFIX} Maria",
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
        deadline_seconds=30,
    )
    principals = {
        subject: await resolver.resolve(issuer=seed.SEED_ISSUER, subject=subject)
        for subject in (ADMIN, RAVI, MARIA)
    }

    async def run_admin(
        callback: Callable[[RosterPublicationService, AuthorizationPrincipal], Awaitable[Any]],
        *,
        branch_id: uuid.UUID = BRANCH_ID,
    ) -> Any:
        principal = principals[ADMIN]

        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(
                RosterPublicationService(RosterPublicationRepository(connection)), principal
            )

        return await executor.execute(
            claims=claims(ADMIN),
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=invoke,
        )

    async def run_staff(
        subject: str,
        callback: Callable[[RosterPublicationService, AuthorizationPrincipal], Awaitable[Any]],
    ) -> Any:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(
                RosterPublicationService(RosterPublicationRepository(connection)), principal
            )

        return await executor.execute(
            claims=claims(subject), principal=principal, operation=invoke
        )

    async def payroll_projection() -> list[Any] | None:
        principal = principals[ADMIN]

        async def invoke(connection: AsyncConnection) -> list[Any] | None:
            return await PayrollRepository(connection).roster_input_projection(
                company_id=COMPANY_ID, branch_id=BRANCH_ID, period=PERIOD
            )

        return await executor.execute(
            claims=claims(ADMIN),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID,
            operation=invoke,
        )

    exact = sorted(
        [{"id": str(value), "expectedVersion": 1} for value in assignments],
        key=lambda item: item["id"],
    )
    publish_request = RosterPublishRequest.model_validate(
        {"assignments": exact, "expectedSourceVersion": None}
    )
    try:
        initial = await run_admin(
            lambda service, actor: service.detail(actor, BRANCH_ID, PERIOD)
        )
        assert initial.id is None and initial.status == "draft" and initial.version == 0
        with migration_engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM public.roster_months")) == 0

        await expect_code(
            "state_conflict",
            run_admin(
                lambda service, actor: service.publish(
                    actor,
                    BRANCH_ID,
                    PERIOD,
                    RosterPublishRequest.model_validate(
                        {"assignments": exact[:1], "expectedSourceVersion": None}
                    ),
                )
            ),
        )
        await expect_code(
            "roster_publication_not_ready",
            run_admin(
                lambda service, actor: service.publish(
                    actor, BRANCH_ID, PERIOD, publish_request
                )
            ),
        )
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE public.branches SET enable_staffing_rules=false "
                    "WHERE id=:branch AND company_id=:company"
                ),
                {"branch": BRANCH_ID, "company": COMPANY_ID},
            )
            connection.execute(
                text(
                    "CREATE FUNCTION public.phase10h_verify_reject_version() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced version failure'; END $$"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_phase10h_verify_reject_version BEFORE INSERT "
                    "ON public.roster_publication_versions FOR EACH ROW "
                    "EXECUTE FUNCTION public.phase10h_verify_reject_version()"
                )
            )
        try:
            await run_admin(
                lambda service, actor: service.publish(
                    actor, BRANCH_ID, PERIOD, publish_request
                )
            )
        except DBAPIError:
            pass
        else:
            raise AssertionError("forced publication failure did not roll back")
        finally:
            with migration_engine.begin() as connection:
                connection.execute(
                    text(
                        "DROP TRIGGER IF EXISTS trg_phase10h_verify_reject_version "
                        "ON public.roster_publication_versions"
                    )
                )
                connection.execute(
                    text("DROP FUNCTION IF EXISTS public.phase10h_verify_reject_version()")
                )
        with migration_engine.connect() as connection:
            state = connection.execute(
                text(
                    "SELECT published,version FROM public.roster_assignments "
                    "WHERE id=ANY(:ids) ORDER BY id"
                ),
                {"ids": assignments},
            ).all()
            assert state == [(False, 1), (False, 1)]

        published = await run_admin(
            lambda service, actor: service.publish(
                actor, BRANCH_ID, PERIOD, publish_request
            )
        )
        assert published.status == "published" and published.version == 1
        assert published.record_count == 2 and published.source_version is not None
        await expect_code(
            "state_conflict",
            run_admin(
                lambda service, actor: service.publish(
                    actor, BRANCH_ID, PERIOD, publish_request
                )
            ),
        )
        assert await payroll_projection() is None

        actual_ravi = await run_admin(
            lambda service, actor: service.record_actual_hours(
                actor,
                BRANCH_ID,
                PERIOD,
                assignments[0],
                RosterActualHoursRequest.model_validate(
                    {
                        "actualHours": "12.00",
                        "evidenceSource": "manager_attestation",
                        "reason": "Confirmed roster timesheet",
                        "expectedSourceVersion": published.source_version,
                    }
                ),
            )
        )
        assert actual_ravi.version == 2
        actual_maria = await run_admin(
            lambda service, actor: service.record_actual_hours(
                actor,
                BRANCH_ID,
                PERIOD,
                assignments[1],
                RosterActualHoursRequest.model_validate(
                    {
                        "actualHours": "8.00",
                        "evidenceSource": "timesheet",
                        "reason": "Confirmed roster timesheet",
                        "expectedSourceVersion": actual_ravi.source_version,
                    }
                ),
            )
        )
        assert actual_maria.version == 3 and await payroll_projection() is None

        approved = await run_admin(
            lambda service, actor: service.approve_overtime(
                actor,
                BRANCH_ID,
                PERIOD,
                assignments[0],
                RosterOvertimeApprovalRequest.model_validate(
                    {
                        "reason": "Approved roster overtime",
                        "expectedSourceVersion": actual_maria.source_version,
                        "attendanceSourceIds": [],
                    }
                ),
            )
        )
        assert approved.version == 4
        projection = await payroll_projection()
        assert projection is not None and len(projection) == 2
        ravi = next(item for item in projection if item["employee_id"] == RAVI_ID)
        assert Decimal(ravi["actual_hours"]) == Decimal("12.00")
        assert Decimal(ravi["overtime_hours"]) == Decimal("4.00")
        assert Decimal(ravi["overtime_amount"]) == Decimal("288.46")
        assert ravi["source_version"] == approved.source_version
        assert ravi["source_row_ids"] == [assignments[0]]

        ravi_schedule = await run_staff(
            RAVI, lambda service, actor: service.personal_schedule(actor, PERIOD)
        )
        maria_schedule = await run_staff(
            MARIA, lambda service, actor: service.personal_schedule(actor, PERIOD)
        )
        assert [item.employee_id for item in ravi_schedule] == [RAVI_ID]
        assert [item.employee_id for item in maria_schedule] == [MARIA_ID]
        assert ravi_schedule[0].overtime_hours == Decimal("4.00")
        colleagues = await run_staff(
            RAVI,
            lambda service, actor: service.colleagues(
                actor, ravi_schedule[0].date
            ),
        )
        assert [item.employee_id for item in colleagues] == [MARIA_ID]

        other = await run_admin(
            lambda service, actor: service.detail(actor, OTHER_BRANCH_ID, PERIOD),
            branch_id=OTHER_BRANCH_ID,
        )
        assert other.id is None and other.status == "draft" and other.record_count == 0
        with migration_engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM public.roster_months")) == 1

        async def mutate_version(connection: AsyncConnection) -> None:
            await connection.execute(
                text(
                    "UPDATE public.roster_publication_versions SET reason='tampered' "
                    "WHERE id=:id"
                ),
                {"id": approved.current_version_id},
            )

        try:
            await executor.execute(
                claims=claims(ADMIN),
                principal=principals[ADMIN],
                selected_admin_branch_id=BRANCH_ID,
                operation=mutate_version,
            )
        except DBAPIError:
            pass
        else:
            raise AssertionError("append-only publication version accepted an update")

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE public.roster_assignments SET planned_hours=9 "
                    "WHERE id=:id"
                ),
                {"id": assignments[0]},
            )
        assert await payroll_projection() is None
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE public.roster_assignments SET planned_hours=8 "
                    "WHERE id=:id"
                ),
                {"id": assignments[0]},
            )
        assert await payroll_projection() is not None
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE public.roster_months SET status='draft',version=0,"
                    "current_version_id=NULL,source_version=NULL,published_at=NULL,"
                    "published_by_app_user_id=NULL"
                )
            )
            connection.execute(text("DELETE FROM public.roster_publication_memberships"))
            connection.execute(text("DELETE FROM public.roster_overtime_approvals"))
            connection.execute(text("DELETE FROM public.roster_actual_hours_evidence"))
            connection.execute(text("DELETE FROM public.roster_publication_versions"))
            connection.execute(text("DELETE FROM public.roster_months"))
            connection.execute(
                text("DELETE FROM public.roster_assignments WHERE id=ANY(:ids)"),
                {"ids": assignments},
            )
            connection.execute(
                text(
                    "UPDATE public.branches SET enable_staffing_rules=true "
                    "WHERE id=:branch AND company_id=:company"
                ),
                {"branch": BRANCH_ID, "company": COMPANY_ID},
            )
            clean(connection, rows)
        migration_engine.dispose()

    print("Phase 10H roster publication and payroll projection verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
