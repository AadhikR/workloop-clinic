from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.repositories.leave_balance import LeaveBalanceRepository, LockedBalanceState
from app.schemas.leave_balance import (
    LeaveBalanceResponse,
    LeaveBalanceYearRequest,
    LeaveRequestResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError
from app.services.leave_balance import (
    BalanceInputs,
    accrued_days,
    calendar_days,
    carry_forward,
    recompute_balance,
    sick_tiers,
    working_days,
)
from app.services.leave_balance_service import BalanceListQuery, LeaveBalanceService

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
EMPLOYEE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698d1")
REPORT_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698d2")
TYPE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698e1")
BALANCE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698f1")


def row(**values: object) -> RowMapping:
    return cast(RowMapping, values)


def principal(role: AppRole, employee_id: uuid.UUID | None = EMPLOYEE_ID) -> AuthorizationPrincipal:
    staff = role is not AppRole.ADMIN
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=employee_id if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


def test_day_counting_covers_weekends_holidays_and_half_days() -> None:
    assert calendar_days(date(2026, 9, 11), date(2026, 9, 13)) == Decimal("3.00")
    assert working_days(
        date(2026, 9, 11),
        date(2026, 9, 14),
        weekend_definition="fri-sat",
        holidays=[date(2026, 9, 13)],
    ) == Decimal("1.00")
    assert working_days(
        date(2026, 9, 11),
        date(2026, 9, 14),
        weekend_definition="sat-sun",
    ) == Decimal("2.00")
    assert calendar_days(date(2026, 9, 11), date(2026, 9, 11), half_day=True) == Decimal("0.50")
    with pytest.raises(ValueError, match="half-day"):
        working_days(
            date(2026, 9, 11),
            date(2026, 9, 12),
            weekend_definition="fri-sat",
            half_day=True,
        )


def test_accrual_carry_forward_sick_tiers_and_future_years_are_decimal_safe() -> None:
    assert accrued_days(
        Decimal("30.00"),
        accrual_type="monthly",
        leave_year=2026,
        business_date=date(2026, 9, 30),
        employment_start_date=date(2020, 1, 1),
    ) == Decimal("22.50")
    assert accrued_days(
        Decimal("30.00"),
        accrual_type="monthly",
        leave_year=2027,
        business_date=date(2026, 9, 30),
        employment_start_date=date(2020, 1, 1),
    ) == Decimal("0.00")
    assert accrued_days(
        Decimal("30.00"),
        accrual_type="monthly",
        leave_year=2026,
        business_date=date(2026, 7, 1),
        employment_start_date=date(2026, 1, 1),
    ) == Decimal("12.00")
    assert carry_forward(
        Decimal("20.235"),
        enabled=True,
        type_allowed=True,
        settings_cap=15,
        type_cap=10,
    ) == Decimal("10.00")
    assert sick_tiers(Decimal("50.50")) == (
        Decimal("15.00"),
        Decimal("30.00"),
        Decimal("5.50"),
    )
    assert sick_tiers(Decimal("2.50"), probation=True) == (
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("2.50"),
    )


def test_balance_calculation_reserves_pending_and_preserves_once_per_career_state() -> None:
    balance = recompute_balance(
        BalanceInputs(
            entitlement=Decimal("30.00"),
            accrual_type="fixed",
            leave_year=2026,
            business_date=date(2026, 9, 13),
            employment_start_date=date(2020, 1, 1),
            previous_remaining=Decimal("12.00"),
            carry_forward_allowed=True,
            settings_carry_forward_cap=15,
            type_carry_forward_cap=10,
            used_days=Decimal("5.50"),
            pending_days=Decimal("2.25"),
        )
    )
    assert balance["carried_forward"] == Decimal("10.00")
    assert balance["remaining_days"] == Decimal("32.25")

    exhausted = recompute_balance(
        BalanceInputs(
            entitlement=Decimal("30.00"),
            accrual_type="once_per_career",
            leave_year=2027,
            business_date=date(2027, 1, 1),
            employment_start_date=date(2020, 1, 1),
            once_per_career=True,
            hajj_taken=True,
        )
    )
    assert exhausted["entitled_days"] == exhausted["remaining_days"] == Decimal("0.00")


def test_exact_balance_projection_serializes_two_place_strings() -> None:
    response = LeaveBalanceResponse(
        employee_id=EMPLOYEE_ID,
        leave_type_id=TYPE_ID,
        leave_year=2026,
        entitled_days=Decimal("30"),
        accrued_days=Decimal("22.5"),
        used_days=Decimal("3"),
        pending_days=Decimal("0.5"),
        carried_forward=Decimal("2"),
        remaining_days=Decimal("21"),
        sick_full_pay_used=Decimal("0"),
        sick_half_pay_used=Decimal("0"),
        sick_unpaid_used=Decimal("0"),
    )
    assert response.model_dump(mode="json", by_alias=True) == {
        "employeeId": str(EMPLOYEE_ID),
        "leaveTypeId": str(TYPE_ID),
        "leaveYear": 2026,
        "entitledDays": "30.00",
        "accruedDays": "22.50",
        "usedDays": "3.00",
        "pendingDays": "0.50",
        "carriedForward": "2.00",
        "remainingDays": "21.00",
        "sickFullPayUsed": "0.00",
        "sickHalfPayUsed": "0.00",
        "sickUnpaidUsed": "0.00",
    }
    with pytest.raises(ValidationError):
        LeaveBalanceYearRequest.model_validate({"leaveYear": 2026, "employeeId": str(EMPLOYEE_ID)})


def test_exact_request_projection_serializes_days_and_utc_instants() -> None:
    instant = datetime(2026, 9, 13, 8, tzinfo=UTC)
    response = LeaveRequestResponse(
        id=uuid.uuid4(),
        branch_id=BRANCH_ID,
        employee_id=EMPLOYEE_ID,
        leave_type_id=TYPE_ID,
        start_date=date(2026, 9, 14),
        end_date=date(2026, 9, 14),
        is_half_day=True,
        half_day_period="AM",
        days_requested=Decimal("0.5"),
        status="Pending",
        reason="Appointment",
        rejection_reason="",
        manager_rejection_reason="",
        relationship="",
        deceased_name="",
        date_of_death=None,
        child_birth_date=None,
        child_name="",
        expected_due_date=None,
        institution_name="",
        exam_dates="",
        substitute_employee_id=None,
        approval_level_required=1,
        approval_comment="",
        warnings=[],
        submitted_at=instant,
        created_at=instant,
        updated_at=instant,
    )
    serialized = response.model_dump(mode="json", by_alias=True)
    assert serialized["daysRequested"] == "0.50"
    assert serialized["attachment"] is None
    assert serialized["submittedAt"] == "2026-09-13T08:00:00.000Z"
    assert serialized["createdAt"] == "2026-09-13T08:00:00.000Z"
    assert serialized["updatedAt"] == "2026-09-13T08:00:00.000Z"


def state_for_rules(*, employment_status: str = "Active") -> LockedBalanceState:
    return LockedBalanceState(
        settings=row(
            weekend_definition="fri-sat",
            carry_forward_enabled=True,
            carry_forward_max_days=15,
        ),
        employees=[
            row(
                id=EMPLOYEE_ID,
                employment_start_date=date(2020, 1, 1),
                employment_status=employment_status,
                gender="Male",
            )
        ],
        leave_types=[
            row(
                id=TYPE_ID,
                code="SICK",
                annual_entitlement_days=Decimal("90.00"),
                accrual_type="fixed",
                day_count_type="calendar",
                carry_forward_allowed=False,
                carry_forward_max_days=0,
                gender_restriction=None,
                min_service_months=0,
                once_per_career=False,
                is_unlimited=False,
                probation_eligible=True,
            )
        ],
        requests=[
            row(
                id=uuid.uuid4(),
                employee_id=EMPLOYEE_ID,
                leave_type_id=TYPE_ID,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 2, 19),
                is_half_day=False,
                status="Approved",
            ),
            row(
                id=uuid.uuid4(),
                employee_id=EMPLOYEE_ID,
                leave_type_id=TYPE_ID,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 1),
                is_half_day=True,
                status="ManagerApproved",
            ),
        ],
        balances=[],
        holidays=[],
    )


def test_recalculation_derives_request_days_reservations_and_sick_tiers() -> None:
    rows = LeaveBalanceService.balance_rows(state_for_rules(), 2026, date(2026, 9, 13))
    assert rows == [
        {
            "employee_id": EMPLOYEE_ID,
            "leave_type_id": TYPE_ID,
            "entitled_days": Decimal("90.00"),
            "accrued_days": Decimal("90.00"),
            "used_days": Decimal("50.00"),
            "pending_days": Decimal("0.50"),
            "carried_forward": Decimal("0.00"),
            "remaining_days": Decimal("39.50"),
            "sick_full_pay_used": Decimal("15.00"),
            "sick_half_pay_used": Decimal("30.00"),
            "sick_unpaid_used": Decimal("5.00"),
            "hajj_taken": False,
        }
    ]


class ApproverRepository:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.queried = False

    async def approver_can_read_employee(self, *_values: object) -> bool:
        return self.allowed

    async def list_balances(self, *_values: object, **_options: object) -> list[dict[str, object]]:
        self.queried = True
        return []

    async def balance_cursor_exists(self, *_values: object, **_options: object) -> bool:
        return True


@pytest.mark.asyncio
async def test_approver_balance_read_requires_a_verified_direct_or_delegated_target() -> None:
    query = BalanceListQuery(50, 2026, REPORT_ID, None, None)
    denied_repository = ApproverRepository(False)
    denied = LeaveBalanceService(
        cast(AsyncConnection, object()),
        EmployeeCursorCodec(b"0" * 32, clock=lambda: datetime(2026, 9, 13, tzinfo=UTC)),
        cast(LeaveBalanceRepository, denied_repository),
    )
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await denied.list_approver_balances(principal(AppRole.EMPLOYEE), query)
    assert denied_repository.queried is False

    allowed_repository = ApproverRepository(True)
    allowed = LeaveBalanceService(
        cast(AsyncConnection, object()),
        EmployeeCursorCodec(b"0" * 32, clock=lambda: datetime(2026, 9, 13, tzinfo=UTC)),
        cast(LeaveBalanceRepository, allowed_repository),
    )
    rows, cursor = await allowed.list_approver_balances(principal(AppRole.EMPLOYEE), query)
    assert rows == [] and cursor is None
    assert allowed_repository.queried is True
