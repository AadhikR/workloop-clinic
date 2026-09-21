from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, field_serializer, field_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

_PERIOD = re.compile(r"^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def validate_roster_period(value: str) -> str:
    if not _PERIOD.fullmatch(value):
        raise ValueError("period must use YYYY-MM")
    return value


def _hours(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def _instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class RosterDraftCreateRequest(StrictRequestSchema):
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    date: date
    planned_hours: Decimal = Field(ge=Decimal("0.25"), le=24, max_digits=4, decimal_places=2)
    notes: str = Field(default="", max_length=500)

    @field_validator("planned_hours")
    @classmethod
    def finite_hours(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("planned hours must be finite")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str) -> str:
        return value.strip()


class RosterDraftReplaceRequest(RosterDraftCreateRequest):
    expected_version: int = Field(ge=1)


class RosterDraftDeleteRequest(StrictRequestSchema):
    expected_version: int = Field(ge=1)


class RosterAssignmentResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    department: str
    shift_id: uuid.UUID
    shift_name: str
    shift_code: str | None
    shift_category: str
    date: date
    published: bool
    planned_hours: Decimal
    notes: str
    version: int = Field(ge=1)
    leave_conflict: bool
    updated_at: datetime

    @field_serializer("planned_hours")
    def serialize_hours(self, value: Decimal) -> str:
        return _hours(value)

    @field_serializer("updated_at")
    def serialize_instant(self, value: datetime) -> str:
        return _instant(value)


class RosterLeaveConflictResponse(ApiSchema):
    roster_assignment_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    date: date
    leave_request_id: uuid.UUID
    leave_status: Literal["Approved", "ManagerApproved"]
    violation_digest: str
    overridden: bool

    @field_validator("violation_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("invalid violation digest")
        return value


class RosterStaffingViolationResponse(ApiSchema):
    code: Literal["staffing_shortfall"] = "staffing_shortfall"
    department: str
    date: date
    shift_category: str
    required: int = Field(ge=1)
    assigned: int = Field(ge=0)
    deficit: int = Field(ge=1)
    rule_id: uuid.UUID
    violation_digest: str
    overridden: bool

    @field_validator("violation_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("invalid violation digest")
        return value


class RosterValidationResponse(ApiSchema):
    period: str
    staffing_enforced: bool
    leave_conflicts: list[RosterLeaveConflictResponse]
    staffing_violations: list[RosterStaffingViolationResponse] | None
    ready: bool

    @field_validator("period")
    @classmethod
    def valid_period(cls, value: str) -> str:
        return validate_roster_period(value)


class RosterComplianceOverrideRequest(StrictRequestSchema):
    violation_digest: str
    reason: str = Field(min_length=10, max_length=500)

    @field_validator("violation_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        if not _DIGEST.fullmatch(value):
            raise ValueError("invalid violation digest")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        result = value.strip()
        if not 10 <= len(result) <= 500:
            raise ValueError("reason must contain 10 to 500 non-space characters")
        return result


class RosterComplianceOverrideResponse(ApiSchema):
    id: uuid.UUID
    period: str
    rule_code: Literal["leave_conflict", "staffing_shortfall"]
    violation_digest: str
    violation_snapshot: dict[str, Any]
    reason: str
    created_at: datetime

    @field_validator("period")
    @classmethod
    def valid_period(cls, value: str) -> str:
        return validate_roster_period(value)

    @field_serializer("created_at")
    def serialize_instant(self, value: datetime) -> str:
        return _instant(value)
