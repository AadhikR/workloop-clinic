from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import Field, field_serializer

from app.http.schemas import ApiSchema


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class NotificationResponse(ApiSchema):
    id: uuid.UUID
    type: str
    title: str
    body: str
    related_entity_type: str
    related_entity_id: str
    read_at: datetime | None
    created_at: datetime

    @field_serializer("read_at", "created_at")
    def serialize_timestamp(self, value: datetime | None) -> str | None:
        return _timestamp(value)


class NotificationListResponse(ApiSchema):
    items: list[NotificationResponse]
    next_cursor: str | None
    as_of: datetime
    source_version: str

    @field_serializer("as_of")
    def serialize_timestamp(self, value: datetime) -> str:
        result = _timestamp(value)
        assert result is not None
        return result


class NotificationUnreadCountResponse(ApiSchema):
    count: int = Field(ge=0)
    as_of: datetime

    @field_serializer("as_of")
    def serialize_timestamp(self, value: datetime) -> str:
        result = _timestamp(value)
        assert result is not None
        return result


class NotificationReadAllResponse(ApiSchema):
    changed_count: int = Field(ge=0)
    unread_count: int = Field(ge=0)
    as_of: datetime

    @field_serializer("as_of")
    def serialize_timestamp(self, value: datetime) -> str:
        result = _timestamp(value)
        assert result is not None
        return result
