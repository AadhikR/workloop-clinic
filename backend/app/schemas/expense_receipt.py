from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import field_serializer, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


class ReceiptSubmissionRequest(StrictRequestSchema):
    claim_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def distinct_targets(self) -> ReceiptSubmissionRequest:
        if self.claim_id is not None and self.employee_id is not None:
            raise ValueError("claimId and employeeId cannot both be supplied")
        return self


class ReceiptSubmissionResponse(ApiSchema):
    id: uuid.UUID
    submission_token: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ExpenseReceiptResponse(ApiSchema):
    id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime
    expires_at: datetime | None

    @field_serializer("uploaded_at", "expires_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ReceiptDownloadResponse(ApiSchema):
    url: str
    expires_at: datetime

    @field_serializer("expires_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
