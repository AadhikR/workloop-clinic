from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.services.dashboards import DashboardService
from app.services.execution import ServiceExecutionError

COMPANY = uuid.UUID("c5000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("c5000000-0000-4000-8000-000000000002")
USER = uuid.UUID("c5000000-0000-4000-8000-000000000003")
EMPLOYEE = uuid.UUID("c5000000-0000-4000-8000-000000000004")
VERSION = uuid.UUID("c5000000-0000-4000-8000-000000000005")
NOW = datetime(2026, 9, 24, 8, tzinfo=UTC)


def principal(role: AppRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=USER,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY,
        employee_id=None if role is AppRole.ADMIN else EMPLOYEE,
        branch_id=None if role is AppRole.ADMIN else BRANCH,
    )


def admin_source() -> dict[str, object]:
    return {
        "as_of": NOW,
        "business_date": date(2026, 9, 24),
        "active_headcount": 9,
        "payroll_period": "2026-08",
        "payroll_total": Decimal("1000.10"),
        "payroll_employee_count": 9,
        "wps_status": "confirmed",
        "previous_payroll_total": Decimal("999.99"),
        "nafis_period": "2026-08",
        "ratio_percent": Decimal("2.10"),
        "required_percent": Decimal("2.00"),
        "nafis_compliant": True,
        "nafis_headcount": 9,
        "emirati_count": 1,
        "expiry_due": 2,
    }


def clinical_source() -> dict[str, object]:
    return {
        "as_of": NOW,
        "business_date": date(2026, 9, 24),
        "active_headcount": 4,
        "valid_count": 1,
        "expiring_count": 1,
        "expired_count": 1,
        "assignment_count": 3,
        "on_duty_count": 2,
        "current_version_id": VERSION,
        "roster_version": "sha256:" + "b" * 64,
        "published_at": NOW,
        "record_count": 3,
        "publication_kind": "publication",
    }


def self_source() -> dict[str, object]:
    return {
        "as_of": NOW,
        "business_date": date(2026, 9, 24),
        "employment_status": "Active",
        "remaining_days": Decimal("12.50"),
        "payslip_period": "2026-08",
        "net_pay": Decimal("7000.25"),
        "attendance_status": "PRESENT",
        "assigned_assets": 2,
        "shift_name": "Day shift",
        "roster_version": "sha256:" + "c" * 64,
    }


class Repository:
    def __init__(self, rows: dict[str, dict[str, object]], *, fail: bool = False) -> None:
        self.rows = rows
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    async def snapshot(self, kind: str, **values: object) -> dict[str, object]:
        self.calls.append({"kind": kind, **values})
        if self.fail:
            raise RuntimeError("source down")
        return self.rows[kind]


@pytest.mark.asyncio
async def test_admin_snapshot_preserves_phase9_decimals_and_server_drills() -> None:
    repository = Repository({"admin": admin_source()})
    result = await DashboardService(repository).read("admin", principal(AppRole.ADMIN), BRANCH)
    by_code = {card.code: card for card in result.cards}
    assert by_code["finalizedPayroll"].value == "1000.10"
    assert by_code["finalizedPayroll"].comparison is not None
    assert by_code["finalizedPayroll"].comparison.value == "999.99"
    assert by_code["nafisRatio"].value == "2.10"
    assert by_code["wpsStatus"].value == "confirmed"
    assert by_code["expiryDue"].value == 2
    assert by_code["expiryDue"].drill_down is not None
    assert by_code["expiryDue"].drill_down.target == "recordsBenefits"
    assert result.source_version.startswith("sha256:")
    assert repository.calls[0]["company_id"] == COMPANY
    assert repository.calls[0]["branch_id"] == BRANCH


@pytest.mark.asyncio
async def test_clinical_snapshot_uses_verified_eligible_counts_and_published_roster() -> None:
    result = await DashboardService(Repository({"clinical": clinical_source()})).read(
        "clinical", principal(AppRole.ADMIN), BRANCH
    )
    values = {card.code: card.value for card in result.cards}
    assert values["credentialsValid"] == 1
    assert values["credentialsExpiring"] == 1
    assert values["credentialsExpired"] == 1
    assert values["publishedRoster"] == 3
    assert values["staffingValidation"] == "passed"


@pytest.mark.asyncio
async def test_self_snapshot_is_bound_to_principal_employee() -> None:
    repository = Repository({"self": self_source()})
    result = await DashboardService(repository).read("self", principal(AppRole.EMPLOYEE), BRANCH)
    assert repository.calls[0]["employee_id"] == EMPLOYEE
    values = {card.code: card.value for card in result.cards}
    assert values["leaveBalance"] == "12.50"
    assert values["latestPayslip"] == "7000.25"


@pytest.mark.asyncio
async def test_dashboard_source_failure_is_safe_and_never_partial() -> None:
    service = DashboardService(Repository({"admin": admin_source()}, fail=True))
    with pytest.raises(ServiceExecutionError, match="dashboard_source_unavailable"):
        await service.read("admin", principal(AppRole.ADMIN), BRANCH)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "role"),
    [("admin", AppRole.EMPLOYEE), ("clinical", AppRole.MANAGER), ("self", AppRole.ADMIN)],
)
async def test_dashboard_roles_fail_closed(kind: str, role: AppRole) -> None:
    service = DashboardService(Repository({}))
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await service.read(kind, principal(role), BRANCH)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_repeated_reads_call_only_the_read_repository() -> None:
    repository = Repository({"admin": admin_source()})
    service = DashboardService(repository)
    for _ in range(5):
        await service.read("admin", principal(AppRole.ADMIN), BRANCH)
    assert len(repository.calls) == 5


@pytest.mark.asyncio
async def test_source_version_tracks_source_state_not_response_clock() -> None:
    first_source = admin_source()
    second_source = {**admin_source(), "as_of": datetime(2026, 9, 24, 9, tzinfo=UTC)}
    first = await DashboardService(Repository({"admin": first_source})).read(
        "admin", principal(AppRole.ADMIN), BRANCH
    )
    second = await DashboardService(Repository({"admin": second_source})).read(
        "admin", principal(AppRole.ADMIN), BRANCH
    )
    assert first.as_of != second.as_of
    assert first.source_version == second.source_version
