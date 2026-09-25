from __future__ import annotations

import uuid
from datetime import date
from typing import cast

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
