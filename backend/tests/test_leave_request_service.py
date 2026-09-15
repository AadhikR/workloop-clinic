from __future__ import annotations

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.repositories.leave_request import employee_lock_key
from app.schemas.leave_request import AdminLeaveSubmissionRequest, LeaveSubmissionRequest
from app.services.leave_request import type_fields_valid

TYPE_ID = uuid.UUID("8e000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = uuid.UUID("8e000000-0000-4000-8000-000000000002")


def values(**changes: object) -> dict[str, object]:
    request: dict[str, object] = {
        "leaveTypeId": str(TYPE_ID),
        "startDate": "2026-09-28",
        "endDate": "2026-09-28",
        "isHalfDay": False,
        "halfDayPeriod": None,
        "reason": "Appointment",
        "attachmentId": None,
        "relationship": None,
        "deceasedName": None,
        "dateOfDeath": None,
        "childBirthDate": None,
        "childName": None,
        "expectedDueDate": None,
        "institutionName": None,
        "examDates": None,
        "substituteEmployeeId": None,
    }
    request.update(changes)
    return request


def parsed(**changes: object) -> LeaveSubmissionRequest:
    return LeaveSubmissionRequest.model_validate(values(**changes))


def test_submission_schema_is_strict_and_validates_half_days() -> None:
    assert parsed(reason="  Appointment  ").reason == "Appointment"
    with pytest.raises(ValidationError):
        LeaveSubmissionRequest.model_validate({**values(), "daysRequested": "1.00"})
    with pytest.raises(ValidationError):
        parsed(isHalfDay=True, halfDayPeriod="AM", endDate="2026-09-29")
    with pytest.raises(ValidationError):
        parsed(isHalfDay=False, halfDayPeriod="PM")
    with pytest.raises(ValidationError):
        LeaveSubmissionRequest.model_validate({**values(), "employeeId": str(EMPLOYEE_ID)})
    assert (
        AdminLeaveSubmissionRequest.model_validate(
            {**values(), "employeeId": str(EMPLOYEE_ID)}
        ).employee_id
        == EMPLOYEE_ID
    )


@pytest.mark.parametrize(
    ("code", "changes", "valid"),
    [
        ("ANNUAL", {}, True),
        ("ANNUAL", {"childName": "Wrong field"}, False),
        ("BEREAVEMENT", {"relationship": "Parent"}, True),
        ("BEREAVEMENT", {}, False),
        ("PATERNITY", {"childBirthDate": "2026-09-15"}, True),
        ("PATERNITY", {}, False),
        ("MATERNITY", {"expectedDueDate": "2026-10-01"}, True),
        ("MATERNITY", {"expectedDueDate": "2026-10-01", "childName": "Wrong"}, False),
        ("STUDY", {"institutionName": "Clinic", "examDates": "2026-09-28"}, True),
        ("STUDY", {"institutionName": "Clinic"}, False),
    ],
)
def test_type_specific_fields_are_exact(code: str, changes: dict[str, object], valid: bool) -> None:
    assert type_fields_valid(code, parsed(**changes)) is valid


def test_employee_lock_key_is_stable_scoped_and_signed() -> None:
    company = uuid.UUID("8e000000-0000-4000-8000-000000000003")
    branch = uuid.UUID("8e000000-0000-4000-8000-000000000004")
    first = employee_lock_key(company, branch, EMPLOYEE_ID)
    assert first == employee_lock_key(company, branch, EMPLOYEE_ID)
    assert first != employee_lock_key(company, branch, uuid.uuid4())
    assert -(2**63) <= first < 2**63
    assert parsed(childBirthDate="2026-09-15").child_birth_date == date(2026, 9, 15)
