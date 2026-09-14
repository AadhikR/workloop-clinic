from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer

from app.http.schemas import ApiSchema, StrictRequestSchema
from app.schemas.leave_attachment import LeaveAttachmentResponse


class LeaveBalanceResponse(ApiSchema):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_year: int
    entitled_days: Decimal
    accrued_days: Decimal
    used_days: Decimal
    pending_days: Decimal
    carried_forward: Decimal
    remaining_days: Decimal
    sick_full_pay_used: Decimal
    sick_half_pay_used: Decimal
    sick_unpaid_used: Decimal

    @field_serializer(
        "entitled_days",
        "accrued_days",
        "used_days",
        "pending_days",
        "carried_forward",
        "remaining_days",
        "sick_full_pay_used",
        "sick_half_pay_used",
        "sick_unpaid_used",
    )
    def serialize_days(self, value: Decimal) -> str:
        return f"{value:.2f}"


class LeaveRequestResponse(ApiSchema):
    id: uuid.UUID
    branch_id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    is_half_day: bool
    half_day_period: Literal["AM", "PM"] | None
    days_requested: Decimal
    status: Literal[
        "Pending",
        "ManagerApproved",
        "ManagerRejected",
        "Approved",
        "Rejected",
        "Cancelled",
    ]
    reason: str
    attachment: LeaveAttachmentResponse | None = None
    rejection_reason: str
    manager_rejection_reason: str
    relationship: str
    deceased_name: str
    date_of_death: date | None
    child_birth_date: date | None
    child_name: str
    expected_due_date: date | None
    institution_name: str
    exam_dates: str
    substitute_employee_id: uuid.UUID | None
    approval_level_required: int
    approval_comment: str
    warnings: list[str]
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime

    @field_serializer("days_requested")
    def serialize_requested(self, value: Decimal) -> str:
        return f"{value:.2f}"

    @field_serializer("submitted_at", "created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class LeaveBalanceYearRequest(StrictRequestSchema):
    leave_year: int = Field(ge=2000, le=2100)
