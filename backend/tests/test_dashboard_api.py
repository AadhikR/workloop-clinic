from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.dashboards import DashboardCard, DashboardResponse
from app.services.execution import ServiceExecutionError
from tests.test_http_boundary import make_settings

COMPANY = uuid.UUID("c6000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("c6000000-0000-4000-8000-000000000002")
USER = uuid.UUID("c6000000-0000-4000-8000-000000000003")
EMPLOYEE = uuid.UUID("c6000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 9, 24, 8, tzinfo=UTC)


def claims() -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer="https://seed.workloop.test",
        subject="subject",
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def principal(role: AppRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=USER,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY,
        employee_id=None if role is AppRole.ADMIN else EMPLOYEE,
        branch_id=None if role is AppRole.ADMIN else BRANCH,
    )


class StubService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, AuthorizationPrincipal, uuid.UUID]] = []

    async def read(
        self, kind: str, actor: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> DashboardResponse:
        self.calls.append((kind, actor, branch_id))
        if self.fail:
            raise ServiceExecutionError("dashboard_source_unavailable")
        return DashboardResponse(
            as_of=NOW,
            business_date=date(2026, 9, 24),
            source_version="sha256:" + "a" * 64,
            cards=[
                DashboardCard(
                    code="testCard",
                    label="Test card",
                    value=1,
                    unit="items",
                    severity="info",
                )
            ],
        )


class RecordingExecutor:
    def __init__(self, expected_branch: uuid.UUID | None) -> None:
        self.expected_branch = expected_branch

    async def execute(
        self,
        *,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
        **_values: object,
    ) -> object:
        assert selected_admin_branch_id == self.expected_branch
        return await operation(cast(AsyncConnection, object()))


@asynccontextmanager
async def client_for(
    role: AppRole, *, fail: bool = False
) -> AsyncGenerator[tuple[AsyncClient, StubService], None]:
    from app.main import create_app

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = RecordingExecutor(
        BRANCH if role is AppRole.ADMIN else None
    )
    service = StubService(fail)

    def service_factory(_connection: AsyncConnection) -> StubService:
        return service

    application.state.dashboard_service_factory = service_factory
    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, service


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["admin", "clinical"])
async def test_admin_dashboards_require_selected_branch(kind: str) -> None:
    async with client_for(AppRole.ADMIN) as (client, service):
        response = await client.get(
            f"/api/v1/dashboards/{kind}", headers={"X-Workloop-Branch-ID": str(BRANCH)}
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert service.calls[0][0] == kind
    assert service.calls[0][2] == BRANCH


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_self_dashboard_uses_principal_scope_without_selector(role: AppRole) -> None:
    async with client_for(role) as (client, service):
        response = await client.get("/api/v1/dashboards/self")
    assert response.status_code == 200
    assert service.calls[0][1].employee_id == EMPLOYEE


@pytest.mark.asyncio
async def test_self_dashboard_rejects_employee_id_and_unknown_filters() -> None:
    async with client_for(AppRole.EMPLOYEE) as (client, service):
        response = await client.get(f"/api/v1/dashboards/self?employeeId={uuid.uuid4()}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert service.calls == []


@pytest.mark.asyncio
async def test_dashboard_branch_headers_are_role_derived() -> None:
    async with client_for(AppRole.ADMIN) as (client, _service):
        missing = await client.get("/api/v1/dashboards/admin")
    async with client_for(AppRole.EMPLOYEE) as (client, _service):
        forged = await client.get(
            "/api/v1/dashboards/self", headers={"X-Workloop-Branch-ID": str(BRANCH)}
        )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "branch_required"
    assert forged.status_code == 422
    assert forged.json()["error"]["code"] == "invalid_branch"


@pytest.mark.asyncio
async def test_dashboard_source_failure_returns_safe_503_without_cards() -> None:
    async with client_for(AppRole.ADMIN, fail=True) as (client, _service):
        response = await client.get(
            "/api/v1/dashboards/admin", headers={"X-Workloop-Branch-ID": str(BRANCH)}
        )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dashboard_source_unavailable"
    assert "data" not in response.json()
