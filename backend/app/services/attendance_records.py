from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import cast

from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.attendance_calculation import AttendanceCalculationRepository
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.attendance_calculation import (
    AttendanceCalculationBatchRequest,
    AttendanceCalculationRequest,
    AttendanceRecordResponse,
    PersonalAttendanceResponse,
    PersonalRawEventResponse,
)
from app.services.attendance_calculation import DUBAI, CalculationSnapshot, ShiftSnapshot, calculate
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True)
class RecordListQuery:
    employee_id: uuid.UUID | None
    from_date: date | None
    to_date: date | None
    limit: int
    cursor: str | None


def _record(row: RowMapping) -> AttendanceRecordResponse:
    values = dict(row)
    snapshot = cast(dict[str, object], values["source_snapshot"])
    values["expected_hours"] = snapshot.get("expectedHours", "0.00")
    values["resolution_type"] = values["resolution_type"] or None
    return AttendanceRecordResponse.model_validate(
        {field: values[field] for field in AttendanceRecordResponse.model_fields}
    )


def _source_value(value: object) -> object:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _source_row(row: RowMapping | None, fields: tuple[str, ...]) -> dict[str, object] | None:
    if row is None:
        return None
    return {field: _source_value(row[field]) for field in fields}


def _owned_events(
    attendance_date: date,
    shift: ShiftSnapshot | None,
    events: list[RowMapping],
) -> list[RowMapping]:
    if shift is None or shift.shift_type == "flexible":
        start = datetime.combine(attendance_date, time.min, tzinfo=DUBAI)
        end = start + timedelta(days=1)
    else:
        assert shift.start_time is not None and shift.end_time is not None
        start = datetime.combine(attendance_date, shift.start_time, tzinfo=DUBAI)
        if shift.shift_type == "overnight":
            end = datetime.combine(
                attendance_date + timedelta(days=1), shift.end_time, tzinfo=DUBAI
            )
        elif shift.shift_type == "split":
            assert shift.split_end_time is not None
            end = datetime.combine(attendance_date, shift.split_end_time, tzinfo=DUBAI)
        else:
            end = datetime.combine(attendance_date, shift.end_time, tzinfo=DUBAI)
        start -= timedelta(hours=4)
        end += timedelta(hours=4)
    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    return [item for item in events if start_utc <= item["event_time"] < end_utc]


class AttendanceRecordService:
    def __init__(
        self, connection: AsyncConnection, cursor_codec: EmployeeCursorCodec | None = None
    ) -> None:
        self.repository = AttendanceCalculationRepository(connection)
        self.cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    async def list_admin(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, query: RecordListQuery
    ) -> tuple[list[AttendanceRecordResponse], str | None]:
        self._admin(principal)
        return await self._records_page(principal, branch_id, query, "list_attendance_records")

    async def _records_page(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: RecordListQuery,
        operation_id: str,
    ) -> tuple[list[AttendanceRecordResponse], str | None]:
        after = None
        try:
            if query.cursor is not None:
                if self.cursor_codec is None:
                    raise ValueError
                cursor_id = self.cursor_codec.decode(
                    principal=principal,
                    branch_id=branch_id,
                    operation_id=operation_id,
                    query=query,
                    cursor=query.cursor,
                )
                if cursor_id is None:
                    raise ValueError
                after = await self.repository.record_position(
                    principal.company_id, branch_id, cursor_id
                )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = list(
            await self.repository.records(
                principal.company_id,
                branch_id,
                query.employee_id,
                query.from_date,
                query.to_date,
                after,
                query.limit + 1,
            )
        )
        page_rows = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit and page_rows:
            assert self.cursor_codec is not None
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                last_id=page_rows[-1]["id"],
            )
        return [_record(row) for row in page_rows], next_cursor

    async def personal_today(self, principal: AuthorizationPrincipal) -> PersonalAttendanceResponse:
        if principal.employee_id is None or principal.branch_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        today = await self.repository.business_date()
        row = await self.repository.today_record(
            principal.company_id, principal.branch_id, principal.employee_id, today
        )
        if row is not None:
            return PersonalAttendanceResponse(
                record=_record(row), raw_event_fallback="none", raw_events=[]
            )
        events = await self.repository.self_events(
            principal.company_id, principal.branch_id, principal.employee_id, today
        )
        return PersonalAttendanceResponse(
            record=None,
            raw_event_fallback="self_only",
            raw_events=[
                PersonalRawEventResponse(
                    id=item["id"],
                    event_type=item["event_type"],
                    event_time=item["event_time"],
                    method=item["method"],
                )
                for item in events
            ],
        )

    async def personal_history(
        self, principal: AuthorizationPrincipal, query: RecordListQuery
    ) -> tuple[list[AttendanceRecordResponse], str | None]:
        if principal.employee_id is None or principal.branch_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        return await self._records_page(
            principal,
            principal.branch_id,
            RecordListQuery(
                employee_id=principal.employee_id,
                from_date=query.from_date,
                to_date=query.to_date,
                limit=query.limit,
                cursor=query.cursor,
            ),
            "list_personal_attendance",
        )

    async def calculate_one(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: AttendanceCalculationRequest,
    ) -> AttendanceRecordResponse:
        self._admin(principal)
        if request.attendance_date > await self.repository.business_date():
            raise ServiceExecutionError("validation_failed")
        try:
            sources = await self.repository.calculation_sources(
                principal.company_id, branch_id, request.employee_id, request.attendance_date
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if sources.get("closed") is True:
            raise ServiceExecutionError("state_conflict")
        employee = sources["employee"]
        settings = sources["settings"]
        assert isinstance(employee, RowMapping) and isinstance(settings, RowMapping)
        if (
            not employee["active"]
            or employee["employment_status"] == "Terminated"
            or (
                employee["employment_start_date"] is not None
                and request.attendance_date < employee["employment_start_date"]
            )
            or (
                employee["termination_date"] is not None
                and request.attendance_date > employee["termination_date"]
            )
        ):
            raise ServiceExecutionError("resource_not_found")
        shift_row = sources["shift"]
        shift = None
        if isinstance(shift_row, RowMapping):
            shift = ShiftSnapshot(
                shift_row["id"],
                shift_row["shift_type"],
                Decimal(shift_row["expected_hours"]),
                shift_row["break_minutes"],
                shift_row["late_grace_minutes"],
                shift_row["early_departure_grace_minutes"],
                shift_row["start_time"],
                shift_row["end_time"],
                shift_row["split_start_time"],
                shift_row["split_end_time"],
                shift_row["min_hours_flexible"],
            )
        source_events = cast(list[RowMapping], sources["events"])
        raw_events = _owned_events(request.attendance_date, shift, source_events)
        current = cast(RowMapping | None, sources["current"])
        resolution_type = None if current is None else current["resolution_type"] or None
        leave_settings = cast(RowMapping | None, sources["leaveSettings"])
        ramadan = bool(
            leave_settings
            and leave_settings["ramadan_active"]
            and leave_settings["ramadan_start"]
            <= request.attendance_date
            <= leave_settings["ramadan_end"]
        )
        weekday = request.attendance_date.strftime("%a")
        snapshot = CalculationSnapshot(
            request.attendance_date,
            shift,
            tuple((item["event_type"], item["event_time"]) for item in raw_events),
            weekday in settings["weekend_days"],
            bool(sources["holiday"]),
            bool(sources["leave"]),
            resolution_type == "WFH",
            ramadan,
            weekday in settings["working_days"],
            Decimal(employee["basic_salary"]),
            settings["late_deduction_policy"],
            Decimal(settings["late_deduction_amount"]),
            Decimal(settings["max_daily_overtime_hours"]),
            Decimal(settings["default_hours_per_day"]),
        )
        result = calculate(snapshot)
        prior_required = cast(list[RowMapping], sources["priorRequired"])
        evidence_flags = list(result.blocker_flags)
        if resolution_type is not None:
            evidence_flags.append(f"resolution:{resolution_type.lower()}")
        if (
            result.status == "UNEXPLAINED_ABSENCE"
            and len(prior_required) == 2
            and all(item["status"] == "UNEXPLAINED_ABSENCE" for item in prior_required)
        ):
            evidence_flags.append("consecutive_unexplained_absence")
        roster = cast(RowMapping | None, sources["roster"])
        assignment = cast(RowMapping | None, sources["assignment"])
        holiday = cast(RowMapping | None, sources["holiday"])
        approved_leave = cast(list[RowMapping], sources["leave"])
        assert roster is None or isinstance(roster, RowMapping)
        assert assignment is None or isinstance(assignment, RowMapping)
        assert holiday is None or isinstance(holiday, RowMapping)
        source_snapshot: dict[str, object] = {
            "snapshotVersion": 1,
            "attendanceDate": request.attendance_date.isoformat(),
            "employment": _source_row(
                employee,
                (
                    "id",
                    "active",
                    "employment_status",
                    "employment_start_date",
                    "termination_date",
                    "basic_salary",
                    "updated_at",
                ),
            ),
            "attendanceSettings": _source_row(
                settings,
                (
                    "id",
                    "working_days",
                    "weekend_days",
                    "default_hours_per_day",
                    "late_deduction_policy",
                    "late_deduction_amount",
                    "max_daily_overtime_hours",
                    "updated_at",
                ),
            ),
            "shift": _source_row(
                shift_row,
                (
                    "id",
                    "shift_type",
                    "start_time",
                    "end_time",
                    "break_minutes",
                    "expected_hours",
                    "late_grace_minutes",
                    "early_departure_grace_minutes",
                    "split_start_time",
                    "split_end_time",
                    "is_overnight",
                    "min_hours_flexible",
                    "updated_at",
                ),
            )
            if isinstance(shift_row, RowMapping)
            else None,
            "shiftSource": {
                "kind": "publishedRoster" if roster is not None else "effectiveAssignment",
                "row": _source_row(
                    roster,
                    ("id", "shift_id", "planned_hours", "updated_at"),
                )
                if roster is not None
                else _source_row(
                    assignment,
                    ("id", "shift_id", "effective_from", "effective_to", "updated_at"),
                ),
            }
            if shift is not None
            else {"kind": "branchDefault", "row": None},
            "clockEvents": [
                {
                    "id": str(item["id"]),
                    "eventType": item["event_type"],
                    "eventTime": item["event_time"].isoformat(),
                }
                for item in raw_events
            ],
            "holiday": _source_row(holiday, ("id", "date", "name", "type", "created_at")),
            "approvedLeave": [
                _source_row(
                    item,
                    ("id", "status", "start_date", "end_date", "updated_at"),
                )
                for item in approved_leave
            ],
            "ramadan": _source_row(
                leave_settings,
                ("id", "ramadan_active", "ramadan_start", "ramadan_end", "updated_at"),
            )
            if isinstance(leave_settings, RowMapping)
            else None,
            "priorRequiredAttendance": [
                {
                    "id": None if item["id"] is None else str(item["id"]),
                    "date": item["day"].isoformat(),
                    "status": item["status"],
                }
                for item in prior_required
            ],
            "expectedHours": f"{result.expected_hours:.2f}",
            "resolution": None
            if current is None or resolution_type is None
            else {
                "type": resolution_type,
                "resolvedAt": _source_value(current["resolved_at"]),
                "sourceDigest": current["resolution_source_digest"],
            },
        }
        digest = hashlib.sha256(
            json.dumps(source_snapshot, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if current is not None and request.expected_source_digest is None:
            raise ServiceExecutionError("state_conflict")
        if request.expected_source_digest is not None and request.expected_source_digest != (
            None if current is None else current["source_digest"]
        ):
            raise ServiceExecutionError("state_conflict")
        if (
            request.expected_calculation_version is not None
            and request.expected_calculation_version
            != (None if current is None else current["calculation_version"])
        ):
            raise ServiceExecutionError("state_conflict")
        values: dict[str, object] = {
            "shift_id": None if shift is None else shift.shift_id,
            "clock_in_time": result.clock_in,
            "clock_out_time": result.clock_out,
            "total_hours": result.total_hours,
            "status": result.status,
            "late_minutes": result.late_minutes,
            "early_departure_minutes": result.early_departure_minutes,
            "overtime_hours": result.overtime_hours,
            "overtime_type": result.overtime_type,
            "overtime_amount": result.overtime_amount,
            "worked_on_rest_day": result.worked_on_rest_day,
            "rest_day_substitute": snapshot.rest_day_substitute,
            "missing_clock_out": result.missing_clock_out,
            "is_ramadan_day": ramadan,
            "absence_deduction": result.absence_deduction,
            "late_deduction": result.late_deduction,
            "source_snapshot": source_snapshot,
            "source_digest": digest,
            "source_clock_event_ids": [item["id"] for item in raw_events],
            "evidence_flags": sorted(set(evidence_flags)),
            "source_stale": False,
            "overtime_approved": False,
            "overtime_approved_by_app_user_id": None,
            "overtime_approved_at": None,
            "overtime_approval_source_digest": None,
            "calculation_version": 1
            if current is None
            else int(current["calculation_version"]) + 1,
            "expected_digest": None if current is None else current["source_digest"],
            "expected_version": None if current is None else current["calculation_version"],
        }
        try:
            saved = await self.repository.save_calculation(
                principal.company_id,
                branch_id,
                request.employee_id,
                request.attendance_date,
                values,
            )
            return _record(saved)
        except ResourceNotFoundError:
            raise ServiceExecutionError("state_conflict") from None

    async def calculate_batch(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: AttendanceCalculationBatchRequest,
    ) -> list[AttendanceRecordResponse]:
        self._admin(principal)
        return [
            await self.calculate_one(principal, branch_id, item)
            for item in sorted(request.items, key=lambda value: value.employee_id.bytes)
        ]

    async def authorize_batch_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if kind != "tenant" or resource_id is not None:
            raise ServiceExecutionError("resource_not_found")

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if (
            kind != "attendance_record"
            or resource_id is None
            or not await self.repository.resource_exists(
                principal.company_id, branch_id, resource_id
            )
        ):
            raise ServiceExecutionError("resource_not_found")
