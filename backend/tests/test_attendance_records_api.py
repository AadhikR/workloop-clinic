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
from app.schemas.attendance_calculation import AttendanceRecordResponse, PersonalAttendanceResponse
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY_ID = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
USER_ID = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = uuid.UUID("40000000-0000-4000-8000-000000000001")
RECORD_ID = uuid.UUID("50000000-0000-4000-8000-000000000001")
KEY = "70000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 8, 27, 8, tzinfo=UTC)


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
    staff = role is not AppRole.ADMIN
    return AuthorizationPrincipal(
        app_user_id=USER_ID,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=EMPLOYEE_ID if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


def record() -> AttendanceRecordResponse:
    return AttendanceRecordResponse(
        id=RECORD_ID,
        employee_id=EMPLOYEE_ID,
        date=date(2026, 8, 27),
        shift_id=None,
        clock_in_time=NOW,
        clock_out_time=NOW,
        total_hours=Decimal("8.00"),
        expected_hours=Decimal("8.00"),
        status="PRESENT",
        late_minutes=0,
        early_departure_minutes=0,
        overtime_hours=Decimal("0.00"),
        overtime_type=None,
        overtime_amount=Decimal("0.00"),
        absence_deduction=Decimal("0.00"),
        late_deduction=Decimal("0.00"),
        worked_on_rest_day=False,
        rest_day_substitute=False,
        missing_clock_out=False,
        is_ramadan_day=False,
        period_closed=False,
        evidence_flags=[],
        source_digest="a" * 64,
        source_stale=False,
        calculation_version=1,
        updated_at=NOW,
    )


class StubService:
    async def list_admin(self, *_: object) -> tuple[list[AttendanceRecordResponse], None]:
        return [record()], None

    async def personal_history(self, *_: object) -> tuple[list[AttendanceRecordResponse], None]:
        return [record()], None

    async def personal_today(self, *_: object) -> PersonalAttendanceResponse:
        return PersonalAttendanceResponse(record=record(), raw_event_fallback="none", raw_events=[])

    async def calculate_one(self, *_: object) -> AttendanceRecordResponse:
        return record()

    async def calculate_batch(self, *_: object) -> list[AttendanceRecordResponse]:
        return [record()]

    async def authorize_replay(self, *_: object) -> None:
        return None

    async def authorize_batch_replay(self, *_: object) -> None:
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

    def service_factory(_connection: AsyncConnection) -> StubService:
        return StubService()

    def idempotency_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application.state.attendance_record_service_factory = service_factory
    application.state.idempotency_coordinator_factory = idempotency_factory
    application.dependency_overrides[require_access_token] = lambda: claims()
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_admin_list_and_calculation_use_bounded_contracts() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    body = {"employeeId": str(EMPLOYEE_ID), "attendanceDate": "2026-08-27"}
    async with client_for(AppRole.ADMIN) as client:
        listing = await client.get("/api/v1/attendance-records?limit=20", headers=headers)
        missing_key = await client.post(
            "/api/v1/attendance/calculations", headers=headers, json=body
        )
        calculated = await client.post(
            "/api/v1/attendance/calculations",
            headers={**headers, "Idempotency-Key": KEY},
            json=body,
        )
        batch = await client.post(
            "/api/v1/attendance/calculations/batch",
            headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
            json={"items": [body]},
        )
    assert listing.status_code == 200
    assert listing.json()["page"] == {"limit": 20, "nextCursor": None, "hasMore": False}
    assert missing_key.status_code == 400
    assert calculated.status_code == 200
    assert calculated.headers["location"] == f"/api/v1/attendance-records/{RECORD_ID}"
    assert batch.status_code == 200
    assert batch.json()["data"][0]["id"] == str(RECORD_ID)


@pytest.mark.asyncio
async def test_employee_reads_today_and_history_without_employee_selector() -> None:
    async with client_for(AppRole.EMPLOYEE) as client:
        today = await client.get("/api/v1/attendance/me/today")
        history = await client.get("/api/v1/attendance/me?limit=20")
        rejected = await client.get(f"/api/v1/attendance/me?employeeId={uuid.uuid4()}")
    assert today.status_code == history.status_code == 200
    assert today.json()["data"]["record"]["employeeId"] == str(EMPLOYEE_ID)
    assert history.json()["data"][0]["employeeId"] == str(EMPLOYEE_ID)
    assert rejected.status_code == 422
