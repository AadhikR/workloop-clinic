from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from typing import Literal

from pydantic import Field, field_serializer, field_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

IncidentType = Literal[
    "patient_safety",
    "medication_error",
    "injury",
    "needlestick",
    "infection",
    "equipment",
    "near_miss",
    "workplace",
    "other",
]
IncidentSeverity = Literal["low", "moderate", "high", "critical"]
IncidentStatus = Literal["open", "investigating", "closed"]


class IncidentFields(StrictRequestSchema):
    incident_date: date
    incident_time: time | None = None
    location: str = Field(default="", max_length=180)
    department: str = Field(default="", max_length=180)
    incident_type: IncidentType = "other"
    severity: IncidentSeverity = "low"
    description: str = Field(min_length=1, max_length=10000)
    reported_by_id: uuid.UUID | None = None
    involved_emp_id: uuid.UUID | None = None
    immediate_action: str = Field(default="", max_length=10000)
    notes: str = Field(default="", max_length=10000)

    @field_validator(
        "location", "department", "description", "immediate_action", "notes", mode="before"
    )
    @classmethod
    def trim_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class IncidentCreateRequest(IncidentFields):
    pass


class IncidentUpdateRequest(IncidentFields):
    expected_updated_at: datetime


class IncidentVersionRequest(StrictRequestSchema):
    expected_updated_at: datetime


class IncidentInvestigationRequest(IncidentVersionRequest):
    root_cause: str = Field(min_length=1, max_length=10000)

    @field_validator("root_cause", mode="before")
    @classmethod
    def trim_root_cause(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class IncidentCorrectiveActionRequest(IncidentVersionRequest):
    corrective_action: str = Field(min_length=1, max_length=10000)

    @field_validator("corrective_action", mode="before")
    @classmethod
    def trim_corrective_action(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class IncidentResponse(ApiSchema):
    id: uuid.UUID
    incident_date: date
    incident_time: time | None
    location: str
    department: str
    incident_type: IncidentType
    severity: IncidentSeverity
    description: str
    reported_by_id: uuid.UUID | None
    reported_by_name: str | None
    involved_emp_id: uuid.UUID | None
    involved_employee_name: str | None
    immediate_action: str
    root_cause: str
    corrective_action: str
    status: IncidentStatus
    closed_date: date | None
    closed_by_app_user_id: uuid.UUID | None
    notes: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
