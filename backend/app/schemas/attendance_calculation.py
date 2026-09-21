from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


def _instant(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AttendanceRecordResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    date: date
    shift_id: uuid.UUID | None
    clock_in_time: datetime | None
    clock_out_time: datetime | None
    total_hours: Decimal
    expected_hours: Decimal
    status: str
    resolution_type: Literal["LEAVE_LINKED", "UNAUTHORISED", "WFH"] | None = None
    late_minutes: int
    early_departure_minutes: int
    overtime_hours: Decimal
    overtime_type: str | None
    overtime_amount: Decimal
    overtime_approved: bool = False
    absence_deduction: Decimal
    late_deduction: Decimal
    worked_on_rest_day: bool
    rest_day_substitute: bool
    missing_clock_out: bool
    is_ramadan_day: bool
    period_closed: bool
    evidence_flags: list[str]
    source_digest: str
    source_stale: bool
    calculation_version: int
    updated_at: datetime

    @field_serializer("clock_in_time", "clock_out_time", "updated_at")
    def serialize_instant(self, value: datetime | None) -> str | None:
        return _instant(value)

    @field_serializer(
        "total_hours",
        "expected_hours",
        "overtime_hours",
        "overtime_amount",
        "absence_deduction",
        "late_deduction",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return f"{value:.2f}"


class AttendanceCalculationRequest(StrictRequestSchema):
    employee_id: uuid.UUID
    attendance_date: date
    expected_source_digest: str | None = Field(default=None, min_length=1, max_length=128)
    expected_calculation_version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_expected_version(self) -> AttendanceCalculationRequest:
        if (self.expected_source_digest is None) != (self.expected_calculation_version is None):
            raise ValueError("expected digest and calculation version must be supplied together")
        return self


class AttendanceCalculationBatchRequest(StrictRequestSchema):
    items: list[AttendanceCalculationRequest] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_daily_unique_employees(self) -> AttendanceCalculationBatchRequest:
        dates = {item.attendance_date for item in self.items}
        employees = [item.employee_id for item in self.items]
        if len(dates) != 1 or len(set(employees)) != len(employees):
            raise ValueError("batch must contain one date and unique employees")
        return self


class AttendanceRecordListQuery(ApiSchema):
    employee_id: uuid.UUID | None = None
    from_date: date | None = None
    to_date: date | None = None
    limit: int = 50
    cursor: str | None = None


class PersonalRawEventResponse(ApiSchema):
    id: uuid.UUID
    event_type: str
    event_time: datetime
    method: str

    @field_serializer("event_time")
    def serialize_event_time(self, value: datetime) -> str:
        result = _instant(value)
        assert result is not None
        return result


class PersonalAttendanceResponse(ApiSchema):
    record: AttendanceRecordResponse | None
    raw_event_fallback: Literal["none", "self_only"]
    raw_events: list[PersonalRawEventResponse]
