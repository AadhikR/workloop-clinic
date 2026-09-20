from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

DayName = Literal["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
ShiftType = Literal["fixed", "flexible", "split", "overnight"]
ShiftCategory = Literal["morning", "afternoon", "night", "flexible", "split"]
LatePolicy = Literal["none", "per_minute", "per_occurrence"]
ALL_DAYS = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"}
CODE = re.compile(r"^[A-Z0-9](?:[A-Z0-9-]{0,10}[A-Z0-9])?$")
COLOR = re.compile(r"^#[0-9A-F]{6}$")


def _instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _decimal(value: object, *, low: str, high: str) -> Decimal:
    if isinstance(value, float):
        raise ValueError("binary floating point is not accepted")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid decimal") from None
    exponent = parsed.as_tuple().exponent
    if (
        not parsed.is_finite()
        or "e" in str(value).lower()
        or not isinstance(exponent, int)
        or exponent < -2
    ):
        raise ValueError("invalid decimal")
    if parsed < Decimal(low) or parsed > Decimal(high):
        raise ValueError("decimal outside allowed range")
    return parsed.quantize(Decimal("0.01"))


def _validate_days(working: list[str], weekend: list[str]) -> None:
    if (
        not working
        or not weekend
        or len(set(working)) != len(working)
        or len(set(weekend)) != len(weekend)
    ):
        raise ValueError("day lists must be nonempty and unique")
    if set(working) & set(weekend) or set(working) | set(weekend) != ALL_DAYS:
        raise ValueError("working and weekend days must partition the week")


class AttendanceSettingsResponse(ApiSchema):
    id: uuid.UUID
    working_days: list[DayName]
    weekend_days: list[DayName]
    default_hours_per_day: Decimal
    late_grace_minutes: int
    early_departure_grace_minutes: int
    overtime_requires_approval: bool
    max_daily_overtime_hours: Decimal
    late_deduction_policy: LatePolicy
    late_deduction_amount: Decimal
    wfh_enabled: bool
    regularisation_max_days_per_month: int
    regularisation_window_days: int
    biometric_api_enabled: bool
    biometric_api_key_configured: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("default_hours_per_day", "max_daily_overtime_hours", "late_deduction_amount")
    def serialize_decimal(self, value: Decimal) -> str:
        return f"{value:.2f}"

    @field_serializer("created_at", "updated_at")
    def serialize_instant(self, value: datetime) -> str:
        return _instant(value)


class AttendanceSettingsUpdateRequest(StrictRequestSchema):
    working_days: list[DayName]
    weekend_days: list[DayName]
    default_hours_per_day: Decimal
    late_grace_minutes: int = Field(ge=0, le=240)
    early_departure_grace_minutes: int = Field(ge=0, le=240)
    overtime_requires_approval: bool
    max_daily_overtime_hours: Decimal
    late_deduction_policy: LatePolicy
    late_deduction_amount: Decimal
    wfh_enabled: bool
    regularisation_max_days_per_month: int = Field(ge=0, le=31)
    regularisation_window_days: int = Field(ge=0, le=365)
    biometric_api_enabled: bool
    biometric_api_key: str | None = Field(default=None, min_length=16, max_length=512)
    expected_updated_at: datetime

    @field_validator("default_hours_per_day", mode="before")
    @classmethod
    def validate_default_hours(cls, value: object) -> Decimal:
        return _decimal(value, low="0.25", high="24.00")

    @field_validator("max_daily_overtime_hours", mode="before")
    @classmethod
    def validate_overtime_hours(cls, value: object) -> Decimal:
        return _decimal(value, low="0.00", high="12.00")

    @field_validator("late_deduction_amount", mode="before")
    @classmethod
    def validate_late_amount(cls, value: object) -> Decimal:
        return _decimal(value, low="0.00", high="9999999999.99")

    @model_validator(mode="after")
    def validate_settings(self) -> Self:
        _validate_days(list(self.working_days), list(self.weekend_days))
        return self


class ShiftResponse(ApiSchema):
    id: uuid.UUID
    name: str
    shift_type: ShiftType
    start_time: time | None
    end_time: time | None
    break_minutes: int
    expected_hours: Decimal
    late_grace_minutes: int
    early_departure_grace_minutes: int
    split_start_time: time | None
    split_end_time: time | None
    is_overnight: bool
    min_hours_flexible: Decimal | None
    is_active: bool
    color: str
    code: str | None
    shift_category: ShiftCategory
    min_staff: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("expected_hours", "min_hours_flexible")
    def serialize_hours(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.2f}"

    @field_serializer("created_at", "updated_at")
    def serialize_instant(self, value: datetime) -> str:
        return _instant(value)


class ShiftFields(StrictRequestSchema):
    name: str = Field(min_length=1, max_length=80)
    shift_type: ShiftType
    start_time: time | None
    end_time: time | None
    break_minutes: int = Field(ge=0, le=240)
    expected_hours: Decimal
    late_grace_minutes: int = Field(ge=0, le=240)
    early_departure_grace_minutes: int = Field(ge=0, le=240)
    split_start_time: time | None
    split_end_time: time | None
    is_overnight: bool
    min_hours_flexible: Decimal | None
    color: str
    code: str | None
    shift_category: ShiftCategory
    min_staff: int = Field(ge=0, le=999)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not CODE.fullmatch(value):
            raise ValueError("invalid shift code")
        return value

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        value = value.upper()
        if not COLOR.fullmatch(value):
            raise ValueError("invalid color")
        return value

    @field_validator("expected_hours", mode="before")
    @classmethod
    def validate_expected_hours(cls, value: object) -> Decimal:
        return _decimal(value, low="0.25", high="24.00")

    @field_validator("min_hours_flexible", mode="before")
    @classmethod
    def validate_flexible_hours(cls, value: object) -> Decimal | None:
        return None if value is None else _decimal(value, low="0.25", high="24.00")

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.shift_type == "fixed":
            valid = (
                self.start_time is not None
                and self.end_time is not None
                and self.start_time < self.end_time
                and not self.is_overnight
                and self.split_start_time is None
                and self.split_end_time is None
                and self.min_hours_flexible is None
                and self.shift_category in {"morning", "afternoon", "night"}
            )
        elif self.shift_type == "overnight":
            valid = (
                self.start_time is not None
                and self.end_time is not None
                and self.end_time <= self.start_time
                and self.is_overnight
                and self.shift_category == "night"
                and self.split_start_time is None
                and self.split_end_time is None
                and self.min_hours_flexible is None
            )
        elif self.shift_type == "split":
            valid = (
                self.start_time is not None
                and self.end_time is not None
                and self.split_start_time is not None
                and self.split_end_time is not None
                and self.start_time < self.end_time <= self.split_start_time < self.split_end_time
                and not self.is_overnight
                and self.shift_category == "split"
                and self.min_hours_flexible is None
            )
        else:
            valid = (
                self.start_time is None
                and self.end_time is None
                and self.split_start_time is None
                and self.split_end_time is None
                and not self.is_overnight
                and self.shift_category == "flexible"
                and self.break_minutes == 0
                and self.min_hours_flexible is not None
                and self.min_hours_flexible <= self.expected_hours
            )
        if not valid:
            raise ValueError("shift fields do not match the shift type")
        return self


class ShiftCreateRequest(ShiftFields):
    pass


class ShiftUpdateRequest(StrictRequestSchema):
    expected_updated_at: datetime
    name: str | None = Field(default=None, min_length=1, max_length=80)
    shift_type: ShiftType | None = None
    start_time: time | None = None
    end_time: time | None = None
    break_minutes: int | None = Field(default=None, ge=0, le=240)
    expected_hours: Decimal | None = None
    late_grace_minutes: int | None = Field(default=None, ge=0, le=240)
    early_departure_grace_minutes: int | None = Field(default=None, ge=0, le=240)
    split_start_time: time | None = None
    split_end_time: time | None = None
    is_overnight: bool | None = None
    min_hours_flexible: Decimal | None = None
    color: str | None = None
    code: str | None = None
    shift_category: ShiftCategory | None = None
    min_staff: int | None = Field(default=None, ge=0, le=999)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.model_fields_set == {"expected_updated_at"}:
            raise ValueError("at least one shift change is required")
        return self


class ShiftDeactivateRequest(StrictRequestSchema):
    expected_updated_at: datetime


class ShiftAssignmentResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    effective_from: date
    effective_to: date | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_instant(self, value: datetime) -> str:
        return _instant(value)


class ShiftAssignmentCreateRequest(StrictRequestSchema):
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    effective_from: date
    expected_current_assignment_id: uuid.UUID | None
    expected_current_assignment_updated_at: datetime | None

    @model_validator(mode="after")
    def validate_expected_pair(self) -> Self:
        if (self.expected_current_assignment_id is None) != (
            self.expected_current_assignment_updated_at is None
        ):
            raise ValueError("expected assignment fields must both be null or both be set")
        return self
