from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.schemas.attendance_periods import AttendancePeriodCloseRequest, AttendancePeriodResponse
from app.services.attendance_periods import AttendancePeriodService
from app.services.execution import ServiceExecutionError

COMPANY = UUID("10000000-0000-4000-8000-000000000001")
BRANCH = UUID("20000000-0000-4000-8000-000000000001")
USER = UUID("30000000-0000-4000-8000-000000000001")
PERIOD_ID = UUID("40000000-0000-4000-8000-000000000001")


def principal(role: AppRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        USER,
        AccountStatus.ACTIVE,
        role,
        COMPANY,
        None if role is AppRole.ADMIN else UUID(int=5),
        None if role is AppRole.ADMIN else BRANCH,
    )


def period() -> AttendancePeriodResponse:
    return AttendancePeriodResponse(
        id=PERIOD_ID,
        period="2026-08",
        status="closed",
        payroll_ready=True,
        version=1,
        blocker_count=0,
        blockers=[],
        source_version="sha256:" + "a" * 64,
        closed_at=datetime(2026, 9, 21, 20, tzinfo=UTC),
        closed_by_actor_name="Administrator",
        amendment_reason=None,
    )


class Repository:
    def __init__(self) -> None:
        self.arguments: tuple[object, ...] | None = None

    async def close(self, *arguments: object) -> AttendancePeriodResponse:
        self.arguments = arguments
        return period()


@pytest.mark.asyncio
async def test_close_derives_scope_actor_and_version_from_trusted_context() -> None:
    repository = Repository()
    service = AttendancePeriodService(repository, object())  # type: ignore[arg-type]
    response = await service.close(
        principal(AppRole.ADMIN),
        BRANCH,
        "2026-08",
        AttendancePeriodCloseRequest(expected_version=0),
    )
    assert response.source_version == "sha256:" + "a" * 64
    assert repository.arguments == (COMPANY, BRANCH, USER, "2026-08", 0, None)


@pytest.mark.asyncio
async def test_non_admin_period_close_is_rejected_before_repository_access() -> None:
    repository = Repository()
    service = AttendancePeriodService(repository, object())  # type: ignore[arg-type]
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await service.close(
            principal(AppRole.MANAGER),
            BRANCH,
            "2026-08",
            AttendancePeriodCloseRequest(expected_version=0),
        )
    assert repository.arguments is None


def test_close_request_requires_a_reason_only_for_successor_versions() -> None:
    with pytest.raises(ValidationError):
        AttendancePeriodCloseRequest(expected_version=0, amendment_reason="Late event")
    with pytest.raises(ValidationError):
        AttendancePeriodCloseRequest(expected_version=1)
    amended = AttendancePeriodCloseRequest(
        expected_version=1, amendment_reason="  Approved late evidence  "
    )
    assert amended.amendment_reason == "Approved late evidence"
