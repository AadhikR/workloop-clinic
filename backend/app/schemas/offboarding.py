from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

VisaStatus = Literal["not_started", "initiated", "submitted_gdrfa", "cancelled"]
TaskSource = Literal["template", "custom"]

MONEY_PATTERN = r"^(0|[1-9]\d{0,11})\.\d{2}$"
DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class OffboardingTaskCreateRequest(StrictRequestSchema):
    task_name: str = Field(min_length=1, max_length=180)
    expected_checklist_updated_at: datetime

    @field_validator("task_name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class OffboardingTaskUpdateRequest(StrictRequestSchema):
    expected_checklist_updated_at: datetime
    expected_task_updated_at: datetime
    notes: str = Field(default="", max_length=1000)

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class OffboardingVisaRequest(StrictRequestSchema):
    expected_checklist_updated_at: datetime
    status: VisaStatus


class SettlementInputs(StrictRequestSchema):
    expected_checklist_updated_at: datetime
    notice_pay: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    notice_deduction: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2
    )
    other_earnings: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    other_deductions: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2
    )
    adjustment_reason: str = Field(default="", max_length=1000)

    @field_validator("notice_pay", "notice_deduction", "other_earnings", "other_deductions")
    @classmethod
    def exact_money(cls, value: Decimal) -> Decimal:
        if re.fullmatch(MONEY_PATTERN, f"{value:.2f}") is None:
            raise ValueError("invalid money")
        return value

    @field_validator("adjustment_reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_adjustment_reason(self) -> SettlementInputs:
        if (
            any(
                value != Decimal("0.00")
                for value in (
                    self.notice_pay,
                    self.notice_deduction,
                    self.other_earnings,
                    self.other_deductions,
                )
            )
            and not self.adjustment_reason
        ):
            raise ValueError("adjustmentReason is required for manual adjustments")
        return self


class SettlementCompleteRequest(SettlementInputs):
    expected_source_digest: str = Field(pattern=DIGEST_PATTERN)
    termination_reason: str = Field(min_length=1, max_length=1000)

    @field_validator("termination_reason", mode="before")
    @classmethod
    def trim_termination_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class OffboardingTaskResponse(ApiSchema):
    id: uuid.UUID
    task_name: str
    completed: bool
    completed_at: datetime | None
    notes: str
    sort_order: int
    source: TaskSource
    template_id: uuid.UUID | None
    updated_at: datetime

    @field_serializer("completed_at", "updated_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class OffboardingChecklistResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employment_status: str
    status: Literal["in_progress", "completed"]
    visa_cancellation_status: VisaStatus
    visa_cancellation_date: date | None
    final_settlement_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    tasks: list[OffboardingTaskResponse]

    @field_serializer("created_at", "updated_at", "completed_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SettlementAmounts(ApiSchema):
    final_salary: Decimal
    leave_encashment: Decimal
    gratuity: Decimal
    notice_pay: Decimal
    other_earnings: Decimal
    advance_deduction: Decimal
    asset_deduction: Decimal
    notice_deduction: Decimal
    other_deductions: Decimal
    gross_amount: Decimal
    total_deductions: Decimal
    net_amount: Decimal

    @field_serializer(
        "final_salary",
        "leave_encashment",
        "gratuity",
        "notice_pay",
        "other_earnings",
        "advance_deduction",
        "asset_deduction",
        "notice_deduction",
        "other_deductions",
        "gross_amount",
        "total_deductions",
        "net_amount",
    )
    def serialize_money(self, value: Decimal) -> str:
        return f"{value:.2f}"


class SettlementPreviewResponse(SettlementAmounts):
    policy_version: str
    policy_digest: str
    source_digest: str
    source_captured_at: datetime
    service_days: Decimal
    gratuity_days: Decimal
    leave_days: Decimal

    @field_serializer("service_days", "gratuity_days", "leave_days")
    def serialize_days(self, value: Decimal) -> str:
        return format(value, "f")

    @field_serializer("source_captured_at")
    def serialize_captured_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class FinalSettlementResponse(SettlementPreviewResponse):
    id: uuid.UUID
    checklist_id: uuid.UUID
    employee_id: uuid.UUID
    completed_at: datetime

    @field_serializer("completed_at")
    def serialize_completed_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class OffboardingLetterSource(ApiSchema):
    checklist_id: uuid.UUID
    settlement_id: uuid.UUID
    employee_name: str
    job_title: str
    department: str
    employment_start_date: date
    termination_date: date
    branch_name: str
    completed_at: datetime

    @field_serializer("completed_at")
    def serialize_completed_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
