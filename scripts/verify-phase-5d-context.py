import argparse
import asyncio
import os
import uuid
from datetime import date, datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import (
    ApplicationUserResolver,
    AuthorizationPrincipal,
)
from app.db.authorization_context import (
    CONTEXT_KEYS,
    CONTEXT_READER_NAMES,
    AuthorizationContextError,
    AuthorizationTransactionFactory,
)
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.identity import AccountStatus, AppRole
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

PROBE_TABLE = "_phase5d_context_probe"
PROBE_IDS = {
    "horizon_admin": uuid.UUID("51000000-0000-4000-8000-000000000001"),
    "horizon_manager": uuid.UUID("52000000-0000-4000-8000-000000000001"),
    "horizon_employee": uuid.UUID("53000000-0000-4000-8000-000000000001"),
    "cedar_admin": uuid.UUID("61000000-0000-4000-8000-000000000001"),
}
SUBJECTS = {
    "horizon_admin": "hr.admin@horizon.test",
    "horizon_manager": "aisha.manager@horizon.test",
    "horizon_employee": "ravi.employee@horizon.test",
    "cedar_admin": "hr.admin@cedar.test",
}

READ_CONTEXT = text(
    """
SELECT
  public.workloop_identity_issuer(),
  public.workloop_identity_subject(),
  public.workloop_app_user_id(),
  public.workloop_role(),
  public.workloop_company_id(),
  public.workloop_employee_id(),
  public.workloop_branch_id(),
  public.workloop_actor_kind(),
  public.workloop_actor_key(),
  public.workloop_business_date()
"""
)

READ_RAW_CONTEXT = text(
    """
SELECT
  pg_catalog.current_setting('workloop.identity_issuer', true),
  pg_catalog.current_setting('workloop.identity_subject', true),
  pg_catalog.current_setting('workloop.app_user_id', true),
  pg_catalog.current_setting('workloop.role', true),
  pg_catalog.current_setting('workloop.company_id', true),
  pg_catalog.current_setting('workloop.employee_id', true),
  pg_catalog.current_setting('workloop.branch_id', true),
  pg_catalog.current_setting('workloop.actor_kind', true),
  pg_catalog.current_setting('workloop.actor_key', true),
  pg_catalog.current_setting('workloop.business_date', true)
"""
)

SET_RAW_CONTEXT = text(
    """
SELECT
  pg_catalog.set_config('workloop.identity_issuer', :identity_issuer, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.identity_subject', :identity_subject, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.app_user_id', :app_user_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.role', :role, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.company_id', :company_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.employee_id', :employee_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.branch_id', :branch_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.actor_kind', :actor_kind, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.actor_key', :actor_key, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.business_date', :business_date, true) IS NOT NULL
"""
)

PROBE_PREDICATE = """
current_user = 'workloop_runtime'
AND public.workloop_actor_kind() = 'human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() = DATE '2026-09-06'
AND public.workloop_app_user_id() = app_user_id
AND EXISTS (
  SELECT 1
  FROM public.app_users AS context_app_user
  WHERE context_app_user.id = app_user_id
    AND context_app_user.identity_issuer = public.workloop_identity_issuer()
    AND context_app_user.identity_subject = public.workloop_identity_subject()
    AND context_app_user.status::text = 'active'
)
AND public.workloop_role() = allowed_role
AND public.workloop_company_id() = company_id
AND public.workloop_branch_id() = branch_id
AND public.workloop_employee_id() IS NOT DISTINCT FROM employee_id
"""


def _row_values(table: str, **matches: object) -> dict[str, object]:
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
    app_user = _row_values("app_users", identity_subject=subject)
    profile = _row_values("user_profiles", app_user_id=app_user["id"])
    employee_id = cast(uuid.UUID | None, profile["employee_id"])
    employee = None if employee_id is None else _row_values("employees", id=employee_id)
    return AuthorizationPrincipal(
        app_user_id=cast(uuid.UUID, app_user["id"]),
        account_status=AccountStatus.ACTIVE,
        role=AppRole(cast(str, profile["role"])),
        company_id=cast(uuid.UUID, profile["company_id"]),
        employee_id=employee_id,
        branch_id=None if employee is None else cast(uuid.UUID, employee["branch_id"]),
    )


def claims_for(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def _probe_rows() -> list[dict[str, object]]:
    horizon_admin = principal_for(SUBJECTS["horizon_admin"])
    horizon_manager = principal_for(SUBJECTS["horizon_manager"])
    horizon_employee = principal_for(SUBJECTS["horizon_employee"])
    cedar_admin = principal_for(SUBJECTS["cedar_admin"])
    return [
        {
            "id": PROBE_IDS["horizon_admin"],
            "company_id": horizon_admin.company_id,
            "branch_id": c.BRANCH_DXB,
            "app_user_id": horizon_admin.app_user_id,
            "employee_id": None,
            "allowed_role": "admin",
            "payload": "original",
        },
        {
            "id": PROBE_IDS["horizon_manager"],
            "company_id": horizon_manager.company_id,
            "branch_id": horizon_manager.branch_id,
            "app_user_id": horizon_manager.app_user_id,
            "employee_id": horizon_manager.employee_id,
            "allowed_role": "manager",
            "payload": "original",
        },
        {
            "id": PROBE_IDS["horizon_employee"],
            "company_id": horizon_employee.company_id,
            "branch_id": horizon_employee.branch_id,
            "app_user_id": horizon_employee.app_user_id,
            "employee_id": horizon_employee.employee_id,
            "allowed_role": "employee",
            "payload": "original",
        },
        {
            "id": PROBE_IDS["cedar_admin"],
            "company_id": cedar_admin.company_id,
            "branch_id": c.BRANCH_SHJ,
            "app_user_id": cedar_admin.app_user_id,
            "employee_id": None,
            "allowed_role": "admin",
            "payload": "original",
        },
    ]


async def _verify_wrong_login(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_size=1, max_overflow=0)
    try:
        active_principal = principal_for(SUBJECTS["horizon_employee"])
        transaction_factory = AuthorizationTransactionFactory(
            engine=engine,
            clock=lambda: datetime(2026, 9, 6, 12, tzinfo=ZoneInfo("Asia/Dubai")),
        )
        try:
            async with transaction_factory.transaction(
                claims=claims_for(SUBJECTS["horizon_employee"]),
                principal=active_principal,
            ):
                raise AssertionError("migration login reached protected SQL")
        except AuthorizationContextError:
            pass
        else:
            raise AssertionError(
                "migration login was accepted as a human runtime login"
            )
    finally:
        await engine.dispose()


def setup(database_url: str) -> None:
    rows = build_rows()
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            connection.exec_driver_sql(f"DROP TABLE IF EXISTS public.{PROBE_TABLE}")
            connection.exec_driver_sql(
                f"""
CREATE TABLE public.{PROBE_TABLE} (
  id uuid PRIMARY KEY,
  company_id uuid NOT NULL,
  branch_id uuid NOT NULL,
  app_user_id uuid NOT NULL,
  employee_id uuid NULL,
  allowed_role text NOT NULL,
  payload text NOT NULL
)
"""
            )
            connection.execute(
                text(
                    f"""
INSERT INTO public.{PROBE_TABLE} (
  id, company_id, branch_id, app_user_id, employee_id, allowed_role, payload
)
VALUES (
  :id, :company_id, :branch_id, :app_user_id, :employee_id, :allowed_role, :payload
)
"""
                ),
                _probe_rows(),
            )
            connection.exec_driver_sql(
                f"ALTER TABLE public.{PROBE_TABLE} ENABLE ROW LEVEL SECURITY"
            )
            connection.exec_driver_sql(
                f"""
CREATE POLICY phase5d_context_probe_policy
ON public.{PROBE_TABLE}
FOR ALL
TO workloop_runtime
USING ({PROBE_PREDICATE})
WITH CHECK ({PROBE_PREDICATE})
"""
            )
            connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{PROBE_TABLE} TO workloop_runtime"
            )
        asyncio.run(_verify_wrong_login(database_url))
    finally:
        engine.dispose()


def cleanup(database_url: str) -> None:
    rows = build_rows()
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"DROP TABLE IF EXISTS public.{PROBE_TABLE}")
            clean(connection, rows)
    finally:
        engine.dispose()


def runtime_values(
    active_principal: AuthorizationPrincipal, subject: str
) -> dict[str, str]:
    return {
        "identity_issuer": c.SEED_ISSUER,
        "identity_subject": subject,
        "app_user_id": str(active_principal.app_user_id),
        "role": active_principal.role.value,
        "company_id": str(active_principal.company_id),
        "employee_id": ""
        if active_principal.employee_id is None
        else str(active_principal.employee_id),
        "branch_id": ""
        if active_principal.branch_id is None
        else str(active_principal.branch_id),
        "actor_kind": "human",
        "actor_key": "",
        "business_date": "2026-09-06",
    }


async def context_is_empty(connection: AsyncConnection) -> None:
    values = (await connection.execute(READ_CONTEXT)).one()
    assert len(values) == len(CONTEXT_KEYS)
    assert all(value is None for value in values)
    raw_values = (await connection.execute(READ_RAW_CONTEXT)).one()
    assert len(raw_values) == len(CONTEXT_KEYS)
    assert all(value in (None, "") for value in raw_values)


async def pooled_context_is_empty(engine: Any) -> None:
    async with engine.connect() as connection:
        await context_is_empty(connection)
        visible = (
            await connection.execute(text(f"SELECT id FROM public.{PROBE_TABLE}"))
        ).scalars()
        assert list(visible) == []


async def probe_payload(
    transaction_factory: AuthorizationTransactionFactory,
    subject: str,
    probe_id: uuid.UUID,
    *,
    branch_id: uuid.UUID | None = None,
) -> str:
    async with transaction_factory.transaction(
        claims=claims_for(subject),
        principal=principal_for(subject),
        verified_admin_branch_id=branch_id,
    ) as connection:
        row = (
            await connection.execute(
                text(f"SELECT payload FROM public.{PROBE_TABLE} WHERE id = :id"),
                {"id": probe_id},
            )
        ).one()
        return cast(str, row[0])


async def verify_identity_bootstrap_cleanup(database_url: str) -> None:
    engine = create_async_engine(database_url, pool_size=1, max_overflow=0)
    try:
        resolver = ApplicationUserResolver(
            engine=engine,
            issuer=c.SEED_ISSUER,
            timeout_seconds=5,
        )
        resolved = await resolver.resolve(
            issuer=c.SEED_ISSUER,
            subject=SUBJECTS["horizon_employee"],
        )
        assert resolved == principal_for(SUBJECTS["horizon_employee"])
        await pooled_context_is_empty(engine)
    finally:
        await engine.dispose()


async def verify_commit_and_exception_cleanup(
    engine: Any, transaction_factory: AuthorizationTransactionFactory
) -> None:
    subject = SUBJECTS["horizon_employee"]
    active_principal = principal_for(subject)
    async with transaction_factory.transaction(
        claims=claims_for(subject), principal=active_principal
    ) as connection:
        values = (await connection.execute(READ_CONTEXT)).one()
        assert values == (
            c.SEED_ISSUER,
            subject,
            active_principal.app_user_id,
            "employee",
            active_principal.company_id,
            active_principal.employee_id,
            active_principal.branch_id,
            "human",
            None,
            date(2026, 9, 6),
        )
        result = await connection.execute(
            text(
                f"UPDATE public.{PROBE_TABLE} SET payload = 'committed' WHERE id = :id"
            ),
            {"id": PROBE_IDS["horizon_employee"]},
        )
        assert result.rowcount == 1
    await pooled_context_is_empty(engine)

    try:
        async with transaction_factory.transaction(
            claims=claims_for(subject), principal=active_principal
        ) as connection:
            result = await connection.execute(
                text(
                    f"UPDATE public.{PROBE_TABLE} SET payload = 'rolled-back' WHERE id = :id"
                ),
                {"id": PROBE_IDS["horizon_employee"]},
            )
            assert result.rowcount == 1
            raise RuntimeError("synthetic protected failure")
    except RuntimeError:
        pass
    else:
        raise AssertionError("protected exception did not escape")
    await pooled_context_is_empty(engine)
    assert (
        await probe_payload(
            transaction_factory,
            subject,
            PROBE_IDS["horizon_employee"],
        )
        == "committed"
    )


async def verify_explicit_rollback(engine: Any) -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        await connection.execute(
            text(
                "SELECT pg_catalog.set_config('workloop.company_id', :company_id, true)"
            ),
            {"company_id": str(c.COMPANY_ID[c.HORIZON])},
        )
        assert (
            await connection.execute(text("SELECT public.workloop_company_id()"))
        ).scalar_one() == c.COMPANY_ID[c.HORIZON]
        await transaction.rollback()
        await context_is_empty(connection)
        await connection.rollback()
    await pooled_context_is_empty(engine)


async def verify_cancellation_cleanup(
    engine: Any, transaction_factory: AuthorizationTransactionFactory
) -> None:
    entered = asyncio.Event()
    hold = asyncio.Event()
    subject = SUBJECTS["horizon_manager"]

    async def cancelled_work() -> None:
        async with transaction_factory.transaction(
            claims=claims_for(subject), principal=principal_for(subject)
        ):
            entered.set()
            await hold.wait()

    task = asyncio.create_task(cancelled_work())
    await asyncio.wait_for(entered.wait(), timeout=5)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("cancelled work completed")
    await pooled_context_is_empty(engine)


async def verify_concurrent_scope(
    transaction_factory: AuthorizationTransactionFactory,
) -> None:
    cases = (
        ("horizon_admin", c.BRANCH_DXB),
        ("horizon_manager", None),
        ("horizon_employee", None),
        ("cedar_admin", c.BRANCH_SHJ),
    )

    async def visible_probe(case: str, branch_id: uuid.UUID | None) -> uuid.UUID:
        subject = SUBJECTS[case]
        async with transaction_factory.transaction(
            claims=claims_for(subject),
            principal=principal_for(subject),
            verified_admin_branch_id=branch_id,
        ) as connection:
            await asyncio.sleep(0.05)
            rows = (
                await connection.execute(text(f"SELECT id FROM public.{PROBE_TABLE}"))
            ).scalars()
            visible = list(rows)
            assert visible == [PROBE_IDS[case]]
            return visible[0]

    results = await asyncio.gather(*(visible_probe(*case) for case in cases))
    assert set(results) == {PROBE_IDS[case] for case, _ in cases}


async def assert_raw_context_denied(engine: Any, values: dict[str, str]) -> None:
    async with engine.begin() as connection:
        await connection.execute(SET_RAW_CONTEXT, values)
        visible = (
            await connection.execute(text(f"SELECT id FROM public.{PROBE_TABLE}"))
        ).scalars()
        assert list(visible) == []
        result = await connection.execute(
            text(f"UPDATE public.{PROBE_TABLE} SET payload = 'denied'")
        )
        assert result.rowcount == 0


async def verify_malformed_partial_and_actor_context(
    engine: Any, transaction_factory: AuthorizationTransactionFactory
) -> None:
    subject = SUBJECTS["horizon_employee"]
    active_principal = principal_for(SUBJECTS["horizon_employee"])
    base = runtime_values(active_principal, subject)
    malformed = (
        {**base, "identity_issuer": "   "},
        {**base, "identity_subject": "x" * 256},
        {**base, "app_user_id": "not-a-uuid"},
        {**base, "company_id": "not-a-uuid"},
        {**base, "employee_id": "not-a-uuid"},
        {**base, "branch_id": "not-a-uuid"},
        {**base, "role": "owner"},
        {**base, "business_date": "2026-02-30"},
        {**base, "actor_kind": "scheduled_job", "actor_key": "expiry_processing"},
        {key.removeprefix("workloop."): "" for key in CONTEXT_KEYS},
    )
    expected_payload = await probe_payload(
        transaction_factory,
        subject,
        PROBE_IDS["horizon_employee"],
    )
    for values in malformed:
        await assert_raw_context_denied(engine, values)
        assert (
            await probe_payload(
                transaction_factory,
                subject,
                PROBE_IDS["horizon_employee"],
            )
            == expected_payload
        )


async def verify_stale_and_mismatched_principals(
    transaction_factory: AuthorizationTransactionFactory,
) -> None:
    subject = SUBJECTS["horizon_employee"]
    active_principal = principal_for(subject)
    stale_principals = (
        AuthorizationPrincipal(
            app_user_id=uuid.uuid4(),
            account_status=active_principal.account_status,
            role=active_principal.role,
            company_id=active_principal.company_id,
            employee_id=active_principal.employee_id,
            branch_id=active_principal.branch_id,
        ),
        AuthorizationPrincipal(
            app_user_id=active_principal.app_user_id,
            account_status=active_principal.account_status,
            role=active_principal.role,
            company_id=uuid.uuid4(),
            employee_id=active_principal.employee_id,
            branch_id=active_principal.branch_id,
        ),
    )
    for stale in stale_principals:
        try:
            async with transaction_factory.transaction(
                claims=claims_for(subject), principal=stale
            ):
                raise AssertionError("stale principal reached protected SQL")
        except AuthorizationContextError:
            pass
        else:
            raise AssertionError("stale principal was accepted")

    try:
        async with transaction_factory.transaction(
            claims=claims_for("different-synthetic-subject"),
            principal=active_principal,
        ):
            raise AssertionError("mismatched identity reached protected SQL")
    except AuthorizationContextError:
        pass
    else:
        raise AssertionError("mismatched identity was accepted")


async def verify_runtime_privileges(engine: Any) -> None:
    async with engine.connect() as connection:
        role = (
            await connection.execute(
                text(
                    """
SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls
FROM pg_catalog.pg_roles
WHERE rolname = 'workloop_runtime'
"""
                )
            )
        ).one()
        assert role == (False, False, False, False, False)
        assert (
            await connection.execute(
                text("SELECT pg_catalog.has_schema_privilege('public', 'CREATE')")
            )
        ).scalar_one() is False
        membership_count = (
            await connection.execute(
                text(
                    """
SELECT pg_catalog.count(*)
FROM pg_catalog.pg_auth_members AS membership
JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
WHERE member.rolname = 'workloop_runtime'
"""
                )
            )
        ).scalar_one()
        assert membership_count == 0

        helper_rows = (
            await connection.execute(
                text(
                    """
SELECT
  procedure.proname,
  pg_catalog.pg_get_userbyid(procedure.proowner),
  procedure.prosecdef,
  procedure.provolatile,
  procedure.proconfig,
  pg_catalog.has_function_privilege('workloop_runtime', procedure.oid, 'EXECUTE'),
  pg_catalog.has_function_privilege('public', procedure.oid, 'EXECUTE')
FROM pg_catalog.pg_proc AS procedure
JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
WHERE namespace.nspname = 'public'
  AND procedure.proname = ANY(:names)
ORDER BY procedure.proname
"""
                ),
                {"names": list(CONTEXT_READER_NAMES)},
            )
        ).all()
        assert [row[0] for row in helper_rows] == sorted(CONTEXT_READER_NAMES)
        for (
            _,
            owner,
            is_definer,
            volatility,
            settings,
            runtime_execute,
            public_execute,
        ) in helper_rows:
            assert owner == "workloop_migration"
            assert is_definer is False
            assert volatility == "s"
            assert settings == ["search_path=pg_catalog, pg_temp"]
            assert runtime_execute is True
            assert public_execute is False

        ownership_count = (
            await connection.execute(
                text(
                    """
SELECT pg_catalog.count(*)
FROM pg_catalog.pg_class AS object
JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = object.relnamespace
WHERE namespace.nspname = 'public'
  AND pg_catalog.pg_get_userbyid(object.relowner) = 'workloop_runtime'
"""
                )
            )
        ).scalar_one()
        assert ownership_count == 0
        await connection.rollback()

    for forbidden_sql in (
        "SET ROLE workloop_migration",
        "CREATE TABLE public.phase5d_forbidden_create (id integer)",
    ):
        async with engine.connect() as connection:
            try:
                await connection.execute(text(forbidden_sql))
            except DBAPIError:
                await connection.rollback()
            else:
                raise AssertionError("runtime role gained a forbidden capability")


async def verify_runtime(database_url: str) -> None:
    await verify_identity_bootstrap_cleanup(database_url)
    engine = create_async_engine(
        database_url, pool_size=4, max_overflow=0, pool_pre_ping=True
    )
    transaction_factory = AuthorizationTransactionFactory(
        engine=engine,
        clock=lambda: datetime(2026, 9, 6, 12, tzinfo=ZoneInfo("Asia/Dubai")),
    )
    try:
        await verify_commit_and_exception_cleanup(engine, transaction_factory)
        await verify_explicit_rollback(engine)
        await verify_cancellation_cleanup(engine, transaction_factory)
        await verify_concurrent_scope(transaction_factory)
        await verify_malformed_partial_and_actor_context(engine, transaction_factory)
        await verify_stale_and_mismatched_principals(transaction_factory)
        await verify_runtime_privileges(engine)
        await pooled_context_is_empty(engine)
    finally:
        await engine.dispose()


def required_url(mode: str) -> str:
    variable = "DATABASE_URL" if mode == "verify" else "MIGRATION_DATABASE_URL"
    value = os.environ.get(variable)
    if not value:
        raise SystemExit(f"{variable} is required")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("setup", "verify", "cleanup"))
    mode = parser.parse_args().mode
    database_url = required_url(mode)
    if mode == "setup":
        setup(database_url)
    elif mode == "cleanup":
        cleanup(database_url)
    else:
        asyncio.run(verify_runtime(database_url))
    print(f"Phase 5D context {mode} passed.")


if __name__ == "__main__":
    main()
