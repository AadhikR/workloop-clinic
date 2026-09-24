from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.repositories.roster import RosterRepository, period_dates
from app.schemas.roster_publication import (
    ColleagueScheduleEntryResponse,
    PublishedScheduleEntryResponse,
    RosterActualHoursRequest,
    RosterOvertimeApprovalRequest,
    RosterPublicationResponse,
    RosterPublishRequest,
)
from app.services.execution import ServiceExecutionError

ZERO = Decimal("0.00")


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _number(value: Decimal | None) -> str | None:
    return None if value is None else f"{value.quantize(Decimal('0.01')):.2f}"


def _canonical(payload: dict[str, Any]) -> tuple[str, str]:
    value = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return value, "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _digest_ids(values: list[uuid.UUID]) -> str:
    canonical = json.dumps([str(value) for value in sorted(values)], separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def _publication(row: RowMapping) -> RosterPublicationResponse:
    return RosterPublicationResponse.model_validate(dict(row))


class RosterPublicationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def _ensure_month(self, company_id: uuid.UUID, branch_id: uuid.UUID, period: str) -> None:
        await self.connection.execute(
            text(
                "INSERT INTO public.roster_months(company_id,branch_id,period) "
                "VALUES (:company,:branch,:period) ON CONFLICT (branch_id,period) DO NOTHING"
            ),
            {"company": company_id, "branch": branch_id, "period": period},
        )

    async def _month(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        *,
        lock: bool = False,
    ) -> RowMapping | None:
        suffix = " FOR UPDATE OF month" if lock else ""
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT month.id,month.period,month.status,month.version,"
                        "month.current_version_id,month.source_version,month.published_at,"
                        "month.published_by_app_user_id,"
                        "coalesce(version.record_count,0)::integer record_count "
                        "FROM public.roster_months month LEFT JOIN "
                        "public.roster_publication_versions version "
                        "ON version.id=month.current_version_id "
                        "WHERE month.company_id=:company AND month.branch_id=:branch "
                        "AND month.period=:period" + suffix
                    ),
                    {"company": company_id, "branch": branch_id, "period": period},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def detail(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> RosterPublicationResponse:
        row = await self._month(company_id, branch_id, period)
        if row is None:
            return RosterPublicationResponse(
                id=None,
                period=period,
                status="draft",
                version=0,
                current_version_id=None,
                source_version=None,
                published_at=None,
                published_by_app_user_id=None,
                record_count=0,
            )
        return _publication(row)

    async def _lock_publish_inputs(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> tuple[RowMapping, list[RowMapping]]:
        start, end = period_dates(period)
        await self._ensure_month(company_id, branch_id, period)
        month = await self._month(company_id, branch_id, period, lock=True)
        assert month is not None
        rows = list(
            (
                await self.connection.execute(
                    text(
                        "SELECT roster.id,roster.version,roster.employee_id,"
                        "employee.name employee_name,"
                        "employee.department,employee.active,employee.employment_status,"
                        "employee.employment_start_date,employee.termination_date,"
                        "roster.shift_id,shift.name shift_name,shift.code shift_code,"
                        "shift.shift_category,shift.is_active,roster.date,roster.planned_hours,"
                        "roster.notes,roster.published FROM public.roster_assignments roster "
                        "JOIN public.employees employee ON employee.id=roster.employee_id "
                        "AND employee.company_id=roster.company_id "
                        "AND employee.branch_id=roster.branch_id "
                        "JOIN public.shifts shift ON shift.id=roster.shift_id "
                        "AND shift.company_id=roster.company_id "
                        "AND shift.branch_id=roster.branch_id "
                        "WHERE roster.company_id=:company AND roster.branch_id=:branch "
                        "AND roster.date BETWEEN :start AND :end "
                        "ORDER BY roster.id FOR UPDATE OF roster,employee,shift"
                    ),
                    {
                        "company": company_id,
                        "branch": branch_id,
                        "start": start,
                        "end": end,
                    },
                )
            ).mappings()
        )
        await self.connection.execute(
            text(
                "SELECT id FROM public.leave_requests WHERE company_id=:company "
                "AND branch_id=:branch AND start_date<=:end AND end_date>=:start "
                "ORDER BY id FOR SHARE"
            ),
            {"company": company_id, "branch": branch_id, "start": start, "end": end},
        )
        await self.connection.execute(
            text(
                "SELECT id FROM public.department_staffing_rules WHERE company_id=:company "
                "AND branch_id=:branch AND (effective_from IS NULL OR effective_from<=:end) "
                "AND (effective_to IS NULL OR effective_to>=:start) ORDER BY id FOR SHARE"
            ),
            {"company": company_id, "branch": branch_id, "start": start, "end": end},
        )
        await self.connection.execute(
            text("SELECT public.phase10h_lock_roster_overrides(:period)"),
            {"period": period},
        )
        return month, rows

    @staticmethod
    def _base_memberships(rows: list[RowMapping]) -> list[dict[str, Any]]:
        return [
            {
                "source_assignment_id": row["id"],
                "source_assignment_version": int(row["version"]) + 1,
                "employee_id": row["employee_id"],
                "employee_name": row["employee_name"],
                "department": row["department"],
                "shift_id": row["shift_id"],
                "shift_name": row["shift_name"],
                "shift_code": row["shift_code"],
                "shift_category": row["shift_category"],
                "date": row["date"],
                "planned_hours": Decimal(row["planned_hours"]),
                "notes": row["notes"],
                "actual_evidence_id": None,
                "actual_hours": None,
                "overtime_approval_id": None,
                "overtime_hours": ZERO,
                "overtime_amount": ZERO,
                "attendance_overlap_hours": ZERO,
                "attendance_source_ids": [],
                "salary_source_version": None,
            }
            for row in rows
        ]

    @staticmethod
    def _membership_payload(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "actualEvidenceId": (
                str(row["actual_evidence_id"]) if row["actual_evidence_id"] else None
            ),
            "actualHours": _number(row["actual_hours"]),
            "attendanceOverlapHours": _number(row["attendance_overlap_hours"]),
            "attendanceSourceIds": [str(value) for value in row["attendance_source_ids"]],
            "date": row["date"].isoformat(),
            "department": row["department"],
            "employeeId": str(row["employee_id"]),
            "employeeName": row["employee_name"],
            "notes": row["notes"],
            "overtimeApprovalId": (
                str(row["overtime_approval_id"]) if row["overtime_approval_id"] else None
            ),
            "overtimeAmount": _number(row["overtime_amount"]),
            "overtimeHours": _number(row["overtime_hours"]),
            "plannedHours": _number(row["planned_hours"]),
            "rosterAssignmentId": str(row["source_assignment_id"]),
            "rosterAssignmentVersion": row["source_assignment_version"],
            "salarySourceVersion": row["salary_source_version"],
            "shiftCategory": row["shift_category"],
            "shiftCode": row["shift_code"],
            "shiftId": str(row["shift_id"]),
            "shiftName": row["shift_name"],
        }

    async def _create_version(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        month: RowMapping,
        actor_id: uuid.UUID,
        kind: str,
        reason: str,
        published_at: datetime,
        memberships: list[dict[str, Any]],
    ) -> RosterPublicationResponse:
        version_number = int(month["version"]) + 1
        version_id = uuid.uuid4()
        payload = {
            "branchId": str(branch_id),
            "companyId": str(company_id),
            "kind": kind,
            "memberships": [
                self._membership_payload(row)
                for row in sorted(
                    memberships,
                    key=lambda item: (
                        item["date"],
                        item["employee_id"],
                        item["source_assignment_id"],
                    ),
                )
            ],
            "period": month["period"],
            "publishedAt": _iso(published_at),
            "version": version_number,
        }
        canonical, source_version = _canonical(payload)
        assignment_ids = [row["source_assignment_id"] for row in memberships]
        await self.connection.execute(
            text(
                "INSERT INTO public.roster_publication_versions("
                "id,company_id,branch_id,roster_month_id,prior_version_id,period,version,kind,"
                "source_version,source_canonical,source_payload,affected_row_digest,record_count,"
                "actor_app_user_id,reason,published_at) VALUES ("
                ":id,:company,:branch,:month,:prior,:period,:version,:kind,:source_version,"
                ":canonical,CAST(:payload AS jsonb),:digest,:count,:actor,:reason,:published_at)"
            ),
            {
                "id": version_id,
                "company": company_id,
                "branch": branch_id,
                "month": month["id"],
                "prior": month["current_version_id"],
                "period": month["period"],
                "version": version_number,
                "kind": kind,
                "source_version": source_version,
                "canonical": canonical,
                "payload": canonical,
                "digest": _digest_ids(assignment_ids),
                "count": len(memberships),
                "actor": actor_id,
                "reason": reason,
                "published_at": published_at,
            },
        )
        statement = text(
            "INSERT INTO public.roster_publication_memberships("
            "id,company_id,branch_id,publication_version_id,source_assignment_id,"
            "source_assignment_version,employee_id,employee_name,department,shift_id,shift_name,"
            "shift_code,shift_category,date,planned_hours,notes,actual_evidence_id,actual_hours,"
            "overtime_approval_id,overtime_hours,overtime_amount,attendance_overlap_hours,"
            "attendance_source_ids,salary_source_version,source_payload) VALUES ("
            ":id,:company,:branch,:version_id,:source_assignment_id,"
            ":source_assignment_version,:employee_id,:employee_name,:department,:shift_id,"
            ":shift_name,:shift_code,:shift_category,:date,:planned_hours,:notes,"
            ":actual_evidence_id,:actual_hours,:overtime_approval_id,:overtime_hours,"
            ":overtime_amount,:attendance_overlap_hours,:attendance_source_ids,"
            ":salary_source_version,CAST(:source_payload AS jsonb))"
        ).bindparams(bindparam("attendance_source_ids", type_=ARRAY(UUID(as_uuid=True))))
        for row in memberships:
            source_payload = json.dumps(
                self._membership_payload(row), sort_keys=True, separators=(",", ":")
            )
            await self.connection.execute(
                statement,
                {
                    "id": uuid.uuid4(),
                    "company": company_id,
                    "branch": branch_id,
                    "version_id": version_id,
                    **row,
                    "source_payload": source_payload,
                },
            )
        await self.connection.execute(
            text(
                "UPDATE public.roster_months SET status='published',version=:version,"
                "current_version_id=:version_id,source_version=:source_version,"
                "published_at=:published_at,published_by_app_user_id=:actor,updated_at=now() "
                "WHERE id=:id AND company_id=:company AND branch_id=:branch"
            ),
            {
                "version": version_number,
                "version_id": version_id,
                "source_version": source_version,
                "published_at": published_at,
                "actor": actor_id,
                "id": month["id"],
                "company": company_id,
                "branch": branch_id,
            },
        )
        row = await self._month(company_id, branch_id, month["period"])
        assert row is not None
        return _publication(row)

    async def publish(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        period: str,
        request: RosterPublishRequest,
    ) -> RosterPublicationResponse:
        month, rows = await self._lock_publish_inputs(company_id, branch_id, period)
        if month["status"] != "draft" or month["source_version"] != request.expected_source_version:
            raise ServiceExecutionError("state_conflict")
        if not rows or any(row["published"] for row in rows):
            raise ServiceExecutionError("roster_publication_not_ready")
        expected = [(item.id, item.expected_version) for item in request.assignments]
        if expected != sorted(expected) or len({item[0] for item in expected}) != len(expected):
            raise ServiceExecutionError("validation_failed")
        actual = sorted((row["id"], int(row["version"])) for row in rows)
        if expected != actual:
            raise ServiceExecutionError("state_conflict")
        for row in rows:
            if (
                not row["active"]
                or row["employment_status"] not in {"Active", "Probation"}
                or not row["is_active"]
                or (
                    row["employment_start_date"] is not None
                    and row["date"] < row["employment_start_date"]
                )
                or (row["termination_date"] is not None and row["date"] > row["termination_date"])
            ):
                raise ServiceExecutionError("roster_publication_not_ready")
        validation = await RosterRepository(self.connection).validation(
            company_id, branch_id, period
        )
        if not validation.ready:
            raise ServiceExecutionError("roster_publication_not_ready")
        await self.connection.execute(
            text("SELECT public.phase10h_publish_assignments(:ids,:versions)"),
            {
                "ids": [item[0] for item in expected],
                "versions": [item[1] for item in expected],
            },
        )
        for assignment_id, _version in expected:
            await self.connection.execute(
                text("SELECT public.create_workflow_notification('roster_published',:source_id)"),
                {"source_id": str(assignment_id)},
            )
        published_at = (
            await self.connection.execute(text("SELECT clock_timestamp()"))
        ).scalar_one()
        return await self._create_version(
            company_id=company_id,
            branch_id=branch_id,
            month=month,
            actor_id=actor_id,
            kind="publication",
            reason="",
            published_at=published_at,
            memberships=self._base_memberships(rows),
        )

    async def _locked_current(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period: str, source_version: str
    ) -> tuple[RowMapping, list[dict[str, Any]]]:
        month = await self._month(company_id, branch_id, period, lock=True)
        if (
            month is None
            or month["status"] != "published"
            or month["source_version"] != source_version
        ):
            raise ServiceExecutionError("state_conflict")
        rows = list(
            (
                await self.connection.execute(
                    text(
                        "SELECT source_assignment_id,source_assignment_version,employee_id,"
                        "employee_name,department,shift_id,shift_name,shift_code,shift_category,"
                        "date,planned_hours,notes,actual_evidence_id,actual_hours,"
                        "overtime_approval_id,overtime_hours,overtime_amount,"
                        "attendance_overlap_hours,attendance_source_ids,salary_source_version "
                        "FROM public.roster_publication_memberships "
                        "WHERE company_id=:company AND branch_id=:branch "
                        "AND publication_version_id=:version ORDER BY date,employee_id,"
                        "source_assignment_id FOR SHARE"
                    ),
                    {
                        "company": company_id,
                        "branch": branch_id,
                        "version": month["current_version_id"],
                    },
                )
            ).mappings()
        )
        if not rows or len(rows) != int(month["record_count"]):
            raise ServiceExecutionError("payroll_input_not_ready")
        return month, [dict(row) for row in rows]

    async def record_actual_hours(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        request: RosterActualHoursRequest,
    ) -> RosterPublicationResponse:
        month, rows = await self._locked_current(
            company_id, branch_id, period, request.expected_source_version
        )
        target = next((row for row in rows if row["source_assignment_id"] == assignment_id), None)
        if target is None:
            raise ServiceExecutionError("resource_not_found")
        evidence_id = uuid.uuid4()
        await self.connection.execute(
            text(
                "INSERT INTO public.roster_actual_hours_evidence("
                "id,company_id,branch_id,roster_month_id,source_assignment_id,employee_id,"
                "prior_evidence_id,actual_hours,evidence_source,reason,actor_app_user_id) VALUES ("
                ":id,:company,:branch,:month,:assignment,:employee,:prior,:hours,:source,"
                ":reason,:actor)"
            ),
            {
                "id": evidence_id,
                "company": company_id,
                "branch": branch_id,
                "month": month["id"],
                "assignment": assignment_id,
                "employee": target["employee_id"],
                "prior": target["actual_evidence_id"],
                "hours": request.actual_hours,
                "source": request.evidence_source,
                "reason": request.reason,
                "actor": actor_id,
            },
        )
        target.update(
            {
                "actual_evidence_id": evidence_id,
                "actual_hours": request.actual_hours,
                "overtime_approval_id": None,
                "overtime_hours": ZERO,
                "overtime_amount": ZERO,
                "attendance_overlap_hours": ZERO,
                "attendance_source_ids": [],
                "salary_source_version": None,
            }
        )
        published_at = (
            await self.connection.execute(text("SELECT clock_timestamp()"))
        ).scalar_one()
        return await self._create_version(
            company_id=company_id,
            branch_id=branch_id,
            month=month,
            actor_id=actor_id,
            kind="actual_hours",
            reason=request.reason,
            published_at=published_at,
            memberships=rows,
        )

    async def approve_overtime(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        request: RosterOvertimeApprovalRequest,
    ) -> RosterPublicationResponse:
        month, rows = await self._locked_current(
            company_id, branch_id, period, request.expected_source_version
        )
        target = next((row for row in rows if row["source_assignment_id"] == assignment_id), None)
        if target is None:
            raise ServiceExecutionError("resource_not_found")
        if target["actual_hours"] is None or target["actual_evidence_id"] is None:
            raise ServiceExecutionError("payroll_input_not_ready")
        overtime_hours = _money(Decimal(target["actual_hours"]) - Decimal(target["planned_hours"]))
        if overtime_hours <= ZERO or target["overtime_approval_id"] is not None:
            raise ServiceExecutionError("state_conflict")
        attendance_rows = list(
            (
                await self.connection.execute(
                    text(
                        "SELECT overtime_hours,source_clock_event_ids "
                        "FROM public.attendance_records "
                        "WHERE company_id=:company AND branch_id=:branch AND employee_id=:employee "
                        "AND date=:day ORDER BY id FOR SHARE"
                    ),
                    {
                        "company": company_id,
                        "branch": branch_id,
                        "employee": target["employee_id"],
                        "day": target["date"],
                    },
                )
            ).mappings()
        )
        attendance_overlap = sum(
            (Decimal(row["overtime_hours"]) for row in attendance_rows), start=ZERO
        )
        attendance_id_set: set[uuid.UUID] = set()
        for row in attendance_rows:
            attendance_id_set.update(cast(list[uuid.UUID], row["source_clock_event_ids"] or []))
        attendance_ids = sorted(attendance_id_set)
        if attendance_overlap != ZERO or request.attendance_source_ids != attendance_ids:
            raise ServiceExecutionError("payroll_input_not_ready")
        employee = (
            (
                await self.connection.execute(
                    text(
                        "SELECT basic_salary,updated_at FROM public.employees WHERE id=:employee "
                        "AND company_id=:company AND branch_id=:branch FOR SHARE"
                    ),
                    {
                        "employee": target["employee_id"],
                        "company": company_id,
                        "branch": branch_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        amount = _money(
            Decimal(employee["basic_salary"]) / Decimal(208) * Decimal("1.25") * overtime_hours
        )
        salary_source_version = _iso(employee["updated_at"])
        approval_id = uuid.uuid4()
        await self.connection.execute(
            text(
                "INSERT INTO public.roster_overtime_approvals("
                "id,company_id,branch_id,roster_month_id,source_assignment_id,"
                "actual_evidence_id,employee_id,overtime_hours,overtime_amount,"
                "attendance_overlap_hours,attendance_source_ids,salary_source_version,reason,"
                "actor_app_user_id) VALUES (:id,:company,:branch,:month,:assignment,:evidence,"
                ":employee,:hours,:amount,0,:attendance_ids,:salary_version,:reason,:actor)"
            ).bindparams(bindparam("attendance_ids", type_=ARRAY(UUID(as_uuid=True)))),
            {
                "id": approval_id,
                "company": company_id,
                "branch": branch_id,
                "month": month["id"],
                "assignment": assignment_id,
                "evidence": target["actual_evidence_id"],
                "employee": target["employee_id"],
                "hours": overtime_hours,
                "amount": amount,
                "attendance_ids": attendance_ids,
                "salary_version": salary_source_version,
                "reason": request.reason,
                "actor": actor_id,
            },
        )
        target.update(
            {
                "overtime_approval_id": approval_id,
                "overtime_hours": overtime_hours,
                "overtime_amount": amount,
                "attendance_overlap_hours": ZERO,
                "attendance_source_ids": attendance_ids,
                "salary_source_version": salary_source_version,
            }
        )
        published_at = (
            await self.connection.execute(text("SELECT clock_timestamp()"))
        ).scalar_one()
        return await self._create_version(
            company_id=company_id,
            branch_id=branch_id,
            month=month,
            actor_id=actor_id,
            kind="overtime_approval",
            reason=request.reason,
            published_at=published_at,
            memberships=rows,
        )

    async def personal_schedule(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID, period: str
    ) -> list[PublishedScheduleEntryResponse]:
        rows = (
            await self.connection.execute(
                text(
                    "SELECT membership.source_assignment_id roster_assignment_id,"
                    "membership.employee_id,membership.employee_name,membership.department,"
                    "membership.shift_id,membership.shift_name,membership.shift_code,"
                    "membership.shift_category,membership.date,membership.planned_hours,"
                    "membership.actual_hours,membership.overtime_hours,membership.notes,"
                    "month.source_version,month.version publication_version,month.published_at "
                    "FROM public.roster_months month JOIN public.roster_publication_memberships "
                    "membership ON membership.publication_version_id=month.current_version_id "
                    "AND membership.company_id=month.company_id "
                    "AND membership.branch_id=month.branch_id "
                    "WHERE month.company_id=:company AND month.branch_id=:branch "
                    "AND month.period=:period AND month.status='published' "
                    "AND membership.employee_id=:employee "
                    "ORDER BY membership.date,membership.source_assignment_id"
                ),
                {
                    "company": company_id,
                    "branch": branch_id,
                    "employee": employee_id,
                    "period": period,
                },
            )
        ).mappings()
        return [PublishedScheduleEntryResponse.model_validate(dict(row)) for row in rows]

    async def colleagues(self, day: date) -> list[ColleagueScheduleEntryResponse]:
        rows = (
            await self.connection.execute(
                text(
                    "SELECT employee_id,employee_name,roster_assignment_id,shift_id,"
                    "shift_name,shift_code,shift_category,work_date date "
                    "FROM public.phase10h_colleague_schedule(:day)"
                ),
                {"day": day},
            )
        ).mappings()
        return [ColleagueScheduleEntryResponse.model_validate(dict(row)) for row in rows]

    async def exists(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, version_id: uuid.UUID
    ) -> bool:
        return bool(
            await self.connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM public.roster_publication_versions "
                    "WHERE id=:id AND company_id=:company AND branch_id=:branch)"
                ),
                {"id": version_id, "company": company_id, "branch": branch_id},
            )
        )
