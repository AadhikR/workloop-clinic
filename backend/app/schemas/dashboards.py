from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.http.schemas import ApiSchema

DashboardSeverity = Literal["info", "success", "warning", "critical"]
DashboardValue = int | str


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
