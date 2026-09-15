from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema
from app.schemas.leave_balance import LeaveBalanceResponse, LeaveRequestResponse
from app.schemas.leave_configuration import LeaveTypeResponse


class LeaveDecisionRequest(StrictRequestSchema):
    decision: Literal["approve", "reject"]
    reason: str = Field(max_length=2000)
    expected_updated_at: datetime

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def rejection_has_reason(self) -> LeaveDecisionRequest:
        if self.decision == "reject" and not self.reason:
            raise ValueError("rejection reason is required")
        return self


class QueueEmployeeResponse(ApiSchema):
    id: uuid.UUID
    employee_number: str
    name: str
    job_title: str
    department: str


class LeaveQueueItemResponse(ApiSchema):
    request: LeaveRequestResponse
    employee: QueueEmployeeResponse
    leave_type: LeaveTypeResponse
    balance: LeaveBalanceResponse | None
    can_decide: bool
    visible_because: Literal["directReport", "activeDelegation", "administrator"]


class LeaveApprovalDelegateCreate(StrictRequestSchema):
    approver_employee_id: uuid.UUID
    delegate_employee_id: uuid.UUID
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def validate_dates_and_people(self) -> LeaveApprovalDelegateCreate:
        if self.to_date < self.from_date:
            raise ValueError("delegation ends before it starts")
        if self.approver_employee_id == self.delegate_employee_id:
            raise ValueError("approver and delegate must differ")
        return self


class LeaveApprovalDelegateUpdate(LeaveApprovalDelegateCreate):
    expected_updated_at: datetime


class LeaveApprovalDelegateDelete(StrictRequestSchema):
    expected_updated_at: datetime


class LeaveApprovalDelegateResponse(ApiSchema):
    id: uuid.UUID
    branch_id: uuid.UUID
    approver_employee_id: uuid.UUID
    delegate_employee_id: uuid.UUID
    from_date: date
    to_date: date
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class LeaveAuditEntryResponse(ApiSchema):
    id: uuid.UUID
    leave_request_id: uuid.UUID
    action: str
    reason: str
    old_status: str
    new_status: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
