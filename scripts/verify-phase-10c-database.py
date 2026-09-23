#!/usr/bin/env python3
"""Exercise Phase 10C attendance ingestion against PostgreSQL."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.attendance_ingestion import (
    BiometricCandidate,
    BiometricImportRequest,
    BiometricMappingRequest,
    ManualClockEventRequest,
)
from app.services.attendance_ingestion import (
    AttendanceIngestionService,
    EventListQuery,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
EMPLOYEE = "ravi.employee@horizon.test"
COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
BADGE = "P10C-VERIFY"
DUBAI = ZoneInfo("Asia/Dubai")


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
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "a1c3e5f7b9d4"
        )
        connection.execute(
            text(
                "DELETE FROM public.audit_events WHERE action IN "
                "('attendance_manual_event_created','biometric_mapping_replaced',"
                "'biometric_mapping_deleted','attendance_biometric_batch_imported')"
            )
        )
        connection.execute(text("DELETE FROM public.attendance_import_row_outcomes"))
        connection.execute(
            text(
                "DELETE FROM public.clock_events WHERE notes='Phase 10C verification' "
                "OR source_badge_no=:badge"
            ),
            {"badge": BADGE},
        )
        connection.execute(text("DELETE FROM public.attendance_import_batches"))
        connection.execute(
            text("DELETE FROM public.biometric_mappings WHERE badge_no=:badge"),
            {"badge": BADGE},
        )
        connection.execute(
            text(
                "DELETE FROM public.attendance_periods "
                "WHERE company_id=:company AND current_version_id IS NULL"
            ),
            {"company": COMPANY_ID},
        )
        apply_rows(connection, rows)
        validate(connection, rows)
        business_date = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        event_date = datetime.combine(
            business_date, time(9, 15), tzinfo=DUBAI
        ).astimezone(UTC)

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
        for subject in (ADMIN, MANAGER, EMPLOYEE)
    }
    codec = EmployeeCursorCodec(b"c" * 32)
    created_event_ids: set[uuid.UUID] = set()
    batch_ids: set[uuid.UUID] = set()

    async def run_service(
        subject: str,
        callback: Callable[
            [AttendanceIngestionService, AuthorizationPrincipal], Awaitable[Any]
        ],
        *,
        branch_id: uuid.UUID | None = None,
    ) -> Any:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> Any:
            return await callback(
                AttendanceIngestionService(connection, codec), principal
            )

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=branch_id if subject == ADMIN else None,
            operation=invoke,
        )

    try:
        manual_request = ManualClockEventRequest(
            employee_id=EMPLOYEE_ID,
            event_type="CLOCK_IN",
            event_time=event_date,
            note="Phase 10C verification",
        )
        manual = await run_service(
            ADMIN,
            lambda service, principal: service.manual(
                principal, BRANCH_ID, manual_request
            ),
            branch_id=BRANCH_ID,
        )
        created_event_ids.add(manual.id)
        await expect_code(
            "clock_event_conflict",
            run_service(
                ADMIN,
                lambda service, principal: service.manual(
                    principal, BRANCH_ID, manual_request
                ),
                branch_id=BRANCH_ID,
            ),
        )
        await expect_code(
            "operation_not_permitted",
            run_service(
                MANAGER,
                lambda service, principal: service.manual(
                    principal, BRANCH_ID, manual_request
                ),
            ),
        )
        await expect_code(
            "resource_not_found",
            run_service(
                ADMIN,
                lambda service, principal: service.manual(
                    principal, OTHER_BRANCH_ID, manual_request
                ),
                branch_id=OTHER_BRANCH_ID,
            ),
        )

        mapping = await run_service(
            ADMIN,
            lambda service, principal: service.replace_mapping(
                principal,
                BRANCH_ID,
                BADGE,
                BiometricMappingRequest(
                    employee_id=EMPLOYEE_ID, device_name="Phase 10C scanner"
                ),
            ),
            branch_id=BRANCH_ID,
        )
        import_request = BiometricImportRequest(
            source_bytes=320,
            candidates=[
                BiometricCandidate(
                    badge_no=BADGE,
                    event_type="CLOCK_OUT",
                    event_time=event_date.replace(hour=10),
                    device_name="Phase 10C scanner",
                ),
                BiometricCandidate(
                    badge_no=BADGE,
                    event_type="CLOCK_OUT",
                    event_time=event_date.replace(hour=10, second=20),
                    device_name="Phase 10C scanner",
                ),
                BiometricCandidate(
                    badge_no="P10C-UNKNOWN",
                    event_type="CLOCK_IN",
                    event_time=event_date.replace(hour=11),
                    device_name="Phase 10C scanner",
                ),
            ],
        )
        imported, concurrent_replay = await asyncio.gather(
            run_service(
                ADMIN,
                lambda service, principal: service.import_candidates(
                    principal, BRANCH_ID, import_request
                ),
                branch_id=BRANCH_ID,
            ),
            run_service(
                ADMIN,
                lambda service, principal: service.import_candidates(
                    principal, BRANCH_ID, import_request
                ),
                branch_id=BRANCH_ID,
            ),
        )
        assert concurrent_replay == imported
        batch_ids.add(imported.id)
        assert (
            imported.accepted_count,
            imported.duplicate_count,
            imported.rejected_count,
        ) == (
            1,
            1,
            1,
        )
        created_event_ids.update(
            item.clock_event_id
            for item in imported.outcomes
            if item.clock_event_id is not None
        )
        replay = await run_service(
            ADMIN,
            lambda service, principal: service.import_candidates(
                principal, BRANCH_ID, import_request
            ),
            branch_id=BRANCH_ID,
        )
        assert replay == imported

        page, cursor = await run_service(
            ADMIN,
            lambda service, principal: service.list_events(
                principal,
                BRANCH_ID,
                EventListQuery(1, EMPLOYEE_ID, None, None, None),
            ),
            branch_id=BRANCH_ID,
        )
        assert len(page) == 1 and cursor is not None
        second_page, _ = await run_service(
            ADMIN,
            lambda service, principal: service.list_events(
                principal,
                BRANCH_ID,
                EventListQuery(1, EMPLOYEE_ID, None, None, cursor),
            ),
            branch_id=BRANCH_ID,
        )
        assert second_page and second_page[0].id != page[0].id
        self_page, _ = await run_service(
            EMPLOYEE,
            lambda service, principal: service.self_events(
                principal, EventListQuery(100, None, None, None, None)
            ),
        )
        assert created_event_ids <= {item.id for item in self_page}

        async def forbidden_update(connection: AsyncConnection) -> None:
            await connection.execute(
                text("UPDATE public.clock_events SET notes='rewrite' WHERE id=:id"),
                {"id": manual.id},
            )

        try:
            await executor.execute(
                claims=claims(ADMIN),
                principal=principals[ADMIN],
                selected_admin_branch_id=BRANCH_ID,
                operation=forbidden_update,
            )
        except DBAPIError as error:
            assert "append-only" in str(error) or "permission denied" in str(error)
        else:
            raise AssertionError("runtime clock-event rewrite was accepted")

        with migration_engine.begin() as connection:
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM public.attendance_import_row_outcomes "
                        "WHERE batch_id=:batch AND company_id=:company AND branch_id=:branch"
                    ),
                    {
                        "batch": imported.id,
                        "company": seed.COMPANY_ID[seed.HORIZON],
                        "branch": BRANCH_ID,
                    },
                )
                == 3
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM public.audit_events WHERE entity_id=ANY(:ids) "
                        "AND action IN ('attendance_manual_event_created',"
                        "'biometric_mapping_replaced','attendance_biometric_batch_imported')"
                    ),
                    {"ids": [manual.id, mapping.id, imported.id]},
                )
                == 3
            )
    finally:
        await runtime_engine.dispose()
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM public.audit_events WHERE action IN "
                    "('attendance_manual_event_created','biometric_mapping_replaced',"
                    "'biometric_mapping_deleted','attendance_biometric_batch_imported')"
                ),
            )
            connection.execute(
                text(
                    "DELETE FROM public.attendance_import_row_outcomes WHERE batch_id=ANY(:ids)"
                ),
                {"ids": list(batch_ids)},
            )
            connection.execute(
                text("DELETE FROM public.clock_events WHERE id=ANY(:ids)"),
                {"ids": list(created_event_ids)},
            )
            connection.execute(
                text("DELETE FROM public.attendance_import_batches WHERE id=ANY(:ids)"),
                {"ids": list(batch_ids)},
            )
            connection.execute(
                text("DELETE FROM public.biometric_mappings WHERE badge_no=:badge"),
                {"badge": BADGE},
            )
            connection.execute(
                text(
                    "DELETE FROM public.attendance_periods "
                    "WHERE company_id=:company AND current_version_id IS NULL"
                ),
                {"company": COMPANY_ID},
            )
            clean(connection, rows)
        migration_engine.dispose()
    print("Phase 10C database authority verification passed.")


if __name__ == "__main__":
    asyncio.run(main())
