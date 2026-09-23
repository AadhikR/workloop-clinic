from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

DOCUMENT_TYPES = frozenset(
    {
        "Visa",
        "Passport",
        "Emirates ID",
        "Labour Card",
        "Work Permit",
        "DHA Licence",
        "DOH Licence",
        "MOH Licence",
        "BLS Certificate",
        "ACLS Certificate",
        "PALS Certificate",
        "NRP Certificate",
        "CME Certificate",
        "Medical Fitness Certificate",
        "Educational Certificate",
        "Professional License",
        "NOC / Reference Letter",
        "Other",
    }
)


class EmployeeDocumentSubmissionRequest(StrictRequestSchema):
    employee_id: uuid.UUID | None = None
    document_type: str
    document_number: str = Field(min_length=1, max_length=120)
    expiry_date: date | None = None
    notes: str = Field(default="", max_length=1000)

    @field_validator("document_type")
    @classmethod
    def valid_document_type(cls, value: str) -> str:
        if value not in DOCUMENT_TYPES:
            raise ValueError("unsupported document type")
        return value

    @field_validator("document_number", "notes", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class EmployeeDocumentSubmissionResponse(ApiSchema):
    id: uuid.UUID
    submission_token: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EmployeeDocumentResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    document_type: str
    status: Literal["pending_verification", "verified", "rejected"]
    rejection_reason: str | None
    file_name: str
    size_bytes: int
    content_type: Literal["application/pdf", "image/png", "image/jpeg"]
    expiry_date: date | None
    notes: str
    reviewer_name: str | None
    uploaded_at: datetime
    reviewed_at: datetime | None
    updated_at: datetime

    @field_serializer("uploaded_at", "reviewed_at", "updated_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EmployeeDocumentDecisionRequest(StrictRequestSchema):
    expected_updated_at: datetime
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class EmployeeDocumentDeleteRequest(StrictRequestSchema):
    expected_updated_at: datetime


class EmployeeDocumentDownloadResponse(ApiSchema):
    url: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EmployeeDocumentDeleteResponse(ApiSchema):
    id: uuid.UUID
    cleanup_pending: bool
