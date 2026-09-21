from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.roster import (
    RosterAssignmentResponse,
    RosterComplianceOverrideResponse,
    RosterValidationResponse,
)
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("20000000-0000-4000-8000-000000000001")
USER = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE = uuid.UUID("40000000-0000-4000-8000-000000000001")
SHIFT = uuid.UUID("50000000-0000-4000-8000-000000000001")
ASSIGNMENT = uuid.UUID("60000000-0000-4000-8000-000000000001")
OVERRIDE = uuid.UUID("70000000-0000-4000-8000-000000000001")
KEY = "80000000-0000-4000-8000-000000000001"


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


def assignment() -> RosterAssignmentResponse:
    return RosterAssignmentResponse(
        id=ASSIGNMENT,
        employee_id=EMPLOYEE,
        employee_name="Synthetic Employee",
        department="Clinical",
        shift_id=SHIFT,
        shift_name="Morning",
        shift_code="M",
        shift_category="morning",
        date=date(2026, 9, 23),
        published=False,
        planned_hours=Decimal("8.00"),
        notes="",
        version=1,
        leave_conflict=False,
        updated_at=datetime(2026, 9, 22, tzinfo=UTC),
    )


class StubService:
    async def list(self, *_: object) -> tuple[list[RosterAssignmentResponse], None]:
        return [assignment()], None

    async def validation(self, *_: object) -> RosterValidationResponse:
        return RosterValidationResponse(
            period="2026-09",
            staffing_enforced=False,
            leave_conflicts=[],
            staffing_violations=None,
            ready=True,
        )

    async def create(self, *_: object) -> RosterAssignmentResponse:
        return assignment()

    async def replace(self, *_: object) -> RosterAssignmentResponse:
        return assignment()

    async def delete(self, *_: object) -> None:
        return None

    async def override(self, *_: object) -> RosterComplianceOverrideResponse:
        return RosterComplianceOverrideResponse(
            id=OVERRIDE,
            period="2026-09",
            rule_code="staffing_shortfall",
            violation_digest="sha256:" + "a" * 64,
            violation_snapshot={"code": "staffing_shortfall"},
            reason="Approved synthetic coverage exception",
            created_at=datetime(2026, 9, 22, tzinfo=UTC),
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
        assert selected_admin_branch_id == BRANCH
        return await operation(cast(AsyncConnection, object()))


def roster_service_factory(_connection: AsyncConnection) -> StubService:
    return StubService()


def idempotency_coordinator_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
    return ImmediateIdempotency()


@asynccontextmanager
async def client_for() -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = RecordingExecutor()
    application.state.roster_service_factory = roster_service_factory
    application.state.idempotency_coordinator_factory = idempotency_coordinator_factory
    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = principal
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_roster_month_and_validation_use_selected_branch_contract() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH)}
    async with client_for() as client:
        listed = await client.get(
            "/api/v1/roster/months/2026-09?department=Clinical&limit=20", headers=headers
        )
        validation = await client.get("/api/v1/roster/months/2026-09/validation", headers=headers)
        invalid = await client.get("/api/v1/roster/months/2026-9", headers=headers)
    assert listed.status_code == validation.status_code == 200
    assert listed.json()["data"][0]["plannedHours"] == "8.00"
    assert validation.json()["data"]["staffingViolations"] is None
    assert invalid.status_code == 404


@pytest.mark.asyncio
async def test_roster_create_requires_idempotency_and_returns_location() -> None:
    branch = {"X-Workloop-Branch-ID": str(BRANCH)}
    body = {
        "employeeId": str(EMPLOYEE),
        "shiftId": str(SHIFT),
        "date": "2026-09-23",
        "plannedHours": "8.00",
        "notes": "",
    }
    async with client_for() as client:
        missing = await client.post(
            "/api/v1/roster/months/2026-09/drafts", headers=branch, json=body
        )
        created = await client.post(
            "/api/v1/roster/months/2026-09/drafts",
            headers={**branch, "Idempotency-Key": KEY},
            json=body,
        )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "idempotency_key_required"
    assert created.status_code == 201
    assert created.headers["location"].endswith(str(ASSIGNMENT))


@pytest.mark.asyncio
async def test_roster_override_requires_closed_request_shape() -> None:
    headers = {
        "X-Workloop-Branch-ID": str(BRANCH),
        "Idempotency-Key": KEY,
    }
    async with client_for() as client:
        invalid = await client.post(
            "/api/v1/roster/months/2026-09/overrides",
            headers=headers,
            json={"violationDigest": "sha256:" + "a" * 64, "reason": "short"},
        )
        created = await client.post(
            "/api/v1/roster/months/2026-09/overrides",
            headers=headers,
            json={
                "violationDigest": "sha256:" + "a" * 64,
                "reason": "Approved synthetic coverage exception",
            },
        )
    assert invalid.status_code == 422
    assert created.status_code == 201
    assert created.json()["data"]["ruleCode"] == "staffing_shortfall"
