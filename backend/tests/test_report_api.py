from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.reports import ReportColumn, ReportResponse, ReportTotals
from app.services.reports import ReportQuery
from tests.test_http_boundary import make_settings

COMPANY = uuid.UUID("c9000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("c9000000-0000-4000-8000-000000000002")
USER = uuid.UUID("c9000000-0000-4000-8000-000000000003")
NOW = datetime(2026, 9, 25, 8, tzinfo=UTC)


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
        employee_id=None,
        branch_id=None,
    )


class StubService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, AuthorizationPrincipal, uuid.UUID, ReportQuery]] = []

    async def read(
        self,
        report_id: str,
        actor: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: ReportQuery,
    ) -> ReportResponse:
        self.calls.append((report_id, actor, branch_id, query))
        return ReportResponse(
            report_id=report_id,
            columns=[ReportColumn(key="employeeId", label="Employee ID", type="string")],
            rows=[],
            totals=ReportTotals(row_count=0),
            filters={"limit": query.limit},
            as_of=NOW,
            source_version="sha256:" + "a" * 64,
        )


class Executor:
    async def execute(
        self,
        *,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
        **_values: object,
    ) -> object:
        assert selected_admin_branch_id == BRANCH
        return await operation(cast(AsyncConnection, object()))


@asynccontextmanager
async def client_for(role: AppRole) -> AsyncGenerator[tuple[AsyncClient, StubService], None]:
    from app.main import create_app

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = Executor()
    service = StubService()
    application.state.report_service_factory = lambda _connection: service
    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, service


@pytest.mark.asyncio
async def test_report_route_accepts_only_catalogued_filters() -> None:
    async with client_for(AppRole.ADMIN) as (client, service):
        response = await client.get(
            "/api/v1/reports/payrollCost?period=2026-08&limit=20",
            headers={"X-Workloop-Branch-ID": str(BRANCH)},
        )
        unknown = await client.get(
            "/api/v1/reports/payrollCost?departmentId=" + str(uuid.uuid4()),
            headers={"X-Workloop-Branch-ID": str(BRANCH)},
        )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert service.calls[0][0] == "payrollCost"
    assert service.calls[0][3].period == "2026-08"
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "unknown_filter"


@pytest.mark.asyncio
async def test_report_route_denies_unknown_reports_roles_and_missing_branch() -> None:
    async with client_for(AppRole.ADMIN) as (client, _service):
        unknown = await client.get(
            "/api/v1/reports/expenses", headers={"X-Workloop-Branch-ID": str(BRANCH)}
        )
        missing = await client.get("/api/v1/reports/headcount")
    async with client_for(AppRole.EMPLOYEE) as (client, _service):
        denied = await client.get(
            "/api/v1/reports/headcount", headers={"X-Workloop-Branch-ID": str(BRANCH)}
        )
    assert unknown.status_code == 404
    assert missing.status_code == 400
    assert denied.status_code == 403
