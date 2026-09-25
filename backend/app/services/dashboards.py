from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, cast

from app.auth.application_user import AuthorizationPrincipal
from app.expiry_command import CLINICAL_DOCUMENT_TYPES
from app.models.identity import AppRole
from app.repositories.dashboards import DashboardKind
from app.schemas.dashboards import (
    DashboardCard,
    DashboardComparison,
    DashboardDrillDown,
    DashboardResponse,
    DashboardSeverity,
)
from app.services.execution import ServiceExecutionError

logger = logging.getLogger(__name__)


class DashboardRepository(Protocol):
    async def snapshot(
        self,
        kind: DashboardKind,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        clinical_types: tuple[str, ...],
    ) -> dict[str, object]: ...


def _money(value: object) -> str:
    return format(Decimal(str(value if value is not None else 0)), ".2f")


def _number(value: object) -> int:
    return int(str(value if value is not None else 0))


def _drill(code: str, target: str) -> DashboardDrillDown:
    return DashboardDrillDown(code=code, target=target)


def _card(
    code: str,
    label: str,
    value: int | str,
    unit: str,
    severity: DashboardSeverity,
    target: str,
    *,
    comparison: DashboardComparison | None = None,
) -> DashboardCard:
    return DashboardCard(
        code=code,
        label=label,
        value=value,
        unit=unit,
        severity=severity,
        comparison=comparison,
        drill_down=_drill(code, target),
    )


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    async def read(
        self,
        kind: DashboardKind,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
    ) -> DashboardResponse:
        if kind in {"admin", "clinical"} and principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        if kind == "self" and (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        try:
            source = await self.repository.snapshot(
                kind,
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=principal.employee_id,
                clinical_types=tuple(sorted(CLINICAL_DOCUMENT_TYPES)),
            )
        except Exception:
            logger.warning(
                "dashboard_source_failed",
                extra={"dashboard_kind": kind, "error_code": "dashboard_source_unavailable"},
            )
            raise ServiceExecutionError("dashboard_source_unavailable") from None
        cards = {
            "admin": self._admin_cards,
            "clinical": self._clinical_cards,
            "self": self._self_cards,
        }[kind](source)
        version_source = {key: value for key, value in source.items() if key != "as_of"}
        canonical = json.dumps(version_source, default=str, separators=(",", ":"), sort_keys=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return DashboardResponse(
            as_of=cast(datetime, source["as_of"]),
            business_date=cast(date, source["business_date"]),
            source_version=f"sha256:{digest}",
            cards=cards,
        )

    @staticmethod
    def _admin_cards(source: dict[str, object]) -> list[DashboardCard]:
        headcount = _number(source["active_headcount"])
        payroll = _money(source["payroll_total"])
        prior = source["previous_payroll_total"]
        wps = str(source["wps_status"] or "not_available")
        nafis_ratio = _money(source["ratio_percent"])
        nafis_available = source["nafis_period"] is not None
        expiry = _number(source["expiry_due"])
        wps_severity: DashboardSeverity = "info"
        if wps == "confirmed":
            wps_severity = "success"
        elif wps == "partial_rejection":
            wps_severity = "warning"
        elif wps == "failed":
            wps_severity = "critical"
        return [
            _card(
                "activeHeadcount",
                "Active headcount",
                headcount,
                "employees",
                "success" if headcount else "info",
                "employees",
            ),
            _card(
                "finalizedPayroll",
                "Latest finalized payroll",
                payroll,
                "AED",
                "info",
                "payroll",
                comparison=(
                    DashboardComparison(
                        label="Previous finalized payroll", value=_money(prior), unit="AED"
                    )
                    if prior is not None
                    else None
                ),
            ),
            _card("wpsStatus", "WPS status", wps, "status", wps_severity, "wps"),
            _card(
                "nafisRatio",
                "Nafis ratio",
                nafis_ratio if nafis_available else "not_available",
                "percent",
                "success"
                if source["nafis_compliant"]
                else ("warning" if nafis_available else "info"),
                "nafis",
            ),
            _card(
                "expiryDue",
                "Expiry actions due",
                expiry,
                "items",
                "warning" if expiry else "success",
                "recordsBenefits",
            ),
        ]

    @staticmethod
    def _clinical_cards(source: dict[str, object]) -> list[DashboardCard]:
        valid = _number(source["valid_count"])
        expiring = _number(source["expiring_count"])
        expired = _number(source["expired_count"])
        assignments = _number(source["assignment_count"])
        on_duty = _number(source["on_duty_count"])
        published = source["current_version_id"] is not None
        return [
            _card(
                "credentialsValid",
                "Valid credentials",
                valid,
                "credentials",
                "success",
                "developmentAssets",
            ),
            _card(
                "credentialsExpiring",
                "Expiring credentials",
                expiring,
                "credentials",
                "warning" if expiring else "success",
                "developmentAssets",
            ),
            _card(
                "credentialsExpired",
                "Expired credentials",
                expired,
                "credentials",
                "critical" if expired else "success",
                "developmentAssets",
            ),
            _card(
                "publishedRoster",
                "Published roster today",
                assignments,
                "assignments",
                "success" if published else "info",
                "roster",
            ),
            _card(
                "staffingValidation",
                "Staffing validation",
                "passed" if published else "not_available",
                "status",
                "success" if published else "info",
                "roster",
            ),
            _card("onDuty", "On duty today", on_duty, "employees", "info", "attendance"),
        ]

    @staticmethod
    def _self_cards(source: dict[str, object]) -> list[DashboardCard]:
        return [
            _card(
                "employmentStatus",
                "Employment status",
                str(source["employment_status"]),
                "status",
                "info",
                "profile",
            ),
            _card(
                "leaveBalance",
                "Leave balance",
                _money(source["remaining_days"]),
                "days",
                "info",
                "leave",
            ),
            _card(
                "latestPayslip",
                "Latest payslip",
                _money(source["net_pay"])
                if source["payslip_period"] is not None
                else "not_available",
                "AED",
                "info",
                "payslips",
            ),
            _card(
                "todayAttendance",
                "Attendance today",
                str(source["attendance_status"] or "not_available"),
                "status",
                "info",
                "attendance",
            ),
            _card(
                "assignedAssets",
                "Assigned assets",
                _number(source["assigned_assets"]),
                "assets",
                "info",
                "developmentAssets",
            ),
            _card(
                "todayShift",
                "Published shift today",
                str(source["shift_name"] or "not_available"),
                "shift",
                "info",
                "schedule",
            ),
        ]
