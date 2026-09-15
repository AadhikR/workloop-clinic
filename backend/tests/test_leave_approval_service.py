from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.leave_approval import (
    LeaveApprovalDelegateCreate,
    LeaveDecisionRequest,
)
from app.services.leave_approval import same_version

EMPLOYEE = uuid.UUID("8f000000-0000-4000-8000-000000000001")
DELEGATE = uuid.UUID("8f000000-0000-4000-8000-000000000002")


def test_decision_requires_server_snapshot_and_rejection_reason() -> None:
    decision = LeaveDecisionRequest.model_validate(
        {
            "decision": "approve",
            "reason": "  Coverage confirmed  ",
            "expectedUpdatedAt": "2026-09-15T08:00:00.000Z",
        }
    )
    assert decision.reason == "Coverage confirmed"
    with pytest.raises(ValidationError):
        LeaveDecisionRequest.model_validate(
            {
                "decision": "reject",
                "reason": "  ",
                "expectedUpdatedAt": "2026-09-15T08:00:00.000Z",
            }
        )
    with pytest.raises(ValidationError):
        LeaveDecisionRequest.model_validate(
            {"decision": "approve", "reason": "", "status": "Approved"}
        )


def test_delegation_schema_rejects_self_and_reversed_dates() -> None:
    values = {
        "approverEmployeeId": str(EMPLOYEE),
        "delegateEmployeeId": str(DELEGATE),
        "fromDate": "2026-09-16",
        "toDate": "2026-09-18",
    }
    parsed = LeaveApprovalDelegateCreate.model_validate(values)
    assert parsed.delegate_employee_id == DELEGATE
    with pytest.raises(ValidationError):
        LeaveApprovalDelegateCreate.model_validate({**values, "delegateEmployeeId": str(EMPLOYEE)})
    with pytest.raises(ValidationError):
        LeaveApprovalDelegateCreate.model_validate({**values, "toDate": "2026-09-15"})


def test_optimistic_versions_match_the_millisecond_http_projection() -> None:
    stored = datetime(2026, 9, 15, 12, 30, 45, 123789, tzinfo=UTC)
    projected = datetime(2026, 9, 15, 12, 30, 45, 123000, tzinfo=UTC)
    stale = datetime(2026, 9, 15, 12, 30, 45, 122000, tzinfo=UTC)

    assert same_version(stored, projected)
    assert not same_version(stored, stale)
