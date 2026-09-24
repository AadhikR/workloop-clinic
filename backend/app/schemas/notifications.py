from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.http.schemas import ApiSchema


class NotificationResponse(ApiSchema):
    id: uuid.UUID
    type: str
    title: str
    body: str
    related_entity_type: str
    related_entity_id: str
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(ApiSchema):
    items: list[NotificationResponse]
    next_cursor: str | None
    as_of: datetime
    source_version: str


class NotificationUnreadCountResponse(ApiSchema):
    count: int = Field(ge=0)
    as_of: datetime


class NotificationReadAllResponse(ApiSchema):
    changed_count: int = Field(ge=0)
    unread_count: int = Field(ge=0)
    as_of: datetime
