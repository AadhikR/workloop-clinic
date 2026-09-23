from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.schemas.offboarding import SettlementInputs, SettlementPreviewResponse
from app.services.offboarding import calculate_gratuity

ID = UUID("12345678-1234-4234-8234-123456789abc")
NOW = datetime(2026, 9, 23, tzinfo=UTC)


def test_phase11g_routes_are_registered_once() -> None:
    operations: list[str] = []
    for path_item in create_app().openapi()["paths"].values():
        for raw_operation in path_item.values():
            if isinstance(raw_operation, dict):
                operation = cast(dict[str, object], raw_operation)
                operation_id = operation.get("operationId")
                if isinstance(operation_id, str):
                    operations.append(operation_id)
    expected = {
        "list_offboarding_checklists",
        "get_offboarding_checklist",
        "initialize_offboarding_checklist",
        "add_offboarding_task",
        "complete_offboarding_task",
        "reopen_offboarding_task",
        "delete_offboarding_task",
        "advance_offboarding_visa",
        "preview_final_settlement",
        "complete_offboarding",
        "get_offboarding_letter_source",
    }
    assert expected <= set(operations)
    assert all(operations.count(operation) == 1 for operation in expected)


@pytest.mark.parametrize(
    ("service_days", "expected"),
    [
        ("364", "0.00"),
        ("365", "7000.00"),
        ("1825", "35000.00"),
        ("2190", "45000.00"),
    ],
)
def test_gratuity_golden_boundaries(service_days: str, expected: str) -> None:
    amount, _ = calculate_gratuity(Decimal("10000.00"), Decimal(service_days))
    assert amount == Decimal(expected)


def test_gratuity_cap_and_half_up_rounding() -> None:
    capped, _ = calculate_gratuity(Decimal("10000.00"), Decimal("36500"))
    rounded, _ = calculate_gratuity(Decimal("10000.00"), Decimal("366"))
    assert capped == Decimal("240000.00")
    assert rounded == Decimal("7019.18")


def test_manual_adjustments_require_review_reason() -> None:
    with pytest.raises(ValidationError):
        SettlementInputs(
            expected_checklist_updated_at=NOW,
            notice_pay=Decimal("100.00"),
        )
    valid = SettlementInputs(
        expected_checklist_updated_at=NOW,
        notice_pay=Decimal("100.00"),
        adjustment_reason="Contract notice payment reviewed",
    )
    assert valid.notice_pay == Decimal("100.00")


def test_settlement_projection_uses_exact_money_strings() -> None:
    response = SettlementPreviewResponse(
        policy_version="1.0.0",
        policy_digest="sha256:" + "a" * 64,
        source_digest="sha256:" + "b" * 64,
        source_captured_at=NOW,
        service_days=Decimal("2190"),
        gratuity_days=Decimal("135.0000"),
        leave_days=Decimal("7.50"),
        final_salary=Decimal("12500.00"),
        leave_encashment=Decimal("2500.00"),
        gratuity=Decimal("45000.00"),
        notice_pay=Decimal("0.00"),
        other_earnings=Decimal("0.00"),
        advance_deduction=Decimal("333.34"),
        asset_deduction=Decimal("0.00"),
        notice_deduction=Decimal("0.00"),
        other_deductions=Decimal("0.00"),
        gross_amount=Decimal("60000.00"),
        total_deductions=Decimal("333.34"),
        net_amount=Decimal("59666.66"),
    ).model_dump(mode="json", by_alias=True)
    assert response["gratuity"] == "45000.00"
    assert response["netAmount"] == "59666.66"
    assert set(response).isdisjoint({"html", "pdf", "template", "objectKey"})
