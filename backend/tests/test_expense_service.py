from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.expense import (
    ExpenseCreateRequest,
    ExpenseDecisionRequest,
    ExpenseQueueResponse,
    ExpenseResponse,
)


def test_expense_submission_accepts_only_fixed_decimal_money_and_known_fields() -> None:
    valid = ExpenseCreateRequest.model_validate(
        {
            "category": "Travel",
            "amount": "350.00",
            "expenseDate": "2026-08-10",
            "description": "Synthetic airport transfer",
            "receiptId": None,
        }
    )
    assert valid.amount == "350.00"
    assert valid.expense_date == date(2026, 8, 10)

    for amount in ("350", "350.0", "3.5e2", "-1.00", "NaN"):
        with pytest.raises(ValidationError):
            ExpenseCreateRequest.model_validate(
                {
                    "category": "Travel",
                    "amount": amount,
                    "expenseDate": "2026-08-10",
                    "description": "Synthetic",
                    "receiptId": None,
                }
            )
    with pytest.raises(ValidationError):
        ExpenseCreateRequest.model_validate(
            {
                "category": "Travel",
                "amount": "350.00",
                "expenseDate": "2026-08-10",
                "description": "Synthetic",
                "receiptId": None,
                "status": "approved",
            }
        )


def test_expense_decision_requires_a_strict_reason_and_version() -> None:
    version = "2026-09-16T12:00:00.000Z"
    approved = ExpenseDecisionRequest.model_validate({"expectedUpdatedAt": version, "reason": None})
    rejected = ExpenseDecisionRequest.model_validate(
        {"expectedUpdatedAt": version, "reason": "Outside policy"}
    )
    assert approved.reason is None
    assert rejected.reason == "Outside policy"
    with pytest.raises(ValidationError):
        ExpenseDecisionRequest.model_validate({"expectedUpdatedAt": version, "reason": " "})


def test_expense_projections_are_strict_and_do_not_expose_receipt_keys_or_actor_ids() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    claim_id = UUID("91000000-0000-4000-8000-000000000001")
    employee_id = UUID("91000000-0000-4000-8000-000000000002")
    self_projection = ExpenseResponse(
        id=claim_id,
        category="Travel",
        amount=f"{Decimal('350'):.2f}",
        expense_date=date(2026, 8, 10),
        description="Synthetic airport transfer",
        status="pending",
        rejection_reason=None,
        has_receipt=True,
        payroll_period=None,
        created_at=now,
        updated_at=now,
    )
    queue_projection = ExpenseQueueResponse(
        **self_projection.model_dump(),
        employee_id=employee_id,
        employee_name="Synthetic Employee",
        manager_decision_at=None,
        admin_decision_at=None,
        can_decide=True,
        manager_actor_name=None,
        admin_actor_name=None,
    )
    values = queue_projection.model_dump(mode="json", by_alias=True)
    assert values["amount"] == "350.00"
    assert "objectKey" not in values
    assert "approvedByAppUserId" not in values
    assert "managerApprovedByAppUserId" not in values
