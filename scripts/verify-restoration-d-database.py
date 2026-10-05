"""Verify routing changes against a disposable synthetic PostgreSQL database."""

import asyncio
import json
import os
import sys
import uuid
from typing import Any, cast

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.main import create_app
from app.routing_api import change_routing, read_routing
from app.schemas.routing import RoutingChangeRequest
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.organization import BranchCursorCodec
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from starlette.requests import Request

BRANCH = seed.BRANCH_DXB
COMPANY = seed.COMPANY_ID[seed.HORIZON]


def cleanup() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.begin() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM companies WHERE id NOT IN (:one,:two)"),
                {
                    "one": seed.COMPANY_ID[seed.HORIZON],
                    "two": seed.COMPANY_ID[seed.CEDAR],
                },
            )
            == 0
        )
        for table in ["idempotency_records", "audit_events"]:
            connection.execute(
                text(f"DELETE FROM {table} WHERE company_id IN (:one,:two)"),
                {
                    "one": seed.COMPANY_ID[seed.HORIZON],
                    "two": seed.COMPANY_ID[seed.CEDAR],
                },
            )
        clean(connection, build_rows())
    engine.dispose()


async def main() -> None:
    url = os.environ["MIGRATION_DATABASE_URL"]
    if "15432" not in url and os.environ.get("RESTORATION_D_DISPOSABLE") != "true":
        raise RuntimeError("disposable database confirmation required")
    migration = create_engine(url)
    with migration.begin() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "f3a5c7e9b1d4"
        )
        apply_rows(connection, build_rows())
        validate(connection, build_rows())
    runtime_url = make_url(url).set(
        username="workloop_runtime",
        password=os.environ.get("WORKLOOP_RUNTIME_PASSWORD", make_url(url).password),
    )
    runtime = create_async_engine(runtime_url)
    resolver = ApplicationUserResolver(
        engine=runtime, issuer=seed.SEED_ISSUER, timeout_seconds=5
    )
    principal = await resolver.resolve(
        issuer=seed.SEED_ISSUER, subject="hr.admin@horizon.test"
    )
    claims = AccessTokenClaims(
        issuer=seed.SEED_ISSUER,
        subject="hr.admin@horizon.test",
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )
    app = create_app()
    app.state.organization_cursor_codec = BranchCursorCodec(b"D" * 32)
    app.state.authorized_service_executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime, setup_timeout_seconds=5),
        deadline_seconds=15,
    )

    def request(key: uuid.UUID | None = None) -> Request:
        headers = [] if key is None else [(b"idempotency-key", str(key).encode())]
        return Request(
            {"type": "http", "headers": headers, "app": app, "query_string": b""}
        )

    async def snapshot() -> dict[str, Any]:
        result = await read_routing(request(), claims, principal, BRANCH, str(BRANCH))
        return cast(dict[str, Any], result.data.model_dump(mode="json", by_alias=True))

    async def command(value: dict[str, Any], key: uuid.UUID | None = None) -> Any:
        return await change_routing(
            request(key or uuid.uuid4()),
            RoutingChangeRequest.model_validate(value),
            claims,
            principal,
            BRANCH,
            str(BRANCH),
        )

    def body(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "expectedUpdatedAt": value["branch"]["updatedAt"],
            "routingCode": "987654321",
            "drafts": value["drafts"],
        }

    def retained() -> list[Any]:
        with migration.connect() as connection:
            return list(
                connection.execute(
                    text(
                        "SELECT id,scr_bank_routing_code,updated_at "
                        "FROM payroll_runs WHERE branch_id<>:branch OR status='generated' "
                        "ORDER BY id"
                    ),
                    {"branch": BRANCH},
                ).all()
            )

    async def conflict(value: dict[str, Any]) -> None:
        try:
            await command(value)
        except ServiceExecutionError as error:
            assert error.code == "state_conflict", error.code
        else:
            raise AssertionError("expected conflict")

    initial = await snapshot()
    assert initial["drafts"]
    frozen = retained()
    valid = body(initial)
    await conflict({**valid, "expectedUpdatedAt": "2020-01-01T00:00:00.000Z"})
    await conflict({**valid, "drafts": []})
    with migration.connect() as connection:
        generated_id = connection.scalar(
            text("SELECT id FROM payroll_runs WHERE status='generated' LIMIT 1")
        )
    await conflict(
        {**valid, "drafts": [{**valid["drafts"][0], "id": str(generated_id)}]}
    )
    await conflict(
        {
            **valid,
            "drafts": [{**item, "sourceDigest": "a" * 64} for item in valid["drafts"]],
        }
    )
    await conflict(
        {
            **valid,
            "drafts": [
                {**item, "expectedUpdatedAt": "2020-01-01T00:00:00.000Z"}
                for item in valid["drafts"]
            ],
        }
    )
    assert (await snapshot()) == initial
    run_id = uuid.UUID(valid["drafts"][0]["id"])
    with migration.begin() as connection:
        actor = principal.app_user_id
        connection.execute(
            text(
                "UPDATE payroll_runs SET approval_status='approved',approved_at=now(),"
                "approved_by_app_user_id=:actor WHERE id=:id"
            ),
            {"actor": actor, "id": run_id},
        )
    await conflict(body(await snapshot()))
    with migration.begin() as connection:
        connection.execute(
            text(
                "UPDATE payroll_runs SET approval_status='draft',approved_at=NULL,"
                "approved_by_app_user_id=NULL WHERE id=:id"
            ),
            {"id": run_id},
        )
    valid = body(await snapshot())
    before = await snapshot()
    with migration.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION public.restoration_d_fail_audit() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit failure'; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER restoration_d_fail_audit BEFORE INSERT ON audit_events "
                "FOR EACH ROW WHEN (NEW.action='payroll_routing_changed') "
                "EXECUTE FUNCTION public.restoration_d_fail_audit()"
            )
        )
    try:
        try:
            await command(valid)
        except DBAPIError:
            pass
        else:
            raise AssertionError("expected audit rollback")
        assert await snapshot() == before
    finally:
        with migration.begin() as connection:
            connection.execute(
                text("DROP TRIGGER restoration_d_fail_audit ON audit_events")
            )
            connection.execute(text("DROP FUNCTION public.restoration_d_fail_audit()"))

    key = uuid.uuid4()
    with migration.connect() as connection:
        prior_audits = connection.scalar(
            text(
                "SELECT count(*) FROM audit_events WHERE action IN "
                "('branch_payroll_routing_changed','payroll_routing_changed')"
            )
        )
    result = await command(valid, key)
    payload = json.loads(result.body)
    assert payload["data"]["branch"]["defaultBankRoutingCode"] == "987654321"
    assert {item["id"] for item in payload["data"]["changedRuns"]} == {
        item["id"] for item in valid["drafts"]
    }
    replay = await command(valid, key)
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert json.loads(replay.body) == json.loads(result.body)
    try:
        await command({**valid, "routingCode": "123456789"}, key)
    except ServiceExecutionError as error:
        assert error.code == "idempotency_conflict"
    else:
        raise AssertionError("expected idempotency conflict")
    assert retained() == frozen
    with migration.connect() as connection:
        audits = connection.execute(
            text(
                "SELECT action,entity_id,metadata FROM audit_events "
                "WHERE action IN ('branch_payroll_routing_changed','payroll_routing_changed')"
            )
        ).all()
        assert len(audits) == prior_audits + len(valid["drafts"]) + 1
        assert all(row.metadata == {} for row in audits)

    locker = create_async_engine(url)
    for table, resource in [("branches", BRANCH), ("payroll_runs", run_id)]:
        current = body(await snapshot())
        async with locker.connect() as locked:
            transaction = await locked.begin()
            await locked.execute(
                text(f"SELECT id FROM {table} WHERE id=:id FOR UPDATE"),
                {"id": resource},
            )
            pending = asyncio.create_task(command(current))
            await asyncio.sleep(0.2)
            assert not pending.done(), f"command did not lock {table}"
            await locked.execute(
                text(f"UPDATE {table} SET updated_at=clock_timestamp() WHERE id=:id"),
                {"id": resource},
            )
            await transaction.commit()
        try:
            await pending
        except ServiceExecutionError as error:
            assert error.code == "state_conflict"
        else:
            raise AssertionError("stale concurrent version accepted")
    await locker.dispose()

    async def denied(connection: AsyncConnection) -> None:
        await connection.execute(
            text("SELECT set_config('workloop.role','employee',true)")
        )
        await connection.execute(
            text(
                "SELECT public.change_branch_payroll_routing(:branch,now(),"
                "'123456789','[]'::jsonb)"
            ),
            {"branch": BRANCH},
        )

    try:
        await app.state.authorized_service_executor.execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=BRANCH,
            operation=denied,
        )
    except DBAPIError as error:
        assert getattr(error.orig, "sqlstate", None) == "42501"
    else:
        raise AssertionError("forged role accepted")
    await runtime.dispose()
    migration.dispose()
    print(
        "Part D routing PostgreSQL proof passed: atomic scope, versions, source digests, "
        "approvals, rollback, replay, audit, locks, and role denial."
    )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    url = os.environ["MIGRATION_DATABASE_URL"]
    if "15432" not in url and os.environ.get("RESTORATION_D_DISPOSABLE") != "true":
        raise RuntimeError("disposable database confirmation required")
    cleanup()
    try:
        asyncio.run(main())
    finally:
        cleanup()
