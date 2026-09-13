from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Timestamped(ApiSchema):
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return _instant(value)


class LeaveSettingsResponse(Timestamped):
    id: uuid.UUID
    branch_id: uuid.UUID
    leave_year_type: Literal["calendar"]
    weekend_definition: Literal["fri-sat", "sat-sun"]
    carry_forward_enabled: bool
    carry_forward_max_days: int
    approval_chain: Literal["1-level", "2-level"]
    ramadan_active: bool
    ramadan_start: date | None
    ramadan_end: date | None


class LeaveSettingsRequest(StrictRequestSchema):
    expected_updated_at: datetime | None = None
    leave_year_type: Literal["calendar"] = "calendar"
    weekend_definition: Literal["fri-sat", "sat-sun"] = "fri-sat"
    carry_forward_enabled: bool = True
    carry_forward_max_days: int = Field(default=15, ge=0, le=366)
    approval_chain: Literal["1-level", "2-level"] = "1-level"
    ramadan_active: bool = False
    ramadan_start: date | None = None
    ramadan_end: date | None = None

    @field_validator("expected_updated_at", mode="before")
    @classmethod
    def validate_instant(cls, value: object) -> object:
        if value is not None and (not isinstance(value, str) or not INSTANT.fullmatch(value)):
            raise ValueError("invalid instant")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> LeaveSettingsRequest:
        if (self.ramadan_start is None) != (self.ramadan_end is None):
            raise ValueError("Ramadan dates must be supplied together")
        if self.ramadan_start and self.ramadan_end and self.ramadan_end < self.ramadan_start:
            raise ValueError("Ramadan end must not precede Ramadan start")
        return self


LEAVE_TYPE_FIELDS = {
    "code",
    "name",
    "color",
    "is_paid",
    "is_unlimited",
    "requires_approval",
    "requires_attachment",
    "requires_reason",
    "min_notice_days",
    "annual_entitlement_days",
    "accrual_type",
    "day_count_type",
    "auto_approve",
    "carry_forward_allowed",
    "carry_forward_max_days",
    "gender_restriction",
    "min_service_months",
    "once_per_career",
    "not_deducted_from_annual",
    "affects_payroll",
    "law_reference",
    "is_active",
    "sort_order",
    "probation_eligible",
}


class LeaveTypeResponse(Timestamped):
    id: uuid.UUID
    branch_id: uuid.UUID
    code: str
    name: str
    color: str
    is_paid: bool
    is_unlimited: bool
    requires_approval: bool
    requires_attachment: bool
    requires_reason: bool
    min_notice_days: int
    annual_entitlement_days: Decimal
    accrual_type: str
    day_count_type: str
    auto_approve: bool
    carry_forward_allowed: bool
    carry_forward_max_days: int
    gender_restriction: str | None
    min_service_months: int
    once_per_career: bool
    not_deducted_from_annual: bool
    affects_payroll: bool
    law_reference: str
    is_active: bool
    sort_order: int
    probation_eligible: bool

    @field_serializer("annual_entitlement_days")
    def serialize_days(self, value: Decimal) -> str:
        return f"{value:.2f}"


class LeaveTypeRequest(StrictRequestSchema):
    expected_updated_at: datetime | None = None
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    color: str = Field(default="#6b7280", min_length=1, max_length=32)
    is_paid: bool = True
    is_unlimited: bool = False
    requires_approval: bool = True
    requires_attachment: bool = False
    requires_reason: bool = False
    min_notice_days: int = Field(default=0, ge=0, le=366)
    annual_entitlement_days: Decimal = Field(default=Decimal("0.00"), ge=0, le=9999)
    accrual_type: str = Field(default="fixed", min_length=1, max_length=40)
    day_count_type: Literal["calendar", "working"] = "calendar"
    auto_approve: bool = False
    carry_forward_allowed: bool = False
    carry_forward_max_days: int = Field(default=0, ge=0, le=366)
    gender_restriction: str | None = Field(default=None, max_length=40)
    min_service_months: int = Field(default=0, ge=0, le=1_200)
    once_per_career: bool = False
    not_deducted_from_annual: bool = False
    affects_payroll: bool = False
    law_reference: str = Field(default="", max_length=500)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100_000)
    probation_eligible: bool = True

    @field_validator("code", "name", "color", "accrual_type", "law_reference")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_text(self) -> LeaveTypeRequest:
        if not self.code or not self.name:
            raise ValueError("code and name must not be blank")
        if self.carry_forward_allowed and self.carry_forward_max_days == 0:
            raise ValueError("carry-forward types need a positive cap")
        return self


class PublicHolidayResponse(ApiSchema):
    id: uuid.UUID
    branch_id: uuid.UUID
    date: date
    name: str
    type: str
    year: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return _instant(value)


class PublicHolidayRequest(StrictRequestSchema):
    date: date
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="federal", min_length=1, max_length=40)
    expected_created_at: datetime | None = None

    @field_validator("name", "type")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class SeedHolidaysRequest(StrictRequestSchema):
    year: int = Field(ge=2000, le=2100)
    holidays: list[PublicHolidayRequest] = Field(min_length=1, max_length=100)
