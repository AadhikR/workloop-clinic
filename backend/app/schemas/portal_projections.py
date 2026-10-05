from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import field_serializer

from app.http.schemas import ApiSchema, CollectionResponse
from app.schemas.advance import AdvanceScheduleRow, AdvanceStatus


class AdminWorkspaceResponse(ApiSchema):
    business_date: date
    active_employees: int
    payroll_runs: int
    draft_payrolls: int
    sif_generated: int
    insurance_policies: int
    alerts: dict[str, int]


class EmployeeExpiryResponse(ApiSchema):
    id: str
    employee_id: uuid.UUID
    employee_name: str
    source_type: str
    expiry_date: date | None
    status: Literal["valid", "expiring", "expired"]


class EmployeeDirectoryDetailResponse(ApiSchema):
    id: uuid.UUID
    mol_id: str
    allowance: str
    visa_expiry: date | None
    emirates_id_expiry: date | None


class ClinicalWorkforceRowResponse(ApiSchema):
    id: str
    employee_id: uuid.UUID
    employee_name: str
    department: str
    job_title: str
    status: str
    source_date: date | None
    source_time: datetime | None
    source_label: str

    @field_serializer("source_time")
    def serialize_time(self, value: datetime | None) -> str | None:
        return (
            None
            if value is None
            else value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        )


class ClinicalDepartmentResponse(ApiSchema):
    department: str
    headcount: int
    credentialled: int
    rostered: int
    min_staff: int


class ClinicalWorkforceSummaryResponse(ApiSchema):
    business_date: date
    counts: dict[str, int]
    compliant: int
    rostered: int
    departments: list[ClinicalDepartmentResponse]


class LeaveActionResponse(ApiSchema):
    id: uuid.UUID
    request_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    leave_type: str
    start_date: date
    end_date: date
    action: Literal["approved", "rejected", "manager_approved", "manager_rejected"]
    reason: str
    actor_name: str
    action_at: datetime

    @field_serializer("action_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class RetainedRecordResponse(ApiSchema):
    id: uuid.UUID
    entity_type: Literal["appraisal", "incident_report", "expense_claim", "salary_advance"]
    label: str
    status: str
    archived: bool
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class OwnAdvancePaymentResponse(ApiSchema):
    id: uuid.UUID
    amount: str
    paid_date: date
    payroll_period: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class OwnAdvanceSummaryResponse(ApiSchema):
    advance_id: uuid.UUID
    amount: str
    total_paid: str
    outstanding_balance: str
    status: AdvanceStatus
    updated_at: datetime
    source_version: str
    schedule: list[AdvanceScheduleRow]

    @field_serializer("updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class OwnAdvanceProgressResponse(CollectionResponse[OwnAdvancePaymentResponse]):
    summary: OwnAdvanceSummaryResponse
