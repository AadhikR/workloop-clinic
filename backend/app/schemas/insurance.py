from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


def _money(value: object) -> Decimal:
    if not isinstance(value, str) or not value or "." not in value:
        raise ValueError("money must be a decimal string")
    whole, fraction = value.split(".", 1)
    if len(fraction) != 2 or not whole.isdigit() or not fraction.isdigit():
        raise ValueError("money must have two decimal places")
    amount = Decimal(value)
    if amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError("money out of range")
    return amount


class InsurancePolicyFields(StrictRequestSchema):
    insurer_name: str = Field(min_length=1, max_length=180)
    policy_number: str = Field(min_length=1, max_length=120)
    tier_name: str = Field(min_length=1, max_length=120)
    annual_premium: Decimal
    renewal_date: date | None = None
    broker_name: str = Field(default="", max_length=180)
    broker_contact: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)

    @field_validator(
        "insurer_name",
        "policy_number",
        "tier_name",
        "broker_name",
        "broker_contact",
        "notes",
        mode="before",
    )
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("annual_premium", mode="before")
    @classmethod
    def validate_money(cls, value: object) -> Decimal:
        return _money(value)


class InsurancePolicyCreateRequest(InsurancePolicyFields):
    pass


class InsurancePolicyUpdateRequest(InsurancePolicyFields):
    expected_updated_at: datetime


class InsurancePolicyDeleteRequest(StrictRequestSchema):
    expected_updated_at: datetime


class InsurancePolicyResponse(ApiSchema):
    id: uuid.UUID
    insurer_name: str
    policy_number: str
    tier_name: str
    annual_premium: Decimal
    renewal_date: date | None
    broker_name: str
    broker_contact: str
    notes: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("annual_premium")
    def serialize_money(self, value: Decimal) -> str:
        return f"{value:.2f}"

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CoverageReplaceRequest(StrictRequestSchema):
    policy_id: uuid.UUID
    member_id: str = Field(min_length=1, max_length=120)
    card_number: str = Field(default="", max_length=120)
    effective_date: date
    expiry_date: date | None = None
    tier_name: str = Field(min_length=1, max_length=120)
    expected_updated_at: datetime | None = None

    @field_validator("member_id", "card_number", "tier_name", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def dates_in_order(self) -> CoverageReplaceRequest:
        if self.expiry_date is not None and self.expiry_date < self.effective_date:
            raise ValueError("expiry date precedes effective date")
        return self


class EmployeeCoverageResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    policy_id: uuid.UUID
    member_id: str
    card_number: str
    effective_date: date
    expiry_date: date | None
    tier_name: str
    insurer_name: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SelfInsuranceResponse(ApiSchema):
    policy_id: uuid.UUID
    insurer_name: str
    tier_name: str
    effective_date: date
    expiry_date: date | None


class InsuranceDependantFields(StrictRequestSchema):
    name: str = Field(min_length=1, max_length=180)
    relationship: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    card_number: str = Field(default="", max_length=120)

    @field_validator("name", "relationship", "card_number", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class InsuranceDependantCreateRequest(InsuranceDependantFields):
    pass


class InsuranceDependantUpdateRequest(InsuranceDependantFields):
    expected_updated_at: datetime


class InsuranceDependantDeleteRequest(StrictRequestSchema):
    expected_updated_at: datetime


class InsuranceDependantResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    name: str
    relationship: str
    date_of_birth: date | None
    card_number: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DeletedInsuranceResponse(ApiSchema):
    id: uuid.UUID
    deleted: bool
