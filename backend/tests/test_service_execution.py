import asyncio
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.db.authorization_context import (
    AuthorizationBranchUnavailableError,
    AuthorizationContextError,
    AuthorizationContextUnavailableError,
)
from app.models.identity import AccountStatus, AppRole
from app.services.execution import (
    AuthorizedServiceExecutor,
    ServiceDeadlineExceeded,
    ServiceExecutionError,
)


class StubFactory:
    def __init__(self, failure: Exception | None = None) -> None:
        self.calls: list[uuid.UUID | None] = []
        self.entered = 0
        self.exited = 0
        self.connection = cast(AsyncConnection, object())
        self.failure = failure

    @asynccontextmanager
    async def transaction(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        verified_admin_branch_id: uuid.UUID | None = None,
    ) -> AsyncGenerator[AsyncConnection]:
        del claims, principal
        self.calls.append(verified_admin_branch_id)
        if self.failure is not None:
            raise self.failure
        self.entered += 1
        try:
            yield self.connection
        finally:
            self.exited += 1


def claims() -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer="https://seed.workloop.test",
        subject="synthetic-subject",
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def principal() -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=AppRole.ADMIN,
        company_id=uuid.uuid4(),
        employee_id=None,
        branch_id=None,
    )


@pytest.mark.asyncio
async def test_service_owns_one_authorized_transaction_with_selected_branch() -> None:
    factory = StubFactory()
    executor = AuthorizedServiceExecutor(cast(Any, factory), deadline_seconds=1)
    selected_branch = uuid.uuid4()

    async def operation(connection: AsyncConnection) -> str:
        assert connection is factory.connection
        assert factory.entered == 1
        assert factory.exited == 0
        return "done"

    result = await executor.execute(
        claims=claims(),
        principal=principal(),
        operation=operation,
        selected_admin_branch_id=selected_branch,
    )

    assert result == "done"
    assert factory.calls == [selected_branch]
    assert factory.exited == 1


@pytest.mark.asyncio
async def test_service_cleanup_runs_for_error_timeout_and_cancellation() -> None:
    for outcome in ("error", "timeout", "cancel"):
        factory = StubFactory()
        executor = AuthorizedServiceExecutor(cast(Any, factory), deadline_seconds=0.01)

        async def operation(_connection: AsyncConnection, current_outcome: str = outcome) -> None:
            if current_outcome == "error":
                raise RuntimeError("abort")
            await asyncio.sleep(10)

        task = asyncio.create_task(
            executor.execute(claims=claims(), principal=principal(), operation=operation)
        )
        if outcome == "cancel":
            await asyncio.sleep(0)
            task.cancel()

        expected = {
            "error": RuntimeError,
            "timeout": ServiceDeadlineExceeded,
            "cancel": asyncio.CancelledError,
        }[outcome]
        with pytest.raises(expected):
            await task
        assert factory.entered == factory.exited == 1


@pytest.mark.parametrize(
    ("failure", "expected_code"),
    [
        (AuthorizationBranchUnavailableError(), "resource_not_found"),
        (
            AuthorizationContextUnavailableError(),
            "application_account_lookup_unavailable",
        ),
        (AuthorizationContextError(), "application_account_unavailable"),
    ],
)
@pytest.mark.asyncio
async def test_service_maps_transaction_entry_failures_to_safe_codes(
    failure: Exception, expected_code: str
) -> None:
    factory = StubFactory(failure)
    executor = AuthorizedServiceExecutor(cast(Any, factory), deadline_seconds=1)

    async def operation(_connection: AsyncConnection) -> None:
        pytest.fail("failed transaction reached service operation")

    with pytest.raises(ServiceExecutionError) as captured:
        await executor.execute(
            claims=claims(),
            principal=principal(),
            operation=operation,
            selected_admin_branch_id=uuid.uuid4(),
        )

    assert captured.value.code == expected_code
    assert factory.entered == factory.exited == 0
