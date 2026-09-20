from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.repositories.attendance_configuration import AttendanceConfigurationRepository
from app.schemas.attendance_configuration import (
    AttendanceSettingsUpdateRequest,
    ShiftAssignmentCreateRequest,
    ShiftCreateRequest,
    ShiftDeactivateRequest,
    ShiftUpdateRequest,
)
from app.services.attendance_configuration import AttendanceConfigurationService
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
SHIFT_ID = uuid.UUID("31000000-0000-4000-8000-000000000001")
ASSIGNMENT_ID = uuid.UUID("32000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 18, 8, tzinfo=UTC)


def principal(role: AppRole = AppRole.ADMIN) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=None,
        branch_id=None,
    )


def settings_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": uuid.UUID("33000000-0000-4000-8000-000000000001"),
        "working_days": ["Sun", "Mon", "Tue", "Wed", "Thu"],
        "weekend_days": ["Fri", "Sat"],
        "default_hours_per_day": Decimal("8.00"),
        "late_grace_minutes": 10,
        "early_departure_grace_minutes": 10,
        "overtime_requires_approval": True,
        "max_daily_overtime_hours": Decimal("2.00"),
        "late_deduction_policy": "none",
        "late_deduction_amount": Decimal("0.00"),
        "wfh_enabled": False,
        "regularisation_max_days_per_month": 2,
        "regularisation_window_days": 7,
        "biometric_api_enabled": False,
        "biometric_api_key": "stored-biometric-key",
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(changes)
    return row


def shift_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": SHIFT_ID,
        "name": "Morning",
        "shift_type": "fixed",
        "start_time": datetime.strptime("08:00", "%H:%M").time(),
        "end_time": datetime.strptime("17:00", "%H:%M").time(),
        "break_minutes": 60,
        "expected_hours": Decimal("8.00"),
        "late_grace_minutes": 10,
        "early_departure_grace_minutes": 10,
        "split_start_time": None,
        "split_end_time": None,
        "is_overnight": False,
        "min_hours_flexible": None,
        "is_active": True,
        "color": "#6366F1",
        "code": "M",
        "shift_category": "morning",
        "min_staff": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(changes)
    return row


def assignment_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": ASSIGNMENT_ID,
        "employee_id": EMPLOYEE_ID,
        "shift_id": SHIFT_ID,
        "effective_from": date(2026, 9, 1),
        "effective_to": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(changes)
    return row


class FakeRepository:
    def __init__(self) -> None:
        self.settings = settings_row()
        self.shift = shift_row()
        self.assignments = [assignment_row()]
        self.referenced = False
        self.has_current_or_future = False
        self.closed: tuple[uuid.UUID, date] | None = None

    async def fetch_settings(self, *_args: object, **_options: object) -> dict[str, object]:
        return self.settings

    async def update_settings(
        self, _company_id: uuid.UUID, _branch_id: uuid.UUID, values: dict[str, object]
    ) -> dict[str, object]:
        self.settings = {**self.settings, **values, "updated_at": NOW + timedelta(minutes=1)}
        return self.settings

    async def fetch_shift(self, *_args: object, **_options: object) -> dict[str, object]:
        return self.shift

    async def shift_has_any_reference(self, *_args: object) -> bool:
        return self.referenced

    async def shift_has_current_or_future_assignment(self, *_args: object) -> bool:
        return self.has_current_or_future

    async def update_shift(
        self,
        _company_id: uuid.UUID,
        _branch_id: uuid.UUID,
        _shift_id: uuid.UUID,
        values: dict[str, object],
    ) -> dict[str, object]:
        self.shift = {**self.shift, **values, "updated_at": NOW + timedelta(minutes=1)}
        return self.shift

    async def business_date(self) -> date:
        return date(2026, 9, 18)

    async def fetch_employee_for_assignment(self, *_args: object) -> dict[str, object]:
        return {"id": EMPLOYEE_ID, "active": True, "employment_status": "Active"}

    async def lock_assignments(self, *_args: object) -> list[dict[str, object]]:
        return self.assignments

    async def close_assignment(self, assignment_id: uuid.UUID, effective_to: date) -> None:
        self.closed = assignment_id, effective_to

    async def create_assignment(
        self,
        _company_id: uuid.UUID,
        _branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        shift_id: uuid.UUID,
        effective_from: date,
        effective_to: date | None,
    ) -> dict[str, object]:
        return assignment_row(
            id=uuid.UUID("32000000-0000-4000-8000-000000000002"),
            employee_id=employee_id,
            shift_id=shift_id,
            effective_from=effective_from,
            effective_to=effective_to,
            updated_at=NOW + timedelta(minutes=1),
        )


def service() -> tuple[AttendanceConfigurationService, FakeRepository]:
    repository = FakeRepository()
    active = AttendanceConfigurationService(
        cast(AsyncConnection, object()),
        EmployeeCursorCodec(b"0" * 32),
        cast(AttendanceConfigurationRepository, repository),
    )
    return active, repository


def settings_request(**changes: object) -> AttendanceSettingsUpdateRequest:
    values: dict[str, object] = {
        "workingDays": ["Sun", "Mon", "Tue", "Wed", "Thu"],
        "weekendDays": ["Fri", "Sat"],
        "defaultHoursPerDay": "8.00",
        "lateGraceMinutes": 10,
        "earlyDepartureGraceMinutes": 10,
        "overtimeRequiresApproval": True,
        "maxDailyOvertimeHours": "2.00",
        "lateDeductionPolicy": "none",
        "lateDeductionAmount": "0.00",
        "wfhEnabled": True,
        "regularisationMaxDaysPerMonth": 2,
        "regularisationWindowDays": 7,
        "biometricApiEnabled": True,
        "biometricApiKey": "replacement-secret",
        "expectedUpdatedAt": NOW,
    }
    values.update(changes)
    return AttendanceSettingsUpdateRequest.model_validate(values)


@pytest.mark.asyncio
async def test_settings_secret_is_write_only_and_audit_is_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit: list[dict[str, object]] = []

    async def record_audit(_connection: object, **values: object) -> None:
        audit.append(values)

    monkeypatch.setattr("app.services.attendance_configuration.append_audit_event", record_audit)
    active, repository = service()
    repository.settings["biometric_api_key"] = ""
    result = await active.update_settings(principal(), BRANCH_ID, settings_request())

    assert result.biometric_api_key_configured is True
    assert "biometric_api_key" not in result.model_dump()
    assert repository.settings["biometric_api_key"] == "replacement-secret"
    assert "replacement-secret" not in repr(audit)
    changed_fields = cast(list[str], audit[0]["changed_fields"])
    assert "biometric_api_key" not in changed_fields
    assert "biometric_api_key_configured" in changed_fields


@pytest.mark.asyncio
async def test_stale_settings_and_referenced_shift_changes_fail_closed() -> None:
    active, repository = service()
    with pytest.raises(ServiceExecutionError, match="state_conflict"):
        await active.update_settings(
            principal(),
            BRANCH_ID,
            settings_request(expectedUpdatedAt=NOW - timedelta(seconds=1)),
        )

    repository.referenced = True
    update = ShiftUpdateRequest.model_validate({"expectedUpdatedAt": NOW, "name": "Early Morning"})
    with pytest.raises(ServiceExecutionError, match="retained_shift"):
        await active.update_shift(principal(), BRANCH_ID, SHIFT_ID, update)


@pytest.mark.asyncio
async def test_historical_reference_allows_deactivation_but_future_reference_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def discard_audit(_connection: object, **_values: object) -> None:
        return None

    monkeypatch.setattr("app.services.attendance_configuration.append_audit_event", discard_audit)
    active, repository = service()
    repository.referenced = True
    request = ShiftDeactivateRequest.model_validate({"expectedUpdatedAt": NOW})
    result = await active.deactivate_shift(
        principal(), BRANCH_ID, SHIFT_ID, request.expected_updated_at
    )
    assert result.is_active is False

    active, repository = service()
    repository.has_current_or_future = True
    with pytest.raises(ServiceExecutionError, match="retained_shift"):
        await active.deactivate_shift(principal(), BRANCH_ID, SHIFT_ID, request.expected_updated_at)


@pytest.mark.asyncio
async def test_assignment_closes_covering_row_and_stops_before_next_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def discard_audit(_connection: object, **_values: object) -> None:
        return None

    monkeypatch.setattr("app.services.attendance_configuration.append_audit_event", discard_audit)
    active, repository = service()
    repository.assignments.append(
        assignment_row(
            id=uuid.UUID("32000000-0000-4000-8000-000000000003"),
            effective_from=date(2026, 10, 1),
        )
    )
    request = ShiftAssignmentCreateRequest.model_validate(
        {
            "employeeId": EMPLOYEE_ID,
            "shiftId": SHIFT_ID,
            "effectiveFrom": "2026-09-20",
            "expectedCurrentAssignmentId": ASSIGNMENT_ID,
            "expectedCurrentAssignmentUpdatedAt": NOW,
        }
    )
    result = await active.assign_shift(principal(), BRANCH_ID, request)
    assert repository.closed == (ASSIGNMENT_ID, date(2026, 9, 19))
    assert result.effective_to == date(2026, 9, 30)


def test_configuration_schemas_enforce_partition_decimal_and_shift_shape() -> None:
    with pytest.raises(ValidationError):
        settings_request(workingDays=["Sun", "Sun"], weekendDays=["Fri", "Sat"])
    with pytest.raises(ValidationError):
        settings_request(defaultHoursPerDay=8.001)
    with pytest.raises(ValidationError):
        ShiftCreateRequest.model_validate(
            {
                "name": "Broken",
                "shiftType": "fixed",
                "startTime": "17:00",
                "endTime": "08:00",
                "breakMinutes": 60,
                "expectedHours": "8.00",
                "lateGraceMinutes": 10,
                "earlyDepartureGraceMinutes": 10,
                "splitStartTime": None,
                "splitEndTime": None,
                "isOvernight": False,
                "minHoursFlexible": None,
                "color": "#6366F1",
                "code": "M",
                "shiftCategory": "morning",
                "minStaff": 1,
            }
        )
