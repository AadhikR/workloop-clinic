from __future__ import annotations

import json
import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.http.errors import api_error

_CURSOR_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class _DuplicateJsonName(ValueError):
    pass


def parse_strict_json(body: bytes) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in pairs:
            if name in result:
                raise _DuplicateJsonName
            result[name] = value
        return result

    try:
        text = body.decode("utf-8")
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJsonName):
        raise ValueError("invalid JSON") from None


@dataclass(frozen=True, slots=True)
class Pagination:
    limit: int
    cursor: str | None


def parse_pagination(*, limit: str | None, cursor: str | None) -> Pagination:
    parsed_limit = 50
    if limit is not None:
        if not limit.isascii() or not limit.isdigit() or (len(limit) > 1 and limit[0] == "0"):
            raise ValueError("invalid limit")
        parsed_limit = int(limit)
        if not 1 <= parsed_limit <= 100:
            raise ValueError("invalid limit")
    if cursor is not None and (
        not cursor or len(cursor) > 512 or _CURSOR_PATTERN.fullmatch(cursor) is None
    ):
        raise ValueError("invalid cursor")
    return Pagination(limit=parsed_limit, cursor=cursor)


def parse_sort(
    value: str | None,
    *,
    allowed_fields: Collection[str],
    default: tuple[str, ...],
) -> tuple[tuple[str, bool], ...]:
    fields = default if value is None else tuple(value.split(","))
    if not fields or len(fields) > 3 or any(not field for field in fields):
        raise ValueError("invalid sort")
    parsed: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for item in fields:
        descending = item.startswith("-")
        name = item[1:] if descending else item
        if not name or name not in allowed_fields or name in seen:
            raise ValueError("invalid sort")
        seen.add(name)
        parsed.append((name, descending))
    return tuple(parsed)


def validate_query_parameters(
    request: Request,
    *,
    allowed: Collection[str],
    repeatable: Collection[str] = (),
) -> None:
    allowed_names = set(allowed)
    repeatable_names = set(repeatable)
    seen: set[str] = set()
    details: list[dict[str, str]] = []
    for name, _value in request.query_params.multi_items():
        if name not in allowed_names:
            details.append(
                {
                    "path": f"query.{name}",
                    "code": "unknown_field",
                    "message": "Field is not allowed",
                }
            )
        elif name in seen and name not in repeatable_names:
            details.append(
                {
                    "path": f"query.{name}",
                    "code": "duplicate_parameter",
                    "message": "Parameter must appear once",
                }
            )
        seen.add(name)
    if details:
        raise api_error(
            "validation_failed",
            details=sorted(details, key=lambda item: (item["path"], item["code"])),
        )
