import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.db.authorization_context import (
    CONTEXT_KEYS,
    CONTEXT_READER_NAMES,
    AuthorizationContextError,
    AuthorizationTransactionFactory,
)
from app.models.identity import AccountStatus, AppRole


class ScalarResult:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one(self) -> object:
        return self.value


class StubAuthorizationConnection:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.statements: list[tuple[Any, dict[str, str] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(
        self, statement: Any, parameters: dict[str, str] | None = None
    ) -> ScalarResult:
        self.statements.append((statement, parameters))
        is_validation = "FROM public.app_users" in str(statement)
        return ScalarResult(self.valid if is_validation else True)

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[None]:
        try:
            yield
        except BaseException:
            self.rollbacks += 1
            raise
        else:
            self.commits += 1


class StubAuthorizationEngine:
    def __init__(self, connection: StubAuthorizationConnection) -> None:
        self.connection = connection
        self.connect_count = 0

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[StubAuthorizationConnection]:
        self.connect_count += 1
        yield self.connection


def claims(subject: str = "synthetic-subject") -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer="https://seed.workloop.test",
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def principal(role: AppRole) -> AuthorizationPrincipal:
    staff = role in {AppRole.MANAGER, AppRole.EMPLOYEE}
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=uuid.uuid4(),
        employee_id=uuid.uuid4() if staff else None,
        branch_id=uuid.uuid4() if staff else None,
    )


def factory(
    connection: StubAuthorizationConnection,
    *,
    now: datetime = datetime(2026, 9, 5, 21, 30, tzinfo=UTC),
) -> AuthorizationTransactionFactory:
    engine = cast(AsyncEngine, StubAuthorizationEngine(connection))
    return AuthorizationTransactionFactory(engine=engine, clock=lambda: now)


def test_context_key_and_reader_catalogues_are_exact() -> None:
    assert CONTEXT_KEYS == (
        "workloop.identity_issuer",
        "workloop.identity_subject",
        "workloop.app_user_id",
        "workloop.role",
        "workloop.company_id",
        "workloop.employee_id",
        "workloop.branch_id",
        "workloop.actor_kind",
        "workloop.actor_key",
        "workloop.business_date",
    )
    assert tuple(key.replace(".", "_") for key in CONTEXT_KEYS) == CONTEXT_READER_NAMES


@pytest.mark.asyncio
async def test_human_transaction_sets_bound_local_values_and_commits() -> None:
    connection = StubAuthorizationConnection()
    active_principal = principal(AppRole.MANAGER)

    async with factory(connection).transaction(
        claims=claims(), principal=active_principal
    ) as yielded:
        assert yielded is connection

    assert connection.commits == 1
    assert connection.rollbacks == 0
    assert len(connection.statements) == 2
    context_statement, values = connection.statements[0]
    sql = str(context_statement)
    assert sql.count("true)") == 10
    assert values is not None
    assert values == {
        "identity_issuer": "https://seed.workloop.test",
        "identity_subject": "synthetic-subject",
        "app_user_id": str(active_principal.app_user_id),
        "role": "manager",
        "company_id": str(active_principal.company_id),
        "employee_id": str(active_principal.employee_id),
        "branch_id": str(active_principal.branch_id),
        "business_date": "2026-09-06",
    }
    assert all(value not in sql for value in values.values())


@pytest.mark.asyncio
async def test_admin_transaction_uses_only_verified_branch() -> None:
    connection = StubAuthorizationConnection()
    active_principal = principal(AppRole.ADMIN)
    selected_branch = uuid.uuid4()

    async with factory(connection).transaction(
        claims=claims(),
        principal=active_principal,
        verified_admin_branch_id=selected_branch,
    ):
        pass

    values = connection.statements[0][1]
    assert values is not None
    assert values["employee_id"] == ""
    assert values["branch_id"] == str(selected_branch)


@pytest.mark.asyncio
async def test_consumer_exception_rolls_back_transaction() -> None:
    connection = StubAuthorizationConnection()

    with pytest.raises(RuntimeError, match="protected operation failed"):
        async with factory(connection).transaction(
            claims=claims(), principal=principal(AppRole.EMPLOYEE)
        ):
            raise RuntimeError("protected operation failed")

    assert connection.commits == 0
    assert connection.rollbacks == 1


@pytest.mark.asyncio
async def test_database_revalidation_rejects_stale_principal() -> None:
    connection = StubAuthorizationConnection(valid=False)

    with pytest.raises(AuthorizationContextError):
        async with factory(connection).transaction(
            claims=claims(), principal=principal(AppRole.EMPLOYEE)
        ):
            pytest.fail("stale context reached protected SQL")

    assert connection.commits == 0
    assert connection.rollbacks == 1


@pytest.mark.parametrize(
    ("active_principal", "selected_branch"),
    [
        (principal(AppRole.MANAGER), uuid.uuid4()),
        (
            AuthorizationPrincipal(
                app_user_id=uuid.uuid4(),
                account_status=AccountStatus.ACTIVE,
                role=AppRole.ADMIN,
                company_id=uuid.uuid4(),
                employee_id=uuid.uuid4(),
                branch_id=None,
            ),
            None,
        ),
        (
            AuthorizationPrincipal(
                app_user_id=uuid.uuid4(),
                account_status=AccountStatus.DISABLED,
                role=AppRole.EMPLOYEE,
                company_id=uuid.uuid4(),
                employee_id=uuid.uuid4(),
                branch_id=uuid.uuid4(),
            ),
            None,
        ),
    ],
    ids=["staff-selector", "admin-employee-link", "disabled-account"],
)
@pytest.mark.asyncio
async def test_invalid_principal_shapes_fail_before_checkout(
    active_principal: AuthorizationPrincipal,
    selected_branch: uuid.UUID | None,
) -> None:
    connection = StubAuthorizationConnection()
    engine = StubAuthorizationEngine(connection)
    transaction_factory = AuthorizationTransactionFactory(
        engine=cast(AsyncEngine, engine),
        clock=lambda: datetime(2026, 9, 6, tzinfo=UTC),
    )

    with pytest.raises(AuthorizationContextError):
        async with transaction_factory.transaction(
            claims=claims(),
            principal=active_principal,
            verified_admin_branch_id=selected_branch,
        ):
            pytest.fail("invalid context reached protected SQL")

    assert engine.connect_count == 0


@pytest.mark.asyncio
async def test_naive_clock_fails_before_checkout() -> None:
    connection = StubAuthorizationConnection()
    engine = StubAuthorizationEngine(connection)
    transaction_factory = AuthorizationTransactionFactory(
        engine=cast(AsyncEngine, engine),
        clock=lambda: datetime(2026, 9, 6),
    )

    with pytest.raises(AuthorizationContextError):
        async with transaction_factory.transaction(
            claims=claims(), principal=principal(AppRole.EMPLOYEE)
        ):
            pytest.fail("untrusted date reached protected SQL")

    assert engine.connect_count == 0
