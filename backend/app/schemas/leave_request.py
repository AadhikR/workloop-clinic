from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.http.schemas import StrictRequestSchema


class LeaveSubmissionRequest(StrictRequestSchema):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    is_half_day: bool
    half_day_period: Literal["AM", "PM"] | None
    reason: str = Field(max_length=2000)
    attachment_id: uuid.UUID | None
    relationship: Literal["Spouse", "Parent", "Child", "Sibling"] | None
    deceased_name: str | None = Field(max_length=200)
    date_of_death: date | None
    child_birth_date: date | None
    child_name: str | None = Field(max_length=200)
    expected_due_date: date | None
    institution_name: str | None = Field(max_length=300)
    exam_dates: str | None = Field(max_length=1000)
    substitute_employee_id: uuid.UUID | None

    @field_validator(
        "reason",
        "deceased_name",
        "child_name",
        "institution_name",
        "exam_dates",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_dates(self) -> LeaveSubmissionRequest:
        if self.end_date < self.start_date:
            raise ValueError("end date precedes start date")
        if self.is_half_day:
            if self.start_date != self.end_date or self.half_day_period is None:
                raise ValueError("invalid half-day range")
        elif self.half_day_period is not None:
            raise ValueError("half-day period requires a half-day request")
        return self


class AdminLeaveSubmissionRequest(LeaveSubmissionRequest):
    employee_id: uuid.UUID


class LeaveCancellationRequest(StrictRequestSchema):
    pass
