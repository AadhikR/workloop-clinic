from __future__ import annotations

import uuid
from typing import Protocol, cast

from pydantic import BaseModel

from app.http.schemas import CollectionResponse, Page


class Identified(Protocol):
    id: uuid.UUID | str


def uuid_page[Item: BaseModel](items: list[Item], limit: int) -> CollectionResponse[Item]:
    visible = items[:limit]
    has_more = len(items) > limit
    return CollectionResponse(
        data=visible,
        page=Page(
            limit=limit,
            next_cursor=str(cast(Identified, visible[-1]).id) if has_more else None,
            has_more=has_more,
        ),
    )
