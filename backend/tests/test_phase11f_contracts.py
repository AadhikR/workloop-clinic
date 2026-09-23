from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.schemas.letter_requests import (
    LetterRequestCreateRequest,
    LetterRequestPrintSource,
    LetterRequestResponse,
)

ID = UUID("12345678-1234-4234-8234-123456789abc")
NOW = datetime(2026, 9, 23, tzinfo=UTC)


def test_phase11f_routes_are_registered_once() -> None:
    operations: list[str] = []
    for path_item in create_app().openapi()["paths"].values():
        for raw_operation in path_item.values():
            if isinstance(raw_operation, dict):
                operation = cast(dict[str, object], raw_operation)
                operation_id = operation.get("operationId")
                if isinstance(operation_id, str):
                    operations.append(operation_id)
    expected = {
        "list_self_letter_requests",
        "submit_letter_request",
        "list_letter_requests",
        "get_letter_request",
        "complete_letter_request",
        "reject_letter_request",
        "get_letter_request_print_source",
    }
    assert expected <= set(operations)
    assert all(operations.count(operation) == 1 for operation in expected)


def test_submission_contract_enforces_named_letter_and_custom_boundaries() -> None:
    request = LetterRequestCreateRequest.model_validate(
        {
            "requestKind": "letter",
            "letterType": "salary_certificate_bank",
            "purpose": "Emirates NBD",
        }
    )
    assert request.stored_letter_type() == "salary_certificate_bank"
    assert request.stored_purpose() == "Emirates NBD"
    custom = LetterRequestCreateRequest.model_validate(
        {"requestKind": "custom", "subject": "ABC", "details": "12345"}
    )
    assert custom.stored_letter_type() == "ABC"
    assert custom.stored_purpose() == "12345"
    for invalid in (
        {"requestKind": "letter", "letterType": "unknown", "purpose": "Emirates NBD"},
        {"requestKind": "letter", "letterType": "salary_certificate_bank", "purpose": "bank"},
        {"requestKind": "custom", "subject": "AB", "details": "12345"},
        {"requestKind": "custom", "subject": "ABC", "details": "1234"},
    ):
        with pytest.raises(ValidationError):
            LetterRequestCreateRequest.model_validate(invalid)


def test_staff_projection_omits_salary_and_print_source_is_allowlisted() -> None:
    response = LetterRequestResponse(
        id=ID,
        employee_id=ID,
        employee_name="Synthetic clinician",
        job_title="Clinician",
        department="Clinical",
        employment_start_date=date(2024, 1, 1),
        branch_name="Synthetic branch",
        request_kind="letter",
        letter_type="salary_certificate_bank",
        purpose="Emirates NBD",
        status="completed",
        notes="",
        rejection_reason="",
        requested_at=NOW,
        completed_at=NOW,
        actioned_at=NOW,
        updated_at=NOW,
    ).model_dump(mode="json", by_alias=True)
    assert "basicSalary" not in response and "allowance" not in response
    source = LetterRequestPrintSource(
        request_id=ID,
        request_kind="letter",
        letter_type="salary_certificate_bank",
        purpose="Emirates NBD",
        employee_name="Synthetic clinician",
        job_title="Clinician",
        department="Clinical",
        employment_start_date=date(2024, 1, 1),
        branch_name="Synthetic branch",
        basic_salary=Decimal("10000.00"),
        allowance=Decimal("2500.00"),
        requested_at=NOW,
        completed_at=NOW,
    ).model_dump(mode="json", by_alias=True)
    assert source["basicSalary"] == "10000.00"
    assert set(source).isdisjoint({"html", "template", "pdf", "objectKey"})
