from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

TrainingStatus = Literal["planned", "in_progress", "completed", "cancelled"]
CertificationStatus = Literal["pending_review", "verified", "rejected"]


def _decimal(value: object, *, places: int, maximum: str) -> Decimal:
    if not isinstance(value, str) or "." not in value:
        raise ValueError("value must be a decimal string")
    whole, fraction = value.split(".", 1)
    if len(fraction) != places or not whole.isdigit() or not fraction.isdigit():
        raise ValueError(f"value must have {places} decimal places")
    amount = Decimal(value)
    if amount < 0 or amount > Decimal(maximum):
        raise ValueError("value out of range")
    return amount


class TrainingFields(StrictRequestSchema):
    training_title: str = Field(min_length=1, max_length=180)
    training_type: str = Field(default="external", min_length=1, max_length=120)
    provider: str = Field(default="", max_length=180)
    start_date: date | None = None
    end_date: date | None = None
    duration_hours: Decimal | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator("training_title", "training_type", "provider", "notes", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("duration_hours", mode="before")
    @classmethod
    def validate_duration(cls, value: object) -> Decimal | None:
        return None if value is None else _decimal(value, places=2, maximum="9999.99")

    @model_validator(mode="after")
    def dates_in_order(self) -> TrainingFields:
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end date precedes start date")
        return self


class TrainingAdminCreateRequest(TrainingFields):
    employee_id: uuid.UUID
    cost: Decimal = Decimal("0.00")
    is_cme: bool = False

    @field_validator("cost", mode="before")
    @classmethod
    def validate_cost(cls, value: object) -> Decimal:
        return _decimal(value, places=2, maximum="9999999999.99")


class TrainingStaffCreateRequest(TrainingFields):
    employee_id: uuid.UUID | None = None


class TrainingUpdateRequest(TrainingFields):
    cost: Decimal = Decimal("0.00")
    is_cme: bool = False
    expected_updated_at: datetime

    @field_validator("cost", mode="before")
    @classmethod
    def validate_cost(cls, value: object) -> Decimal:
        return _decimal(value, places=2, maximum="9999999999.99")


class TrainingCompleteRequest(StrictRequestSchema):
    end_date: date
    duration_hours: Decimal
    score: str = Field(default="", max_length=120)
    passed: bool
    is_cme: bool
    expected_updated_at: datetime

    @field_validator("duration_hours", mode="before")
    @classmethod
    def validate_duration(cls, value: object) -> Decimal:
        return _decimal(value, places=2, maximum="9999.99")

    @field_validator("score", mode="before")
    @classmethod
    def trim_score(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class VersionRequest(StrictRequestSchema):
    expected_updated_at: datetime


class TrainingResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    training_title: str
    training_type: str
    provider: str
    start_date: date | None
    end_date: date | None
    duration_hours: Decimal | None
    cost: Decimal
    status: TrainingStatus
    score: str
    passed: bool | None
    notes: str
    is_cme: bool
    has_evidence: bool
    file_name: str | None
    content_type: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("duration_hours", "cost")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.2f}"

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CertificationFields(StrictRequestSchema):
    certification_name: str = Field(min_length=1, max_length=180)
    issuing_body: str = Field(min_length=1, max_length=180)
    certificate_no: str = Field(default="", max_length=120)
    issued_date: date | None = None
    expiry_date: date | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator("certification_name", "issuing_body", "certificate_no", "notes", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def dates_in_order(self) -> CertificationFields:
        if (
            self.issued_date is not None
            and self.expiry_date is not None
            and self.expiry_date < self.issued_date
        ):
            raise ValueError("expiry date precedes issue date")
        return self


class CertificationAdminCreateRequest(CertificationFields):
    employee_id: uuid.UUID


class CertificationStaffCreateRequest(CertificationFields):
    employee_id: uuid.UUID | None = None


class CertificationDecisionRequest(StrictRequestSchema):
    expected_updated_at: datetime
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CertificationResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    certification_name: str
    issuing_body: str
    certificate_no: str
    issued_date: date | None
    expiry_date: date | None
    notes: str
    status: CertificationStatus
    has_evidence: bool
    file_name: str | None
    content_type: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("reviewed_at", "created_at", "updated_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CmeRequirementRequest(StrictRequestSchema):
    required_hours: Decimal
    notes: str = Field(default="", max_length=1000)
    expected_updated_at: datetime | None = None

    @field_validator("required_hours", mode="before")
    @classmethod
    def validate_hours(cls, value: object) -> Decimal:
        return _decimal(value, places=1, maximum="9999.9")

    @field_validator("notes", mode="before")
    @classmethod
    def trim_notes(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CmeRequirementResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    year: int
    required_hours: Decimal
    notes: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("required_hours")
    def serialize_hours(self, value: Decimal) -> str:
        return f"{value:.1f}"

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class CmeSummaryResponse(ApiSchema):
    year: int
    target_hours: Decimal
    achieved_hours: Decimal
    gap_hours: Decimal

    @field_serializer("target_hours", "achieved_hours", "gap_hours")
    def serialize_hours(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):.1f}"


class EvidenceDownloadResponse(ApiSchema):
    url: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DeletedDevelopmentResponse(ApiSchema):
    id: uuid.UUID
    deleted: bool
