from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

RequestKind = Literal["letter", "custom"]
RequestStatus = Literal["pending", "completed", "rejected"]
LetterType = Literal[
    "salary_certificate_bank",
    "salary_certificate_embassy",
    "noc",
    "salary_transfer_letter",
    "employment_confirmation",
]

LETTER_TYPES = frozenset(
    {
        "salary_certificate_bank",
        "salary_certificate_embassy",
        "noc",
        "salary_transfer_letter",
        "employment_confirmation",
    }
)
EXTERNAL_LETTER_TYPES = frozenset(
    {
        "salary_certificate_bank",
        "salary_certificate_embassy",
        "noc",
        "salary_transfer_letter",
    }
)
SALARY_LETTER_TYPES = frozenset(
    {
        "salary_certificate_bank",
        "salary_certificate_embassy",
        "salary_transfer_letter",
    }
)


class LetterRequestCreateRequest(StrictRequestSchema):
    request_kind: RequestKind
    letter_type: LetterType | None = None
    purpose: str = Field(default="", max_length=500)
    subject: str | None = Field(default=None, min_length=3, max_length=120)
    details: str | None = Field(default=None, min_length=5, max_length=2000)

    @field_validator("purpose", "subject", "details", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_kind_fields(self) -> LetterRequestCreateRequest:
        if self.request_kind == "letter":
            if self.letter_type is None or self.subject is not None or self.details is not None:
                raise ValueError("letter request fields do not match requestKind")
            if self.letter_type in EXTERNAL_LETTER_TYPES and len(self.purpose) < 5:
                raise ValueError("purpose must contain at least 5 characters")
        elif (
            self.letter_type is not None
            or self.purpose != ""
            or self.subject is None
            or self.details is None
        ):
            raise ValueError("custom request fields do not match requestKind")
        return self

    def stored_letter_type(self) -> str:
        if self.request_kind == "letter":
            assert self.letter_type is not None
            return self.letter_type
        assert self.subject is not None
        return self.subject

    def stored_purpose(self) -> str:
        if self.request_kind == "letter":
            return self.purpose
        assert self.details is not None
        return self.details


class LetterRequestDecisionRequest(StrictRequestSchema):
    expected_requested_at: datetime


class LetterRequestRejectRequest(LetterRequestDecisionRequest):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LetterRequestResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    job_title: str
    department: str
    employment_start_date: date | None
    branch_name: str
    request_kind: RequestKind
    letter_type: str
    purpose: str
    status: RequestStatus
    notes: str
    rejection_reason: str
    requested_at: datetime
    completed_at: datetime | None
    actioned_at: datetime | None
    updated_at: datetime

    @field_serializer("requested_at", "completed_at", "actioned_at", "updated_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class LetterRequestPrintSource(ApiSchema):
    request_id: uuid.UUID
    request_kind: RequestKind
    letter_type: str
    purpose: str
    employee_name: str
    job_title: str
    department: str
    employment_start_date: date | None
    branch_name: str
    basic_salary: Decimal | None
    allowance: Decimal | None
    requested_at: datetime
    completed_at: datetime

    @field_serializer("basic_salary", "allowance")
    def serialize_money(self, value: Decimal | None) -> str | None:
        return None if value is None else f"{value:.2f}"

    @field_serializer("requested_at", "completed_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
