from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.schemas.attendance_periods import (
    AttendancePeriodBlockerResponse,
    AttendancePeriodResponse,
)
from app.services.execution import ServiceExecutionError


def period_dates(period: str, business_date: date) -> tuple[date, date]:
    year, month = (int(part) for part in period.split("-"))
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start, min(end, business_date)


def _period(
    row: RowMapping, blockers: list[AttendancePeriodBlockerResponse]
) -> AttendancePeriodResponse:
    return AttendancePeriodResponse(
        id=row["id"],
        period=row["period"],
        status=row["status"],
        payroll_ready=row["payroll_ready"],
        version=row["version"],
        blocker_count=sum(item.count for item in blockers),
        blockers=blockers,
        source_version=row["source_version"],
        closed_at=row["closed_at"],
        closed_by_actor_name="Administrator" if row["closed_by_app_user_id"] else None,
        amendment_reason=row["amendment_reason"],
    )


class AttendancePeriodRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()

    async def _ensure_period(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> None:
        await self.connection.execute(
            text(
                "INSERT INTO public.attendance_periods(company_id,branch_id,period) "
                "VALUES (:company_id,:branch_id,:period) ON CONFLICT (branch_id,period) DO NOTHING"
            ),
            {"company_id": company_id, "branch_id": branch_id, "period": period},
        )

    async def row(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        *,
        lock: bool = False,
    ) -> RowMapping | None:
        suffix = " FOR UPDATE OF attendance_period" if lock else ""
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT attendance_period.*,period_version.amendment_reason "
                        "FROM public.attendance_periods attendance_period "
                        "LEFT JOIN public.attendance_period_versions period_version "
                        "ON period_version.id=attendance_period.current_version_id "
                        "WHERE attendance_period.company_id=:company_id "
                        "AND attendance_period.branch_id=:branch_id "
                        "AND attendance_period.period=:period" + suffix
                    ),
                    {"company_id": company_id, "branch_id": branch_id, "period": period},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def list(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
    ) -> list[RowMapping]:
        marker = ""
        parameters: dict[str, object] = {
            "company_id": company_id,
            "branch_id": branch_id,
            "limit": limit,
        }
        if after is not None:
            marker = (
                " AND (attendance_period.period<:after_period OR "
                "(attendance_period.period=:after_period "
                "AND attendance_period.id>:after_id))"
            )
            parameters.update(after_period=after[0], after_id=after[1])
        return list(
            (
                await self.connection.execute(
                    text(
                        "SELECT attendance_period.*,period_version.amendment_reason "
                        "FROM public.attendance_periods attendance_period "
                        "LEFT JOIN public.attendance_period_versions period_version "
                        "ON period_version.id=attendance_period.current_version_id "
                        "WHERE attendance_period.company_id=:company_id "
                        "AND attendance_period.branch_id=:branch_id"
                        + marker
                        + " ORDER BY attendance_period.period DESC,"
                        "attendance_period.id LIMIT :limit"
                    ),
                    parameters,
                )
            ).mappings()
        )

    async def position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period_id: uuid.UUID
    ) -> tuple[str, uuid.UUID]:
        row = (
            (
                await self.connection.execute(
                    text(
                        "SELECT period,id FROM public.attendance_periods "
                        "WHERE company_id=:company_id AND branch_id=:branch_id AND id=:id"
                    ),
                    {"company_id": company_id, "branch_id": branch_id, "id": period_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("invalid_cursor")
        return row["period"], row["id"]

    async def blockers(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        business_date: date,
    ) -> list[AttendancePeriodBlockerResponse]:
        start, end = period_dates(period, business_date)
        if end < start:
            return [AttendancePeriodBlockerResponse(code="missing_calculation_days", count=1)]
        rows = (
            await self.connection.execute(
                text(
                    """
WITH counts AS (
  SELECT 'missing_clock_outs'::text code,count(*)::bigint count
  FROM public.attendance_records record
  WHERE record.company_id=:company_id AND record.branch_id=:branch_id
    AND record.date BETWEEN :start AND :end AND record.missing_clock_out
  UNION ALL
  SELECT 'unresolved_absences',count(*) FROM public.attendance_records record
  WHERE record.company_id=:company_id AND record.branch_id=:branch_id
    AND record.date BETWEEN :start AND :end
    AND record.status='UNEXPLAINED_ABSENCE' AND record.resolution_type=''
  UNION ALL
  SELECT 'pending_corrections',count(*) FROM public.regularisation_requests request
  WHERE request.company_id=:company_id AND request.branch_id=:branch_id
    AND request.attendance_date BETWEEN :start AND :end AND request.status='Pending'
  UNION ALL
  SELECT 'unapproved_overtime',count(*) FROM public.attendance_records record
  JOIN public.attendance_settings settings
    ON settings.company_id=record.company_id AND settings.branch_id=record.branch_id
  WHERE record.company_id=:company_id AND record.branch_id=:branch_id
    AND record.date BETWEEN :start AND :end AND settings.overtime_requires_approval
    AND record.overtime_hours>0 AND NOT record.overtime_approved
  UNION ALL
  SELECT 'stale_source_snapshots',count(*) FROM public.attendance_records record
  WHERE record.company_id=:company_id AND record.branch_id=:branch_id
    AND record.date BETWEEN :start AND :end AND record.source_stale
  UNION ALL
  SELECT 'ambiguous_events',count(*) FROM public.attendance_records record
  WHERE record.company_id=:company_id AND record.branch_id=:branch_id
    AND record.date BETWEEN :start AND :end
    AND record.evidence_flags && ARRAY[
      'ambiguous_events','unmatched_clock_out','negative_interval','missing_split_interval'
    ]::text[]
  UNION ALL
  SELECT 'salary_source_changed',count(*) FROM public.attendance_records record
  JOIN public.employees employee ON employee.id=record.employee_id
    AND employee.company_id=record.company_id AND employee.branch_id=record.branch_id
  WHERE record.company_id=:company_id AND record.branch_id=:branch_id
    AND record.date BETWEEN :start AND :end
    AND (
      (record.source_snapshot#>>'{employment,basic_salary}')::numeric
        IS DISTINCT FROM employee.basic_salary
      OR (record.source_snapshot#>>'{employment,updated_at}')::timestamptz
        IS DISTINCT FROM employee.updated_at
    )
  UNION ALL
  SELECT 'missing_calculation_days',count(*) FROM (
    SELECT employee.id,day::date
    FROM public.employees employee
    CROSS JOIN LATERAL generate_series(
      CAST(:start AS date),CAST(:end AS date),interval '1 day'
    ) day
    WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
      AND employee.active AND employee.employment_status IN ('Active','Probation','On Leave')
      AND (employee.employment_start_date IS NULL OR employee.employment_start_date<=day::date)
      AND (employee.termination_date IS NULL OR employee.termination_date>=day::date)
      AND NOT EXISTS (
        SELECT 1 FROM public.attendance_records record
        WHERE record.company_id=:company_id AND record.branch_id=:branch_id
          AND record.employee_id=employee.id AND record.date=day::date
      )
  ) missing
)
SELECT code,count FROM counts WHERE count>0 ORDER BY code
"""
                ),
                {
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "start": start,
                    "end": end,
                },
            )
        ).mappings()
        return [
            AttendancePeriodBlockerResponse(code=row["code"], count=int(row["count"]))
            for row in rows
        ]

    async def response(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> AttendancePeriodResponse:
        row = await self.row(company_id, branch_id, period)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        blockers = (
            []
            if row["payroll_ready"]
            else await self.blockers(company_id, branch_id, period, await self.business_date())
        )
        return _period(row, blockers)

    async def list_responses(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
    ) -> list[AttendancePeriodResponse]:
        rows = await self.list(company_id, branch_id, after, limit)
        business_date = await self.business_date()
        result: list[AttendancePeriodResponse] = []
        for row in rows:
            blockers = (
                []
                if row["payroll_ready"]
                else await self.blockers(company_id, branch_id, row["period"], business_date)
            )
            result.append(_period(row, blockers))
        return result

    async def _lock_sources(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        start: date,
        end: date,
    ) -> tuple[RowMapping, list[RowMapping], list[uuid.UUID]]:
        await self._ensure_period(company_id, branch_id, period)
        period_row = await self.row(company_id, branch_id, period, lock=True)
        assert period_row is not None
        records = list(
            (
                await self.connection.execute(
                    text(
                        "SELECT record.*,employee.updated_at employee_updated_at,"
                        "employee.basic_salary employee_basic_salary,"
                        "settings.overtime_requires_approval "
                        "FROM public.attendance_records record "
                        "JOIN public.employees employee ON employee.id=record.employee_id "
                        "AND employee.company_id=record.company_id "
                        "AND employee.branch_id=record.branch_id "
                        "JOIN public.attendance_settings settings "
                        "ON settings.company_id=record.company_id "
                        "AND settings.branch_id=record.branch_id "
                        "WHERE record.company_id=:company_id AND record.branch_id=:branch_id "
                        "AND record.date BETWEEN :start AND :end "
                        "ORDER BY record.id FOR UPDATE OF record,employee,settings"
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "start": start,
                        "end": end,
                    },
                )
            ).mappings()
        )
        await self.connection.execute(
            text(
                "SELECT id FROM public.regularisation_requests "
                "WHERE company_id=:company_id AND branch_id=:branch_id "
                "AND attendance_date BETWEEN :start AND :end ORDER BY id FOR UPDATE"
            ),
            {"company_id": company_id, "branch_id": branch_id, "start": start, "end": end},
        )
        event_end = datetime.combine(end + timedelta(days=2), datetime.min.time())
        event_start = datetime.combine(start - timedelta(days=1), datetime.min.time())
        events = list(
            (
                await self.connection.execute(
                    text(
                        "SELECT public.phase10f_lock_clock_events("
                        ":company_id,:branch_id,:event_start,:event_end) id"
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "event_start": event_start,
                        "event_end": event_end,
                    },
                )
            ).mappings()
        )
        return period_row, records, [row["id"] for row in events]

    async def close(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        period: str,
        expected_version: int,
        amendment_reason: str | None,
    ) -> AttendancePeriodResponse:
        business_date = await self.business_date()
        start, end = period_dates(period, business_date)
        if start > business_date:
            raise ServiceExecutionError("validation_failed")
        period_row, records, event_ids = await self._lock_sources(
            company_id, branch_id, period, start, end
        )
        current_version = int(period_row["version"])
        if period_row["payroll_ready"] and expected_version == 0 and amendment_reason is None:
            return _period(period_row, [])
        if expected_version != current_version:
            raise ServiceExecutionError("state_conflict")
        if current_version == 0 and amendment_reason is not None:
            raise ServiceExecutionError("state_conflict")
        if current_version > 0 and amendment_reason is None:
            raise ServiceExecutionError("state_conflict")
        if current_version > 0:
            prior_payload_value = (
                await self.connection.execute(
                    text(
                        "SELECT source_payload FROM public.attendance_period_versions "
                        "WHERE id=:version_id AND company_id=:company_id "
                        "AND branch_id=:branch_id"
                    ),
                    {
                        "version_id": period_row["current_version_id"],
                        "company_id": company_id,
                        "branch_id": branch_id,
                    },
                )
            ).scalar_one()
            if not isinstance(prior_payload_value, dict):
                raise ServiceExecutionError("state_conflict")
            prior_payload = cast(dict[str, object], prior_payload_value)
            prior_evidence_value = prior_payload.get("evidenceIds", [])
            if not isinstance(prior_evidence_value, list):
                raise ServiceExecutionError("state_conflict")
            prior_evidence_items = cast(list[object], prior_evidence_value)
            prior_evidence = [str(value) for value in prior_evidence_items]
            current_evidence = sorted(str(value) for value in event_ids)
            if current_evidence == prior_evidence:
                raise ServiceExecutionError("state_conflict")
        blockers = await self.blockers(company_id, branch_id, period, business_date)
        if blockers:
            raise ServiceExecutionError("attendance_period_not_ready")

        version_number = current_version + 1
        record_payloads: list[dict[str, object]] = []
        for record in records:
            source_snapshot = cast(dict[str, object], dict(record["source_snapshot"]))
            employment = source_snapshot.get("employment")
            salary_version = ""
            if isinstance(employment, dict):
                employment_values = cast(dict[str, object], employment)
                salary_version = str(employment_values.get("updated_at", ""))
            standard = record["overtime_type"] in {"STANDARD", "NIGHT_SHIFT"}
            rest_day = record["overtime_type"] in {"REST_DAY_NO_SUB", "REST_DAY_WITH_SUB"}
            overtime_allowed = bool(
                record["overtime_approved"] or not record["overtime_requires_approval"]
            )
            overtime_hours = Decimal(record["overtime_hours"])
            overtime_amount = Decimal(record["overtime_amount"])
            standard_hours = overtime_hours if standard and overtime_allowed else Decimal()
            standard_amount = overtime_amount if standard and overtime_allowed else Decimal()
            rest_hours = overtime_hours if rest_day and overtime_allowed else Decimal()
            rest_amount = overtime_amount if rest_day and overtime_allowed else Decimal()
            item: dict[str, object] = {
                "sourceRecordId": str(record["id"]),
                "employeeId": str(record["employee_id"]),
                "date": record["date"].isoformat(),
                "absenceDays": "1.00"
                if record["status"] == "UNEXPLAINED_ABSENCE"
                and record["resolution_type"] == "UNAUTHORISED"
                else "0.00",
                "absenceAmount": f"{Decimal(record['absence_deduction']):.2f}",
                "lateMinutes": int(record["late_minutes"]),
                "lateAmount": f"{Decimal(record['late_deduction']):.2f}",
                "standardOvertimeHours": f"{standard_hours:.2f}",
                "standardOvertimeAmount": f"{standard_amount:.2f}",
                "restDayOvertimeHours": f"{rest_hours:.2f}",
                "restDayOvertimeAmount": f"{rest_amount:.2f}",
                "calculationVersion": int(record["calculation_version"]),
                "sourceDigest": record["source_digest"],
                "sourceClockEventIds": sorted(
                    str(value) for value in record["source_clock_event_ids"]
                ),
                "salarySourceVersion": salary_version,
            }
            record_payloads.append(item)
        record_payloads.sort(key=lambda item: str(item["sourceRecordId"]))
        payload: dict[str, object] = {
            "scope": {"companyId": str(company_id), "branchId": str(branch_id)},
            "period": period,
            "version": version_number,
            "priorVersionId": None
            if period_row["current_version_id"] is None
            else str(period_row["current_version_id"]),
            "amendmentReason": amendment_reason,
            "affectedRowIds": [item["sourceRecordId"] for item in record_payloads],
            "evidenceIds": sorted(str(value) for value in event_ids),
            "records": record_payloads,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        source_version = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
        version_row = (
            (
                await self.connection.execute(
                    text(
                        "INSERT INTO public.attendance_period_versions"
                        "(company_id,branch_id,attendance_period_id,prior_version_id,period,version,"
                        "source_version,source_canonical,source_payload,record_count,amendment_reason,"
                        "closed_by_app_user_id) VALUES "
                        "(:company_id,:branch_id,:period_id,:prior_version_id,:period,:version,"
                        ":source_version,:source_canonical,CAST(:source_payload AS jsonb),"
                        ":record_count,"
                        ":amendment_reason,:actor_id) RETURNING id,closed_at"
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "period_id": period_row["id"],
                        "prior_version_id": period_row["current_version_id"],
                        "period": period,
                        "version": version_number,
                        "source_version": source_version,
                        "source_canonical": canonical,
                        "source_payload": canonical,
                        "record_count": len(record_payloads),
                        "amendment_reason": amendment_reason or "",
                        "actor_id": actor_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        for record, item in zip(records, record_payloads, strict=True):
            await self.connection.execute(
                text(
                    "INSERT INTO public.attendance_period_record_snapshots"
                    "(company_id,branch_id,period_version_id,source_record_id,employee_id,date,"
                    "absence_days,absence_amount,late_minutes,late_amount,standard_overtime_hours,"
                    "standard_overtime_amount,rest_day_overtime_hours,rest_day_overtime_amount,"
                    "calculation_version,source_digest,source_clock_event_ids,salary_source_version,"
                    "source_payload) VALUES (:company_id,:branch_id,:version_id,:record_id,"
                    ":employee_id,:date,:absence_days,:absence_amount,:late_minutes,:late_amount,"
                    ":standard_hours,:standard_amount,:rest_hours,:rest_amount,:calculation_version,"
                    ":source_digest,:event_ids,:salary_version,CAST(:source_payload AS jsonb))"
                ),
                {
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "version_id": version_row["id"],
                    "record_id": record["id"],
                    "employee_id": record["employee_id"],
                    "date": record["date"],
                    "absence_days": item["absenceDays"],
                    "absence_amount": item["absenceAmount"],
                    "late_minutes": item["lateMinutes"],
                    "late_amount": item["lateAmount"],
                    "standard_hours": item["standardOvertimeHours"],
                    "standard_amount": item["standardOvertimeAmount"],
                    "rest_hours": item["restDayOvertimeHours"],
                    "rest_amount": item["restDayOvertimeAmount"],
                    "calculation_version": item["calculationVersion"],
                    "source_digest": item["sourceDigest"],
                    "event_ids": record["source_clock_event_ids"],
                    "salary_version": item["salarySourceVersion"],
                    "source_payload": json.dumps(item, sort_keys=True, separators=(",", ":")),
                },
            )
        if current_version == 0:
            await self.connection.execute(
                text(
                    "UPDATE public.attendance_records SET period_closed=true "
                    "WHERE company_id=:company_id AND branch_id=:branch_id "
                    "AND date BETWEEN :start AND :end"
                ),
                {
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "start": start,
                    "end": end,
                },
            )
        await self.connection.execute(
            text(
                "UPDATE public.attendance_periods SET status='closed',payroll_ready=true,"
                "open_items=0,version=:version,current_version_id=:version_id,"
                "source_version=:source_version,closed_at=:closed_at,"
                "closed_by_app_user_id=:actor_id WHERE id=:period_id"
            ),
            {
                "version": version_number,
                "version_id": version_row["id"],
                "source_version": source_version,
                "closed_at": version_row["closed_at"],
                "actor_id": actor_id,
                "period_id": period_row["id"],
            },
        )
        await self.connection.execute(
            text(
                "INSERT INTO public.attendance_period_audit_log"
                "(company_id,branch_id,period_version_id,period,action,actor_app_user_id,reason) "
                "VALUES (:company_id,:branch_id,:version_id,:period,:action,:actor_id,:reason)"
            ),
            {
                "company_id": company_id,
                "branch_id": branch_id,
                "version_id": version_row["id"],
                "period": period,
                "action": "PERIOD_CLOSED" if current_version == 0 else "PERIOD_AMENDED",
                "actor_id": actor_id,
                "reason": amendment_reason or "Attendance period closed",
            },
        )
        saved = await self.row(company_id, branch_id, period)
        assert saved is not None
        return _period(saved, [])

    async def exists(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period_id: uuid.UUID
    ) -> bool:
        return (
            await self.connection.execute(
                text(
                    "SELECT id FROM public.attendance_periods "
                    "WHERE company_id=:company_id AND branch_id=:branch_id AND id=:id"
                ),
                {"company_id": company_id, "branch_id": branch_id, "id": period_id},
            )
        ).scalar_one_or_none() is not None
