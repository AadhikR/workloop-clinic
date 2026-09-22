from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


def _instant(value: datetime | None) -> str | None:
    return (
        None
        if value is None
        else value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )


def _reason(value: str) -> str:
    result = value.strip()
    if not 3 <= len(result) <= 500:
        raise ValueError("reason must contain 3 to 500 non-space characters")
    return result


class ShiftSwapSubmitRequest(StrictRequestSchema):
    requester_date: date
    target_employee_id: uuid.UUID
    target_date: date
    reason: str = Field(min_length=3, max_length=500)
    expected_source_version: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return _reason(value)

    @model_validator(mode="after")
    def distinct_dates(self) -> ShiftSwapSubmitRequest:
        if self.requester_date == self.target_date:
            raise ValueError("swap dates must be distinct")
        if self.requester_date.strftime("%Y-%m") != self.target_date.strftime("%Y-%m"):
            raise ValueError("swap dates must be in the same roster month")
        return self


class ShiftSwapTransitionRequest(StrictRequestSchema):
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return None if value is None else _reason(value)


class ShiftSwapApproveRequest(StrictRequestSchema):
    expected_version: int = Field(ge=1)
    expected_source_version: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ShiftSwapResponse(ApiSchema):
    id: uuid.UUID
    requester_employee_id: uuid.UUID
    requester_employee_name: str
    target_employee_id: uuid.UUID
    target_employee_name: str
    requester_date: date
    target_date: date
    reason: str
    status: Literal["pending", "approved", "rejected", "cancelled"]
    rejection_reason: str
    expected_source_version: str
    requester_assignment_id: uuid.UUID
    target_assignment_id: uuid.UUID
    requester_assignment_version: int = Field(ge=1)
    target_assignment_version: int = Field(ge=1)
    approved_publication_version_id: uuid.UUID | None
    decided_at: datetime | None
    decided_by_app_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def valid_transition(self) -> ShiftSwapResponse:
        pending = self.status == "pending"
        approved = self.status == "approved"
        if pending != (self.decided_at is None and self.decided_by_app_user_id is None):
            raise ValueError("swap decision state is inconsistent")
        if approved != (self.approved_publication_version_id is not None):
            raise ValueError("swap publication state is inconsistent")
        if self.status == "rejected" and not self.rejection_reason.strip():
            raise ValueError("rejected swap requires a reason")
        return self

    @field_serializer("decided_at", "created_at", "updated_at")
    def serialize_instant(self, value: datetime | None) -> str | None:
        return _instant(value)
