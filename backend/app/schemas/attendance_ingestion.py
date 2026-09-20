from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


def _instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ClockEventResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    event_type: Literal["CLOCK_IN", "CLOCK_OUT"]
    event_time: datetime
    method: Literal["WEB", "MOBILE", "MANUAL", "BIOMETRIC", "EMPLOYEE_APP"]
    notes: str
    created_at: datetime

    @field_serializer("event_time", "created_at")
    def serialize_instant(self, value: datetime) -> str:
        return _instant(value)


class ManualClockEventRequest(StrictRequestSchema):
    employee_id: uuid.UUID
    event_type: Literal["CLOCK_IN", "CLOCK_OUT"]
    event_time: datetime
    note: str = Field(min_length=1, max_length=500)

    @field_validator("event_time")
    @classmethod
    def require_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("note is required")
        return value


class BiometricMappingRequest(StrictRequestSchema):
    employee_id: uuid.UUID
    device_name: str = Field(min_length=1, max_length=120)

    @field_validator("device_name")
    @classmethod
    def normalize_device(cls, value: str) -> str:
        return value.strip()


class BiometricMappingResponse(ApiSchema):
    id: uuid.UUID
    badge_no: str
    employee_id: uuid.UUID
    device_name: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_instant(self, value: datetime) -> str:
        return _instant(value)


class BiometricCandidate(StrictRequestSchema):
    badge_no: str = Field(min_length=1, max_length=120)
    event_type: Literal["CLOCK_IN", "CLOCK_OUT"]
    event_time: datetime
    device_name: str = Field(default="Default", min_length=1, max_length=120)

    @field_validator("badge_no", "device_name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.strip()
        if not value or "\x00" in value or value.startswith(("=", "+", "-", "@")):
            raise ValueError("invalid import value")
        return value

    @field_validator("event_time")
    @classmethod
    def require_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value


class BiometricImportRequest(StrictRequestSchema):
    candidates: list[BiometricCandidate] = Field(min_length=1, max_length=5000)
    source_bytes: int = Field(ge=1, le=2_097_152)


class ImportRowOutcome(ApiSchema):
    row_number: int
    outcome: Literal["accepted", "duplicate", "unknown_badge", "invalid"]
    reason_code: str | None
    clock_event_id: uuid.UUID | None


class BiometricImportResponse(ApiSchema):
    id: uuid.UUID
    accepted_count: int
    duplicate_count: int
    rejected_count: int
    outcomes: list[ImportRowOutcome]
