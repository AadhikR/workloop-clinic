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
from app.schemas.shift_swaps import ShiftSwapResponse
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("20000000-0000-4000-8000-000000000001")
USER = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE = uuid.UUID("40000000-0000-4000-8000-000000000001")
TARGET = uuid.UUID("40000000-0000-4000-8000-000000000002")
SWAP = uuid.UUID("50000000-0000-4000-8000-000000000001")
REQUESTER_ASSIGNMENT = uuid.UUID("60000000-0000-4000-8000-000000000001")
TARGET_ASSIGNMENT = uuid.UUID("60000000-0000-4000-8000-000000000002")
KEY = "70000000-0000-4000-8000-000000000001"
SOURCE = "sha256:" + "a" * 64


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
        USER,
        AccountStatus.ACTIVE,
        role,
        COMPANY,
        None if role is AppRole.ADMIN else EMPLOYEE,
        None if role is AppRole.ADMIN else BRANCH,
    )


def swap() -> ShiftSwapResponse:
    now = datetime(2026, 9, 22, 6, tzinfo=UTC)
    return ShiftSwapResponse(
        id=SWAP,
        requester_employee_id=EMPLOYEE,
        requester_employee_name="Ravi Test",
        target_employee_id=TARGET,
        target_employee_name="Fatima Test",
        requester_date=date(2026, 10, 5),
        target_date=date(2026, 10, 6),
        reason="Family appointment",
        status="pending",
        rejection_reason="",
        expected_source_version=SOURCE,
        requester_assignment_id=REQUESTER_ASSIGNMENT,
        target_assignment_id=TARGET_ASSIGNMENT,
        requester_assignment_version=2,
        target_assignment_version=2,
        approved_publication_version_id=None,
        decided_at=None,
        decided_by_app_user_id=None,
        created_at=now,
        updated_at=now,
        version=1,
    )


class StubService:
    async def personal(self, *_: object) -> list[ShiftSwapResponse]:
        return [swap()]

    async def admin(self, *_: object) -> list[ShiftSwapResponse]:
        return [swap()]

    async def submit(self, *_: object) -> ShiftSwapResponse:
        return swap()

    async def cancel(self, *_: object) -> ShiftSwapResponse:
        return swap()

    async def reject(self, *_: object) -> ShiftSwapResponse:
        return swap()

    async def approve(self, *_: object) -> ShiftSwapResponse:
        return swap()

    async def authorize_replay(self, *_: object) -> None:
        return None


class ImmediateIdempotency:
    async def execute(self, **values: object) -> IdempotentResponse:
        return await cast(Callable[[], Awaitable[IdempotentResponse]], values["mutation"])()


class RecordingExecutor:
    def __init__(self, expected_branch: uuid.UUID | None) -> None:
        self.expected_branch = expected_branch

    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> object:
        assert selected_admin_branch_id == self.expected_branch
        return await operation(cast(AsyncConnection, object()))


@asynccontextmanager
async def client_for(role: AppRole) -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    def shift_swap_service_factory(_connection: AsyncConnection) -> StubService:
        return StubService()

    def idempotency_coordinator_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = RecordingExecutor(
        BRANCH if role is AppRole.ADMIN else None
    )
    application.state.shift_swap_service_factory = shift_swap_service_factory
    application.state.idempotency_coordinator_factory = idempotency_coordinator_factory
    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_staff_lists_submits_and_cancels_own_swaps() -> None:
    headers = {"Idempotency-Key": KEY}
    async with client_for(AppRole.EMPLOYEE) as client:
        listing = await client.get("/api/v1/roster/shift-swaps/self?status=pending&limit=20")
        submitted = await client.post(
            "/api/v1/roster/shift-swaps",
            headers=headers,
            json={
                "requesterDate": "2026-10-05",
                "targetEmployeeId": str(TARGET),
                "targetDate": "2026-10-06",
                "reason": "Family appointment",
                "expectedSourceVersion": SOURCE,
            },
        )
        cancelled = await client.post(
            f"/api/v1/roster/shift-swaps/{SWAP}/cancel",
            headers=headers,
            json={"expectedVersion": 1, "reason": None},
        )
    assert listing.status_code == 200
    assert submitted.status_code == 201
    assert cancelled.status_code == 200
    assert submitted.headers["location"] == f"/api/v1/roster/shift-swaps/{SWAP}"
    assert listing.json()["data"][0]["expectedSourceVersion"] == SOURCE


@pytest.mark.asyncio
async def test_admin_lists_rejects_and_approves_selected_branch_swaps() -> None:
    headers = {"Idempotency-Key": KEY, "X-Workloop-Branch-ID": str(BRANCH)}
    async with client_for(AppRole.ADMIN) as client:
        listing = await client.get(
            "/api/v1/roster/shift-swaps?status=pending&limit=100",
            headers={"X-Workloop-Branch-ID": str(BRANCH)},
        )
        rejected = await client.post(
            f"/api/v1/roster/shift-swaps/{SWAP}/reject",
            headers=headers,
            json={"expectedVersion": 1, "reason": "Coverage is required"},
        )
        approved = await client.post(
            f"/api/v1/roster/shift-swaps/{SWAP}/approve",
            headers=headers,
            json={"expectedVersion": 1, "expectedSourceVersion": SOURCE},
        )
    assert listing.status_code == rejected.status_code == approved.status_code == 200
    assert "location" not in rejected.headers
    assert "location" not in approved.headers


@pytest.mark.asyncio
async def test_shift_swap_routes_reject_unknown_fields_and_invalid_transitions() -> None:
    async with client_for(AppRole.EMPLOYEE) as client:
        bad_query = await client.get("/api/v1/roster/shift-swaps/self?status=unsafe")
        bad_body = await client.post(
            "/api/v1/roster/shift-swaps",
            headers={"Idempotency-Key": KEY},
            json={
                "requesterDate": "2026-10-05",
                "targetEmployeeId": str(TARGET),
                "targetDate": "2026-10-05",
                "reason": "Family appointment",
                "expectedSourceVersion": SOURCE,
                "salary": "10000.00",
            },
        )
    assert bad_query.status_code == bad_body.status_code == 422
