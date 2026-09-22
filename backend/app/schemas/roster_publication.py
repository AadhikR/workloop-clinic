from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from app.http.schemas import ApiSchema, StrictRequestSchema
from app.schemas.roster import validate_roster_period


def _instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _decimal(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


class RosterPublishAssignment(StrictRequestSchema):
    id: uuid.UUID
    expected_version: int = Field(ge=1)


class RosterPublishRequest(StrictRequestSchema):
    assignments: list[RosterPublishAssignment] = Field(min_length=1, max_length=5000)
    expected_source_version: str | None = None


class RosterActualHoursRequest(StrictRequestSchema):
    actual_hours: Decimal = Field(ge=0, le=24, max_digits=5, decimal_places=2)
    evidence_source: Literal["manager_attestation", "timesheet", "biometric_reconciliation"]
    reason: str = Field(min_length=3, max_length=500)
    expected_source_version: str

    @field_validator("actual_hours")
    @classmethod
    def finite_hours(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("actual hours must be finite")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        result = value.strip()
        if not 3 <= len(result) <= 500:
            raise ValueError("reason must contain 3 to 500 non-space characters")
        return result


class RosterOvertimeApprovalRequest(StrictRequestSchema):
    reason: str = Field(min_length=3, max_length=500)
    expected_source_version: str
    attendance_source_ids: list[uuid.UUID] = Field(default_factory=list[uuid.UUID], max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        result = value.strip()
        if not 3 <= len(result) <= 500:
            raise ValueError("reason must contain 3 to 500 non-space characters")
        return result


class RosterPublicationResponse(ApiSchema):
    id: uuid.UUID
    period: str
    status: Literal["draft", "published"]
    version: int = Field(ge=0)
    current_version_id: uuid.UUID | None
    source_version: str | None
    published_at: datetime | None
    published_by_app_user_id: uuid.UUID | None
    record_count: int = Field(ge=0)

    @field_validator("period")
    @classmethod
    def valid_period(cls, value: str) -> str:
        return validate_roster_period(value)

    @field_serializer("published_at")
    def serialize_instant(self, value: datetime | None) -> str | None:
        return _instant(value) if value is not None else None


class PublishedScheduleEntryResponse(ApiSchema):
    roster_assignment_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    department: str
    shift_id: uuid.UUID
    shift_name: str
    shift_code: str | None
    shift_category: str
    date: date
    planned_hours: Decimal
    actual_hours: Decimal | None
    overtime_hours: Decimal
    notes: str
    source_version: str
    publication_version: int = Field(ge=1)
    published_at: datetime

    @field_serializer("planned_hours", "actual_hours", "overtime_hours")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return _decimal(value) if value is not None else None

    @field_serializer("published_at")
    def serialize_published_at(self, value: datetime) -> str:
        return _instant(value)


class ColleagueScheduleEntryResponse(ApiSchema):
    employee_id: uuid.UUID
    employee_name: str
    roster_assignment_id: uuid.UUID
    shift_id: uuid.UUID
    shift_name: str
    shift_code: str | None
    shift_category: str
    date: date
