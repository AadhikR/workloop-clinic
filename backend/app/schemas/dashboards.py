from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from pydantic import Field, field_serializer

from app.http.schemas import ApiSchema

DashboardSeverity = Literal["info", "success", "warning", "critical"]
DashboardValue = int | str


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DashboardComparison(ApiSchema):
    label: str
    value: DashboardValue
    unit: str


class DashboardDrillDown(ApiSchema):
    code: str
    target: str


class DashboardCard(ApiSchema):
    code: str
    label: str
    value: DashboardValue
    unit: str
    severity: DashboardSeverity
    comparison: DashboardComparison | None = None
    drill_down: DashboardDrillDown | None = None


class DashboardResponse(ApiSchema):
    as_of: datetime
    business_date: date
    source_version: str
    cards: list[DashboardCard] = Field(min_length=1, max_length=20)

    @field_serializer("as_of")
    def serialize_timestamp(self, value: datetime) -> str:
        return _timestamp(value)
