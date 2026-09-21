from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.schemas.roster import (
    RosterAssignmentResponse,
    RosterComplianceOverrideResponse,
    RosterDraftCreateRequest,
    RosterDraftReplaceRequest,
    RosterLeaveConflictResponse,
    RosterStaffingViolationResponse,
    RosterValidationResponse,
)
from app.services.execution import ServiceExecutionError


def period_dates(period: str) -> tuple[date, date]:
    year, month = (int(value) for value in period.split("-"))
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _assignment(row: RowMapping) -> RosterAssignmentResponse:
    return RosterAssignmentResponse.model_validate(dict(row))


def _violation_digest(snapshot: dict[str, Any]) -> str:
    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


class RosterRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> tuple[date, uuid.UUID, uuid.UUID]:
        row = (
            await self.connection.execute(
                text(
                    "SELECT date,employee_id,id FROM public.roster_assignments "
                    "WHERE company_id=:company AND branch_id=:branch AND id=:id"
                ),
                {"company": company_id, "branch": branch_id, "id": assignment_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row.date, row.employee_id, row.id

    async def list(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        department: str | None,
        employee_id: uuid.UUID | None,
        after: tuple[date, uuid.UUID, uuid.UUID] | None,
        limit: int,
    ) -> list[RosterAssignmentResponse]:
        start, end = period_dates(period)
        marker = ""
        parameters: dict[str, object] = {
            "company": company_id,
            "branch": branch_id,
            "start": start,
            "end": end,
            "department": department,
            "employee": employee_id,
            "limit": limit,
        }
        if after is not None:
            marker = (
                "AND (roster.date,roster.employee_id,roster.id)>"
                "(:after_date,:after_employee,:after_id) "
            )
            parameters.update(
                {
                    "after_date": after[0],
                    "after_employee": after[1],
                    "after_id": after[2],
                }
            )
        rows = (
            await self.connection.execute(
                text(
                    "SELECT roster.id,roster.employee_id,employee.name employee_name,"
                    "employee.department,roster.shift_id,shift.name shift_name,"
                    "shift.code shift_code,"
                    "shift.shift_category,roster.date,roster.published,roster.planned_hours,"
                    "roster.notes,roster.version,roster.updated_at,EXISTS("
                    "SELECT 1 FROM public.leave_requests leave_request "
                    "WHERE leave_request.company_id=roster.company_id "
                    "AND leave_request.branch_id=roster.branch_id "
                    "AND leave_request.employee_id=roster.employee_id "
                    "AND roster.date BETWEEN leave_request.start_date AND leave_request.end_date "
                    "AND leave_request.status IN ('Approved','ManagerApproved')) leave_conflict "
                    "FROM public.roster_assignments roster "
                    "JOIN public.employees employee ON employee.id=roster.employee_id "
                    "AND employee.company_id=roster.company_id "
                    "AND employee.branch_id=roster.branch_id "
                    "JOIN public.shifts shift ON shift.id=roster.shift_id "
                    "AND shift.company_id=roster.company_id AND shift.branch_id=roster.branch_id "
                    "WHERE roster.company_id=:company AND roster.branch_id=:branch "
                    "AND roster.date BETWEEN :start AND :end "
                    "AND (:department IS NULL OR employee.department=:department) "
                    "AND (:employee IS NULL OR roster.employee_id=:employee) "
                    + marker
                    + "ORDER BY roster.date,roster.employee_id,roster.id LIMIT :limit"
                ),
                parameters,
            )
        ).mappings()
        return [_assignment(row) for row in rows]

    async def _validate_sources(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        values: RosterDraftCreateRequest,
    ) -> None:
        employee = (
            await self.connection.execute(
                text(
                    "SELECT active,employment_status FROM public.employees "
                    "WHERE id=:employee AND company_id=:company AND branch_id=:branch FOR SHARE"
                ),
                {"employee": values.employee_id, "company": company_id, "branch": branch_id},
            )
        ).one_or_none()
        shift = (
            await self.connection.execute(
                text(
                    "SELECT is_active FROM public.shifts WHERE id=:shift "
                    "AND company_id=:company AND branch_id=:branch FOR SHARE"
                ),
                {"shift": values.shift_id, "company": company_id, "branch": branch_id},
            )
        ).one_or_none()
        if employee is None or shift is None:
            raise ServiceExecutionError("resource_not_found")
        if not employee.active or employee.employment_status not in {"Active", "Probation"}:
            raise ServiceExecutionError("state_conflict")
        if not shift.is_active:
            raise ServiceExecutionError("state_conflict")
        leave_conflict = await self.connection.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM public.leave_requests WHERE company_id=:company "
                "AND branch_id=:branch AND employee_id=:employee "
                "AND :day BETWEEN start_date AND end_date "
                "AND status IN ('Approved','ManagerApproved'))"
            ),
            {
                "company": company_id,
                "branch": branch_id,
                "employee": values.employee_id,
                "day": values.date,
            },
        )
        if leave_conflict:
            raise ServiceExecutionError("state_conflict")

    async def detail(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> RosterAssignmentResponse:
        rows = await self.connection.execute(
            text(
                "SELECT roster.id,roster.employee_id,employee.name employee_name,"
                "employee.department,roster.shift_id,shift.name shift_name,shift.code shift_code,"
                "shift.shift_category,roster.date,roster.published,roster.planned_hours,"
                "roster.notes,roster.version,roster.updated_at,EXISTS("
                "SELECT 1 FROM public.leave_requests leave_request "
                "WHERE leave_request.company_id=roster.company_id "
                "AND leave_request.branch_id=roster.branch_id "
                "AND leave_request.employee_id=roster.employee_id "
                "AND roster.date BETWEEN leave_request.start_date AND leave_request.end_date "
                "AND leave_request.status IN ('Approved','ManagerApproved')) leave_conflict "
                "FROM public.roster_assignments roster "
                "JOIN public.employees employee ON employee.id=roster.employee_id "
                "AND employee.company_id=roster.company_id AND employee.branch_id=roster.branch_id "
                "JOIN public.shifts shift ON shift.id=roster.shift_id "
                "AND shift.company_id=roster.company_id AND shift.branch_id=roster.branch_id "
                "WHERE roster.id=:id AND roster.company_id=:company AND roster.branch_id=:branch"
            ),
            {"id": assignment_id, "company": company_id, "branch": branch_id},
        )
        row = rows.mappings().one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return _assignment(row)

    async def create(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        values: RosterDraftCreateRequest,
    ) -> RosterAssignmentResponse:
        await self._validate_sources(company_id, branch_id, values)
        assignment_id = uuid.uuid4()
        try:
            await self.connection.execute(
                text(
                    "INSERT INTO public.roster_assignments"
                    "(id,company_id,branch_id,employee_id,shift_id,date,published,"
                    "planned_hours,notes) "
                    "VALUES (:id,:company,:branch,:employee,:shift,:day,false,:hours,:notes)"
                ),
                {
                    "id": assignment_id,
                    "company": company_id,
                    "branch": branch_id,
                    "employee": values.employee_id,
                    "shift": values.shift_id,
                    "day": values.date,
                    "hours": values.planned_hours,
                    "notes": values.notes,
                },
            )
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        return await self.detail(company_id, branch_id, assignment_id)

    async def replace(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        values: RosterDraftReplaceRequest,
    ) -> RosterAssignmentResponse:
        start, end = period_dates(period)
        await self._validate_sources(company_id, branch_id, values)
        try:
            result = await self.connection.execute(
                text(
                    "UPDATE public.roster_assignments SET employee_id=:employee,shift_id=:shift,"
                    "date=:day,planned_hours=:hours,notes=:notes,version=version+1 "
                    "WHERE id=:id AND company_id=:company AND branch_id=:branch "
                    "AND date BETWEEN :start AND :end "
                    "AND NOT published AND version=:version"
                ),
                {
                    "id": assignment_id,
                    "company": company_id,
                    "branch": branch_id,
                    "start": start,
                    "end": end,
                    "employee": values.employee_id,
                    "shift": values.shift_id,
                    "day": values.date,
                    "hours": values.planned_hours,
                    "notes": values.notes,
                    "version": values.expected_version,
                },
            )
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        if result.rowcount != 1:
            exists = await self.connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM public.roster_assignments WHERE id=:id "
                    "AND company_id=:company AND branch_id=:branch)"
                ),
                {"id": assignment_id, "company": company_id, "branch": branch_id},
            )
            raise ServiceExecutionError("state_conflict" if exists else "resource_not_found")
        return await self.detail(company_id, branch_id, assignment_id)

    async def delete(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        expected_version: int,
    ) -> None:
        start, end = period_dates(period)
        result = await self.connection.execute(
            text(
                "DELETE FROM public.roster_assignments roster WHERE roster.id=:id "
                "AND roster.company_id=:company AND roster.branch_id=:branch "
                "AND roster.date BETWEEN :start AND :end "
                "AND NOT roster.published AND roster.version=:version AND NOT EXISTS("
                "SELECT 1 FROM public.shift_swap_requests swap "
                "WHERE swap.company_id=roster.company_id AND swap.branch_id=roster.branch_id "
                "AND ((swap.requester_employee_id=roster.employee_id "
                "AND swap.requester_date=roster.date) OR "
                "(swap.target_employee_id=roster.employee_id "
                "AND swap.target_date=roster.date)))"
            ),
            {
                "id": assignment_id,
                "company": company_id,
                "branch": branch_id,
                "start": start,
                "end": end,
                "version": expected_version,
            },
        )
        if result.rowcount != 1:
            exists = await self.connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM public.roster_assignments WHERE id=:id "
                    "AND company_id=:company AND branch_id=:branch)"
                ),
                {"id": assignment_id, "company": company_id, "branch": branch_id},
            )
            raise ServiceExecutionError("state_conflict" if exists else "resource_not_found")

    async def validation(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> RosterValidationResponse:
        start, end = period_dates(period)
        leave_rows = (
            await self.connection.execute(
                text(
                    "SELECT roster.id roster_assignment_id,roster.employee_id,"
                    "employee.name employee_name,roster.date,"
                    "leave_request.id leave_request_id,"
                    "leave_request.status leave_status "
                    "FROM public.roster_assignments roster "
                    "JOIN public.employees employee ON employee.id=roster.employee_id "
                    "AND employee.company_id=roster.company_id "
                    "AND employee.branch_id=roster.branch_id "
                    "JOIN public.leave_requests leave_request "
                    "ON leave_request.employee_id=roster.employee_id "
                    "AND leave_request.company_id=roster.company_id "
                    "AND leave_request.branch_id=roster.branch_id "
                    "AND roster.date BETWEEN leave_request.start_date AND leave_request.end_date "
                    "AND leave_request.status IN ('Approved','ManagerApproved') "
                    "WHERE roster.company_id=:company AND roster.branch_id=:branch "
                    "AND roster.date BETWEEN :start AND :end "
                    "ORDER BY roster.date,roster.employee_id,leave_request.id"
                ),
                {"company": company_id, "branch": branch_id, "start": start, "end": end},
            )
        ).mappings()
        override_digests = set(
            (
                await self.connection.execute(
                    text(
                        "SELECT violation_digest FROM public.compliance_overrides "
                        "WHERE company_id=:company AND branch_id=:branch "
                        "AND override_type='roster_publish' AND roster_month=:period"
                    ),
                    {"company": company_id, "branch": branch_id, "period": period},
                )
            ).scalars()
        )
        leave_conflicts: list[RosterLeaveConflictResponse] = []
        for row in leave_rows:
            snapshot: dict[str, Any] = {
                "code": "leave_conflict",
                "period": period,
                "branchId": str(branch_id),
                "rosterAssignmentId": str(row["roster_assignment_id"]),
                "employeeId": str(row["employee_id"]),
                "date": row["date"].isoformat(),
                "leaveRequestId": str(row["leave_request_id"]),
                "leaveStatus": row["leave_status"],
            }
            digest = _violation_digest(snapshot)
            leave_conflicts.append(
                RosterLeaveConflictResponse.model_validate(
                    {
                        **dict(row),
                        "violation_digest": digest,
                        "overridden": digest in override_digests,
                    }
                )
            )
        staffing_enforced = bool(
            await self.connection.scalar(
                text(
                    "SELECT enable_staffing_rules FROM public.branches "
                    "WHERE id=:branch AND company_id=:company"
                ),
                {"company": company_id, "branch": branch_id},
            )
        )
        if not staffing_enforced:
            return RosterValidationResponse(
                period=period,
                staffing_enforced=False,
                leave_conflicts=leave_conflicts,
                staffing_violations=None,
                ready=all(item.overridden for item in leave_conflicts),
            )
        staffing_rows = (
            await self.connection.execute(
                text(
                    "WITH dates AS (SELECT generate_series(CAST(:start AS date),"
                    "CAST(:end AS date),'1 day')::date attendance_day),"
                    "ranked AS (SELECT rule.id rule_id,rule.department,rule.shift_category,"
                    "rule.min_staff required,dates.attendance_day,row_number() OVER ("
                    "PARTITION BY dates.attendance_day,"
                    "rule.department,rule.shift_category "
                    "ORDER BY rule.effective_from DESC NULLS LAST,"
                    "rule.id DESC) rank FROM dates JOIN public.department_staffing_rules rule "
                    "ON rule.company_id=:company AND rule.branch_id=:branch "
                    "AND (rule.effective_from IS NULL "
                    "OR rule.effective_from<=dates.attendance_day) "
                    "AND (rule.effective_to IS NULL "
                    "OR rule.effective_to>=dates.attendance_day)),"
                    "counts AS (SELECT roster.date attendance_day,employee.department,"
                    "shift.shift_category,"
                    "count(*)::integer assigned FROM public.roster_assignments roster "
                    "JOIN public.employees employee ON employee.id=roster.employee_id "
                    "AND employee.company_id=roster.company_id "
                    "AND employee.branch_id=roster.branch_id "
                    "JOIN public.shifts shift ON shift.id=roster.shift_id "
                    "AND shift.company_id=roster.company_id AND shift.branch_id=roster.branch_id "
                    "WHERE roster.company_id=:company AND roster.branch_id=:branch "
                    "AND roster.date BETWEEN :start AND :end AND employee.active "
                    "AND employee.employment_status IN ('Active','Probation') AND shift.is_active "
                    "GROUP BY roster.date,employee.department,shift.shift_category) "
                    "SELECT ranked.rule_id,ranked.department,ranked.attendance_day date,"
                    "ranked.shift_category,"
                    "ranked.required,coalesce(counts.assigned,0)::integer assigned "
                    "FROM ranked LEFT JOIN counts "
                    "ON counts.attendance_day=ranked.attendance_day "
                    "AND counts.department=ranked.department "
                    "AND counts.shift_category=ranked.shift_category WHERE ranked.rank=1 "
                    "AND coalesce(counts.assigned,0)<ranked.required "
                    "ORDER BY ranked.attendance_day,ranked.department,"
                    "ranked.shift_category,ranked.rule_id"
                ),
                {"company": company_id, "branch": branch_id, "start": start, "end": end},
            )
        ).mappings()
        violations: list[RosterStaffingViolationResponse] = []
        for row in staffing_rows:
            assigned = int(row["assigned"])
            required = int(row["required"])
            snapshot: dict[str, Any] = {
                "code": "staffing_shortfall",
                "period": period,
                "branchId": str(branch_id),
                "ruleId": str(row["rule_id"]),
                "department": row["department"],
                "date": row["date"].isoformat(),
                "shiftCategory": row["shift_category"],
                "required": required,
                "assigned": assigned,
                "deficit": required - assigned,
            }
            digest = _violation_digest(snapshot)
            violations.append(
                RosterStaffingViolationResponse(
                    department=row["department"],
                    date=row["date"],
                    shift_category=row["shift_category"],
                    required=required,
                    assigned=assigned,
                    deficit=required - assigned,
                    rule_id=row["rule_id"],
                    violation_digest=digest,
                    overridden=digest in override_digests,
                )
            )
        return RosterValidationResponse(
            period=period,
            staffing_enforced=True,
            leave_conflicts=leave_conflicts,
            staffing_violations=violations,
            ready=all(item.overridden for item in leave_conflicts)
            and all(item.overridden for item in violations),
        )

    async def create_override(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        violation_digest: str,
        reason: str,
    ) -> RosterComplianceOverrideResponse:
        validation = await self.validation(company_id, branch_id, period)
        leave_conflict = next(
            (
                item
                for item in validation.leave_conflicts
                if item.violation_digest == violation_digest and not item.overridden
            ),
            None,
        )
        staffing_violation = next(
            (
                item
                for item in validation.staffing_violations or []
                if item.violation_digest == violation_digest and not item.overridden
            ),
            None,
        )
        if leave_conflict is None and staffing_violation is None:
            raise ServiceExecutionError("state_conflict")
        if leave_conflict is not None:
            rule_code = "leave_conflict"
            snapshot = {
                "code": rule_code,
                "period": period,
                "branchId": str(branch_id),
                "rosterAssignmentId": str(leave_conflict.roster_assignment_id),
                "employeeId": str(leave_conflict.employee_id),
                "date": leave_conflict.date.isoformat(),
                "leaveRequestId": str(leave_conflict.leave_request_id),
                "leaveStatus": leave_conflict.leave_status,
            }
        else:
            assert staffing_violation is not None
            rule_code = "staffing_shortfall"
            snapshot = {
                "code": rule_code,
                "period": period,
                "branchId": str(branch_id),
                "ruleId": str(staffing_violation.rule_id),
                "department": staffing_violation.department,
                "date": staffing_violation.date.isoformat(),
                "shiftCategory": staffing_violation.shift_category,
                "required": staffing_violation.required,
                "assigned": staffing_violation.assigned,
                "deficit": staffing_violation.deficit,
            }
        override_id = uuid.uuid4()
        try:
            await self.connection.execute(
                text(
                    "SELECT public.create_roster_compliance_override"
                    "(:id,:period,:rule_code,:digest,:reason,CAST(:snapshot AS jsonb))"
                ),
                {
                    "id": override_id,
                    "period": period,
                    "rule_code": rule_code,
                    "digest": violation_digest,
                    "reason": reason,
                    "snapshot": json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
                },
            )
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        row = (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,roster_month period,rule_code,violation_digest,"
                        "violation_snapshot,reason,created_at FROM public.compliance_overrides "
                        "WHERE id=:id AND company_id=:company AND branch_id=:branch"
                    ),
                    {"id": override_id, "company": company_id, "branch": branch_id},
                )
            )
            .mappings()
            .one()
        )
        return RosterComplianceOverrideResponse.model_validate(dict(row))

    async def exists(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID,
    ) -> bool:
        table = {
            "roster_assignment": "roster_assignments",
            "compliance_override": "compliance_overrides",
        }.get(kind)
        if table is None:
            return False
        return bool(
            await self.connection.scalar(
                text(
                    f"SELECT EXISTS(SELECT 1 FROM public.{table} WHERE id=:id "
                    "AND company_id=:company AND branch_id=:branch)"
                ),
                {"id": resource_id, "company": company_id, "branch": branch_id},
            )
        )
