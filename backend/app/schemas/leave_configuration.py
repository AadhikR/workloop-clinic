from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from datetime import date as Date
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
DAY_VALUE = re.compile(r"^(?:0|[1-9]\d{0,3})\.\d{2}$")


def _instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _nonblank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("value must not be blank")
    return normalized


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
    ramadan_start: Date | None
    ramadan_end: Date | None


class LeaveSettingsRequest(StrictRequestSchema):
    expected_updated_at: datetime | None = None
    leave_year_type: Literal["calendar"] = "calendar"
    weekend_definition: Literal["fri-sat", "sat-sun"] = "fri-sat"
    carry_forward_enabled: bool = True
    carry_forward_max_days: int = Field(default=15, ge=0, le=366)
    approval_chain: Literal["1-level", "2-level"] = "1-level"
    ramadan_active: bool = False
    ramadan_start: Date | None = None
    ramadan_end: Date | None = None

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


class LeaveTypeCreateRequest(StrictRequestSchema):
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
    accrual_type: Literal["fixed", "monthly", "once_per_career", "none"] = "fixed"
    day_count_type: Literal["calendar", "working"] = "calendar"
    auto_approve: bool = False
    carry_forward_allowed: bool = False
    carry_forward_max_days: int = Field(default=0, ge=0, le=366)
    gender_restriction: Literal["Female", "Male"] | None = None
    min_service_months: int = Field(default=0, ge=0, le=1_200)
    once_per_career: bool = False
    not_deducted_from_annual: bool = False
    affects_payroll: bool = False
    law_reference: str = Field(default="", max_length=500)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0, le=100_000)
    probation_eligible: bool = True

    @field_validator("annual_entitlement_days", mode="before")
    @classmethod
    def validate_days(cls, value: object) -> object:
        if not isinstance(value, str) or DAY_VALUE.fullmatch(value) is None:
            raise ValueError("invalid decimal day value")
        return value

    @field_validator("code", "name", "color", "accrual_type")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _nonblank(value)

    @field_validator("law_reference")
    @classmethod
    def normalize_optional_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_rules(self) -> LeaveTypeCreateRequest:
        if self.carry_forward_allowed and self.carry_forward_max_days == 0:
            raise ValueError("carry-forward types need a positive cap")
        if self.once_per_career and self.accrual_type != "once_per_career":
            raise ValueError("once-per-career types need matching accrual")
        return self


class LeaveTypeUpdateRequest(StrictRequestSchema):
    expected_updated_at: datetime
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    color: str | None = Field(default=None, min_length=1, max_length=32)
    is_paid: bool | None = None
    is_unlimited: bool | None = None
    requires_approval: bool | None = None
    requires_attachment: bool | None = None
    requires_reason: bool | None = None
    min_notice_days: int | None = Field(default=None, ge=0, le=366)
    annual_entitlement_days: Decimal | None = Field(default=None, ge=0, le=9999)
    accrual_type: Literal["fixed", "monthly", "once_per_career", "none"] | None = None
    day_count_type: Literal["calendar", "working"] | None = None
    auto_approve: bool | None = None
    carry_forward_allowed: bool | None = None
    carry_forward_max_days: int | None = Field(default=None, ge=0, le=366)
    gender_restriction: Literal["Female", "Male"] | None = None
    min_service_months: int | None = Field(default=None, ge=0, le=1_200)
    once_per_career: bool | None = None
    not_deducted_from_annual: bool | None = None
    affects_payroll: bool | None = None
    law_reference: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    probation_eligible: bool | None = None

    @field_validator("expected_updated_at", mode="before")
    @classmethod
    def validate_instant(cls, value: object) -> object:
        if not isinstance(value, str) or not INSTANT.fullmatch(value):
            raise ValueError("invalid instant")
        return value

    @field_validator("annual_entitlement_days", mode="before")
    @classmethod
    def validate_days(cls, value: object) -> object:
        if value is not None and (not isinstance(value, str) or DAY_VALUE.fullmatch(value) is None):
            raise ValueError("invalid decimal day value")
        return value

    @field_validator("code", "name", "color", "accrual_type")
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        return None if value is None else _nonblank(value)

    @field_validator("law_reference")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @model_validator(mode="after")
    def validate_changes(self) -> LeaveTypeUpdateRequest:
        supplied = self.model_fields_set - {"expected_updated_at"}
        if not supplied:
            raise ValueError("at least one leave-type field is required")
        nullable = {"gender_restriction"}
        if any(getattr(self, field) is None for field in supplied - nullable):
            raise ValueError("leave-type fields must not be null")
        return self


class PublicHolidayResponse(ApiSchema):
    id: uuid.UUID
    branch_id: uuid.UUID
    date: Date
    name: str
    type: str
    year: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return _instant(value)


class PublicHolidayCreateRequest(StrictRequestSchema):
    date: Date
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default="federal", min_length=1, max_length=40)

    @field_validator("name", "type")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _nonblank(value)


class PublicHolidaySnapshot(StrictRequestSchema):
    date: Date
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=40)

    @field_validator("name", "type")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _nonblank(value)


class PublicHolidayUpdateRequest(StrictRequestSchema):
    expected: PublicHolidaySnapshot
    date: Date | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = Field(default=None, min_length=1, max_length=40)

    @field_validator("name", "type")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return None if value is None else _nonblank(value)

    @model_validator(mode="after")
    def validate_changes(self) -> PublicHolidayUpdateRequest:
        supplied = self.model_fields_set - {"expected"}
        if not supplied or any(getattr(self, field) is None for field in supplied):
            raise ValueError("at least one non-null holiday field is required")
        return self


class SeedHolidaysRequest(StrictRequestSchema):
    year: int = Field(ge=2000, le=2100)
    holidays: list[PublicHolidayCreateRequest] = Field(min_length=1, max_length=100)
