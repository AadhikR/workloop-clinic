from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_serializer

from app.http.schemas import ApiSchema

ReportCell = str | int | bool | None
ReportColumnType = Literal["string", "integer", "decimal", "date", "timestamp", "boolean"]


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ReportColumn(ApiSchema):
    key: str
    label: str
    type: ReportColumnType
    scale: int | None = None
    nullable: bool = False


class ReportTotals(ApiSchema):
    scope: Literal["filtered"] = "filtered"
    row_count: int
    values: dict[str, str | int | dict[str, int]] = Field(default_factory=dict)


class ReportResponse(ApiSchema):
    report_id: str
    columns: list[ReportColumn] = Field(min_length=1, max_length=30)
    rows: list[dict[str, ReportCell]]
    totals: ReportTotals
    filters: dict[str, str | int | None]
    as_of: datetime
    source_version: str
    next_cursor: str | None = None

    @field_serializer("as_of")
    def serialize_timestamp(self, value: datetime) -> str:
        return _timestamp(value)
