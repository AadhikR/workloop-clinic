from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import RowMapping

from app.schemas.wps import ComplianceOverrideRequest, NafisSnapshotResponse
from app.services.wps import entry_values, integer_aed, period_dates


def entry(*, basic: str, variable: str) -> dict[str, object]:
    return {
        "basic_salary": Decimal(basic),
        "housing_allowance": Decimal("0.00"),
        "transport_allowance": Decimal("0.00"),
        "allowance": Decimal("0.00"),
        "increment": Decimal("0.00"),
        "bonus": Decimal("0.00"),
        "other_pay": Decimal("0.00"),
        "variable_allowance": Decimal(variable),
        "leave_deduction": Decimal("0.00"),
        "additional_allowances": [],
        "deductions": [],
    }


def test_wps_integer_values_round_components_independently() -> None:
    row = cast(RowMapping, entry(basic="1000.50", variable="200.50"))
    assert entry_values(row) == (1001, 201, 1202)
    assert integer_aed(Decimal("5238.46")) == 5238


def test_wps_period_dates_include_leap_day() -> None:
    assert period_dates("2028-02") == (date(2028, 2, 1), date(2028, 2, 29))


def test_compliance_override_rejects_unknown_code_and_fields() -> None:
    with pytest.raises(ValidationError):
        ComplianceOverrideRequest.model_validate(
            {"ruleCode": "unknown", "reason": "No", "actorId": str(uuid.uuid4())}
        )


def test_nafis_snapshot_requires_matching_employee_count() -> None:
    with pytest.raises(ValidationError):
        NafisSnapshotResponse(
            id=uuid.uuid4(),
            period="2026-08",
            total_headcount=1,
            emirati_count=1,
            ratio_percent="100.00",
            required_percent="2.00",
            compliant=True,
            source_version="a" * 64,
            qualifying_wage_total="0.00",
            employees=[],
            generated_at=datetime.now(UTC),
        )
