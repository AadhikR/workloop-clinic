from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.services.execution import ServiceExecutionError
from app.services.reports import ReportCursorCodec, ReportQuery, ReportService

COMPANY = uuid.UUID("c8000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("c8000000-0000-4000-8000-000000000002")
USER = uuid.UUID("c8000000-0000-4000-8000-000000000003")
EMPLOYEE = uuid.UUID("c8000000-0000-4000-8000-000000000004")
DEPARTMENT = uuid.UUID("c8000000-0000-4000-8000-000000000005")
NOW = datetime(2026, 9, 25, 8, tzinfo=UTC)


def principal(role: AppRole = AppRole.ADMIN) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=USER,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY,
        employee_id=None if role is AppRole.ADMIN else EMPLOYEE,
        branch_id=None if role is AppRole.ADMIN else BRANCH,
    )


class Repository:
    def __init__(self, rows: list[dict[str, object]], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    async def resolve_employee(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> bool:
        return (company_id, branch_id, employee_id) == (COMPANY, BRANCH, EMPLOYEE)

    async def resolve_department(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, department_id: uuid.UUID
    ) -> str | None:
        if (company_id, branch_id, department_id) == (COMPANY, BRANCH, DEPARTMENT):
            return "Clinical"
        return None

    async def read(
        self, report_id: str, **values: object
    ) -> tuple[datetime, list[dict[str, object]]]:
        self.calls.append({"report_id": report_id, **values})
        if self.fail:
            raise RuntimeError("source failed")
        return NOW, self.rows


def codec() -> ReportCursorCodec:
    return ReportCursorCodec(b"0" * 32)


def headcount_row(index: int) -> dict[str, object]:
    return {
        "employeeId": uuid.UUID(f"c8000000-0000-4000-8000-{index:012d}"),
        "employeeNumber": f"E-{index}",
        "employeeName": "Tied name",
        "department": "Clinical",
        "nationality": "Test",
        "contractType": "Limited",
        "gender": "Other",
        "status": "Active",
    }


@pytest.mark.asyncio
async def test_report_totals_cover_full_filtered_set_and_cursor_is_bound() -> None:
    repository = Repository([headcount_row(index) for index in range(1, 4)])
    service = ReportService(repository, codec())
    first_query = ReportQuery(department_id=DEPARTMENT, limit=2)
    first = await service.read("headcount", principal(), BRANCH, first_query)
    assert len(first.rows) == 2
    assert first.totals.row_count == 3
    assert first.totals.values["byDepartment"] == {"Clinical": 3}
    assert first.totals.values["byStatus"] == {"Active": 3}
    assert first.next_cursor is not None
    assert repository.calls[0]["filters"] == {
        "date_from": None,
        "date_to": None,
        "period": None,
        "status": None,
        "employee_id": None,
        "department": "Clinical",
    }

    second = await service.read(
        "headcount",
        principal(),
        BRANCH,
        ReportQuery(department_id=DEPARTMENT, limit=2, cursor=first.next_cursor),
    )
    assert [row["employeeId"] for row in second.rows] == [str(headcount_row(3)["employeeId"])]
    assert second.totals.row_count == 3

    with pytest.raises(ServiceExecutionError, match="invalid_cursor"):
        await service.read(
            "headcount",
            principal(),
            BRANCH,
            ReportQuery(status="Active", limit=2, cursor=first.next_cursor),
        )


@pytest.mark.asyncio
async def test_report_selectors_resolve_inside_verified_scope() -> None:
    service = ReportService(Repository([]), codec())
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await service.read(
            "headcount", principal(), BRANCH, ReportQuery(department_id=uuid.uuid4())
        )
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await service.read(
            "leaveBalance", principal(), BRANCH, ReportQuery(employee_id=uuid.uuid4())
        )


@pytest.mark.asyncio
async def test_eos_liability_uses_policy_100_and_marks_unsupported_rows() -> None:
    rows = [
        {
            "employeeId": EMPLOYEE,
            "employeeName": "Supported",
            "department": "Clinical",
            "policyVersion": "1.0.0",
            "serviceDays": 365,
            "nationality": "India",
            "workLocationType": "mainland",
            "basicSalary": Decimal("10000.00"),
            "policyAvailable": True,
        },
        {
            "employeeId": uuid.uuid4(),
            "employeeName": "Unsupported",
            "department": "Clinical",
            "policyVersion": "1.0.0",
            "serviceDays": 365,
            "nationality": "UAE",
            "workLocationType": "mainland",
            "basicSalary": Decimal("10000.00"),
            "policyAvailable": True,
        },
    ]
    result = await ReportService(Repository(rows), codec()).read(
        "eosLiability", principal(), BRANCH, ReportQuery()
    )
    assert result.rows[0]["liability"] == "7000.00"
    assert result.rows[0]["status"] == "available"
    assert result.rows[1]["liability"] is None
    assert result.rows[1]["status"] == "unavailable"
    assert result.rows[1]["unavailableReason"] == "uae_national_not_supported"


@pytest.mark.asyncio
async def test_reports_fail_closed_for_role_and_required_source_failure() -> None:
    service = ReportService(Repository([], fail=True), codec())
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await service.read("headcount", principal(AppRole.MANAGER), BRANCH, ReportQuery())
    with pytest.raises(ServiceExecutionError, match="report_source_unavailable"):
        await service.read("headcount", principal(), BRANCH, ReportQuery())
