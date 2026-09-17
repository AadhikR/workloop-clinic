from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import RowMapping

from app.schemas.payroll import (
    PayrollAdjustmentRequest,
    PayrollEntriesRequest,
    PayrollEntryResponse,
    PayrollRunDetailResponse,
)
from app.services.payroll import (
    advance_due,
    automatic_adjustment,
    calculate_entry,
    manual_adjustments,
    prorate,
)


def adjustment(code: str, amount: str, recurrence: str = "recurring") -> PayrollAdjustmentRequest:
    return PayrollAdjustmentRequest.model_validate(
        {
            "id": str(UUID(int=len(code))),
            "code": code,
            "label": code.replace("_", " ").title(),
            "amount": amount,
            "recurrence": recurrence,
            "note": None,
        }
    )


def test_payroll_named_adjustments_match_the_approved_golden_case() -> None:
    values = calculate_entry(
        basic_salary="10000.00",
        housing_allowance="0.00",
        transport_allowance="0.00",
        fixed_allowance="0.00",
        additional_allowances=[
            adjustment("SHIFT_ALLOWANCE", "250.25"),
            adjustment("PROJECT_BONUS", "499.75", "one_time"),
        ],
        deductions=[
            adjustment("PARKING", "100.00"),
            adjustment("EQUIPMENT", "50.00", "one_time"),
        ],
    )
    assert values.gross_pay == Decimal("10750.00")
    assert values.total_deductions == Decimal("150.00")
    assert values.net_pay == Decimal("10600.00")
    assert values.wps_variable_pay == Decimal("600.00")


def test_integrated_automatic_inputs_match_the_approved_golden_case() -> None:
    expense = automatic_adjustment(
        "expense",
        UUID("9e000000-0000-4000-8000-000000000010"),
        "Expense reimbursement",
        Decimal("350.00"),
    )
    roster = automatic_adjustment(
        "roster",
        UUID("9e000000-0000-4000-8000-000000000011"),
        "Roster overtime",
        Decimal("288.46"),
    )
    advance = automatic_adjustment(
        "advance",
        UUID("9e000000-0000-4000-8000-000000000012"),
        "Advance repayment",
        Decimal("500.00"),
    )
    values = calculate_entry(
        basic_salary="12000.00",
        housing_allowance="3000.00",
        transport_allowance="1000.00",
        fixed_allowance="500.00",
        bonus="1000.00",
        leave_deduction="400.00",
        additional_allowances=[expense, roster],
        deductions=[advance],
    )
    assert values.fixed_pay == Decimal("16500.00")
    assert values.gross_pay == Decimal("18138.46")
    assert values.total_deductions == Decimal("900.00")
    assert values.net_pay == Decimal("17238.46")
    assert values.wps_variable_pay == Decimal("5238.46")


def test_advance_due_uses_oldest_unpaid_installment_and_exact_final_cent() -> None:
    row = cast(
        RowMapping,
        {
            "amount": Decimal("1000.00"),
            "outstanding_balance": Decimal("666.67"),
            "repayment_start_month": date(2026, 8, 1),
            "repayment_months": 3,
        },
    )
    due_period, amount = advance_due(row, date(2026, 10, 1))
    assert due_period == date(2026, 9, 1)
    assert amount == Decimal("666.67")


def test_manual_adjustment_filter_never_preserves_reserved_sources() -> None:
    manual: dict[str, object] = {
        "id": str(UUID(int=1)),
        "code": "SHIFT_ALLOWANCE",
        "label": "Shift allowance",
        "amount": "250.00",
        "recurrence": "recurring",
        "note": None,
    }
    automatic = automatic_adjustment(
        "expense",
        UUID("9e000000-0000-4000-8000-000000000020"),
        "Expense reimbursement",
        Decimal("350.00"),
    )
    assert manual_adjustments([manual, automatic]) == [manual]


def test_payroll_proration_rounds_each_component_before_aggregation() -> None:
    components = [prorate(value, 17, 31) for value in ("10000.00", "3333.33", "777.77", "111.11")]
    assert components == [
        Decimal("5483.87"),
        Decimal("1827.96"),
        Decimal("426.52"),
        Decimal("60.93"),
    ]
    values = calculate_entry(
        basic_salary=components[0],
        housing_allowance=components[1],
        transport_allowance=components[2],
        fixed_allowance=components[3],
    )
    assert values.fixed_pay == Decimal("7799.28")
    assert values.net_pay == Decimal("7799.28")


def test_payroll_mid_month_joiner_and_leaver_match_golden_values() -> None:
    joiner = [prorate(value, 14, 28) for value in ("12000.00", "3000.00", "1000.00", "500.00")]
    leaver = [prorate(value, 10, 28) for value in ("12000.00", "3000.00", "1000.00", "500.00")]
    assert joiner == [Decimal("6000.00"), Decimal("1500.00"), Decimal("500.00"), Decimal("250.00")]
    assert leaver == [Decimal("4285.71"), Decimal("1071.43"), Decimal("357.14"), Decimal("178.57")]
    assert sum(joiner) == Decimal("8250.00")
    assert sum(leaver) == Decimal("5892.85")


def test_negative_net_remains_an_exact_editable_draft_value() -> None:
    values = calculate_entry(
        basic_salary="1000.00",
        housing_allowance="0.00",
        transport_allowance="0.00",
        fixed_allowance="0.00",
        deductions=[adjustment("EXCESS", "1000.01")],
    )
    assert values.gross_pay == Decimal("1000.00")
    assert values.total_deductions == Decimal("1000.01")
    assert values.net_pay == Decimal("-0.01")


def test_payroll_requests_reject_unknown_fields_reserved_codes_and_duplicate_employees() -> None:
    with pytest.raises(ValidationError):
        adjustment("AUTO_UNTRUSTED", "1.00")
    preview = {
        "basicSalary": "1000.00",
        "housingAllowance": "0.00",
        "transportAllowance": "0.00",
        "fixedAllowance": "0.00",
        "fixedPay": "1000.00",
        "grossPay": "1000.00",
        "totalDeductions": "0.00",
        "netPay": "1000.00",
        "wpsBasicPay": "1000.00",
        "wpsVariablePay": "0.00",
    }
    entry = {
        "employeeId": "91000000-0000-4000-8000-000000000001",
        "preview": preview,
    }
    with pytest.raises(ValidationError):
        PayrollEntriesRequest.model_validate(
            {
                "expectedUpdatedAt": "2026-09-17T10:00:00.000Z",
                "entries": [entry, entry],
            }
        )
    with pytest.raises(ValidationError):
        PayrollEntriesRequest.model_validate(
            {
                "expectedUpdatedAt": "2026-09-17T10:00:00.000Z",
                "entries": [{**entry, "duCost": "1.00"}],
            }
        )


def test_payroll_detail_projection_is_strict_and_contains_no_sensitive_fields() -> None:
    now = datetime(2026, 9, 17, 10, tzinfo=UTC)
    entry = PayrollEntryResponse(
        id=UUID("91000000-0000-4000-8000-000000000001"),
        employee_id=UUID("91000000-0000-4000-8000-000000000002"),
        employee_name="Synthetic Employee",
        basic_salary="1000.00",
        housing_allowance="0.00",
        transport_allowance="0.00",
        fixed_allowance="0.00",
        increment="0.00",
        bonus="0.00",
        other_pay="0.00",
        variable_allowance="0.00",
        leave_deduction="0.00",
        fixed_pay="1000.00",
        gross_pay="1000.00",
        total_deductions="0.00",
        net_pay="1000.00",
        wps_basic_pay="1000.00",
        wps_variable_pay="0.00",
        excluded=False,
        additional_allowances=[],
        deductions=[],
        source_explanations=[],
        source_fingerprint="a" * 64,
    )
    detail = PayrollRunDetailResponse(
        id=UUID("91000000-0000-4000-8000-000000000003"),
        period="2026-09",
        payment_date=date(2026, 9, 25),
        sequence="0001",
        run_status="draft",
        approval_status="draft",
        employee_count=1,
        total_amount="1000.00",
        validation_status="valid",
        blocking_errors=[],
        source_warnings=[],
        created_at=now,
        updated_at=now,
        entries=[entry],
    ).model_dump(mode="json", by_alias=True)
    assert detail["entries"][0]["netPay"] == "1000.00"
    assert "iban" not in detail["entries"][0]
    assert "actorAppUserId" not in detail
