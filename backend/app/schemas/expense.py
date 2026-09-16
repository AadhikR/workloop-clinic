from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

MONEY = re.compile(r"(?:0|[1-9][0-9]{0,9})\.[0-9]{2}")
ExpenseStatus = Literal[
    "pending",
    "manager_approved",
    "manager_rejected",
    "approved",
    "paid",
    "rejected",
]
EXPENSE_STATUSES = frozenset(
    {"pending", "manager_approved", "manager_rejected", "approved", "paid", "rejected"}
)


class ExpenseCreateRequest(StrictRequestSchema):
    category: str = Field(min_length=1, max_length=80)
    amount: str
    expense_date: date
    description: str = Field(min_length=1, max_length=2000)
    receipt_id: uuid.UUID | None = None

    @field_validator("category", "description", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: str) -> str:
        if not MONEY.fullmatch(value):
            raise ValueError("amount must use fixed two-decimal notation")
        try:
            amount = Decimal(value)
        except InvalidOperation:
            raise ValueError("invalid amount") from None
        if amount <= 0 or amount > Decimal("9999999999.99"):
            raise ValueError("amount is outside the accepted range")
        return value


class ExpenseDecisionRequest(StrictRequestSchema):
    expected_updated_at: datetime
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ExpenseDeleteRequest(StrictRequestSchema):
    expected_updated_at: datetime


class ExpenseResponse(ApiSchema):
    id: uuid.UUID
    category: str
    amount: str
    expense_date: date
    description: str
    status: ExpenseStatus
    rejection_reason: str | None
    has_receipt: bool
    payroll_period: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ExpenseQueueResponse(ExpenseResponse):
    employee_id: uuid.UUID
    employee_name: str
    manager_decision_at: datetime | None
    admin_decision_at: datetime | None
    can_decide: bool
    manager_actor_name: str | None = None
    admin_actor_name: str | None = None

    @field_serializer("manager_decision_at", "admin_decision_at")
    def serialize_optional_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ExpenseQuery(ApiSchema):
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=512)
    status: ExpenseStatus | None = None
    employee_id: uuid.UUID | None = None
    from_date: date | None = None
    to_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> ExpenseQuery:
        if (
            self.from_date is not None
            and self.to_date is not None
            and self.to_date < self.from_date
        ):
            raise ValueError("toDate precedes fromDate")
        return self
