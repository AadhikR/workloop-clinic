from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


def _instant(value: datetime | None) -> str | None:
    return (
        None
        if value is None
        else value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )


class RegularisationSubmitRequest(StrictRequestSchema):
    attendance_date: date
    correct_clock_in: datetime
    correct_clock_out: datetime
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        result = value.strip()
        if not 3 <= len(result) <= 500:
            raise ValueError("reason must contain 3 to 500 non-space characters")
        return result

    @model_validator(mode="after")
    def validate_span(self) -> RegularisationSubmitRequest:
        if self.correct_clock_in.tzinfo is None or self.correct_clock_out.tzinfo is None:
            raise ValueError("clock instants must include an offset")
        if self.correct_clock_out <= self.correct_clock_in:
            raise ValueError("clock out must follow clock in")
        if (self.correct_clock_out - self.correct_clock_in).total_seconds() > 24 * 60 * 60:
            raise ValueError("correction span exceeds one day")
        return self


class RegularisationDecisionRequest(StrictRequestSchema):
    expected_version: int = Field(ge=1)
    rejection_reason: str | None = Field(default=None, min_length=3, max_length=500)

    @field_validator("rejection_reason")
    @classmethod
    def normalize_rejection_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        result = value.strip()
        if not 3 <= len(result) <= 500:
            raise ValueError("rejection reason must contain 3 to 500 non-space characters")
        return result


class AbsenceResolutionRequest(StrictRequestSchema):
    expected_calculation_version: int = Field(ge=1)
    resolution_type: Literal["LEAVE_LINKED", "UNAUTHORISED", "WFH"]
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        result = value.strip()
        if not 3 <= len(result) <= 500:
            raise ValueError("reason must contain 3 to 500 non-space characters")
        return result


class OvertimeApprovalRequest(StrictRequestSchema):
    expected_calculation_version: int = Field(ge=1)


class RegularisationResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    attendance_date: date
    correct_clock_in: datetime
    correct_clock_out: datetime
    reason: str
    status: Literal["Pending", "Approved", "Rejected"]
    rejection_reason: str | None
    submitted_at: datetime
    decided_at: datetime | None
    version: int

    @field_serializer("correct_clock_in", "correct_clock_out", "submitted_at", "decided_at")
    def serialize_instant(self, value: datetime | None) -> str | None:
        return _instant(value)


class AttendanceAuditResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    attendance_date: date | None
    action: str
    occurred_at: datetime

    @field_serializer("occurred_at")
    def serialize_instant(self, value: datetime) -> str:
        result = _instant(value)
        assert result is not None
        return result


class AttendanceExceptionRecordResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    date: date
    status: str
    resolution_type: str | None
    absence_deduction: Decimal
    overtime_hours: Decimal
    overtime_type: str | None
    overtime_amount: Decimal
    overtime_approved: bool
    overtime_approved_at: datetime | None
    overtime_approval_source_digest: str | None
    resolved_at: datetime | None
    resolution_source_digest: str | None
    calculation_version: int

    @field_serializer("overtime_approved_at", "resolved_at")
    def serialize_instant(self, value: datetime | None) -> str | None:
        return _instant(value)

    @field_serializer("absence_deduction", "overtime_hours", "overtime_amount")
    def serialize_decimal(self, value: Decimal) -> str:
        return f"{value:.2f}"
