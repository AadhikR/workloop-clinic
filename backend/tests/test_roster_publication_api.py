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
from app.schemas.roster_publication import (
    ColleagueScheduleEntryResponse,
    PublishedScheduleEntryResponse,
    RosterPublicationResponse,
)
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("20000000-0000-4000-8000-000000000001")
USER = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE = uuid.UUID("40000000-0000-4000-8000-000000000001")
VERSION = uuid.UUID("50000000-0000-4000-8000-000000000001")
ASSIGNMENT = uuid.UUID("60000000-0000-4000-8000-000000000001")
SHIFT = uuid.UUID("70000000-0000-4000-8000-000000000001")
KEY = "80000000-0000-4000-8000-000000000001"
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


def publication() -> RosterPublicationResponse:
    return RosterPublicationResponse(
        id=uuid.UUID("90000000-0000-4000-8000-000000000001"),
        period="2026-12",
        status="published",
        version=1,
        current_version_id=VERSION,
        source_version=SOURCE,
        published_at=datetime(2026, 12, 1, tzinfo=UTC),
        published_by_app_user_id=USER,
        record_count=1,
    )


class StubService:
    async def detail(self, *_: object) -> RosterPublicationResponse:
        return publication()

    async def publish(self, *_: object) -> RosterPublicationResponse:
        return publication()

    async def record_actual_hours(self, *_: object) -> RosterPublicationResponse:
        return publication()

    async def approve_overtime(self, *_: object) -> RosterPublicationResponse:
        return publication()

    async def personal_schedule(self, *_: object) -> list[PublishedScheduleEntryResponse]:
        return [
            PublishedScheduleEntryResponse(
                roster_assignment_id=ASSIGNMENT,
                employee_id=EMPLOYEE,
                employee_name="Ravi Test",
                department="Nursing",
                shift_id=SHIFT,
                shift_name="Morning",
                shift_code="M",
                shift_category="morning",
                date=date(2026, 12, 3),
                planned_hours=Decimal("8.00"),
                actual_hours=Decimal("12.00"),
                overtime_hours=Decimal("4.00"),
                notes="",
                source_version=SOURCE,
                publication_version=1,
                published_at=datetime(2026, 12, 1, tzinfo=UTC),
            )
        ]

    async def colleagues(self, *_: object) -> list[ColleagueScheduleEntryResponse]:
        return [
            ColleagueScheduleEntryResponse(
                employee_id=uuid.UUID("40000000-0000-4000-8000-000000000002"),
                employee_name="Maria Test",
                roster_assignment_id=uuid.UUID("60000000-0000-4000-8000-000000000002"),
                shift_id=SHIFT,
                shift_name="Morning",
                shift_code="M",
                shift_category="morning",
                date=date(2026, 12, 3),
            )
        ]

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

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = RecordingExecutor(
        BRANCH if role is AppRole.ADMIN else None
    )
    application.state.roster_publication_service_factory = lambda _: StubService()
    application.state.idempotency_coordinator_factory = lambda _: ImmediateIdempotency()
    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_admin_publication_and_evidence_routes_are_strict_and_idempotent() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH), "Idempotency-Key": KEY}
    async with client_for(AppRole.ADMIN) as client:
        detail = await client.get(
            "/api/v1/roster/months/2026-12/publication",
            headers={"X-Workloop-Branch-ID": str(BRANCH)},
        )
        publish = await client.post(
            "/api/v1/roster/months/2026-12/publish",
            headers=headers,
            json={
                "assignments": [{"id": str(ASSIGNMENT), "expectedVersion": 1}],
                "expectedSourceVersion": None,
            },
        )
        actual = await client.post(
            f"/api/v1/roster/months/2026-12/assignments/{ASSIGNMENT}/actual-hours",
            headers=headers,
            json={
                "actualHours": "12.00",
                "evidenceSource": "timesheet",
                "reason": "Confirmed timesheet",
                "expectedSourceVersion": SOURCE,
            },
        )
        overtime = await client.post(
            f"/api/v1/roster/months/2026-12/assignments/{ASSIGNMENT}/overtime-approval",
            headers=headers,
            json={
                "reason": "Approved overtime",
                "expectedSourceVersion": SOURCE,
                "attendanceSourceIds": [],
            },
        )
    assert {
        detail.status_code,
        publish.status_code,
        actual.status_code,
        overtime.status_code,
    } == {200}
    assert publish.headers["location"] == "/api/v1/roster/months/2026-12/publication"
    assert actual.json()["data"]["sourceVersion"] == SOURCE


@pytest.mark.asyncio
async def test_staff_reads_only_personal_schedule_and_safe_colleague_fields() -> None:
    async with client_for(AppRole.EMPLOYEE) as client:
        schedule = await client.get("/api/v1/roster/schedules/self?period=2026-12")
        colleagues = await client.get("/api/v1/roster/schedules/colleagues?date=2026-12-03")
    assert schedule.status_code == colleagues.status_code == 200
    assert schedule.json()["data"][0]["employeeId"] == str(EMPLOYEE)
    assert schedule.json()["data"][0]["overtimeHours"] == "4.00"
    assert set(colleagues.json()["data"][0]) == {
        "employeeId",
        "employeeName",
        "rosterAssignmentId",
        "shiftId",
        "shiftName",
        "shiftCode",
        "shiftCategory",
        "date",
    }
