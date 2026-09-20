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
from app.schemas.attendance_ingestion import (
    BiometricImportResponse,
    BiometricMappingResponse,
    ClockEventResponse,
)
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY_ID = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
ADMIN_ID = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = uuid.UUID("40000000-0000-4000-8000-000000000001")
EVENT_ID = uuid.UUID("50000000-0000-4000-8000-000000000001")
MAPPING_ID = uuid.UUID("60000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 20, 8, tzinfo=UTC)
KEY = "70000000-0000-4000-8000-000000000001"


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
    employee = role is AppRole.EMPLOYEE
    return AuthorizationPrincipal(
        app_user_id=ADMIN_ID,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=EMPLOYEE_ID if employee else None,
        branch_id=BRANCH_ID if employee else None,
    )


def clock_event() -> ClockEventResponse:
    return ClockEventResponse(
        id=EVENT_ID,
        employee_id=EMPLOYEE_ID,
        event_type="CLOCK_IN",
        event_time=NOW,
        method="MANUAL",
        notes="Correction",
        created_at=NOW,
    )


class StubService:
    async def list_events(self, *_: object) -> tuple[list[ClockEventResponse], None]:
        return [clock_event()], None

    async def self_events(self, *_: object) -> tuple[list[ClockEventResponse], None]:
        return [clock_event()], None

    async def mappings(self, *_: object) -> tuple[list[BiometricMappingResponse], None]:
        return [
            BiometricMappingResponse(
                id=MAPPING_ID,
                badge_no="A-1",
                employee_id=EMPLOYEE_ID,
                device_name="Front door",
                created_at=NOW,
            )
        ], None

    async def manual(self, *_: object) -> ClockEventResponse:
        return clock_event()

    async def import_candidates(self, *_: object) -> BiometricImportResponse:
        return BiometricImportResponse(
            id=MAPPING_ID,
            accepted_count=0,
            duplicate_count=0,
            rejected_count=1,
            outcomes=[],
        )

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
        return await operation(cast(AsyncConnection, object()))


@asynccontextmanager
async def client_for(role: AppRole) -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = RecordingExecutor()
    service = StubService()

    def service_factory(_connection: AsyncConnection) -> StubService:
        return service

    def idempotency_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application.state.attendance_ingestion_service_factory = service_factory
    application.state.idempotency_coordinator_factory = idempotency_factory
    application.dependency_overrides[require_access_token] = lambda: claims()
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_admin_lists_events_and_mappings_with_exact_page_shape() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    async with client_for(AppRole.ADMIN) as client:
        events = await client.get("/api/v1/clock-events?limit=20", headers=headers)
        mappings = await client.get("/api/v1/biometric-mappings?limit=20", headers=headers)
    assert events.status_code == mappings.status_code == 200
    assert events.json()["page"] == {"limit": 20, "nextCursor": None, "hasMore": False}
    assert events.json()["data"][0]["employeeId"] == str(EMPLOYEE_ID)
    assert mappings.json()["data"][0]["badgeNo"] == "A-1"


@pytest.mark.asyncio
async def test_employee_reads_only_self_projection() -> None:
    async with client_for(AppRole.EMPLOYEE) as client:
        response = await client.get("/api/v1/attendance/me/events")
        rejected = await client.get(f"/api/v1/attendance/me/events?employeeId={uuid.uuid4()}")
    assert response.status_code == 200
    assert response.json()["data"][0]["employeeId"] == str(EMPLOYEE_ID)
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_manual_mutation_requires_idempotency_and_returns_location() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    body = {
        "employeeId": str(EMPLOYEE_ID),
        "eventType": "CLOCK_IN",
        "eventTime": "2026-09-20T12:00:00+04:00",
        "note": "Correction",
    }
    async with client_for(AppRole.ADMIN) as client:
        missing = await client.post("/api/v1/clock-events/manual", headers=headers, json=body)
        response = await client.post(
            "/api/v1/clock-events/manual",
            headers={**headers, "Idempotency-Key": KEY},
            json=body,
        )
    assert missing.status_code == 400
    assert response.status_code == 201
    assert response.headers["location"] == f"/api/v1/clock-events/{EVENT_ID}"
    assert response.json()["data"]["eventTime"] == "2026-09-20T08:00:00.000Z"
