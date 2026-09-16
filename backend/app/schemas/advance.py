from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

MONEY = re.compile(r"(?:0|[1-9][0-9]{0,9})\.[0-9]{2}")
PERIOD = re.compile(r"[0-9]{4}-(?:0[1-9]|1[0-2])")
AdvanceStatus = Literal["pending", "active", "settled", "cancelled"]
ADVANCE_STATUSES = frozenset({"pending", "active", "settled", "cancelled"})


def _fixed_money(value: str) -> str:
    if not MONEY.fullmatch(value):
        raise ValueError("amount must use fixed two-decimal notation")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("invalid amount") from None
    if amount <= 0 or amount > Decimal("9999999999.99"):
        raise ValueError("amount is outside the accepted range")
    return value


def _period(value: str) -> str:
    if not PERIOD.fullmatch(value):
        raise ValueError("period must use YYYY-MM notation")
    return value


class AdvanceCreateRequest(StrictRequestSchema):
    amount: str
    reason: str = Field(min_length=1, max_length=500)
    installment_count: int = Field(ge=1, le=120)
    repayment_start_period: str

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        return _fixed_money(value)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("repayment_start_period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        return _period(value)


class AdminAdvanceCreateRequest(AdvanceCreateRequest):
    employee_id: uuid.UUID


class AdvanceVersionRequest(StrictRequestSchema):
    expected_updated_at: datetime


class AdvanceDecisionRequest(AdvanceVersionRequest):
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AdvanceScheduleRequest(AdvanceVersionRequest):
    amount: str
    installment_count: int = Field(ge=1, le=120)
    repayment_start_period: str

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        return _fixed_money(value)

    @field_validator("repayment_start_period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        return _period(value)


class AdvanceRepaymentRequest(AdvanceVersionRequest):
    amount: str

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        return _fixed_money(value)


class AdvanceScheduleRow(ApiSchema):
    period: str
    scheduled_amount: str
    paid_amount: str
    remaining_amount: str
    status: Literal["paid", "partial", "due", "upcoming"]


class AdvanceRepaymentResponse(ApiSchema):
    id: uuid.UUID
    amount: str
    paid_date: date
    payroll_run_id: uuid.UUID | None
    payroll_period: str | None
    repayment_kind: Literal["manual", "payroll", "settlement"]
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AdvanceResponse(ApiSchema):
    id: uuid.UUID
    amount: str
    reason: str
    status: AdvanceStatus
    repayment_start_period: str
    installment_count: int
    monthly_installment: str
    outstanding_balance: str
    next_repayment_period: str | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AdvanceAdminResponse(AdvanceResponse):
    employee_id: uuid.UUID
    employee_name: str
    creator_name: str
    decision_actor_name: str | None
    disbursed_date: date | None
    can_decide: bool
    schedule: list[AdvanceScheduleRow]
    repayments: list[AdvanceRepaymentResponse]
