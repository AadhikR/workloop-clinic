from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_serializer, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

PERIOD = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
COMPLIANCE_CODES = frozenset(
    {
        "visa_expired",
        "emirates_id_expired",
        "labour_card_expired",
        "passport_expired",
        "professional_licence_expired",
    }
)


class WpsVersionRequest(StrictRequestSchema):
    expected_updated_at: datetime


class WpsSubmitRequest(WpsVersionRequest):
    reference_number: str = Field(min_length=1, max_length=100)


class WpsReasonRequest(WpsVersionRequest):
    reason: str = Field(min_length=1, max_length=500)


class WpsEntryVersionRequest(StrictRequestSchema):
    expected_updated_at: datetime


class WpsEntryRejectRequest(WpsEntryVersionRequest):
    reason: str = Field(min_length=1, max_length=500)


class ComplianceOverrideRequest(StrictRequestSchema):
    rule_code: Literal[
        "visa_expired",
        "emirates_id_expired",
        "labour_card_expired",
        "passport_expired",
        "professional_licence_expired",
    ]
    reason: str = Field(min_length=1, max_length=500)
    payroll_entry_id: uuid.UUID | None = None


class NafisReplaceRequest(StrictRequestSchema):
    expected_generated_at: datetime | None = None


class WpsEntryResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    payment_status: Literal["pending", "paid", "rejected"]
    rejection_reason: str | None
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class WpsRunResponse(ApiSchema):
    run_id: uuid.UUID
    period: str
    payment_date: date
    status: Literal[
        "draft", "sif_generated", "submitted", "confirmed", "partial_rejection", "failed"
    ]
    submitted_at: datetime | None
    confirmed_at: datetime | None
    reference_number: str | None
    updated_at: datetime
    entries: list[WpsEntryResponse]

    @field_serializer("submitted_at", "confirmed_at", "updated_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SifHeaderResponse(ApiSchema):
    employer_mol_id: str
    branch_routing_code: str
    period_start: date
    period_end: date
    payment_date: date
    employee_count: int
    total_integer_pay: int


class SifEntryResponse(ApiSchema):
    payroll_entry_id: uuid.UUID
    employee_mol_id: str
    bank_routing_code: str
    iban: str
    period_start: date
    period_end: date
    paid_days: int
    basic_pay: int
    variable_pay: int
    total_pay: int


class SifInputResponse(ApiSchema):
    mode: Literal["full", "rejected"]
    digest: str
    header: SifHeaderResponse
    entries: list[SifEntryResponse]


class ComplianceOverrideResponse(ApiSchema):
    id: uuid.UUID
    payroll_run_id: uuid.UUID
    payroll_entry_id: uuid.UUID | None
    rule_code: str
    reason: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class NafisEmployeeResponse(ApiSchema):
    employee_id: uuid.UUID
    employee_name: str
    nafis_registration_number: str | None
    qualifying_basic_wage: str


class NafisSnapshotResponse(ApiSchema):
    id: uuid.UUID
    period: str
    total_headcount: int
    emirati_count: int
    ratio_percent: str
    required_percent: str
    compliant: bool
    source_version: str
    qualifying_wage_total: str
    employees: list[NafisEmployeeResponse]
    generated_at: datetime

    @field_serializer("generated_at")
    def serialize_generated_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @model_validator(mode="after")
    def validate_counts(self) -> NafisSnapshotResponse:
        if self.emirati_count != len(self.employees):
            raise ValueError("Emirati count does not match snapshot employees")
        return self
