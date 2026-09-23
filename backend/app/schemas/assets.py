from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, ValidationInfo, field_serializer, field_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

AssetStatus = Literal["available", "assigned", "under_repair", "retired", "lost"]


def _money(value: object) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, str) or "." not in value:
        raise ValueError("money must be a decimal string")
    whole, fraction = value.split(".", 1)
    if len(fraction) != 2 or not whole.isdigit() or not fraction.isdigit():
        raise ValueError("money must have two decimal places")
    amount = Decimal(value)
    if amount < 0 or amount > Decimal("9999999999.99"):
        raise ValueError("money out of range")
    return amount


class AssetFields(StrictRequestSchema):
    name: str = Field(min_length=1, max_length=180)
    asset_code: str = Field(default="", max_length=120)
    category: str = Field(default="other", max_length=120)
    brand: str = Field(default="", max_length=120)
    model: str = Field(default="", max_length=120)
    serial_number: str = Field(default="", max_length=180)
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator(
        "name", "asset_code", "category", "brand", "model", "serial_number", "notes", mode="before"
    )
    @classmethod
    def normalize_text(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized.upper() if info.field_name == "asset_code" else normalized

    @field_validator("purchase_cost", mode="before")
    @classmethod
    def validate_money(cls, value: object) -> Decimal | None:
        return _money(value)


class AssetCreateRequest(AssetFields):
    pass


class AssetUpdateRequest(AssetFields):
    expected_updated_at: datetime


class AssetStatusRequest(StrictRequestSchema):
    status: AssetStatus
    expected_updated_at: datetime


class AssetAssignRequest(StrictRequestSchema):
    employee_id: uuid.UUID
    condition_at_handover: str = Field(default="good", min_length=1, max_length=120)
    notes: str = Field(default="", max_length=1000)
    expected_updated_at: datetime

    @field_validator("condition_at_handover", "notes", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AssetReturnRequest(StrictRequestSchema):
    condition_at_return: str = Field(min_length=1, max_length=120)
    notes: str = Field(default="", max_length=1000)
    expected_updated_at: datetime

    @field_validator("condition_at_return", "notes", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class AssetDeleteRequest(StrictRequestSchema):
    expected_updated_at: datetime


class AssetResponse(ApiSchema):
    id: uuid.UUID
    name: str
    asset_code: str
    category: str
    brand: str
    model: str
    serial_number: str
    purchase_date: date | None
    purchase_cost: Decimal | None
    status: AssetStatus
    notes: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("purchase_cost")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.2f}"

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AssetAssignmentResponse(ApiSchema):
    id: uuid.UUID
    asset_id: uuid.UUID
    employee_id: uuid.UUID
    asset_name: str
    asset_code: str
    status: AssetStatus
    assigned_date: date
    return_date: date | None
    condition_at_handover: str
    condition_at_return: str | None
    notes: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DeletedAssetResponse(ApiSchema):
    id: uuid.UUID
    deleted: bool
