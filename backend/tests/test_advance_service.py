from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.advance import (
    AdminAdvanceCreateRequest,
    AdvanceAdminResponse,
    AdvanceCreateRequest,
    AdvanceRepaymentResponse,
    AdvanceScheduleRequest,
    AdvanceVersionRequest,
)
from app.services.advances import build_schedule, monthly_installment, schedule_values


def test_advance_requests_require_fixed_money_periods_and_known_fields() -> None:
    request = AdvanceCreateRequest.model_validate(
        {
            "amount": "1000.00",
            "reason": "Synthetic emergency",
            "installmentCount": 3,
            "repaymentStartPeriod": "2026-09",
        }
    )
    assert request.installment_count == 3
    assert request.repayment_start_period == "2026-09"
    for amount in ("1000", "1000.0", "1e3", "-1.00", "NaN"):
        with pytest.raises(ValidationError):
            AdvanceCreateRequest.model_validate(
                {
                    "amount": amount,
                    "reason": "Synthetic",
                    "installmentCount": 3,
                    "repaymentStartPeriod": "2026-09",
                }
            )
    with pytest.raises(ValidationError):
        AdminAdvanceCreateRequest.model_validate(
            {
                "employeeId": "91000000-0000-4000-8000-000000000001",
                "amount": "1000.00",
                "reason": "Synthetic",
                "installmentCount": 3,
                "repaymentStartPeriod": "2026-13",
            }
        )
    with pytest.raises(ValidationError):
        AdvanceCreateRequest.model_validate(
            {
                "amount": "1000.00",
                "reason": "Synthetic",
                "installmentCount": 3,
                "repaymentStartPeriod": "2026-09",
                "status": "active",
            }
        )


def test_schedule_uses_half_up_monthly_money_and_an_exact_final_installment() -> None:
    assert monthly_installment(Decimal("1000.00"), 3) == Decimal("333.33")
    assert schedule_values(Decimal("1000.00"), 3) == [
        Decimal("333.33"),
        Decimal("333.33"),
        Decimal("333.34"),
    ]
    assert schedule_values(Decimal("1500.00"), 3) == [
        Decimal("500.00"),
        Decimal("500.00"),
        Decimal("500.00"),
    ]


def test_schedule_applies_partial_repayments_without_losing_the_final_cent() -> None:
    advance = {
        "amount": Decimal("1000.00"),
        "repayment_months": 3,
        "repayment_start_month": date(2026, 8, 1),
    }
    repayments = [{"amount": Decimal("500.00")}]
    schedule = build_schedule(advance, repayments, "2026-09")  # type: ignore[arg-type]
    assert [item.scheduled_amount for item in schedule] == ["333.33", "333.33", "333.34"]
    assert [item.paid_amount for item in schedule] == ["333.33", "166.67", "0.00"]
    assert [item.remaining_amount for item in schedule] == ["0.00", "166.66", "333.34"]
    assert [item.status for item in schedule] == ["paid", "partial", "upcoming"]
    assert sum((Decimal(item.scheduled_amount) for item in schedule), Decimal()) == Decimal(
        "1000.00"
    )


def test_mutable_advance_commands_require_optimistic_timestamps() -> None:
    version = "2026-09-16T12:00:00.000Z"
    parsed = AdvanceVersionRequest.model_validate({"expectedUpdatedAt": version})
    assert parsed.expected_updated_at == datetime(2026, 9, 16, 12, tzinfo=UTC)
    with pytest.raises(ValidationError):
        AdvanceScheduleRequest.model_validate(
            {
                "amount": "1000.00",
                "installmentCount": 3,
                "repaymentStartPeriod": "2026-09",
            }
        )


def test_administrator_projection_is_strict_and_contains_no_actor_ids() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    projection = AdvanceAdminResponse(
        id=UUID("91000000-0000-4000-8000-000000000001"),
        amount="1000.00",
        reason="Synthetic emergency",
        status="active",
        repayment_start_period="2026-09",
        installment_count=3,
        monthly_installment="333.33",
        outstanding_balance="666.67",
        next_repayment_period="2026-10",
        rejection_reason=None,
        created_at=now,
        updated_at=now,
        employee_id=UUID("91000000-0000-4000-8000-000000000002"),
        employee_name="Synthetic Employee",
        creator_name="Administrator",
        decision_actor_name="Administrator",
        disbursed_date=date(2026, 9, 16),
        can_decide=False,
        schedule=[],
        repayments=[
            AdvanceRepaymentResponse(
                id=UUID("91000000-0000-4000-8000-000000000003"),
                amount="333.33",
                paid_date=date(2026, 9, 16),
                payroll_run_id=None,
                payroll_period=None,
                repayment_kind="manual",
                created_at=now,
            )
        ],
    )
    values = projection.model_dump(mode="json", by_alias=True)
    assert values["monthlyInstallment"] == "333.33"
    assert values["repayments"][0]["repaymentKind"] == "manual"
    assert "creatorAppUserId" not in values
    assert "decisionActorAppUserId" not in values
