#!/usr/bin/env python3
"""Exercise Phase 10G roster drafts and compliance gates against PostgreSQL."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
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
from app.repositories.roster import RosterRepository
from app.schemas.roster import (
    RosterComplianceOverrideRequest,
    RosterDraftCreateRequest,
    RosterDraftReplaceRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.roster import RosterService

ADMIN = "hr.admin@horizon.test"
COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
OTHER_EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000001")
SHIFT_ID = seed.derive("shifts", seed.HORIZON, "dubai", None, "M")
PERIOD = "2026-10"
PREFIX = "Phase 10G verification"


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
    leave_id = uuid.uuid4()
    leave_override_id = uuid.uuid4()
    swap_id = uuid.uuid4()
    created_ids: list[uuid.UUID] = []
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "b2d4f6a8c0e5"
        )
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "DELETE FROM public.compliance_overrides WHERE override_type='roster_publish' "
                "AND roster_month=:period"
            ),
            {"period": PERIOD},
        )
        connection.execute(
            text("DELETE FROM public.roster_assignments WHERE notes LIKE :prefix"),
            {"prefix": f"{PREFIX}%"},
        )
        connection.execute(
            text(
                "INSERT INTO public.leave_requests"
                "(id,company_id,branch_id,employee_id,leave_type_id,start_date,end_date,"
                "days_requested,status,reason,approved_by_app_user_id,approved_at) "
                "SELECT :id,:company,:branch,:employee,id,'2026-10-05','2026-10-05',"
                "1,'Approved',:reason,:actor,now() FROM public.leave_types "
                "WHERE company_id=:company AND branch_id=:branch AND code='ANNUAL'"
            ),
            {
                "id": leave_id,
                "company": COMPANY_ID,
                "branch": BRANCH_ID,
                "employee": EMPLOYEE_ID,
                "reason": PREFIX,
                "actor": seed.ADMIN_APP_USER[seed.HORIZON],
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
        deadline_seconds=20,
    )
    principal = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=ADMIN)
    codec = EmployeeCursorCodec(b"g" * 32)

    async def run(
        callback: Callable[[RosterService, AuthorizationPrincipal], Awaitable[Any]],
        *,
        branch_id: uuid.UUID = BRANCH_ID,
    ) -> Any:
        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(RosterService(RosterRepository(connection), codec), principal)

        return await executor.execute(
            claims=claims(),
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=invoke,
        )

    def request(day: str, notes: str) -> RosterDraftCreateRequest:
        return RosterDraftCreateRequest.model_validate(
            {
                "employeeId": str(EMPLOYEE_ID),
                "shiftId": str(SHIFT_ID),
                "date": day,
                "plannedHours": "8.00",
                "notes": f"{PREFIX} {notes}",
            }
        )

    try:
        created = await run(
            lambda service, actor: service.create(
                actor, BRANCH_ID, PERIOD, request("2026-10-04", "created")
            )
        )
        created_ids.append(created.id)
        assert created.version == 1 and not created.published and created.planned_hours == 8

        await expect_code(
            "state_conflict",
            run(
                lambda service, actor: service.create(
                    actor, BRANCH_ID, PERIOD, request("2026-10-04", "duplicate")
                )
            ),
        )
        await expect_code(
            "state_conflict",
            run(
                lambda service, actor: service.create(
                    actor, BRANCH_ID, PERIOD, request("2026-10-05", "leave conflict")
                )
            ),
        )
        await expect_code(
            "resource_not_found",
            run(
                lambda service, actor: service.create(
                    actor, OTHER_BRANCH_ID, PERIOD, request("2026-10-06", "wrong branch")
                ),
                branch_id=OTHER_BRANCH_ID,
            ),
        )

        replacement = RosterDraftReplaceRequest.model_validate(
            {
                **request("2026-10-06", "replaced").model_dump(mode="json", by_alias=True),
                "expectedVersion": 1,
            }
        )
        replaced = await run(
            lambda service, actor: service.replace(
                actor, BRANCH_ID, PERIOD, created.id, replacement
            )
        )
        assert replaced.version == 2 and replaced.date.isoformat() == "2026-10-06"
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.leave_requests"
                    "(id,company_id,branch_id,employee_id,leave_type_id,start_date,end_date,"
                    "days_requested,status,reason,manager_approved_by_app_user_id,"
                    "manager_approved_at) "
                    "SELECT :id,:company,:branch,:employee,id,'2026-10-06','2026-10-06',"
                    "1,'ManagerApproved',:reason,:actor,now() FROM public.leave_types "
                    "WHERE company_id=:company AND branch_id=:branch AND code='ANNUAL'"
                ),
                {
                    "id": leave_override_id,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": EMPLOYEE_ID,
                    "reason": f"{PREFIX} override",
                    "actor": seed.ADMIN_APP_USER[seed.HORIZON],
                },
            )
        await expect_code(
            "state_conflict",
            run(
                lambda service, actor: service.replace(
                    actor, BRANCH_ID, PERIOD, created.id, replacement
                )
            ),
        )

        concurrent_day = "2026-10-07"
        results = await asyncio.gather(
            run(
                lambda service, actor: service.create(
                    actor, BRANCH_ID, PERIOD, request(concurrent_day, "concurrent one")
                )
            ),
            run(
                lambda service, actor: service.create(
                    actor, BRANCH_ID, PERIOD, request(concurrent_day, "concurrent two")
                )
            ),
            return_exceptions=True,
        )
        winners = [item for item in results if not isinstance(item, BaseException)]
        losers = [item for item in results if isinstance(item, ServiceExecutionError)]
        assert len(winners) == len(losers) == 1 and losers[0].code == "state_conflict"
        created_ids.append(winners[0].id)

        validation_result = await run(
            lambda service, actor: service.validation(actor, BRANCH_ID, PERIOD)
        )
        assert validation_result.staffing_enforced
        assert validation_result.leave_conflicts
        assert validation_result.staffing_violations
        assert not validation_result.ready
        leave_conflict = validation_result.leave_conflicts[0]
        leave_override = await run(
            lambda service, actor: service.override(
                actor,
                BRANCH_ID,
                PERIOD,
                RosterComplianceOverrideRequest.model_validate(
                    {
                        "violationDigest": leave_conflict.violation_digest,
                        "reason": f"{PREFIX} approved leave exception",
                    }
                ),
            )
        )
        assert leave_override.rule_code == "leave_conflict"
        assert leave_override.violation_snapshot["leaveStatus"] == "ManagerApproved"
        violation = next(
            item for item in validation_result.staffing_violations if not item.overridden
        )
        override = await run(
            lambda service, actor: service.override(
                actor,
                BRANCH_ID,
                PERIOD,
                RosterComplianceOverrideRequest.model_validate(
                    {
                        "violationDigest": violation.violation_digest,
                        "reason": f"{PREFIX} approved staffing exception",
                    }
                ),
            )
        )
        assert override.rule_code == "staffing_shortfall"
        assert override.violation_snapshot["deficit"] == violation.deficit
        await expect_code(
            "state_conflict",
            run(
                lambda service, actor: service.override(
                    actor,
                    BRANCH_ID,
                    PERIOD,
                    RosterComplianceOverrideRequest(
                        violationDigest=violation.violation_digest,
                        reason=f"{PREFIX} duplicate override",
                    ),
                )
            ),
        )

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE FUNCTION public.phase10g_verify_reject_override() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced override failure'; END $$"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_phase10g_verify_reject_override BEFORE INSERT "
                    "ON public.compliance_overrides FOR EACH ROW "
                    "EXECUTE FUNCTION public.phase10g_verify_reject_override()"
                )
            )
        forced = next(
            item
            for item in validation_result.staffing_violations
            if item.violation_digest != violation.violation_digest
        )
        try:
            await run(
                lambda service, actor: service.override(
                    actor,
                    BRANCH_ID,
                    PERIOD,
                    RosterComplianceOverrideRequest(
                        violationDigest=forced.violation_digest,
                        reason=f"{PREFIX} forced rollback",
                    ),
                )
            )
        except DBAPIError:
            pass
        else:
            raise AssertionError("forced override failure did not roll back")
        finally:
            with migration_engine.begin() as connection:
                connection.execute(
                    text(
                        "DROP TRIGGER IF EXISTS trg_phase10g_verify_reject_override "
                        "ON public.compliance_overrides"
                    )
                )
                connection.execute(
                    text("DROP FUNCTION IF EXISTS public.phase10g_verify_reject_override()")
                )

        with migration_engine.begin() as connection:
            connection.execute(
                text("UPDATE public.roster_assignments SET published=true WHERE id=:id"),
                {"id": created.id},
            )
        await expect_code(
            "state_conflict",
            run(
                lambda service, actor: service.replace(
                    actor,
                    BRANCH_ID,
                    PERIOD,
                    created.id,
                    RosterDraftReplaceRequest.model_validate(
                        {
                            **request("2026-10-06", "published denial").model_dump(
                                mode="json", by_alias=True
                            ),
                            "expectedVersion": 2,
                        }
                    ),
                )
            ),
        )

        retained = await run(
            lambda service, actor: service.create(
                actor, BRANCH_ID, PERIOD, request("2026-10-08", "retained")
            )
        )
        created_ids.append(retained.id)
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.shift_swap_requests"
                    "(id,company_id,branch_id,requester_employee_id,target_employee_id,"
                    "requester_date,reason,status) VALUES "
                    "(:id,:company,:branch,:employee,:target,'2026-10-08',:reason,'pending')"
                ),
                {
                    "id": swap_id,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": EMPLOYEE_ID,
                    "target": OTHER_EMPLOYEE_ID,
                    "reason": PREFIX,
                },
            )
        await expect_code(
            "state_conflict",
            run(
                lambda service, actor: service.delete(
                    actor, BRANCH_ID, PERIOD, retained.id, retained.version
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
        disabled = await run(lambda service, actor: service.validation(actor, BRANCH_ID, PERIOD))
        assert not disabled.staffing_enforced and disabled.staffing_violations is None
        assert disabled.ready and all(item.overridden for item in disabled.leave_conflicts)

        async def mutate_override(connection: AsyncConnection) -> None:
            await connection.execute(
                text("UPDATE public.compliance_overrides SET reason='tampered' WHERE id=:id"),
                {"id": override.id},
            )

        try:
            await executor.execute(
                claims=claims(),
                principal=principal,
                selected_admin_branch_id=BRANCH_ID,
                operation=mutate_override,
            )
        except DBAPIError:
            pass
        else:
            raise AssertionError("immutable roster override accepted an update")
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM public.shift_swap_requests WHERE id=:id"), {"id": swap_id}
            )
            connection.execute(
                text("UPDATE public.roster_assignments SET published=false WHERE id=ANY(:ids)"),
                {"ids": created_ids},
            )
            connection.execute(
                text("DELETE FROM public.roster_assignments WHERE id=ANY(:ids)"),
                {"ids": created_ids},
            )
            connection.execute(
                text(
                    "DELETE FROM public.compliance_overrides WHERE override_type='roster_publish' "
                    "AND roster_month=:period"
                ),
                {"period": PERIOD},
            )
            connection.execute(
                text("DELETE FROM public.leave_requests WHERE id IN (:first,:second)"),
                {"first": leave_id, "second": leave_override_id},
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

    print("Phase 10G database roster draft and compliance verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
