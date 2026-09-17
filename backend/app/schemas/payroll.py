from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

MONEY = re.compile(r"(?:0|[1-9][0-9]{0,9})\.[0-9]{2}")
SIGNED_MONEY = re.compile(r"-?(?:0|[1-9][0-9]{0,9})\.[0-9]{2}")
PERIOD = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
CODE = re.compile(r"[A-Z][A-Z0-9_]{0,39}")
RESERVED_PREFIXES = ("AUTO_", "LEAVE_", "ATTENDANCE_", "ROSTER_", "EXPENSE_", "ADVANCE_")


def _money(value: str, *, signed: bool = False) -> str:
    if not (SIGNED_MONEY if signed else MONEY).fullmatch(value):
        raise ValueError("money must use fixed two-decimal notation")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid money") from None
    if abs(amount) > Decimal("9999999999.99"):
        raise ValueError("money is outside the accepted range")
    return value


def _period(value: str) -> str:
    if not PERIOD.fullmatch(value):
        raise ValueError("period must use YYYY-MM notation")
    return value


class PayrollAdjustmentRequest(StrictRequestSchema):
    id: uuid.UUID
    code: str
    label: str = Field(min_length=1, max_length=80)
    amount: str
    recurrence: Literal["one_time", "recurring"]
    note: str | None = Field(default=None, max_length=500)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if CODE.fullmatch(value) is None or value.startswith(RESERVED_PREFIXES):
            raise ValueError("adjustment code is not allowed")
        return value

    @field_validator("label", "note", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        return _money(value)


class PayrollEntryPreview(StrictRequestSchema):
    basic_salary: str
    housing_allowance: str
    transport_allowance: str
    fixed_allowance: str
    fixed_pay: str
    gross_pay: str
    total_deductions: str
    net_pay: str
    wps_basic_pay: str
    wps_variable_pay: str

    @field_validator("*")
    @classmethod
    def validate_money(cls, value: str) -> str:
        return _money(value, signed=True)


class PayrollEntrySaveRequest(StrictRequestSchema):
    employee_id: uuid.UUID
    increment: str = "0.00"
    bonus: str = "0.00"
    other_pay: str = "0.00"
    variable_allowance: str = "0.00"
    additional_allowances: list[PayrollAdjustmentRequest] = Field(
        default_factory=list[PayrollAdjustmentRequest]
    )
    deductions: list[PayrollAdjustmentRequest] = Field(
        default_factory=list[PayrollAdjustmentRequest]
    )
    excluded: bool = False
    preview: PayrollEntryPreview

    @field_validator("increment", "bonus", "other_pay")
    @classmethod
    def validate_unsigned_money(cls, value: str) -> str:
        return _money(value)

    @field_validator("variable_allowance")
    @classmethod
    def validate_signed_money(cls, value: str) -> str:
        return _money(value, signed=True)

    @model_validator(mode="after")
    def validate_adjustments(self) -> PayrollEntrySaveRequest:
        codes = [item.code for item in self.additional_allowances + self.deductions]
        ids = [item.id for item in self.additional_allowances + self.deductions]
        if len(codes) != len(set(codes)) or len(ids) != len(set(ids)):
            raise ValueError("adjustment codes and IDs must be unique per entry")
        return self


class PayrollCreateRequest(StrictRequestSchema):
    period: str
    payment_date: date

    @field_validator("period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        return _period(value)


class PayrollRepeatRequest(PayrollCreateRequest):
    expected_updated_at: datetime


class PayrollVersionRequest(StrictRequestSchema):
    expected_updated_at: datetime


class PayrollReasonRequest(PayrollVersionRequest):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason is required")
        return value


class PayrollEntriesRequest(PayrollVersionRequest):
    entries: list[PayrollEntrySaveRequest] = Field(max_length=10000)

    @model_validator(mode="after")
    def validate_employee_ids(self) -> PayrollEntriesRequest:
        employee_ids = [item.employee_id for item in self.entries]
        if len(employee_ids) != len(set(employee_ids)):
            raise ValueError("employee IDs must be unique")
        return self


class PayrollAdjustmentResponse(ApiSchema):
    id: uuid.UUID
    code: str
    label: str
    amount: str
    recurrence: Literal["one_time", "recurring"]
    note: str | None


class PayrollEntryResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    basic_salary: str
    housing_allowance: str
    transport_allowance: str
    fixed_allowance: str
    increment: str
    bonus: str
    other_pay: str
    variable_allowance: str
    leave_deduction: str
    fixed_pay: str
    gross_pay: str
    total_deductions: str
    net_pay: str
    wps_basic_pay: str
    wps_variable_pay: str
    excluded: bool
    additional_allowances: list[PayrollAdjustmentResponse]
    deductions: list[PayrollAdjustmentResponse]
    source_explanations: list[str]
    source_fingerprint: str


class PayrollRunResponse(ApiSchema):
    id: uuid.UUID
    period: str
    payment_date: date
    sequence: str
    run_status: Literal["draft", "generated"]
    approval_status: Literal["draft", "pending_approval", "approved"]
    employee_count: int
    total_amount: str
    validation_status: Literal["valid", "blocking"]
    blocking_errors: list[str]
    source_warnings: list[str]
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class PayrollRunDetailResponse(PayrollRunResponse):
    entries: list[PayrollEntryResponse]


class PayrollApprovalHistoryResponse(ApiSchema):
    id: uuid.UUID
    action: Literal["submitted", "recalled", "approved", "rejected"]
    actor_name: str
    reason: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class PayslipLineResponse(ApiSchema):
    label: str
    amount: str


class PayslipResponse(ApiSchema):
    id: uuid.UUID
    period: str
    payment_date: date
    employee_name: str
    earnings: list[PayslipLineResponse]
    deductions: list[PayslipLineResponse]
    gross_pay: str
    total_deductions: str
    net_pay: str
    wps_basic_pay: str
    wps_variable_pay: str
    issued_at: datetime

    @field_serializer("issued_at")
    def serialize_issued_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
