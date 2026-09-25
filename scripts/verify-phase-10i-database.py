#!/usr/bin/env python3
"""Exercise Phase 10I shift swaps against PostgreSQL."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.repositories.roster_publication import RosterPublicationRepository
from app.repositories.shift_swaps import ShiftSwapRepository
from app.schemas.roster_publication import RosterPublishRequest
from app.schemas.shift_swaps import (
    ShiftSwapApproveRequest,
    ShiftSwapSubmitRequest,
    ShiftSwapTransitionRequest,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.roster_publication import RosterPublicationService
from app.services.shift_swaps import ShiftSwapService

ADMIN = "hr.admin@horizon.test"
RAVI = "ravi.employee@horizon.test"
MARIA = "maria.employee@horizon.test"
COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
RAVI_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
MARIA_ID = uuid.UUID("21000000-0000-4000-8000-000000000003")
SHIFT_ID = seed.derive("shifts", seed.HORIZON, "dubai", None, "M")
PERIOD = "2026-12"
RAVI_DAY = "2026-12-03"
MARIA_DAY = "2026-12-04"
PREFIX = "Phase 10I verification"
PAYROLL_RUN_ID = uuid.UUID("10f00000-0000-4000-8000-000000000001")
PAYROLL_ENTRY_ID = uuid.UUID("10f00000-0000-4000-8000-000000000002")


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


def cleanup_verification_rows(connection: Connection) -> None:
    assignment_ids = list(
        connection.scalars(
            text("SELECT id FROM public.roster_assignments WHERE notes LIKE :prefix"),
            {"prefix": f"{PREFIX}%"},
        )
    )
    connection.execute(
        text(
            "DELETE FROM public.notifications WHERE related_entity_type='roster_assignment' "
            "AND related_entity_id=ANY(:ids)"
        ),
        {"ids": [str(value) for value in assignment_ids]},
    )
    connection.execute(
        text("DELETE FROM public.payroll_entries WHERE id=:id"),
        {"id": PAYROLL_ENTRY_ID},
    )
    connection.execute(
        text("DELETE FROM public.payroll_runs WHERE id=:id"),
        {"id": PAYROLL_RUN_ID},
    )
    connection.execute(text("DELETE FROM public.audit_events WHERE action='shift_swap_approved'"))
    connection.execute(text("DELETE FROM public.shift_swap_history"))
    connection.execute(text("DELETE FROM public.shift_swap_requests WHERE contract_version=1"))
    connection.execute(text("DELETE FROM public.roster_publication_memberships"))
    connection.execute(
        text(
            "UPDATE public.roster_months SET status='draft',version=0,"
            "current_version_id=NULL,source_version=NULL,published_at=NULL,"
            "published_by_app_user_id=NULL"
        )
    )
    connection.execute(text("DELETE FROM public.roster_publication_versions"))
    connection.execute(text("DELETE FROM public.roster_months"))
    connection.execute(
        text("DELETE FROM public.roster_assignments WHERE notes LIKE :prefix"),
        {"prefix": f"{PREFIX}%"},
    )
    connection.execute(
        text(
            "UPDATE public.branches SET enable_staffing_rules=true "
            "WHERE id=:branch AND company_id=:company"
        ),
        {"branch": BRANCH_ID, "company": COMPANY_ID},
    )


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD")
    )
    rows = build_rows()
    assignments = sorted([uuid.uuid4(), uuid.uuid4()])
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "d6f8a0c2e4b7"
        )
        cleanup_verification_rows(connection)
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        connection.execute(
            text(
                "UPDATE public.branches SET enable_staffing_rules=false "
                "WHERE id=:branch AND company_id=:company"
            ),
            {"branch": BRANCH_ID, "company": COMPANY_ID},
        )
        connection.execute(
            text("UPDATE public.employees SET department='Nursing' WHERE id=:employee"),
            {"employee": MARIA_ID},
        )
        connection.execute(
            text(
                "INSERT INTO public.roster_assignments("
                "id,company_id,branch_id,employee_id,shift_id,date,published,planned_hours,notes) "
                "VALUES (:ravi,:company,:branch,:ravi_employee,:shift,:ravi_day,false,8,"
                ":ravi_note),"
                "(:maria,:company,:branch,:maria_employee,:shift,:maria_day,false,8,:maria_note)"
            ),
            {
                "ravi": assignments[0],
                "maria": assignments[1],
                "company": COMPANY_ID,
                "branch": BRANCH_ID,
                "ravi_employee": RAVI_ID,
                "maria_employee": MARIA_ID,
                "shift": SHIFT_ID,
                "ravi_day": RAVI_DAY,
                "maria_day": MARIA_DAY,
                "ravi_note": f"{PREFIX} Ravi",
                "maria_note": f"{PREFIX} Maria",
            },
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
        callback: Callable[[ShiftSwapService, AuthorizationPrincipal], Awaitable[Any]],
    ) -> Any:
        principal = principals[ADMIN]

        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(ShiftSwapService(ShiftSwapRepository(connection)), principal)

        return await executor.execute(
            claims=claims(ADMIN),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID,
            operation=invoke,
        )

    async def run_staff(
        subject: str,
        callback: Callable[[ShiftSwapService, AuthorizationPrincipal], Awaitable[Any]],
    ) -> Any:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(ShiftSwapService(ShiftSwapRepository(connection)), principal)

        return await executor.execute(
            claims=claims(subject), principal=principal, operation=invoke
        )

    try:
        admin = principals[ADMIN]

        async def publish(connection: AsyncConnection) -> Any:
            request = RosterPublishRequest.model_validate(
                {
                    "assignments": [
                        {"id": str(value), "expectedVersion": 1} for value in assignments
                    ],
                    "expectedSourceVersion": None,
                }
            )
            return await RosterPublicationService(
                RosterPublicationRepository(connection)
            ).publish(admin, BRANCH_ID, PERIOD, request)

        publication = await executor.execute(
            claims=claims(ADMIN),
            principal=admin,
            selected_admin_branch_id=BRANCH_ID,
            operation=publish,
        )
        assert publication.version == 1 and publication.source_version is not None

        submitted = await run_staff(
            RAVI,
            lambda service, actor: service.submit(
                actor,
                ShiftSwapSubmitRequest.model_validate(
                    {
                        "requesterDate": RAVI_DAY,
                        "targetEmployeeId": str(MARIA_ID),
                        "targetDate": MARIA_DAY,
                        "reason": "Family appointment",
                        "expectedSourceVersion": publication.source_version,
                    }
                ),
            ),
        )
        assert submitted.status == "pending" and submitted.version == 1
        assert submitted.requester_assignment_id == assignments[0]
        assert submitted.target_assignment_id == assignments[1]
        assert submitted.requester_assignment_version == 2
        assert submitted.target_assignment_version == 2
        personal = await run_staff(
            MARIA, lambda service, actor: service.personal(actor, "pending", 100)
        )
        assert [item.id for item in personal] == [submitted.id]
        queue = await run_admin(
            lambda service, actor: service.admin(actor, BRANCH_ID, "pending", 100)
        )
        assert [item.id for item in queue] == [submitted.id]
        await expect_code(
            "state_conflict",
            run_staff(
                RAVI,
                lambda service, actor: service.submit(
                    actor,
                    ShiftSwapSubmitRequest.model_validate(
                        {
                            "requesterDate": RAVI_DAY,
                            "targetEmployeeId": str(MARIA_ID),
                            "targetDate": MARIA_DAY,
                            "reason": "Duplicate request",
                            "expectedSourceVersion": publication.source_version,
                        }
                    ),
                ),
            ),
        )

        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE FUNCTION public.phase10i_verify_reject_history() RETURNS trigger "
                    "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced history failure'; END $$"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_phase10i_verify_reject_history BEFORE INSERT "
                    "ON public.shift_swap_history FOR EACH ROW "
                    "EXECUTE FUNCTION public.phase10i_verify_reject_history()"
                )
            )
        approve_request = ShiftSwapApproveRequest(
            expected_version=1, expected_source_version=publication.source_version
        )
        try:
            await run_admin(
                lambda service, actor: service.approve(
                    actor, BRANCH_ID, submitted.id, approve_request
                )
            )
        except ServiceExecutionError as error:
            assert error.code == "state_conflict"
        else:
            raise AssertionError("forced approval failure did not roll back")
        finally:
            with migration_engine.begin() as connection:
                connection.execute(
                    text(
                        "DROP TRIGGER trg_phase10i_verify_reject_history "
                        "ON public.shift_swap_history"
                    )
                )
                connection.execute(
                    text("DROP FUNCTION public.phase10i_verify_reject_history()")
                )
        with migration_engine.connect() as connection:
            before = connection.execute(
                text(
                    "SELECT employee_id,version FROM public.roster_assignments "
                    "WHERE id=ANY(:ids) ORDER BY id"
                ),
                {"ids": assignments},
            ).all()
            assert before == [(RAVI_ID, 2), (MARIA_ID, 2)]
            assert connection.scalar(
                text("SELECT status FROM public.shift_swap_requests WHERE id=:id"),
                {"id": submitted.id},
            ) == "pending"
            assert connection.scalar(
                text("SELECT count(*) FROM public.roster_publication_versions")
            ) == 1

        approval_outcomes = await asyncio.gather(
            run_admin(
                lambda service, actor: service.approve(
                    actor, BRANCH_ID, submitted.id, approve_request
                )
            ),
            run_admin(
                lambda service, actor: service.approve(
                    actor, BRANCH_ID, submitted.id, approve_request
                )
            ),
            return_exceptions=True,
        )
        approval_winners = [
            outcome for outcome in approval_outcomes if not isinstance(outcome, Exception)
        ]
        approval_conflicts = [
            outcome
            for outcome in approval_outcomes
            if isinstance(outcome, ServiceExecutionError) and outcome.code == "state_conflict"
        ]
        assert len(approval_winners) == len(approval_conflicts) == 1, tuple(
            repr(outcome) for outcome in approval_outcomes
        )
        approved = approval_winners[0]
        assert approved.status == "approved" and approved.version == 2
        assert approved.approved_publication_version_id is not None
        with migration_engine.connect() as connection:
            after = connection.execute(
                text(
                    "SELECT employee_id,version FROM public.roster_assignments "
                    "WHERE id=ANY(:ids) ORDER BY id"
                ),
                {"ids": assignments},
            ).all()
            assert after == [(MARIA_ID, 3), (RAVI_ID, 3)]
            assert connection.scalar(
                text("SELECT count(*) FROM public.roster_publication_versions")
            ) == 2
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM public.roster_publication_memberships "
                    "WHERE publication_version_id=:version"
                ),
                {"version": approved.approved_publication_version_id},
            ) == 2
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM public.shift_swap_history "
                    "WHERE shift_swap_request_id=:swap"
                ),
                {"swap": submitted.id},
            ) == 2
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM public.audit_events "
                    "WHERE action='shift_swap_approved' AND entity_id=:swap"
                ),
                {"swap": submitted.id},
            ) == 1

        with migration_engine.connect() as connection:
            current_source = connection.execute(
                text("SELECT source_version FROM public.roster_months WHERE period=:period"),
                {"period": PERIOD},
            ).scalar_one()
        frozen_request = await run_staff(
            RAVI,
            lambda service, actor: service.submit(
                actor,
                ShiftSwapSubmitRequest.model_validate(
                    {
                        "requesterDate": MARIA_DAY,
                        "targetEmployeeId": str(MARIA_ID),
                        "targetDate": RAVI_DAY,
                        "reason": "Payroll-frozen coverage exchange",
                        "expectedSourceVersion": current_source,
                    }
                ),
            ),
        )
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.payroll_runs("
                    "id,company_id,branch_id,period,payment_date,sequence_no,"
                    "scr_bank_routing_code,description,status,run_by_app_user_id,total_disbursed,"
                    "employee_count,wps_status,approval_status,submitted_for_approval_at,"
                    "submitted_by_app_user_id,approved_by_app_user_id,approved_at,"
                    "source_snapshot_digest) "
                    "VALUES (:id,:company,:branch,:period,'2026-12-25','10I1','999000001',"
                    ":description,'generated',:actor,0,1,'draft','approved',statement_timestamp(),"
                    ":actor,:actor,statement_timestamp(),:digest)"
                ),
                {
                    "id": PAYROLL_RUN_ID,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "period": PERIOD,
                    "description": f"{PREFIX} frozen source",
                    "actor": principals[ADMIN].app_user_id,
                    "digest": "f" * 64,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO public.payroll_entries("
                    "id,payroll_run_id,company_id,branch_id,employee_id,basic_salary,"
                    "housing_allowance,transport_allowance,allowance,additional_allowances,"
                    "deductions,source_snapshot,excluded,wps_payment_status) "
                    "VALUES (:id,:run,:company,:branch,:employee,0,0,0,0,'[]','[]',"
                    "CAST(:snapshot AS jsonb),false,'pending')"
                ),
                {
                    "id": PAYROLL_ENTRY_ID,
                    "run": PAYROLL_RUN_ID,
                    "company": COMPANY_ID,
                    "branch": BRANCH_ID,
                    "employee": RAVI_ID,
                    "snapshot": json.dumps(
                        {
                            "automaticInputs": [
                                {"sourceType": "roster", "sourceVersion": current_source}
                            ]
                        },
                        separators=(",", ":"),
                    ),
                },
            )
        await expect_code(
            "state_conflict",
            run_admin(
                lambda service, actor: service.approve(
                    actor,
                    BRANCH_ID,
                    frozen_request.id,
                    ShiftSwapApproveRequest(
                        expected_version=1,
                        expected_source_version=current_source,
                    ),
                )
            ),
        )
        with migration_engine.begin() as connection:
            assert connection.scalar(
                text("SELECT status FROM public.shift_swap_requests WHERE id=:id"),
                {"id": frozen_request.id},
            ) == "pending"
            assert connection.scalar(
                text("SELECT count(*) FROM public.roster_publication_versions")
            ) == 2
            connection.execute(
                text("DELETE FROM public.payroll_entries WHERE id=:id"),
                {"id": PAYROLL_ENTRY_ID},
            )
            connection.execute(
                text("DELETE FROM public.payroll_runs WHERE id=:id"),
                {"id": PAYROLL_RUN_ID},
            )
        cancelled = await run_staff(
            RAVI,
            lambda service, actor: service.cancel(
                actor,
                frozen_request.id,
                ShiftSwapTransitionRequest(expected_version=1),
            ),
        )
        assert cancelled.status == "cancelled" and cancelled.version == 2
        rejected_request = await run_staff(
            RAVI,
            lambda service, actor: service.submit(
                actor,
                ShiftSwapSubmitRequest.model_validate(
                    {
                        "requesterDate": MARIA_DAY,
                        "targetEmployeeId": str(MARIA_ID),
                        "targetDate": RAVI_DAY,
                        "reason": "Second coverage exchange",
                        "expectedSourceVersion": current_source,
                    }
                ),
            ),
        )
        rejected = await run_admin(
            lambda service, actor: service.reject(
                actor,
                BRANCH_ID,
                rejected_request.id,
                ShiftSwapTransitionRequest(
                    expected_version=1, reason="Coverage requirement changed"
                ),
            )
        )
        assert rejected.status == "rejected" and rejected.version == 2
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            cleanup_verification_rows(connection)
            clean(connection, rows)
        migration_engine.dispose()

    print("Phase 10I protected shift-swap verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
