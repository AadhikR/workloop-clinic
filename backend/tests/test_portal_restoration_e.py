from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.schemas.development import TrainingSelfCompleteRequest


def test_personal_result_rejects_trusted_fields() -> None:
    body = {
        "endDate": "2026-10-05",
        "durationHours": "8.00",
        "score": "92%",
        "passed": True,
        "expectedUpdatedAt": datetime(2026, 10, 5, tzinfo=UTC),
    }
    assert TrainingSelfCompleteRequest.model_validate(body).passed
    for field, value in {
        "employeeId": "e5000000-0000-4000-8000-000000000003",
        "isCme": True,
        "resultVerified": True,
        "cost": "10.00",
        "status": "completed",
    }.items():
        with pytest.raises(ValidationError):
            TrainingSelfCompleteRequest.model_validate({**body, field: value})


def test_training_commands_have_unique_operation_ids() -> None:
    paths = create_app().openapi()["paths"]
    for command, operation in {
        "start": "start_training_record",
        "cancel": "cancel_training_record",
        "self-complete": "complete_self_training_record",
    }.items():
        assert (
            paths[f"/api/v1/training-records/{{record_id}}/{command}"]["post"]["operationId"]
            == operation
        )


@pytest.mark.parametrize("hours", ["-1.00", "2", "2.0", "10000.00", "NaN", 2])
def test_personal_results_require_bounded_exact_decimal_hours(hours: object) -> None:
    with pytest.raises(ValidationError):
        TrainingSelfCompleteRequest.model_validate(
            {
                "endDate": "2026-10-05",
                "durationHours": hours,
                "score": "",
                "passed": True,
                "expectedUpdatedAt": datetime(2026, 10, 5, tzinfo=UTC),
            }
        )


def test_new_revision_keeps_predecessor_and_protects_result_authority() -> None:
    source = (
        Path(__file__).parents[1] / "alembic/versions/e2c4f6a8b0d3_add_training_personal_results.py"
    ).read_text()
    assert '"f1a3c5e7b9d2"' in source
    assert "SECURITY DEFINER" in source
    assert "REVOKE ALL" in source
    assert "result_verified=false,is_cme=false" in source
    assert "FOR UPDATE" in source
