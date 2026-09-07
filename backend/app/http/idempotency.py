from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

from app.http.errors import api_error


def parse_idempotency_key(request: Request, *, required: bool) -> uuid.UUID | None:
    values = request.headers.getlist("idempotency-key")
    if not values:
        if required:
            raise api_error("idempotency_key_required")
        return None
    if len(values) != 1:
        raise api_error("invalid_idempotency_key")
    raw_value = values[0]
    try:
        parsed = uuid.UUID(raw_value)
    except (AttributeError, ValueError):
        raise api_error("invalid_idempotency_key") from None
    if parsed.version != 4 or str(parsed) != raw_value:
        raise api_error("invalid_idempotency_key")
    return parsed


@dataclass(frozen=True, slots=True)
class IdempotencyRequest:
    key: uuid.UUID
    operation_id: str
    method: str


class IdempotencyService(Protocol):
    async def execute(self, request: IdempotencyRequest) -> object:
        """Coordinate a later mutation without defining persistence in Phase 6B."""
