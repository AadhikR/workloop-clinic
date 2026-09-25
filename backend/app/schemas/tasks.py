from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_serializer

from app.http.schemas import ApiSchema

TaskUrgency = Literal["action", "expired", "urgent", "warning", "info"]
TaskCategoryStatus = Literal["ok", "empty", "failed"]


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TaskNavigation(ApiSchema):
    screen: str


class TaskItem(ApiSchema):
    id: str
    entity: str
    entity_id: uuid.UUID
    title: str
    subtitle: str
    urgency: TaskUrgency
    due_date: date | None
    created_at: datetime | None
    navigation: TaskNavigation

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        return _timestamp(value)


class TaskCategory(ApiSchema):
    code: str
    label: str
    status: TaskCategoryStatus
    count: int = Field(ge=0)
    items: list[TaskItem]
    error_code: str | None = None


class TaskListResponse(ApiSchema):
    categories: list[TaskCategory]
    next_cursor: str | None
    as_of: datetime
    source_version: str
    source_unavailable: bool = Field(default=False, exclude=True)

    @field_serializer("as_of")
    def serialize_timestamp(self, value: datetime) -> str:
        result = _timestamp(value)
        assert result is not None
        return result
