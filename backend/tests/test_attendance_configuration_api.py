import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.attendance_configuration import (
    AttendanceSettingsResponse,
    ShiftAssignmentResponse,
    ShiftResponse,
)
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
SHIFT_ID = uuid.UUID("31000000-0000-4000-8000-000000000001")
ASSIGNMENT_ID = uuid.UUID("32000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 18, 8, tzinfo=UTC)
KEY = "7e000000-0000-4000-8000-000000000001"


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
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=EMPLOYEE_ID if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


def settings_response() -> AttendanceSettingsResponse:
    return AttendanceSettingsResponse(
        id=uuid.uuid4(),
        working_days=["Sun", "Mon", "Tue", "Wed", "Thu"],
        weekend_days=["Fri", "Sat"],
        default_hours_per_day=Decimal("8.00"),
        late_grace_minutes=10,
        early_departure_grace_minutes=10,
        overtime_requires_approval=True,
        max_daily_overtime_hours=Decimal("2.00"),
        late_deduction_policy="none",
        late_deduction_amount=Decimal("0.00"),
        wfh_enabled=False,
        regularisation_max_days_per_month=2,
        regularisation_window_days=7,
        biometric_api_enabled=False,
        biometric_api_key_configured=False,
        created_at=NOW,
        updated_at=NOW,
    )


def shift_response() -> ShiftResponse:
    return ShiftResponse(
        id=SHIFT_ID,
        name="Morning",
        shift_type="fixed",
        start_time=time(8),
        end_time=time(17),
        break_minutes=60,
        expected_hours=Decimal("8.00"),
        late_grace_minutes=10,
        early_departure_grace_minutes=10,
        split_start_time=None,
        split_end_time=None,
        is_overnight=False,
        min_hours_flexible=None,
        is_active=True,
        color="#6366F1",
        code="M",
        shift_category="morning",
        min_staff=1,
        created_at=NOW,
        updated_at=NOW,
    )


def assignment_response() -> ShiftAssignmentResponse:
    return ShiftAssignmentResponse(
        id=ASSIGNMENT_ID,
        employee_id=EMPLOYEE_ID,
        shift_id=SHIFT_ID,
        effective_from=date(2026, 9, 20),
        effective_to=None,
        created_at=NOW,
        updated_at=NOW,
    )


class StubService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_settings(self, *_: object) -> AttendanceSettingsResponse:
        self.calls.append("get_settings")
        return settings_response()

    async def update_settings(self, *_: object) -> AttendanceSettingsResponse:
        self.calls.append("update_settings")
        return settings_response()

    async def list_shifts(self, *_: object) -> tuple[list[ShiftResponse], None]:
        self.calls.append("list_shifts")
        return [shift_response()], None

    async def create_shift(self, *_: object) -> ShiftResponse:
        self.calls.append("create_shift")
        return shift_response()

    async def update_shift(self, *_: object) -> ShiftResponse:
        self.calls.append("update_shift")
        return shift_response()

    async def deactivate_shift(self, *_: object) -> ShiftResponse:
        self.calls.append("deactivate_shift")
        return shift_response().model_copy(update={"is_active": False})

    async def list_assignments(self, *_: object) -> tuple[list[ShiftAssignmentResponse], None]:
        self.calls.append("list_assignments")
        return [assignment_response()], None

    async def assign_shift(self, *_: object) -> ShiftAssignmentResponse:
        self.calls.append("assign_shift")
        return assignment_response()

    async def authorize_replay(self, *_: object) -> None:
        self.calls.append("authorize_replay")


class ImmediateIdempotency:
    async def execute(self, **values: object) -> IdempotentResponse:
        return await cast(Callable[[], Awaitable[IdempotentResponse]], values["mutation"])()


class RecordingExecutor:
    def __init__(self) -> None:
        self.selected: list[uuid.UUID | None] = []

    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> object:
        self.selected.append(selected_admin_branch_id)
        return await operation(cast(AsyncConnection, object()))


@asynccontextmanager
async def client_for(role: AppRole) -> AsyncGenerator[tuple[AsyncClient, StubService], None]:
    from app.main import create_app

    service, executor = StubService(), RecordingExecutor()
    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = executor

    def service_factory(_connection: AsyncConnection) -> StubService:
        return service

    def idempotency_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application.state.attendance_configuration_service_factory = service_factory
    application.state.idempotency_coordinator_factory = idempotency_factory
    application.dependency_overrides[require_access_token] = lambda: claims()
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, service


@pytest.mark.asyncio
async def test_admin_reads_redacted_configuration_and_staff_is_denied() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    async with client_for(AppRole.ADMIN) as (client, _service):
        settings = await client.get("/api/v1/attendance-settings", headers=headers)
        shifts = await client.get("/api/v1/shifts", headers=headers)
    assert settings.status_code == shifts.status_code == 200
    assert "biometricApiKey" not in settings.json()["data"]
    assert settings.json()["data"]["biometricApiKeyConfigured"] is False
    async with client_for(AppRole.EMPLOYEE) as (client, service):
        denied = await client.get("/api/v1/attendance-settings", headers=headers)
    assert denied.status_code == 403 and service.calls == []


@pytest.mark.asyncio
async def test_mutations_require_idempotency_and_selected_branch() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    body = {
        "workingDays": ["Sun", "Mon", "Tue", "Wed", "Thu"],
        "weekendDays": ["Fri", "Sat"],
        "defaultHoursPerDay": "8.00",
        "lateGraceMinutes": 10,
        "earlyDepartureGraceMinutes": 10,
        "overtimeRequiresApproval": True,
        "maxDailyOvertimeHours": "2.00",
        "lateDeductionPolicy": "none",
        "lateDeductionAmount": "0.00",
        "wfhEnabled": False,
        "regularisationMaxDaysPerMonth": 2,
        "regularisationWindowDays": 7,
        "biometricApiEnabled": False,
        "expectedUpdatedAt": NOW.isoformat().replace("+00:00", "Z"),
    }
    async with client_for(AppRole.ADMIN) as (client, service):
        missing = await client.put("/api/v1/attendance-settings", headers=headers, json=body)
        accepted = await client.put(
            "/api/v1/attendance-settings", headers={**headers, "Idempotency-Key": KEY}, json=body
        )
    assert missing.status_code == 400
    assert accepted.status_code == 200
    assert service.calls == ["update_settings"]


@pytest.mark.asyncio
async def test_assignment_requires_employee_filter_and_exact_payload() -> None:
    headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    async with client_for(AppRole.ADMIN) as (client, service):
        invalid = await client.get("/api/v1/shift-assignments", headers=headers)
        created = await client.post(
            "/api/v1/shift-assignments",
            headers={**headers, "Idempotency-Key": KEY},
            json={
                "employeeId": str(EMPLOYEE_ID),
                "shiftId": str(SHIFT_ID),
                "effectiveFrom": "2026-09-20",
                "expectedCurrentAssignmentId": None,
                "expectedCurrentAssignmentUpdatedAt": None,
            },
        )
    assert invalid.status_code == 422
    assert created.status_code == 201
    assert service.calls == ["assign_shift"]
