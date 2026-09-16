#!/usr/bin/env python3
"""Verify Phase 8C balance scope, locking, and recalculation with synthetic PostgreSQL data."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.leave import LeaveBalance
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.leave_balance_service import (
    BalanceListQuery,
    LeaveBalanceService,
    RequestCalendarQuery,
)
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

EXPECTED_HEAD = "f9b2c4d6e8a1"
ADMIN = "hr.admin@horizon.test"
AISHA = "aisha.manager@horizon.test"
RAVI = "ravi.employee@horizon.test"
MARIA = "maria.employee@horizon.test"
FATIMA = "fatima.employee@horizon.test"
RAVI_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
MARIA_ID = uuid.UUID("21000000-0000-4000-8000-000000000003")
LEILA_ID = uuid.UUID("22000000-0000-4000-8000-000000000002")
CURSOR_CODEC = EmployeeCursorCodec(b"8" * 32, clock=lambda: c.CLOCK_TIMESTAMP)


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=c.SEED_ISSUER,
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


class ServiceRunner:
    def __init__(self, runtime_url: URL, clock: Callable[[], datetime]) -> None:
        self.engine = create_async_engine(runtime_url)
        self.resolver = ApplicationUserResolver(
            engine=self.engine, issuer=c.SEED_ISSUER, timeout_seconds=2
        )
        self.executor = AuthorizedServiceExecutor(
            AuthorizationTransactionFactory(
                engine=self.engine, setup_timeout_seconds=2, clock=clock
            ),
            deadline_seconds=10,
        )

    async def principal(self, subject: str) -> AuthorizationPrincipal:
        return await self.resolver.resolve(issuer=c.SEED_ISSUER, subject=subject)

    async def run(
        self,
        subject: str,
        principal: AuthorizationPrincipal,
        operation: Callable[[LeaveBalanceService], Awaitable[Any]],
        branch_id: uuid.UUID | None = None,
    ) -> Any:
        async def execute(connection: AsyncConnection) -> Any:
            return await operation(LeaveBalanceService(connection, CURSOR_CODEC))

        return await self.executor.execute(
            claims=claims(subject),
            principal=principal,
            operation=execute,
            selected_admin_branch_id=branch_id,
        )

    async def close(self) -> None:
        await self.engine.dispose()


def balance_query(
    employee_id: uuid.UUID | None = None,
    *,
    limit: int = 100,
    leave_type_id: uuid.UUID | None = None,
    cursor: str | None = None,
    year: int = 2026,
) -> BalanceListQuery:
    return BalanceListQuery(
        limit=limit,
        leave_year=year,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        cursor=cursor,
    )


def request_query(
    employee_id: uuid.UUID | None = None,
    *,
    limit: int = 100,
    status: str | None = None,
    cursor: str | None = None,
) -> RequestCalendarQuery:
    return RequestCalendarQuery(
        limit=limit,
        leave_year=2026,
        employee_id=employee_id,
        leave_type_id=None,
        status=status,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
    )


async def verify_services(runtime_url: URL) -> None:
    runner = ServiceRunner(runtime_url, lambda: c.CLOCK_TIMESTAMP)
    expired_runner = ServiceRunner(
        runtime_url, lambda: datetime(2026, 9, 1, tzinfo=UTC)
    )
    try:
        admin = await runner.principal(ADMIN)
        aisha = await runner.principal(AISHA)
        ravi = await runner.principal(RAVI)
        maria = await runner.principal(MARIA)
        fatima = await runner.principal(FATIMA)

        initialized = await runner.run(
            ADMIN,
            admin,
            lambda service: service.initialize(admin, c.BRANCH_DXB, 2026),
            c.BRANCH_DXB,
        )
        initialized_again = await runner.run(
            ADMIN,
            admin,
            lambda service: service.initialize(admin, c.BRANCH_DXB, 2026),
            c.BRANCH_DXB,
        )
        assert len(initialized) == len(initialized_again) == 45

        first, second = await asyncio.gather(
            runner.run(
                ADMIN,
                admin,
                lambda service: service.recalculate(admin, c.BRANCH_DXB, 2026),
                c.BRANCH_DXB,
            ),
            runner.run(
                ADMIN,
                admin,
                lambda service: service.recalculate(admin, c.BRANCH_DXB, 2026),
                c.BRANCH_DXB,
            ),
        )
        assert [row.model_dump(mode="json") for row in first] == [
            row.model_dump(mode="json") for row in second
        ]

        self_balances = []
        balance_cursor = None
        first_balance_cursor = None
        while True:
            page, balance_cursor = await runner.run(
                RAVI,
                ravi,
                lambda service, cursor=balance_cursor: service.list_self_balances(
                    ravi, balance_query(limit=4, cursor=cursor)
                ),
            )
            self_balances.extend(page)
            first_balance_cursor = first_balance_cursor or balance_cursor
            if balance_cursor is None:
                break
        assert len(self_balances) == 9
        assert {row.employee_id for row in self_balances} == {RAVI_ID}
        assert len({(row.employee_id, row.leave_type_id) for row in self_balances}) == 9
        assert first_balance_cursor is not None
        await expect_code(
            "invalid_cursor",
            runner.run(
                RAVI,
                ravi,
                lambda service: service.list_self_balances(
                    ravi, balance_query(limit=4, cursor=first_balance_cursor, year=2025)
                ),
            ),
        )
        filtered_balances, _ = await runner.run(
            RAVI,
            ravi,
            lambda service: service.list_self_balances(
                ravi, balance_query(leave_type_id=self_balances[0].leave_type_id)
            ),
        )
        assert len(filtered_balances) == 1
        assert set(self_balances[0].model_dump(mode="json", by_alias=True)) == {
            "employeeId",
            "leaveTypeId",
            "leaveYear",
            "entitledDays",
            "accruedDays",
            "usedDays",
            "pendingDays",
            "carriedForward",
            "remainingDays",
            "sickFullPayUsed",
            "sickHalfPayUsed",
            "sickUnpaidUsed",
        }

        self_requests = []
        request_cursor = None
        while True:
            page, request_cursor = await runner.run(
                RAVI,
                ravi,
                lambda service, cursor=request_cursor: service.list_self_requests(
                    ravi, request_query(limit=1, cursor=cursor)
                ),
            )
            self_requests.extend(page)
            if request_cursor is None:
                break
        assert self_requests
        assert {row.employee_id for row in self_requests} == {RAVI_ID}
        assert [row.id for row in self_requests] == sorted(
            row.id for row in self_requests
        )
        assert (
            next(row for row in self_requests if row.is_half_day).days_requested == 0.5
        )
        assert all(row.attachment is None for row in self_requests)
        request_fields = set(self_requests[0].model_dump(mode="json", by_alias=True))
        assert "employeeName" not in request_fields
        assert "managerApprovedByAppUserId" not in request_fields
        filtered_requests, _ = await runner.run(
            RAVI,
            ravi,
            lambda service: service.list_self_requests(
                ravi, request_query(status=self_requests[0].status)
            ),
        )
        assert filtered_requests
        assert {row.status for row in filtered_requests} == {self_requests[0].status}

        manager_balances, _ = await runner.run(
            AISHA,
            aisha,
            lambda service: service.list_approver_balances(
                aisha, balance_query(RAVI_ID)
            ),
        )
        delegate_balances, _ = await runner.run(
            FATIMA,
            fatima,
            lambda service: service.list_approver_balances(
                fatima, balance_query(RAVI_ID)
            ),
        )
        assert manager_balances and delegate_balances
        assert {row.employee_id for row in manager_balances + delegate_balances} == {
            RAVI_ID
        }

        await expect_code(
            "resource_not_found",
            runner.run(
                MARIA,
                maria,
                lambda service: service.list_approver_balances(
                    maria, balance_query(RAVI_ID)
                ),
            ),
        )
        await expect_code(
            "resource_not_found",
            runner.run(
                AISHA,
                aisha,
                lambda service: service.list_approver_balances(
                    aisha, balance_query(LEILA_ID)
                ),
            ),
        )
        expired_fatima = await expired_runner.principal(FATIMA)
        await expect_code(
            "resource_not_found",
            expired_runner.run(
                FATIMA,
                expired_fatima,
                lambda service: service.list_approver_balances(
                    expired_fatima, balance_query(RAVI_ID)
                ),
            ),
        )
        await expect_code(
            "resource_not_found",
            runner.run(
                ADMIN,
                admin,
                lambda service: service.list_admin_balances(
                    admin, c.BRANCH_SHJ, balance_query()
                ),
                c.BRANCH_SHJ,
            ),
        )
        unrelated, _ = await runner.run(
            RAVI,
            ravi,
            lambda service: service.list_self_balances(ravi, balance_query(MARIA_ID)),
        )
        assert {row.employee_id for row in unrelated} == {RAVI_ID}
    finally:
        await expired_runner.close()
        await runner.close()


def table_fingerprints(engine: Engine) -> dict[str, str]:
    tables = (
        "leave_settings",
        "leave_types",
        "public_holidays",
        "leave_requests",
        "leave_audit_log",
        "leave_approval_delegates",
    )
    with engine.connect() as connection:
        return {
            table: connection.exec_driver_sql(
                f"SELECT md5(coalesce(string_agg(row_to_json(source)::text, '' "
                f"ORDER BY source.id), '')) FROM public.{table} AS source"
            ).scalar_one()
            for table in tables
        }


def verify_lock_conflict(engine: Engine) -> None:
    with engine.connect() as guard, engine.connect() as writer:
        guard_transaction = guard.begin()
        writer_transaction = writer.begin()
        try:
            for table in (
                "employees",
                "leave_types",
                "leave_requests",
                "leave_balances",
            ):
                guard.exec_driver_sql(
                    f"LOCK TABLE public.{table} IN SHARE ROW EXCLUSIVE MODE"
                )
            writer.exec_driver_sql("SET LOCAL lock_timeout = '100ms'")
            try:
                writer.exec_driver_sql(
                    "UPDATE public.leave_balances SET pending_days = pending_days WHERE false"
                )
            except DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "55P03"
            else:
                raise AssertionError("balance lock allowed a concurrent writer")
        finally:
            writer_transaction.rollback()
            guard_transaction.rollback()


def verify_persisted_invariants(engine: Engine) -> None:
    with engine.connect() as connection:
        duplicates = connection.exec_driver_sql(
            "SELECT count(*) FROM ("
            "SELECT employee_id, leave_type_id, leave_year FROM public.leave_balances "
            "GROUP BY employee_id, leave_type_id, leave_year HAVING count(*) > 1"
            ") AS duplicate"
        ).scalar_one()
        negative = connection.exec_driver_sql(
            "SELECT count(*) FROM public.leave_balances WHERE "
            "entitled_days < 0 OR accrued_days < 0 OR used_days < 0 OR pending_days < 0 "
            "OR carried_forward < 0 OR remaining_days < 0 OR sick_full_pay_used < 0 "
            "OR sick_half_pay_used < 0 OR sick_unpaid_used < 0"
        ).scalar_one()
        assert duplicates == negative == 0


def cleanup_balances(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            delete(LeaveBalance).where(
                LeaveBalance.company_id.in_(
                    [c.COMPANY_ID[c.HORIZON], c.COMPANY_ID[c.CEDAR]]
                )
            )
        )


def main() -> None:
    migration_url = os.environ["MIGRATION_DATABASE_URL"]
    runtime_url = URL.create(
        "postgresql+psycopg",
        username="workloop_runtime",
        password=os.environ.get("WORKLOOP_RUNTIME_PASSWORD") or None,
        host=os.environ.get("WORKLOOP_DATABASE_HOST", "postgres"),
        database="workloop",
    )
    engine = create_engine(migration_url)
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            assert connection.execute(select(LeaveBalance.id)).first() is not None
            assert (
                connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one()
                == EXPECTED_HEAD
            )
        before = table_fingerprints(engine)
        verify_lock_conflict(engine)
        asyncio.run(verify_services(runtime_url))
        assert table_fingerprints(engine) == before
        verify_persisted_invariants(engine)
        print("Phase 8C balance database check passed")
    finally:
        cleanup_balances(engine)
        with engine.begin() as connection:
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
