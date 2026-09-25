from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.services.execution import ServiceExecutionError


class OutputRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def employees(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
    ) -> list[dict[str, object]]:
        if employee_id is not None:
            visible = await self.connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM public.employees WHERE id=:employee "
                    "AND company_id=:company AND branch_id=:branch)"
                ),
                {"employee": employee_id, "company": company_id, "branch": branch_id},
            )
            if visible is not True:
                raise ServiceExecutionError("resource_not_found")
        rows = (
            await self.connection.execute(
                text(
                    """
SELECT employee.emp_no AS "employeeNumber",employee.name AS "employeeName",
 employee.mol_id AS "molId",employee.job_title AS "jobTitle",
 employee.department,employee.employment_status AS status,
 employee.basic_salary AS "basicSalary",employee.housing_allowance AS housing,
 employee.transport_allowance AS transport,
 employee.basic_salary+employee.housing_allowance+employee.transport_allowance+
   employee.other_allowances AS "totalPackage",
 employee.bank_name AS bank,employee.bank_routing_code AS "bankRoutingCode",
 employee.iban,employee.nationality,employee.visa_type AS "visaType",
 employee.visa_expiry AS "visaExpiry",employee.passport_expiry AS "passportExpiry",
 employee.emirates_id AS "emiratesId",employee.emirates_id_expiry AS "emiratesIdExpiry",
 employee.labour_card_expiry AS "labourCardExpiry"
FROM public.employees employee
WHERE employee.company_id=:company AND employee.branch_id=:branch
 AND (CAST(:employee AS uuid) IS NULL OR employee.id=CAST(:employee AS uuid))
ORDER BY lower(employee.name),employee.id
LIMIT 5001
"""
                ),
                {"company": company_id, "branch": branch_id, "employee": employee_id},
            )
        ).mappings()
        return [dict(row) for row in rows]

    async def attendance_period(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period_id: uuid.UUID
    ) -> str:
        value = await self.connection.scalar(
            text(
                "SELECT period FROM public.attendance_periods WHERE id=:id "
                "AND company_id=:company AND branch_id=:branch"
            ),
            {"id": period_id, "company": company_id, "branch": branch_id},
        )
        if not isinstance(value, str):
            raise ServiceExecutionError("resource_not_found")
        return value

    async def roster(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, start: date, end: date
    ) -> list[dict[str, object]]:
        rows = (
            await self.connection.execute(
                text(
                    """
SELECT roster.date,employee.emp_no AS "employeeNumber",
 employee.name AS "employeeName",employee.department,
 COALESCE(NULLIF(shift.code,''),shift.name) AS "shiftCode",
 shift.name AS "shiftName",shift.shift_category AS "shiftCategory",
 roster.planned_hours AS "plannedHours"
FROM public.roster_assignments roster
JOIN public.employees employee ON employee.id=roster.employee_id
 AND employee.company_id=roster.company_id AND employee.branch_id=roster.branch_id
JOIN public.shifts shift ON shift.id=roster.shift_id
 AND shift.company_id=roster.company_id AND shift.branch_id=roster.branch_id
WHERE roster.company_id=:company AND roster.branch_id=:branch
 AND roster.date BETWEEN :start AND :end AND roster.published
ORDER BY roster.date,lower(employee.name),employee.id,roster.id
LIMIT 5001
"""
                ),
                {"company": company_id, "branch": branch_id, "start": start, "end": end},
            )
        ).mappings()
        return [dict(row) for row in rows]

    async def nafis(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, snapshot_id: uuid.UUID
    ) -> tuple[str, list[dict[str, object]], dict[str, object]]:
        row = (
            (
                await self.connection.execute(
                    text(
                        "SELECT period,snapshot,generated_at FROM public.nafis_reports "
                        "WHERE id=:id "
                        "AND company_id=:company AND branch_id=:branch"
                    ),
                    {"id": snapshot_id, "company": company_id, "branch": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        raw_snapshot = row["snapshot"]
        if not isinstance(raw_snapshot, dict):
            raise ServiceExecutionError("report_source_unavailable")
        snapshot = cast(dict[str, object], raw_snapshot)
        raw_employees = snapshot.get("employees")
        if not isinstance(raw_employees, list):
            raise ServiceExecutionError("report_source_unavailable")
        employees: list[dict[str, object]] = []
        for raw_item in cast(list[object], raw_employees):
            if not isinstance(raw_item, dict):
                raise ServiceExecutionError("report_source_unavailable")
            item = cast(dict[str, object], raw_item)
            employees.append(
                {
                    "employeeId": item.get("employeeId"),
                    "employeeName": item.get("employeeName"),
                    "nafisRegistrationNumber": item.get("nafisRegistrationNumber"),
                    "qualifyingBasicWage": item.get("qualifyingBasicWage"),
                }
            )
        return (
            str(row["period"]),
            employees,
            {
                "snapshot": snapshot,
                "generatedAt": row["generated_at"],
            },
        )

    async def payslip(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        payslip_id: uuid.UUID,
        employee_id: uuid.UUID | None,
    ) -> dict[str, Any]:
        conditions = "slip.id=:id AND slip.company_id=:company AND slip.branch_id=:branch"
        parameters: dict[str, object] = {
            "id": payslip_id,
            "company": company_id,
            "branch": branch_id,
        }
        if employee_id is not None:
            conditions += " AND slip.employee_id=:employee"
            parameters["employee"] = employee_id
        row = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT slip.*,employee.emp_no AS employee_number
FROM public.payslips slip
JOIN public.employees employee ON employee.id=slip.employee_id
 AND employee.company_id=slip.company_id AND employee.branch_id=slip.branch_id
WHERE {conditions}
"""
                    ),
                    parameters,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return self._payslip_source(row)

    async def payslips_for_run(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> tuple[datetime, list[dict[str, Any]]]:
        run = (
            (
                await self.connection.execute(
                    text(
                        "SELECT updated_at FROM public.payroll_runs WHERE id=:id "
                        "AND company_id=:company AND branch_id=:branch "
                        "AND status='generated' AND approval_status='approved'"
                    ),
                    {"id": run_id, "company": company_id, "branch": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if run is None:
            raise ServiceExecutionError("resource_not_found")
        rows = (
            await self.connection.execute(
                text(
                    """
SELECT slip.*,employee.emp_no AS employee_number
FROM public.payslips slip
JOIN public.employees employee ON employee.id=slip.employee_id
 AND employee.company_id=slip.company_id AND employee.branch_id=slip.branch_id
WHERE slip.payroll_run_id=:run AND slip.company_id=:company AND slip.branch_id=:branch
ORDER BY employee.emp_no,slip.employee_id,slip.id
LIMIT 201
"""
                ),
                {"run": run_id, "company": company_id, "branch": branch_id},
            )
        ).mappings()
        return cast(datetime, run["updated_at"]), [self._payslip_source(row) for row in rows]

    async def final_settlement(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
    ) -> dict[str, Any]:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT settlement.*
FROM public.final_settlements settlement
JOIN public.offboarding_checklists checklist
  ON checklist.id=settlement.checklist_id
 AND checklist.company_id=settlement.company_id
 AND checklist.branch_id=settlement.branch_id
WHERE checklist.id=:checklist AND checklist.company_id=:company
 AND checklist.branch_id=:branch AND checklist.status='completed'
"""
                    ),
                    {"checklist": checklist_id, "company": company_id, "branch": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return {
            "id": row["id"],
            "checklistId": row["checklist_id"],
            "employeeId": row["employee_id"],
            "policyVersion": self._snapshot_policy_version(row["source_snapshot"]),
            "policyDigest": self._snapshot_policy_digest(row["source_snapshot"]),
            "sourceDigest": row["source_digest"],
            "sourceCapturedAt": row["source_captured_at"],
            "serviceDays": self._snapshot_value(row["calculation_breakdown"], "serviceDays"),
            "gratuityDays": self._snapshot_value(row["calculation_breakdown"], "gratuityDays"),
            "leaveDays": self._snapshot_value(row["calculation_breakdown"], "leaveDays"),
            "finalSalary": self._money(row["final_salary"]),
            "leaveEncashment": self._money(row["leave_encashment"]),
            "gratuity": self._money(row["gratuity"]),
            "noticePay": self._money(row["notice_pay"]),
            "otherEarnings": self._money(row["other_earnings"]),
            "advanceDeduction": self._money(row["advance_deduction"]),
            "assetDeduction": self._money(row["asset_deduction"]),
            "noticeDeduction": self._money(row["notice_deduction"]),
            "otherDeductions": self._money(row["other_deductions"]),
            "grossAmount": self._money(row["gross_amount"]),
            "totalDeductions": self._money(row["total_deductions"]),
            "netAmount": self._money(row["net_amount"]),
            "completedAt": row["completed_at"],
        }

    @staticmethod
    def _payslip_source(row: Any) -> dict[str, Any]:
        snapshot = cast(dict[str, Any], dict(row["data_snapshot"]))
        return {
            "id": row["id"],
            "employeeId": row["employee_id"],
            "employeeNumber": row["employee_number"],
            "period": row["period"],
            "paymentDate": row["payment_date"],
            "employeeName": snapshot["employeeName"],
            "earnings": snapshot["earnings"],
            "deductions": snapshot["deductions"],
            "grossPay": OutputRepository._money(row["gross_pay"]),
            "totalDeductions": str(snapshot["totalDeductions"]),
            "netPay": OutputRepository._money(row["net_pay"]),
            "wpsBasicPay": str(snapshot["wpsBasicPay"]),
            "wpsVariablePay": str(snapshot["wpsVariablePay"]),
            "issuedAt": row["issued_at"],
        }

    @staticmethod
    def _money(value: object) -> str:
        return f"{Decimal(str(value)):.2f}"

    @staticmethod
    def _snapshot_value(snapshot: object, key: str) -> str:
        if not isinstance(snapshot, dict):
            raise ServiceExecutionError("report_source_unavailable")
        value = cast(dict[str, object], snapshot).get(key)
        if value is None:
            return "0"
        return str(value)

    @staticmethod
    def _snapshot_policy_version(snapshot: object) -> str:
        if not isinstance(snapshot, dict):
            raise ServiceExecutionError("report_source_unavailable")
        source = cast(dict[str, object], snapshot)
        policy = source.get("policy")
        if not isinstance(policy, dict):
            raise ServiceExecutionError("report_source_unavailable")
        return str(cast(dict[str, object], policy)["version"])

    @staticmethod
    def _snapshot_policy_digest(snapshot: object) -> str:
        if not isinstance(snapshot, dict):
            raise ServiceExecutionError("report_source_unavailable")
        source = cast(dict[str, object], snapshot)
        policy = source.get("policy")
        if not isinstance(policy, dict):
            raise ServiceExecutionError("report_source_unavailable")
        return str(cast(dict[str, object], policy)["digest"])
