from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.schemas.attendance_exceptions import RegularisationSubmitRequest
from app.services.attendance_exceptions import AttendanceExceptionService
from app.services.execution import ServiceExecutionError

COMPANY = UUID("10000000-0000-4000-8000-000000000001")
BRANCH = UUID("20000000-0000-4000-8000-000000000001")
USER = UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE = UUID("40000000-0000-4000-8000-000000000001")


class Repository:
    def __init__(self) -> None:
        self.called = False

    async def business_date(self) -> date:
        return date(2026, 8, 27)

    async def submit(self, *_: object):
        self.called = True
        return None


def principal(role: AppRole, employee: UUID | None = EMPLOYEE) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(USER, AccountStatus.ACTIVE, role, COMPANY, employee, BRANCH)


def request(day: date) -> RegularisationSubmitRequest:
    return RegularisationSubmitRequest(
        attendance_date=day,
        correct_clock_in=datetime(2026, 8, 26, 8, tzinfo=UTC),
        correct_clock_out=datetime(2026, 8, 26, 16, tzinfo=UTC),
        reason="Missed biometric punch",
    )


@pytest.mark.asyncio
async def test_employee_submission_derives_identity_and_rejects_future_date() -> None:
    repository = Repository()
    service = AttendanceExceptionService(repository)  # type: ignore[arg-type]
    await service.submit(principal(AppRole.EMPLOYEE), request(date(2026, 8, 26)))
    assert repository.called
    with pytest.raises(ServiceExecutionError, match="validation_failed"):
        await service.submit(principal(AppRole.EMPLOYEE), request(date(2026, 8, 28)))


def test_correction_schema_rejects_invalid_clock_order_and_span() -> None:
    with pytest.raises(ValueError):
        RegularisationSubmitRequest(
            attendance_date=date(2026, 8, 26),
            correct_clock_in=datetime(2026, 8, 26, 8, tzinfo=UTC),
            correct_clock_out=datetime(2026, 8, 26, 8, tzinfo=UTC),
            reason="Missed biometric punch",
        )
    with pytest.raises(ValueError):
        RegularisationSubmitRequest(
            attendance_date=date(2026, 8, 26),
            correct_clock_in=datetime(2026, 8, 26, 8, tzinfo=UTC),
            correct_clock_out=datetime(2026, 8, 27, 9, tzinfo=UTC),
            reason="Missed biometric punch",
        )
