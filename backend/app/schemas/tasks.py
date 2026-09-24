from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.http.schemas import ApiSchema

TaskUrgency = Literal["action", "expired", "urgent", "warning", "info"]
TaskCategoryStatus = Literal["ok", "empty", "failed"]


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
