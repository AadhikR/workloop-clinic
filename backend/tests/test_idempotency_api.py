import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.services.idempotency import RecoveryKey, RecoveryNamespaces
from tests.test_http_boundary import make_settings

APP_USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
KEY = uuid.UUID("7c000000-0000-4000-8000-000000000002")
NOW = datetime(2026, 9, 10, tzinfo=UTC)


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
        app_user_id=APP_USER_ID,
        account_status=AccountStatus.ACTIVE,
        role=AppRole.ADMIN,
        company_id=COMPANY_ID,
        employee_id=None,
        branch_id=None,
    )


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> object:
        assert claims == globals()["claims"]()
        assert principal == globals()["principal"]()
        assert selected_admin_branch_id is None
        self.calls += 1
        return await operation(cast(AsyncConnection, object()))


class StatusCoordinator:
    def __init__(self, status: str) -> None:
        self.value = status
        self.keys: list[uuid.UUID] = []

    async def status(self, *, principal: AuthorizationPrincipal, key: uuid.UUID) -> str:
        assert principal == globals()["principal"]()
        self.keys.append(key)
        return self.value


@asynccontextmanager
async def client_for(
    status: str = "completed",
) -> AsyncGenerator[tuple[AsyncClient, FastAPI, RecordingExecutor, StatusCoordinator]]:
    from app.main import create_app

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    executor = RecordingExecutor()
    coordinator = StatusCoordinator(status)
    application.state.authorized_service_executor = executor

    def coordinator_factory(_connection: AsyncConnection) -> StatusCoordinator:
        return coordinator

    application.state.idempotency_coordinator_factory = coordinator_factory
    application.state.idempotency_recovery_namespaces = RecoveryNamespaces(
        RecoveryKey("1234abcd", b"1" * 32),
        [RecoveryKey("8765dcba", b"2" * 32, NOW + timedelta(days=7))],
        clock=lambda: NOW,
    )

    async def verified_claims() -> AccessTokenClaims:
        return claims()

    async def resolved_principal() -> AuthorizationPrincipal:
        return principal()

    application.dependency_overrides[require_access_token] = verified_claims
    application.dependency_overrides[require_authorization_principal] = resolved_principal
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, application, executor, coordinator


@pytest.mark.asyncio
async def test_recovery_namespaces_and_owned_status_have_exact_shapes() -> None:
    async with client_for() as (client, _application, executor, coordinator):
        namespaces = await client.get("/api/v1/idempotency-recovery-namespaces")
        status = await client.get(
            "/api/v1/idempotency-status", headers={"Idempotency-Key": str(KEY)}
        )

    assert namespaces.status_code == status.status_code == 200
    assert set(namespaces.json()["data"]) == {"current", "accepted"}
    assert namespaces.json()["data"]["current"].startswith("rn1.1234abcd.")
    assert len(namespaces.json()["data"]["accepted"]) == 2
    assert status.json() == {"data": {"status": "completed"}}
    assert coordinator.keys == [KEY]
    assert executor.calls == 1


@pytest.mark.asyncio
async def test_status_rejects_missing_duplicate_invalid_keys_and_branch_headers() -> None:
    async with client_for() as (client, _application, executor, _coordinator):
        missing = await client.get("/api/v1/idempotency-status")
        duplicate = await client.get(
            "/api/v1/idempotency-status",
            headers=[("Idempotency-Key", str(KEY)), ("Idempotency-Key", str(KEY))],
        )
        invalid = await client.get(
            "/api/v1/idempotency-status",
            headers={"Idempotency-Key": str(KEY).upper()},
        )
        selected = await client.get(
            "/api/v1/idempotency-status",
            headers={"Idempotency-Key": str(KEY), "X-Workloop-Branch-ID": str(uuid.uuid4())},
        )

    assert missing.status_code == duplicate.status_code == invalid.status_code == 400
    assert missing.json()["error"]["code"] == "idempotency_key_required"
    assert duplicate.json()["error"]["code"] == "invalid_idempotency_key"
    assert invalid.json()["error"]["code"] == "invalid_idempotency_key"
    assert selected.status_code == 403
    assert executor.calls == 0
