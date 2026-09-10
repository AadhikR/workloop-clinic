"""Verify Phase 7C organization writes and idempotency against synthetic data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import psycopg
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.organization import BranchCreateRequest
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.organization import BranchCursorCodec, OrganizationService

EXPECTED_HEAD = "31d7b4c8e2f0"
CREATED_BRANCH_ID = uuid.UUID("7c000000-0000-4000-8000-000000000001")
FIRST_KEY = uuid.UUID("7c000000-0000-4000-8000-000000000002")
ROLLBACK_KEY = uuid.UUID("7c000000-0000-4000-8000-000000000004")
SERVICE_KEY = uuid.UUID("7c000000-0000-4000-8000-000000000005")
CLEANUP_KEYS = tuple(
    uuid.UUID(f"7c000000-0000-4000-8000-{value:012x}") for value in range(100, 201)
)
CLEANUP_UNEXPIRED_KEY = uuid.UUID("7c000000-0000-4000-8000-000000000201")
CLEANUP_OTHER_COMPANY_KEY = uuid.UUID("7c000000-0000-4000-8000-000000000202")
ADMIN_SUBJECT = "hr.admin@horizon.test"
CURSOR_CODEC = BranchCursorCodec(b"phase-7c-verifier-cursor-key-000")


def row_values(table: str, **matches: object) -> dict[str, object]:
    candidates = [
        row.values
        for row in build_rows()
        if row.table == table
        and all(row.values.get(name) == value for name, value in matches.items())
    ]
    if len(candidates) != 1:
        raise AssertionError(f"expected one synthetic {table} row")
    return candidates[0]


def connect_runtime() -> psycopg.Connection[Any]:
    return psycopg.connect(
        host="postgres",
        dbname="workloop",
        user="workloop_runtime",
        password=os.environ["WORKLOOP_RUNTIME_PASSWORD"],
        autocommit=True,
    )


def context_values(subject: str, branch_id: uuid.UUID | None = None) -> dict[str, object | None]:
    app_user = row_values("app_users", identity_subject=subject)
    profile = row_values("user_profiles", app_user_id=app_user["id"])
    employee_id = cast(uuid.UUID | None, profile["employee_id"])
    employee = None if employee_id is None else row_values("employees", id=employee_id)
    selected_branch = branch_id if employee is None else cast(uuid.UUID, employee["branch_id"])
    return {
        "workloop.identity_issuer": c.SEED_ISSUER,
        "workloop.identity_subject": subject,
        "workloop.app_user_id": app_user["id"],
        "workloop.role": profile["role"],
        "workloop.company_id": profile["company_id"],
        "workloop.employee_id": employee_id,
        "workloop.branch_id": selected_branch,
        "workloop.actor_kind": "human",
        "workloop.actor_key": None,
        "workloop.business_date": date(2026, 9, 10),
    }


@contextmanager
def human_context(
    connection: psycopg.Connection[Any], subject: str, branch_id: uuid.UUID | None = None
) -> Generator[psycopg.Cursor[Any]]:
    with connection.transaction(), connection.cursor() as cursor:
        for name, value in context_values(subject, branch_id).items():
            cursor.execute(
                "SELECT pg_catalog.set_config(%s, %s, true)",
                (name, "" if value is None else str(value)),
            )
        yield cursor


def scalar(cursor: psycopg.Cursor[Any], statement: str, values: tuple[object, ...] = ()) -> Any:
    cursor.execute(cast(Any, statement), values)
    row = cursor.fetchone()
    if row is None:
        raise AssertionError("query returned no row")
    return row[0]


def fingerprint(value: object) -> str:
    encoded = json.dumps(value, default=str, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def verify_first_commit(runtime: psycopg.Connection[Any]) -> None:
    admin = context_values(ADMIN_SUBJECT)
    company_id = cast(uuid.UUID, admin["workloop.company_id"])
    response = {"data": {"id": str(CREATED_BRANCH_ID), "name": "Phase 7C Synthetic"}}
    with human_context(runtime, ADMIN_SUBJECT) as cursor:
        cursor.execute(
            "INSERT INTO idempotency_records(app_user_id,idempotency_key,company_id,branch_id,"
            "operation_id,http_method,route_parameters,fingerprint_version,request_fingerprint) "
            "VALUES (%s,%s,%s,NULL,'create_branch','POST','{}','wlp-idem-fp-v1',%s)",
            (admin["workloop.app_user_id"], FIRST_KEY, company_id, "a" * 64),
        )
        cursor.execute(
            "INSERT INTO branches(id,company_id,name) VALUES (%s,%s,%s)",
            (CREATED_BRANCH_ID, company_id, "Phase 7C Synthetic"),
        )
        cursor.execute(
            "SELECT public.append_audit_event('branch_created','branch',%s,"
            "ARRAY['id']::text[],'Branch created','{}'::jsonb)",
            (CREATED_BRANCH_ID,),
        )
        cursor.execute(
            "UPDATE idempotency_records SET replay_resource_kind='branch',"
            "replay_resource_id=%s,response_status=201,response_body=%s,response_location=%s,"
            "completed_at=statement_timestamp(),"
            "retain_until=statement_timestamp()+interval '7 days' "
            "WHERE app_user_id=%s AND idempotency_key=%s",
            (
                CREATED_BRANCH_ID,
                Jsonb(response),
                f"/api/v1/branches/{CREATED_BRANCH_ID}",
                admin["workloop.app_user_id"],
                FIRST_KEY,
            ),
        )
    with human_context(runtime, ADMIN_SUBJECT) as cursor:
        stored = cursor.execute(
            "SELECT response_status,response_body,response_location FROM idempotency_records "
            "WHERE idempotency_key=%s",
            (FIRST_KEY,),
        ).fetchone()
        assert stored == (201, response, f"/api/v1/branches/{CREATED_BRANCH_ID}")
        assert (
            scalar(cursor, "SELECT count(*) FROM branches WHERE id=%s", (CREATED_BRANCH_ID,))
            == 1
        )
        assert scalar(
            cursor,
            "SELECT count(*) FROM audit_events WHERE action='branch_created' AND entity_id=%s",
            (CREATED_BRANCH_ID,),
        ) == 1


async def verify_service_commit(engine: Engine) -> None:
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
    claims = AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject=ADMIN_SUBJECT,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )
    principal = await resolver.resolve(issuer=c.SEED_ISSUER, subject=ADMIN_SUBJECT)
    command = IdempotencyCommand(
        key=SERVICE_KEY,
        operation_id="create_branch",
        method="POST",
        route_parameters={},
        fingerprint="c" * 64,
    )
    mutation_calls = 0
    created_id: uuid.UUID | None = None

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = OrganizationService(connection, CURSOR_CODEC)

        async def mutate() -> IdempotentResponse:
            nonlocal mutation_calls
            mutation_calls += 1
            branch = await service.create_branch(
                principal,
                BranchCreateRequest.model_validate({"name": "Phase 7C service branch"}),
            )
            return IdempotentResponse(
                status=201,
                body={"data": branch.model_dump(mode="json", by_alias=True)},
                location=f"/api/v1/branches/{branch.id}",
                resource_kind="branch",
                resource_id=branch.id,
            )

        return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
            principal=principal,
            command=command,
            authorize_replay=lambda kind, resource_id: service.authorize_branch_replay(
                principal, kind, resource_id
            ),
            mutation=mutate,
        )

    try:
        first = await executor.execute(claims=claims, principal=principal, operation=operation)
        created_id = first.resource_id
        replay = await executor.execute(claims=claims, principal=principal, operation=operation)
        assert created_id is not None
        assert first.status == 201 and not first.replayed
        assert replay.body == first.body and replay.replayed
        assert mutation_calls == 1
    finally:
        await runtime_engine.dispose()
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM idempotency_records WHERE idempotency_key=:key"),
                {"key": SERVICE_KEY},
            )
            if created_id is not None:
                connection.execute(
                    text("DELETE FROM audit_events WHERE entity_id=:branch_id"),
                    {"branch_id": created_id},
                )
                connection.execute(
                    text("DELETE FROM branches WHERE id=:branch_id"),
                    {"branch_id": created_id},
                )


def insert_completed_record(
    cursor: psycopg.Cursor[Any],
    subject: str,
    key: uuid.UUID,
    created_at: datetime,
    *,
    expired: bool,
) -> None:
    context = context_values(subject)
    branch_id = cast(uuid.UUID | None, context["workloop.branch_id"])
    resource_kind = "branch" if branch_id is not None else "tenant"
    cursor.execute(
        "INSERT INTO idempotency_records(app_user_id,idempotency_key,company_id,branch_id,"
        "operation_id,http_method,route_parameters,fingerprint_version,request_fingerprint,"
        "created_at) VALUES (%s,%s,%s,%s,'cleanup_probe','POST','{}','wlp-idem-fp-v1',%s,%s)",
        (
            context["workloop.app_user_id"],
            key,
            context["workloop.company_id"],
            branch_id,
            fingerprint(str(key)),
            created_at,
        ),
    )
    completed_at = created_at + timedelta(seconds=1)
    retain_until = completed_at + timedelta(days=7 if expired else 30)
    cursor.execute(
        "UPDATE idempotency_records SET replay_resource_kind=%s,replay_resource_id=%s,"
        "response_status=204,response_body=NULL,response_location=NULL,completed_at=%s,"
        "retain_until=%s WHERE app_user_id=%s AND idempotency_key=%s",
        (
            resource_kind,
            branch_id,
            completed_at,
            retain_until,
            context["workloop.app_user_id"],
            key,
        ),
    )


def verify_cleanup_function(runtime: psycopg.Connection[Any], engine: Engine) -> None:
    oldest = datetime(2026, 8, 20, tzinfo=UTC)
    with human_context(runtime, "aisha.manager@horizon.test") as cursor:
        for offset, key in enumerate(CLEANUP_KEYS):
            insert_completed_record(
                cursor,
                "aisha.manager@horizon.test",
                key,
                oldest + timedelta(seconds=offset),
                expired=True,
            )
        insert_completed_record(
            cursor,
            "aisha.manager@horizon.test",
            CLEANUP_UNEXPIRED_KEY,
            datetime.now(UTC),
            expired=False,
        )

    with human_context(runtime, "hr.admin@cedar.test") as cursor:
        insert_completed_record(
            cursor,
            "hr.admin@cedar.test",
            CLEANUP_OTHER_COMPANY_KEY,
            oldest,
            expired=True,
        )

    with pytest_raises(psycopg.errors.InsufficientPrivilege):
        with human_context(runtime, ADMIN_SUBJECT) as cursor:
            cursor.execute(
                "DELETE FROM idempotency_records WHERE idempotency_key=%s",
                (CLEANUP_KEYS[0],),
            )

    with human_context(runtime, ADMIN_SUBJECT) as cursor:
        assert scalar(cursor, "SELECT public.cleanup_expired_idempotency_records()") == 100

    with engine.connect() as connection:
        remaining = connection.execute(
            text(
                "SELECT idempotency_key FROM idempotency_records "
                "WHERE idempotency_key = ANY(:keys) ORDER BY idempotency_key"
            ),
            {"keys": list(CLEANUP_KEYS)},
        ).scalars().all()
        assert remaining == [CLEANUP_KEYS[-1]]
        assert connection.execute(
            text(
                "SELECT count(*) FROM idempotency_records "
                "WHERE idempotency_key IN (:unexpired, :other_company)"
            ),
            {
                "unexpired": CLEANUP_UNEXPIRED_KEY,
                "other_company": CLEANUP_OTHER_COMPANY_KEY,
            },
        ).scalar_one() == 2

    with human_context(runtime, ADMIN_SUBJECT) as cursor:
        assert scalar(cursor, "SELECT public.cleanup_expired_idempotency_records()") == 1
    with human_context(runtime, "hr.admin@cedar.test") as cursor:
        assert scalar(cursor, "SELECT public.cleanup_expired_idempotency_records()") == 1

    manager_id = context_values("aisha.manager@horizon.test")["workloop.app_user_id"]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE app_users SET status='disabled' WHERE id=:app_user_id"),
            {"app_user_id": manager_id},
        )
    try:
        with pytest_raises(psycopg.errors.InsufficientPrivilege):
            with human_context(runtime, "aisha.manager@horizon.test") as cursor:
                cursor.execute("SELECT public.cleanup_expired_idempotency_records()")
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE app_users SET status='active' WHERE id=:app_user_id"),
                {"app_user_id": manager_id},
            )

    with engine.connect() as connection, connection.begin():
        try:
            connection.execute(text("SELECT public.cleanup_expired_idempotency_records()"))
        except Exception as error:
            assert "idempotency cleanup denied" in str(error)
        else:
            raise AssertionError("migration context bypassed cleanup validation")

    with engine.connect() as connection:
        assert not connection.execute(
            text(
                "SELECT has_table_privilege('workloop_runtime',"
                "'public.idempotency_records','DELETE')"
            )
        ).scalar_one()
        assert connection.execute(
            text(
                "SELECT has_function_privilege('workloop_runtime',"
                "'public.cleanup_expired_idempotency_records()','EXECUTE')"
            )
        ).scalar_one()
        assert not connection.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_proc AS procedure "
                "CROSS JOIN LATERAL pg_catalog.aclexplode(procedure.proacl) AS acl "
                "WHERE procedure.oid="
                "'public.cleanup_expired_idempotency_records()'::regprocedure "
                "AND acl.grantee=0 AND acl.privilege_type='EXECUTE')"
            )
        ).scalar_one()
        definition = connection.execute(
            text(
                "SELECT pg_catalog.pg_get_functiondef("
                "'public.cleanup_expired_idempotency_records()'::regprocedure)"
            )
        ).scalar_one().lower()
        assert "security definer" in definition
        assert "limit 100" in definition
        assert "for update skip locked" in definition
        assert "record.company_id = public.workloop_company_id()" in definition

    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM idempotency_records WHERE idempotency_key=:key"),
            {"key": CLEANUP_UNEXPIRED_KEY},
        )


@contextmanager
def pytest_raises(error_type: type[BaseException]) -> Generator[None]:
    try:
        yield
    except error_type:
        return
    raise AssertionError(f"expected {error_type.__name__}")


def verify_guards(runtime: psycopg.Connection[Any]) -> None:
    admin = context_values(ADMIN_SUBJECT)
    company_id = cast(uuid.UUID, admin["workloop.company_id"])
    try:
        with human_context(runtime, ADMIN_SUBJECT) as cursor:
            cursor.execute(
                "INSERT INTO idempotency_records(app_user_id,idempotency_key,company_id,branch_id,"
                "operation_id,http_method,route_parameters,fingerprint_version,"
                "request_fingerprint) "
                "VALUES (%s,%s,%s,NULL,'create_branch','POST','{}','wlp-idem-fp-v1',%s)",
                (admin["workloop.app_user_id"], ROLLBACK_KEY, company_id, "b" * 64),
            )
    except psycopg.errors.CheckViolation:
        pass
    else:
        raise AssertionError("an incomplete reservation committed")
    with human_context(runtime, ADMIN_SUBJECT) as cursor:
        assert scalar(
            cursor,
            "SELECT count(*) FROM idempotency_records WHERE idempotency_key=%s",
            (ROLLBACK_KEY,),
        ) == 0

    with human_context(runtime, "ravi.employee@horizon.test") as cursor:
        before = scalar(cursor, "SELECT name FROM branches WHERE id=%s", (c.BRANCH_DXB,))
        cursor.execute("UPDATE branches SET name='Denied' WHERE id=%s", (c.BRANCH_DXB,))
        assert cursor.rowcount == 0
        assert scalar(cursor, "SELECT name FROM branches WHERE id=%s", (c.BRANCH_DXB,)) == before

    with human_context(runtime, ADMIN_SUBJECT, c.BRANCH_DXB) as cursor:
        before = scalar(cursor, "SELECT count(*) FROM branches WHERE id=%s", (c.BRANCH_DXB,))
        try:
            cursor.execute("DELETE FROM branches WHERE id=%s", (c.BRANCH_DXB,))
        except psycopg.errors.ForeignKeyViolation:
            pass
        else:
            raise AssertionError("a referenced branch was deleted")
    with human_context(runtime, ADMIN_SUBJECT, c.BRANCH_DXB) as cursor:
        assert (
            scalar(cursor, "SELECT count(*) FROM branches WHERE id=%s", (c.BRANCH_DXB,))
            == before
        )


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    runtime = connect_runtime()
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            head = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            assert head == EXPECTED_HEAD
        verify_first_commit(runtime)
        asyncio.run(verify_service_commit(engine))
        verify_cleanup_function(runtime, engine)
        verify_guards(runtime)
        with engine.connect() as connection:
            evidence = {
                "alembicHead": EXPECTED_HEAD,
                "auditEvents": connection.execute(
                    text("SELECT count(*) FROM audit_events WHERE entity_id=:branch_id"),
                    {"branch_id": CREATED_BRANCH_ID},
                ).scalar_one(),
                "idempotencyRecords": connection.execute(
                    text("SELECT count(*) FROM idempotency_records")
                ).scalar_one(),
                "retentionDays": 7,
                "syntheticState": fingerprint({"branch": CREATED_BRANCH_ID, "key": FIRST_KEY}),
            }
            print(json.dumps(evidence, separators=(",", ":"), sort_keys=True))
    finally:
        runtime.close()
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM idempotency_records"))
            connection.execute(
                text("DELETE FROM audit_events WHERE entity_id=:branch_id"),
                {"branch_id": CREATED_BRANCH_ID},
            )
            connection.execute(
                text("DELETE FROM branches WHERE id=:branch_id"),
                {"branch_id": CREATED_BRANCH_ID},
            )
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
