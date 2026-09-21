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
from app.schemas.attendance_exceptions import (
    AttendanceAuditResponse,
    AttendanceExceptionRecordResponse,
    RegularisationResponse,
)
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY_ID = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
USER_ID = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = uuid.UUID("40000000-0000-4000-8000-000000000001")
REQUEST_ID = uuid.UUID("50000000-0000-4000-8000-000000000001")
RECORD_ID = uuid.UUID("60000000-0000-4000-8000-000000000001")
AUDIT_ID = uuid.UUID("70000000-0000-4000-8000-000000000001")
KEY = "80000000-0000-4000-8000-000000000001"
NOW = datetime(2026, 9, 21, 8, tzinfo=UTC)


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


def regularisation() -> RegularisationResponse:
    return RegularisationResponse(
        id=REQUEST_ID,
        employee_id=EMPLOYEE_ID,
        attendance_date=date(2026, 9, 20),
        correct_clock_in=NOW,
        correct_clock_out=NOW.replace(hour=16),
        reason="Missed biometric punch",
        status="Pending",
        rejection_reason=None,
        submitted_at=NOW,
        decided_at=None,
        version=1,
    )


def record() -> AttendanceExceptionRecordResponse:
    return AttendanceExceptionRecordResponse(
        id=RECORD_ID,
        employee_id=EMPLOYEE_ID,
        date=date(2026, 9, 20),
        status="OVERTIME",
        resolution_type=None,
        absence_deduction=Decimal("0.00"),
        overtime_hours=Decimal("2.00"),
        overtime_type="standard",
        overtime_amount=Decimal("120.00"),
        overtime_approved=True,
        overtime_approved_at=NOW,
        overtime_approval_source_digest="a" * 64,
        resolved_at=None,
        resolution_source_digest=None,
        calculation_version=1,
    )


class StubService:
    async def personal(self, *_: object) -> tuple[list[RegularisationResponse], None]:
        return [regularisation()], None

    async def queue(self, *_: object) -> tuple[list[RegularisationResponse], None]:
        return [regularisation()], None

    async def audit(self, *_: object) -> tuple[list[AttendanceAuditResponse], None]:
        return [
            AttendanceAuditResponse(
                id=AUDIT_ID,
                employee_id=EMPLOYEE_ID,
                attendance_date=date(2026, 9, 20),
                action="OVERTIME_APPROVED",
                occurred_at=NOW,
            )
        ], None

    async def submit(self, *_: object) -> RegularisationResponse:
        return regularisation()

    async def decide(self, *_: object) -> RegularisationResponse:
        return regularisation()

    async def resolve_absence(self, *_: object) -> AttendanceExceptionRecordResponse:
        return record()

    async def approve_overtime(self, *_: object) -> AttendanceExceptionRecordResponse:
        return record()

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

    def service_factory(_connection: AsyncConnection) -> StubService:
        return StubService()

    def idempotency_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application.state.attendance_exception_service_factory = service_factory
    application.state.idempotency_coordinator_factory = idempotency_factory
    application.dependency_overrides[require_access_token] = lambda: claims()
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_employee_history_is_paginated_and_self_only() -> None:
    async with client_for(AppRole.EMPLOYEE) as client:
        response = await client.get("/api/v1/attendance/regularisations/me?limit=20")
        rejected = await client.get(
            f"/api/v1/attendance/regularisations/me?employeeId={uuid.uuid4()}"
        )
    assert response.status_code == 200
    assert response.json()["page"] == {"limit": 20, "nextCursor": None, "hasMore": False}
    assert response.json()["data"][0]["employeeId"] == str(EMPLOYEE_ID)
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_admin_queue_and_audit_are_selected_branch_lists() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    async with client_for(AppRole.ADMIN) as client:
        queue = await client.get(
            "/api/v1/attendance/regularisations?status=Pending&limit=25", headers=headers
        )
        audit = await client.get(
            "/api/v1/attendance/audit?action=OVERTIME_APPROVED&limit=25", headers=headers
        )
    assert queue.status_code == audit.status_code == 200
    assert queue.json()["page"]["limit"] == audit.json()["page"]["limit"] == 25
    assert audit.json()["data"][0]["action"] == "OVERTIME_APPROVED"


@pytest.mark.asyncio
async def test_exception_mutations_require_idempotency_and_return_locations() -> None:
    employee_body = {
        "attendanceDate": "2026-09-20",
        "correctClockIn": "2026-09-20T08:00:00+04:00",
        "correctClockOut": "2026-09-20T16:00:00+04:00",
        "reason": "Missed biometric punch",
    }
    async with client_for(AppRole.EMPLOYEE) as client:
        missing = await client.post("/api/v1/attendance/regularisations", json=employee_body)
        submitted = await client.post(
            "/api/v1/attendance/regularisations",
            headers={"Idempotency-Key": KEY},
            json=employee_body,
        )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "idempotency_key_required"
    assert submitted.status_code == 201
    assert submitted.headers["location"].endswith(str(REQUEST_ID))

    headers = {
        "X-Workloop-Branch-ID": str(BRANCH_ID),
        "Idempotency-Key": str(uuid.uuid4()),
    }
    async with client_for(AppRole.ADMIN) as client:
        approved = await client.post(
            f"/api/v1/attendance-records/{RECORD_ID}/overtime-approval",
            headers=headers,
            json={"expectedCalculationVersion": 1},
        )
    assert approved.status_code == 200
    assert approved.headers["location"] == f"/api/v1/attendance-records/{RECORD_ID}"
    assert approved.json()["data"]["overtimeApproved"] is True
