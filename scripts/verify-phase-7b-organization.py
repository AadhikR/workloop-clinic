"""Verify the Phase 7B organization reads against synthetic PostgreSQL data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from typing import Any, cast

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.identity import AccountStatus, AppRole
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.organization import (
    BranchCursorCodec,
    BranchListQuery,
    OrganizationService,
)

TABLES = ("companies", "branches", "app_users", "user_profiles", "employees")
EXPECTED_HEAD = os.environ.get("WORKLOOP_EXPECTED_ALEMBIC_HEAD", "2c4d6e8f0a1b")
CURSOR_CODEC = BranchCursorCodec(b"phase-7b-synthetic-cursor-key!!!")


def row_values(table: str, **matches: object) -> dict[str, object]:
    candidates = [
        row.values
        for row in build_rows()
        if row.table == table
        and all(row.values.get(key) == value for key, value in matches.items())
    ]
    if len(candidates) != 1:
        raise AssertionError(f"expected one synthetic {table} row")
    return candidates[0]


def principal_for(subject: str) -> AuthorizationPrincipal:
    app_user = row_values("app_users", identity_subject=subject)
    profile = row_values("user_profiles", app_user_id=app_user["id"])
    employee_id = cast(uuid.UUID | None, profile["employee_id"])
    employee = None if employee_id is None else row_values("employees", id=employee_id)
    return AuthorizationPrincipal(
        app_user_id=cast(uuid.UUID, app_user["id"]),
        account_status=AccountStatus.ACTIVE,
        role=AppRole(cast(str, profile["role"])),
        company_id=cast(uuid.UUID, profile["company_id"]),
        employee_id=employee_id,
        branch_id=None if employee is None else cast(uuid.UUID, employee["branch_id"]),
    )


def connect_runtime() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host="postgres",
        dbname="workloop",
        user="workloop_runtime",
        password=os.environ["WORKLOOP_RUNTIME_PASSWORD"],
        autocommit=True,
    )


def set_context_value(cursor: psycopg.Cursor[Any], name: str, value: object | None) -> None:
    cursor.execute(
        "SELECT pg_catalog.set_config(%s, %s, true)",
        (name, "" if value is None else str(value)),
    )


@contextmanager
def human_context(
    connection: psycopg.Connection[Any],
    subject: str,
    *,
    branch_id: uuid.UUID | None = None,
    overrides: dict[str, object | None] | None = None,
) -> Generator[psycopg.Cursor[Any]]:
    principal = principal_for(subject)
    selected_branch = principal.branch_id if principal.role is not AppRole.ADMIN else branch_id
    values: dict[str, object | None] = {
        "workloop.identity_issuer": c.SEED_ISSUER,
        "workloop.identity_subject": subject,
        "workloop.app_user_id": principal.app_user_id,
        "workloop.role": principal.role.value,
        "workloop.company_id": principal.company_id,
        "workloop.employee_id": principal.employee_id,
        "workloop.branch_id": selected_branch,
        "workloop.actor_kind": "human",
        "workloop.actor_key": None,
        "workloop.business_date": date(2026, 9, 9),
    }
    values.update(overrides or {})
    with connection.transaction(), connection.cursor() as cursor:
        for name, value in values.items():
            set_context_value(cursor, name, value)
        yield cursor


def scalar(cursor: psycopg.Cursor[Any], query: str, values: tuple[object, ...] = ()) -> Any:
    cursor.execute(cast(Any, query), values)
    row = cursor.fetchone()
    if row is None:
        raise AssertionError("query returned no row")
    return row[0]


def database_fingerprint(engine: Engine) -> str:
    payload: dict[str, list[dict[str, object]]] = {}
    with engine.connect() as connection:
        for table in TABLES:
            rows = connection.execute(
                text(
                    f"SELECT to_jsonb(source) AS value FROM {table} source "
                    "ORDER BY to_jsonb(source)::text"
                )
            ).scalars()
            payload[table] = list(rows)
    encoded = json.dumps(payload, default=str, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_rls_reads(runtime: psycopg.Connection[Any], engine: Engine) -> None:
    horizon_admin = principal_for("hr.admin@horizon.test")
    cedar_admin = principal_for("hr.admin@cedar.test")

    with human_context(runtime, "hr.admin@horizon.test") as cursor:
        assert scalar(cursor, "SELECT count(*) FROM companies") == 1
        assert scalar(cursor, "SELECT count(*) FROM branches") == 2
        assert (
            scalar(
                cursor,
                "SELECT count(*) FROM companies WHERE id = %s",
                (cedar_admin.company_id,),
            )
            == 0
        )
        assert scalar(cursor, "SELECT count(*) FROM branches WHERE id = %s", (c.BRANCH_SHJ,)) == 0

    with human_context(runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB) as cursor:
        assert cursor.execute("SELECT id FROM branches").fetchall() == [(c.BRANCH_DXB,)]
        assert scalar(cursor, "SELECT count(*) FROM branches WHERE id = %s", (c.BRANCH_AUH,)) == 0

    for subject in ("aisha.manager@horizon.test", "ravi.employee@horizon.test"):
        with human_context(runtime, subject) as cursor:
            assert cursor.execute("SELECT id FROM companies").fetchall() == [
                (horizon_admin.company_id,)
            ]
            assert cursor.execute("SELECT id FROM branches").fetchall() == [(c.BRANCH_DXB,)]
            assert (
                scalar(cursor, "SELECT count(*) FROM branches WHERE id = %s", (c.BRANCH_AUH,)) == 0
            )
            assert (
                scalar(cursor, "SELECT count(*) FROM branches WHERE id = %s", (c.BRANCH_SHJ,)) == 0
            )

    original = database_fingerprint(engine)
    employee = principal_for("ravi.employee@horizon.test")
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app_users SET status = 'disabled' WHERE id = :id"),
            {"id": employee.app_user_id},
        )
    disabled = database_fingerprint(engine)
    try:
        with human_context(runtime, "ravi.employee@horizon.test") as cursor:
            assert scalar(cursor, "SELECT count(*) FROM companies") == 0
            assert scalar(cursor, "SELECT count(*) FROM branches") == 0
        assert database_fingerprint(engine) == disabled
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE app_users SET status = 'active' WHERE id = :id"),
                {"id": employee.app_user_id},
            )
    assert database_fingerprint(engine) == original


async def verify_services() -> dict[str, object]:
    runtime_engine = create_async_engine(
        URL.create(
            "postgresql+psycopg",
            username="workloop_runtime",
            password=os.environ["WORKLOOP_RUNTIME_PASSWORD"],
            host="postgres",
            database="workloop",
        )
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine,
        issuer=c.SEED_ISSUER,
        timeout_seconds=2,
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=2),
        deadline_seconds=5,
    )

    async def resolve(subject: str) -> AuthorizationPrincipal:
        return await resolver.resolve(issuer=c.SEED_ISSUER, subject=subject)

    def claims(subject: str) -> AccessTokenClaims:
        return AccessTokenClaims(
            issuer=c.SEED_ISSUER,
            subject=subject,
            audience=("workloop-api",),
            expires_at=1,
            issued_at=1,
            not_before=None,
        )

    async def execute(
        subject: str,
        principal: AuthorizationPrincipal,
        operation: Any,
        *,
        branch_id: uuid.UUID | None = None,
    ) -> Any:
        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            operation=operation,
            selected_admin_branch_id=branch_id,
        )

    try:
        admin_subject = "hr.admin@horizon.test"
        admin = await resolve(admin_subject)

        async def company_operation(connection: AsyncConnection) -> object:
            return await OrganizationService(connection, CURSOR_CODEC).get_company(admin)

        company = await execute(admin_subject, admin, company_operation)
        assert set(company.model_dump(by_alias=True)) == {
            "id",
            "name",
            "sector",
            "nafisQuotaPercent",
            "enableNafis",
            "createdAt",
            "updatedAt",
        }

        first_query = BranchListQuery(limit=1, search=None, sort=(("name", False),), cursor=None)

        async def first_page_operation(connection: AsyncConnection) -> object:
            return await OrganizationService(connection, CURSOR_CODEC).list_branches(
                admin, first_query
            )

        first_page, next_cursor = await execute(admin_subject, admin, first_page_operation)
        assert len(first_page) == 1 and next_cursor is not None
        second_query = BranchListQuery(
            limit=1,
            search=None,
            sort=(("name", False),),
            cursor=next_cursor,
        )

        async def second_page_operation(connection: AsyncConnection) -> object:
            return await OrganizationService(connection, CURSOR_CODEC).list_branches(
                admin, second_query
            )

        second_page, final_cursor = await execute(admin_subject, admin, second_page_operation)
        assert len(second_page) == 1 and final_cursor is None
        assert first_page[0].id != second_page[0].id

        async def detail_operation(connection: AsyncConnection) -> object:
            return await OrganizationService(connection, CURSOR_CODEC).get_branch(
                admin, c.BRANCH_DXB
            )

        detail = await execute(admin_subject, admin, detail_operation, branch_id=c.BRANCH_DXB)
        assert detail.id == c.BRANCH_DXB
        assert set(detail.model_dump(by_alias=True)) == {
            "id",
            "name",
            "molEmployerId",
            "defaultBankRoutingCode",
            "address",
            "contactEmail",
            "defaultSalaryDay",
            "workLocationType",
            "freeZoneName",
            "logoUrl",
            "enableStaffingRules",
            "enableBiometricImport",
            "createdAt",
            "updatedAt",
        }

        try:
            await execute(
                admin_subject,
                admin,
                detail_operation,
                branch_id=c.BRANCH_SHJ,
            )
        except ServiceExecutionError as error:
            assert error.code == "resource_not_found"
        else:
            raise AssertionError("cross-tenant branch selection was accepted")

        staff_results: dict[str, object] = {}

        def employer_operation_for(active: AuthorizationPrincipal) -> Any:
            async def operation(connection: AsyncConnection) -> object:
                return await OrganizationService(connection, CURSOR_CODEC).get_employer(active)

            return operation

        def branch_operation_for(
            active: AuthorizationPrincipal, active_query: BranchListQuery
        ) -> Any:
            async def operation(connection: AsyncConnection) -> object:
                return await OrganizationService(connection, CURSOR_CODEC).list_branches(
                    active, active_query
                )

            return operation

        for subject in ("aisha.manager@horizon.test", "ravi.employee@horizon.test"):
            principal = await resolve(subject)
            query = BranchListQuery(limit=50, search=None, sort=(("name", False),), cursor=None)
            employer = await execute(subject, principal, employer_operation_for(principal))
            branches, cursor = await execute(
                subject, principal, branch_operation_for(principal, query)
            )
            assert employer.branch_name == "Horizon Dubai Main"
            assert [branch.id for branch in branches] == [c.BRANCH_DXB]
            assert cursor is None
            assert set(branches[0].model_dump(by_alias=True)) == {
                "id",
                "name",
                "address",
                "contactEmail",
                "workLocationType",
                "freeZoneName",
                "logoUrl",
            }
            staff_results[principal.role.value] = str(branches[0].id)

        return {
            "adminBranchCount": len(first_page) + len(second_page),
            "companyId": str(company.id),
            "selectedBranchId": str(detail.id),
            "staffBranches": staff_results,
        }
    finally:
        await runtime_engine.dispose()


def main() -> None:
    migration_url = os.environ["MIGRATION_DATABASE_URL"]
    engine = create_engine(migration_url)
    runtime = connect_runtime()
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            heads = (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            )
            assert heads == [EXPECTED_HEAD]
        seeded_fingerprint = database_fingerprint(engine)
        verify_rls_reads(runtime, engine)
        service_evidence = asyncio.run(verify_services())
        assert database_fingerprint(engine) == seeded_fingerprint
        evidence = {
            "alembicHead": EXPECTED_HEAD,
            "databaseFingerprint": seeded_fingerprint,
            "readStateUnchanged": True,
            "service": service_evidence,
        }
        print(json.dumps(evidence, separators=(",", ":"), sort_keys=True))
    finally:
        runtime.close()
        with engine.begin() as connection:
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
