from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.schemas.appraisals import (
    AppraisalCycleCreateRequest,
    AppraisalSectionRatingRequest,
)
from app.schemas.incidents import IncidentCreateRequest
from app.services.appraisals import calculate_weighted_rating

ID = UUID("12345678-1234-4234-8234-123456789abc")
NOW = datetime(2026, 9, 23, tzinfo=UTC)


def test_phase11e_routes_are_registered_once() -> None:
    operations: list[str] = []
    for path_item in create_app().openapi()["paths"].values():
        for raw_operation in path_item.values():
            if isinstance(raw_operation, dict):
                operation = cast(dict[str, object], raw_operation)
                operation_id = operation.get("operationId")
                if isinstance(operation_id, str):
                    operations.append(operation_id)
    expected = {
        "list_appraisal_cycles",
        "create_appraisal_cycle",
        "update_appraisal_cycle",
        "activate_appraisal_cycle",
        "generate_appraisals",
        "close_appraisal_cycle",
        "delete_appraisal_cycle",
        "list_self_appraisals",
        "list_direct_report_appraisals",
        "rate_appraisal_section",
        "review_appraisal",
        "calibrate_appraisal",
        "list_clinical_incidents",
        "create_clinical_incident",
        "update_clinical_incident",
        "investigate_clinical_incident",
        "record_clinical_incident_corrective_action",
        "close_clinical_incident",
    }
    assert expected <= set(operations)
    assert all(operations.count(operation) == 1 for operation in expected)


def test_appraisal_weighted_rating_matches_golden_case() -> None:
    rating = calculate_weighted_rating(
        [
            (Decimal("4.0"), Decimal("2.00")),
            (Decimal("4.0"), Decimal("2.00")),
            (Decimal("3.0"), Decimal("1.50")),
            (Decimal("3.0"), Decimal("1.00")),
            (Decimal("5.0"), Decimal("1.00")),
        ]
    )
    assert rating == Decimal("3.8")


def test_appraisal_dates_and_ratings_are_bounded() -> None:
    with pytest.raises(ValidationError):
        AppraisalCycleCreateRequest.model_validate(
            {"name": "Synthetic cycle", "reviewFrom": "2026-12-31", "reviewTo": "2026-01-01"}
        )
    with pytest.raises(ValidationError):
        AppraisalSectionRatingRequest.model_validate(
            {"expectedUpdatedAt": NOW.isoformat(), "rating": "5.1", "comments": ""}
        )


def test_incident_contract_rejects_empty_or_oversized_clinical_text() -> None:
    base = {
        "incidentDate": date(2026, 9, 23).isoformat(),
        "incidentType": "medication_error",
        "severity": "critical",
        "description": "Synthetic incident",
        "reportedById": str(ID),
    }
    assert IncidentCreateRequest.model_validate(base).description == "Synthetic incident"
    with pytest.raises(ValidationError):
        IncidentCreateRequest.model_validate({**base, "description": "   "})
    with pytest.raises(ValidationError):
        IncidentCreateRequest.model_validate({**base, "notes": "x" * 10001})
