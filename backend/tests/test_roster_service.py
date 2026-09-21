from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.schemas.roster import (
    RosterAssignmentResponse,
    RosterComplianceOverrideRequest,
    RosterDraftCreateRequest,
    RosterDraftReplaceRequest,
)
from app.services.execution import ServiceExecutionError
from app.services.roster import RosterService

COMPANY = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("20000000-0000-4000-8000-000000000001")
USER = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE = uuid.UUID("40000000-0000-4000-8000-000000000001")
SHIFT = uuid.UUID("50000000-0000-4000-8000-000000000001")
ASSIGNMENT = uuid.UUID("60000000-0000-4000-8000-000000000001")


def principal(role: AppRole = AppRole.ADMIN) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        USER,
        AccountStatus.ACTIVE,
        role,
        COMPANY,
        None if role is AppRole.ADMIN else EMPLOYEE,
        None if role is AppRole.ADMIN else BRANCH,
    )


def assignment(version: int = 1) -> RosterAssignmentResponse:
    return RosterAssignmentResponse(
        id=ASSIGNMENT,
        employee_id=EMPLOYEE,
        employee_name="Synthetic Employee",
        department="Clinical",
        shift_id=SHIFT,
        shift_name="Morning",
        shift_code="M",
        shift_category="morning",
        date=date(2026, 9, 23),
        published=False,
        planned_hours=Decimal("8.00"),
        notes="",
        version=version,
        leave_conflict=False,
        updated_at=datetime(2026, 9, 22, tzinfo=UTC),
    )


class Repository:
    def __init__(self) -> None:
        self.arguments: tuple[object, ...] | None = None

    async def create(self, *arguments: object) -> RosterAssignmentResponse:
        self.arguments = arguments
        return assignment()

    async def replace(self, *arguments: object) -> RosterAssignmentResponse:
        self.arguments = arguments
        return assignment(2)


@pytest.mark.asyncio
async def test_draft_mutations_derive_scope_and_enforce_month() -> None:
    repository = Repository()
    service = RosterService(repository, object())  # type: ignore[arg-type]
    request = RosterDraftCreateRequest(
        employee_id=EMPLOYEE,
        shift_id=SHIFT,
        date=date(2026, 9, 23),
        planned_hours=Decimal("8.00"),
        notes="  coverage  ",
    )
    created = await service.create(principal(), BRANCH, "2026-09", request)
    assert created.version == 1
    assert request.notes == "coverage"
    assert repository.arguments == (COMPANY, BRANCH, request)
    with pytest.raises(ServiceExecutionError, match="validation_failed"):
        await service.create(principal(), BRANCH, "2026-08", request)


@pytest.mark.asyncio
async def test_non_admin_cannot_replace_roster_draft() -> None:
    repository = Repository()
    service = RosterService(repository, object())  # type: ignore[arg-type]
    request = RosterDraftReplaceRequest(
        employee_id=EMPLOYEE,
        shift_id=SHIFT,
        date=date(2026, 9, 23),
        planned_hours=Decimal("8.00"),
        expected_version=1,
    )
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await service.replace(principal(AppRole.MANAGER), BRANCH, "2026-09", ASSIGNMENT, request)
    assert repository.arguments is None


def test_roster_requests_reject_unsafe_hours_and_short_override_reasons() -> None:
    with pytest.raises(ValidationError):
        RosterDraftCreateRequest(
            employee_id=EMPLOYEE,
            shift_id=SHIFT,
            date=date(2026, 9, 23),
            planned_hours=Decimal("NaN"),
        )
    with pytest.raises(ValidationError):
        RosterComplianceOverrideRequest(
            violation_digest="sha256:" + "a" * 64,
            reason="short",
        )
