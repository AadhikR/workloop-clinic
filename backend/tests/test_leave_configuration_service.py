import uuid
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.repositories.leave_configuration import LeaveConfigurationRepository
from app.schemas.leave_configuration import (
    LeaveSettingsRequest,
    LeaveTypeCreateRequest,
    LeaveTypeUpdateRequest,
    PublicHolidayCreateRequest,
    PublicHolidaySnapshot,
    PublicHolidayUpdateRequest,
    SeedHolidaysRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError
from app.services.leave_configuration import (
    DEFAULT_LEAVE_TYPES,
    HolidayListQuery,
    LeaveConfigurationService,
    LeaveTypeListQuery,
)

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
OTHER_BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c3")
TYPE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698d1")
SECOND_TYPE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698d2")
HOLIDAY_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698e1")
NOW = datetime(2026, 9, 13, 8, tzinfo=UTC)


def principal(
    role: AppRole = AppRole.ADMIN, branch_id: uuid.UUID | None = None
) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=None,
        branch_id=branch_id,
    )


def type_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": TYPE_ID,
        "branch_id": BRANCH_ID,
        "code": "ANNUAL",
        "name": "Annual Leave",
        "color": "#1a56db",
        "is_paid": True,
        "is_unlimited": False,
        "requires_approval": True,
        "requires_attachment": False,
        "requires_reason": False,
        "min_notice_days": 14,
        "annual_entitlement_days": "30.00",
        "accrual_type": "monthly",
        "day_count_type": "calendar",
        "auto_approve": False,
        "carry_forward_allowed": True,
        "carry_forward_max_days": 15,
        "gender_restriction": None,
        "min_service_months": 0,
        "once_per_career": False,
        "not_deducted_from_annual": False,
        "affects_payroll": False,
        "law_reference": "Article 29",
        "is_active": True,
        "sort_order": 0,
        "probation_eligible": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    row.update(changes)
    return row


def holiday_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": HOLIDAY_ID,
        "branch_id": BRANCH_ID,
        "date": date(2027, 1, 1),
        "name": "New Year",
        "type": "federal",
        "year": 2027,
        "created_at": NOW,
    }
    row.update(changes)
    return row


class FakeRepository:
    def __init__(self) -> None:
        self.types = [type_row(), type_row(id=SECOND_TYPE_ID, code="SICK", name="Sick Leave")]
        self.holidays = [holiday_row()]
        self.active_only: bool | None = None
        self.type_after: tuple[int, str, uuid.UUID] | None = None
        self.seeded_types: list[dict[str, Any]] = []
        self.seeded_holidays: list[dict[str, Any]] = []
        self.type_error: ValueError | None = None
        self.holiday_error: ValueError | None = None

    async def list_types(self, *_values: object, **options: object) -> list[dict[str, object]]:
        self.active_only = cast(bool, options["active_only"])
        self.type_after = cast(tuple[int, str, uuid.UUID] | None, options["after"])
        return self.types

    async def fetch_type_position(
        self, *_values: object, **_options: object
    ) -> tuple[int, str, uuid.UUID]:
        return 0, "Annual Leave", TYPE_ID

    async def update_type(self, **values: object) -> dict[str, object]:
        if self.type_error is not None:
            raise self.type_error
        return type_row(**cast(dict[str, object], values["values"]))

    async def seed_types(self, **values: object) -> list[dict[str, object]]:
        self.seeded_types = list(cast(list[dict[str, Any]], values["defaults"]))
        return self.types

    async def list_holidays(self, *_values: object, **_options: object) -> list[dict[str, object]]:
        return self.holidays

    async def fetch_holiday_position(self, *_values: object) -> tuple[date, uuid.UUID]:
        return date(2027, 1, 1), HOLIDAY_ID

    async def update_holiday(self, **values: object) -> dict[str, object]:
        if self.holiday_error is not None:
            raise self.holiday_error
        return holiday_row(**cast(dict[str, object], values["values"]))

    async def delete_holiday(self, **_values: object) -> None:
        if self.holiday_error is not None:
            raise self.holiday_error

    async def seed_holidays(self, **values: object) -> list[dict[str, object]]:
        self.seeded_holidays = list(cast(list[dict[str, Any]], values["holidays"]))
        return self.holidays


def service() -> tuple[LeaveConfigurationService, FakeRepository]:
    repository = FakeRepository()
    active = LeaveConfigurationService(
        cast(AsyncConnection, object()),
        EmployeeCursorCodec(b"0" * 32),
        cast(LeaveConfigurationRepository, repository),
    )
    return active, repository


def test_request_schemas_require_versions_exact_decimals_and_nonblank_holidays() -> None:
    with pytest.raises(ValidationError):
        LeaveTypeCreateRequest.model_validate(
            {"code": "ANNUAL", "name": "Annual", "annualEntitlementDays": 30}
        )
    with pytest.raises(ValidationError):
        LeaveTypeUpdateRequest.model_validate({"name": "Annual"})
    with pytest.raises(ValidationError):
        LeaveTypeUpdateRequest.model_validate({"expectedUpdatedAt": "2026-09-13T08:00:00Z"})
    with pytest.raises(ValidationError):
        PublicHolidayCreateRequest.model_validate(
            {"date": "2027-01-01", "name": "   ", "type": "federal"}
        )
    with pytest.raises(ValidationError):
        PublicHolidayUpdateRequest.model_validate(
            {"expected": {"date": "2027-01-01", "name": "New Year", "type": "federal"}}
        )


@pytest.mark.asyncio
async def test_staff_reads_only_active_types_in_its_branch() -> None:
    active, repository = service()
    staff = principal(AppRole.EMPLOYEE, BRANCH_ID)
    rows, next_cursor = await active.list_types(
        staff, BRANCH_ID, LeaveTypeListQuery(limit=50, cursor=None), active_only=True
    )
    assert len(rows) == 2
    assert next_cursor is None
    assert repository.active_only is True

    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await active.list_types(
            staff, OTHER_BRANCH_ID, LeaveTypeListQuery(limit=50, cursor=None), active_only=True
        )
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await active.seed_types(staff, BRANCH_ID)
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await active.list_holidays(
            staff, BRANCH_ID, HolidayListQuery(limit=50, year=2027, cursor=None)
        )
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await active.list_holidays(
            staff, BRANCH_ID, HolidayListQuery(limit=50, year=2027, cursor=None)
        )


@pytest.mark.asyncio
async def test_leave_type_cursor_is_bound_and_unsafe_deactivation_is_safe() -> None:
    active, repository = service()
    admin = principal()
    first, cursor = await active.list_types(
        admin, BRANCH_ID, LeaveTypeListQuery(limit=1, cursor=None), active_only=False
    )
    assert [item.id for item in first] == [TYPE_ID]
    assert cursor is not None

    repository.types = [type_row(id=SECOND_TYPE_ID, code="SICK", name="Sick Leave")]
    second, _ = await active.list_types(
        admin, BRANCH_ID, LeaveTypeListQuery(limit=1, cursor=cursor), active_only=False
    )
    assert [item.id for item in second] == [SECOND_TYPE_ID]
    assert repository.type_after == (0, "Annual Leave", TYPE_ID)

    with pytest.raises(ServiceExecutionError, match="invalid_cursor"):
        await active.list_types(
            admin, OTHER_BRANCH_ID, LeaveTypeListQuery(limit=1, cursor=cursor), active_only=False
        )

    repository.type_error = ValueError("unsafe deactivation")
    request = LeaveTypeUpdateRequest.model_validate(
        {"expectedUpdatedAt": "2026-09-13T08:00:00.000Z", "isActive": False}
    )
    with pytest.raises(ServiceExecutionError, match="branch_conflict"):
        await active.update_type(admin, BRANCH_ID, TYPE_ID, request)


@pytest.mark.asyncio
async def test_seeds_are_complete_and_named_holiday_years_are_consistent() -> None:
    active, repository = service()
    seeded = await active.seed_types(principal(), BRANCH_ID)
    assert len(seeded) == 2
    assert [item["code"] for item in repository.seeded_types] == [
        "ANNUAL",
        "SICK",
        "MATERNITY",
        "PATERNITY",
        "BEREAVEMENT",
        "STUDY",
        "HAJJ",
        "UNPAID",
    ]
    assert tuple(repository.seeded_types) == DEFAULT_LEAVE_TYPES

    request = SeedHolidaysRequest.model_validate(
        {
            "year": 2027,
            "holidays": [{"date": "2027-01-01", "name": "New Year", "type": "federal"}],
        }
    )
    await active.seed_holidays(principal(), BRANCH_ID, request)
    assert repository.seeded_holidays[0]["date"] == date(2027, 1, 1)

    wrong_year = SeedHolidaysRequest.model_validate(
        {
            "year": 2028,
            "holidays": [{"date": "2027-01-01", "name": "New Year", "type": "federal"}],
        }
    )
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await active.seed_holidays(principal(), BRANCH_ID, wrong_year)


@pytest.mark.asyncio
async def test_holiday_snapshot_conflicts_and_immutable_rows_have_stable_errors() -> None:
    active, repository = service()
    admin = principal()
    snapshot = PublicHolidaySnapshot.model_validate(
        {"date": "2027-01-01", "name": "New Year", "type": "federal"}
    )
    request = PublicHolidayUpdateRequest.model_validate(
        {"expected": snapshot.model_dump(by_alias=True), "name": "New Year Day"}
    )

    repository.holiday_error = ValueError("state conflict")
    with pytest.raises(ServiceExecutionError, match="state_conflict"):
        await active.update_holiday(admin, BRANCH_ID, HOLIDAY_ID, request)

    repository.holiday_error = ValueError("holiday is immutable")
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await active.delete_holiday(admin, BRANCH_ID, HOLIDAY_ID, snapshot)


def test_settings_version_is_optional_only_for_initial_creation() -> None:
    created = LeaveSettingsRequest.model_validate(
        {
            "leaveYearType": "calendar",
            "weekendDefinition": "fri-sat",
            "carryForwardEnabled": True,
            "carryForwardMaxDays": 15,
            "approvalChain": "1-level",
            "ramadanActive": False,
            "ramadanStart": None,
            "ramadanEnd": None,
        }
    )
    assert created.expected_updated_at is None
    updated = LeaveSettingsRequest.model_validate(
        {**created.model_dump(by_alias=True), "expectedUpdatedAt": "2026-09-13T08:00:00.000Z"}
    )
    assert updated.expected_updated_at == NOW
