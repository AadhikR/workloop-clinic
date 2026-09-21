from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

_PERIOD = re.compile(r"^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])$")


def validate_period(value: str) -> str:
    if not _PERIOD.fullmatch(value):
        raise ValueError("period must use YYYY-MM")
    return value


def _instant(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AttendancePeriodCloseRequest(StrictRequestSchema):
    expected_version: int = Field(default=0, ge=0)
    amendment_reason: str | None = Field(default=None, min_length=3, max_length=500)

    @field_validator("amendment_reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        if not 3 <= len(result) <= 500:
            raise ValueError("amendment reason must contain 3 to 500 non-space characters")
        return result

    @model_validator(mode="after")
    def validate_transition(self) -> AttendancePeriodCloseRequest:
        if self.expected_version == 0 and self.amendment_reason is not None:
            raise ValueError("an initial close cannot include an amendment reason")
        if self.expected_version > 0 and self.amendment_reason is None:
            raise ValueError("an amendment reason is required after the initial close")
        return self


class AttendancePeriodBlockerResponse(ApiSchema):
    code: Literal[
        "ambiguous_events",
        "missing_calculation_days",
        "missing_clock_outs",
        "pending_corrections",
        "salary_source_changed",
        "stale_source_snapshots",
        "unapproved_overtime",
        "unresolved_absences",
    ]
    count: int = Field(ge=1)


class AttendancePeriodResponse(ApiSchema):
    id: uuid.UUID
    period: str
    status: Literal["open", "closed"]
    payroll_ready: bool
    version: int = Field(ge=0)
    blocker_count: int = Field(ge=0)
    blockers: list[AttendancePeriodBlockerResponse]
    source_version: str | None
    closed_at: datetime | None
    closed_by_actor_name: str | None
    amendment_reason: str | None

    @field_validator("period")
    @classmethod
    def valid_period(cls, value: str) -> str:
        return validate_period(value)

    @field_serializer("closed_at")
    def serialize_instant(self, value: datetime | None) -> str | None:
        return _instant(value)


class AttendancePayrollEmployeeResponse(ApiSchema):
    employee_id: uuid.UUID
    absence_days: str
    absence_amount: str
    late_minutes: int
    late_amount: str
    standard_overtime_hours: str
    standard_overtime_amount: str
    rest_day_overtime_hours: str
    rest_day_overtime_amount: str
    source_row_ids: list[uuid.UUID]


class AttendancePayrollProjectionResponse(ApiSchema):
    source_version: str
    closed_at: datetime
    employees: list[AttendancePayrollEmployeeResponse]

    @field_serializer("closed_at")
    def serialize_instant(self, value: datetime) -> str:
        result = _instant(value)
        assert result is not None
        return result
