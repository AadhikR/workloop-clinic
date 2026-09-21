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
from app.schemas.attendance_periods import AttendancePeriodResponse
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("20000000-0000-4000-8000-000000000001")
USER = uuid.UUID("30000000-0000-4000-8000-000000000001")
PERIOD_ID = uuid.UUID("40000000-0000-4000-8000-000000000001")
KEY = "50000000-0000-4000-8000-000000000001"


def claims() -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer="https://seed.workloop.test",
        subject="subject",
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def principal() -> AuthorizationPrincipal:
    return AuthorizationPrincipal(USER, AccountStatus.ACTIVE, AppRole.ADMIN, COMPANY, None, None)


def response() -> AttendancePeriodResponse:
    return AttendancePeriodResponse(
        id=PERIOD_ID,
        period="2026-08",
        status="closed",
        payroll_ready=True,
        version=1,
        blocker_count=0,
        blockers=[],
        source_version="sha256:" + "a" * 64,
        closed_at=datetime(2026, 9, 21, 20, tzinfo=UTC),
        closed_by_actor_name="Administrator",
        amendment_reason=None,
    )


class StubService:
    async def list(self, *_: object) -> tuple[list[AttendancePeriodResponse], None]:
        return [response()], None

    async def detail(self, *_: object) -> AttendancePeriodResponse:
        return response()

    async def close(self, *_: object) -> AttendancePeriodResponse:
        return response()

    async def authorize_replay(self, *_: object) -> None:
        return None


class ImmediateIdempotency:
    async def execute(self, **values: object) -> IdempotentResponse:
        return await cast(Callable[[], Awaitable[IdempotentResponse]], values["mutation"])()


class RecordingExecutor:
    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> object:
        assert selected_admin_branch_id == BRANCH
        return await operation(cast(AsyncConnection, object()))


@asynccontextmanager
async def client_for() -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = RecordingExecutor()

    def service_factory(_connection: AsyncConnection) -> StubService:
        return StubService()

    def idempotency_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application.state.attendance_period_service_factory = service_factory
    application.state.idempotency_coordinator_factory = idempotency_factory
    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = principal
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_period_list_and_detail_use_strict_selected_branch_contracts() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH)}
    async with client_for() as client:
        listed = await client.get("/api/v1/attendance/periods?limit=20", headers=headers)
        detail = await client.get("/api/v1/attendance/periods/2026-08", headers=headers)
        invalid = await client.get("/api/v1/attendance/periods/2026-8", headers=headers)
    assert listed.status_code == detail.status_code == 200
    assert listed.json()["page"] == {"limit": 20, "nextCursor": None, "hasMore": False}
    assert detail.json()["data"]["sourceVersion"] == "sha256:" + "a" * 64
    assert invalid.status_code == 404


@pytest.mark.asyncio
async def test_close_requires_idempotency_and_returns_period_location() -> None:
    branch = {"X-Workloop-Branch-ID": str(BRANCH)}
    body = {"expectedVersion": 0, "amendmentReason": None}
    async with client_for() as client:
        missing = await client.post(
            "/api/v1/attendance/periods/2026-08/close", headers=branch, json=body
        )
        closed = await client.post(
            "/api/v1/attendance/periods/2026-08/close",
            headers={**branch, "Idempotency-Key": KEY},
            json=body,
        )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "idempotency_key_required"
    assert closed.status_code == 200
    assert closed.headers["location"] == "/api/v1/attendance/periods/2026-08"
