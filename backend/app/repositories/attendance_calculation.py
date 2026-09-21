from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.attendance import (
    AttendancePeriod,
    AttendanceRecord,
    AttendanceSettings,
    ClockEvent,
    RosterAssignment,
    Shift,
    ShiftAssignment,
)
from app.models.identity import Employee
from app.models.leave import LeaveRequest, LeaveSettings, PublicHoliday
from app.repositories.scoped import ResourceNotFoundError

RECORD_COLUMNS = tuple(AttendanceRecord.__table__.c)
_DUBAI = ZoneInfo("Asia/Dubai")


class AttendanceCalculationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()

    async def records(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        from_date: date | None,
        to_date: date | None,
        after: tuple[date, uuid.UUID] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        statement = select(*RECORD_COLUMNS).where(
            AttendanceRecord.company_id == company_id, AttendanceRecord.branch_id == branch_id
        )
        if employee_id is not None:
            statement = statement.where(AttendanceRecord.employee_id == employee_id)
        if from_date is not None:
            statement = statement.where(AttendanceRecord.date >= from_date)
        if to_date is not None:
            statement = statement.where(AttendanceRecord.date <= to_date)
        if after is not None:
            marker_date, marker_id = after
            statement = statement.where(
                or_(
                    AttendanceRecord.date < marker_date,
                    and_(AttendanceRecord.date == marker_date, AttendanceRecord.id > marker_id),
                )
            )
        return (
            (
                await self.connection.execute(
                    statement.order_by(AttendanceRecord.date.desc(), AttendanceRecord.id).limit(
                        limit
                    )
                )
            )
            .mappings()
            .all()
        )

    async def record_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, record_id: uuid.UUID
    ) -> tuple[date, uuid.UUID]:
        row = (
            await self.connection.execute(
                select(AttendanceRecord.date, AttendanceRecord.id).where(
                    AttendanceRecord.company_id == company_id,
                    AttendanceRecord.branch_id == branch_id,
                    AttendanceRecord.id == record_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row.date, row.id

    async def today_record(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(*RECORD_COLUMNS).where(
                        AttendanceRecord.company_id == company_id,
                        AttendanceRecord.branch_id == branch_id,
                        AttendanceRecord.employee_id == employee_id,
                        AttendanceRecord.date == attendance_date,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )

    async def self_events(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        limit: int = 20,
    ) -> Sequence[RowMapping]:
        start = datetime.combine(attendance_date, time.min, tzinfo=_DUBAI).astimezone(UTC)
        end = start + timedelta(days=1)
        return (
            (
                await self.connection.execute(
                    select(
                        ClockEvent.id,
                        ClockEvent.event_type,
                        ClockEvent.event_time,
                        ClockEvent.method,
                    )
                    .where(
                        ClockEvent.company_id == company_id,
                        ClockEvent.branch_id == branch_id,
                        ClockEvent.employee_id == employee_id,
                        ClockEvent.superseded_by.is_(None),
                        ClockEvent.event_time >= start,
                        ClockEvent.event_time < end,
                    )
                    .order_by(ClockEvent.event_time.desc(), ClockEvent.id)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        )

    async def calculation_sources(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
    ) -> dict[str, object]:
        employee = (
            (
                await self.connection.execute(
                    select(*Employee.__table__.c)
                    .where(
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                        Employee.id == employee_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        settings = (
            (
                await self.connection.execute(
                    select(*AttendanceSettings.__table__.c)
                    .where(
                        AttendanceSettings.company_id == company_id,
                        AttendanceSettings.branch_id == branch_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if employee is None or settings is None:
            raise ResourceNotFoundError
        period = (
            await self.connection.execute(
                select(AttendancePeriod.status).where(
                    AttendancePeriod.company_id == company_id,
                    AttendancePeriod.branch_id == branch_id,
                    AttendancePeriod.period == attendance_date.strftime("%Y-%m"),
                )
            )
        ).scalar_one_or_none()
        if period == "closed":
            return {"closed": True}
        roster = (
            (
                await self.connection.execute(
                    select(
                        RosterAssignment.id,
                        RosterAssignment.shift_id,
                        RosterAssignment.updated_at,
                        RosterAssignment.planned_hours,
                    )
                    .where(
                        RosterAssignment.company_id == company_id,
                        RosterAssignment.branch_id == branch_id,
                        RosterAssignment.employee_id == employee_id,
                        RosterAssignment.date == attendance_date,
                        RosterAssignment.published.is_(True),
                    )
                    .with_for_update(read=True)
                )
            )
            .mappings()
            .one_or_none()
        )
        assignment = None
        if roster is None:
            assignment = (
                (
                    await self.connection.execute(
                        select(
                            ShiftAssignment.id,
                            ShiftAssignment.shift_id,
                            ShiftAssignment.effective_from,
                            ShiftAssignment.effective_to,
                            ShiftAssignment.updated_at,
                        )
                        .where(
                            ShiftAssignment.company_id == company_id,
                            ShiftAssignment.branch_id == branch_id,
                            ShiftAssignment.employee_id == employee_id,
                            ShiftAssignment.effective_from <= attendance_date,
                            or_(
                                ShiftAssignment.effective_to.is_(None),
                                ShiftAssignment.effective_to >= attendance_date,
                            ),
                        )
                        .with_for_update(read=True)
                    )
                )
                .mappings()
                .one_or_none()
            )
        shift_id = (
            roster["shift_id"]
            if roster is not None
            else (assignment["shift_id"] if assignment is not None else None)
        )
        shift = None
        if shift_id is not None:
            shift = (
                (
                    await self.connection.execute(
                        select(*Shift.__table__.c)
                        .where(
                            Shift.company_id == company_id,
                            Shift.branch_id == branch_id,
                            Shift.id == shift_id,
                        )
                        .with_for_update(read=True)
                    )
                )
                .mappings()
                .one_or_none()
            )
        local_midnight = datetime.combine(attendance_date, time.min, tzinfo=_DUBAI)
        start = (local_midnight - timedelta(hours=4)).astimezone(UTC)
        end = (local_midnight + timedelta(days=2, hours=4)).astimezone(UTC)
        events = (
            (
                await self.connection.execute(
                    select(ClockEvent.id, ClockEvent.event_type, ClockEvent.event_time)
                    .where(
                        ClockEvent.company_id == company_id,
                        ClockEvent.branch_id == branch_id,
                        ClockEvent.employee_id == employee_id,
                        ClockEvent.superseded_by.is_(None),
                        ClockEvent.event_time >= start,
                        ClockEvent.event_time < end,
                    )
                    .order_by(ClockEvent.event_time, ClockEvent.id)
                )
            )
            .mappings()
            .all()
        )
        holiday = (
            (
                await self.connection.execute(
                    select(*PublicHoliday.__table__.c).where(
                        PublicHoliday.company_id == company_id,
                        PublicHoliday.branch_id == branch_id,
                        PublicHoliday.date == attendance_date,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        leave = (
            (
                await self.connection.execute(
                    select(*LeaveRequest.__table__.c).where(
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                        LeaveRequest.employee_id == employee_id,
                        LeaveRequest.status == "Approved",
                        LeaveRequest.start_date <= attendance_date,
                        LeaveRequest.end_date >= attendance_date,
                    )
                )
            )
            .mappings()
            .all()
        )
        leave_settings = (
            (
                await self.connection.execute(
                    select(*LeaveSettings.__table__.c).where(
                        LeaveSettings.company_id == company_id, LeaveSettings.branch_id == branch_id
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        current = await self.today_record(company_id, branch_id, employee_id, attendance_date)
        prior_required = (
            (
                await self.connection.exec_driver_sql(
                    """
                    WITH bounds AS (
                      SELECT min(date) AS first_date
                      FROM public.attendance_records
                      WHERE company_id = %s AND branch_id = %s
                        AND employee_id = %s AND date < %s
                    ), required_days AS (
                      SELECT day::date AS day
                      FROM bounds,
                           LATERAL generate_series(first_date, %s::date - 1, interval '1 day') day
                      WHERE to_char(day, 'Dy') = ANY(%s::text[])
                        AND NOT EXISTS (
                          SELECT 1 FROM public.public_holidays holiday
                          WHERE holiday.company_id = %s AND holiday.branch_id = %s
                            AND holiday.date = day::date
                        )
                        AND NOT EXISTS (
                          SELECT 1 FROM public.leave_requests leave_request
                          WHERE leave_request.company_id = %s
                            AND leave_request.branch_id = %s
                            AND leave_request.employee_id = %s
                            AND leave_request.status = 'Approved'
                            AND day::date BETWEEN leave_request.start_date
                                              AND leave_request.end_date
                        )
                    )
                    SELECT record.id, required_days.day, record.status
                    FROM required_days
                    LEFT JOIN public.attendance_records record
                      ON record.company_id = %s AND record.branch_id = %s
                     AND record.employee_id = %s AND record.date = required_days.day
                    ORDER BY required_days.day DESC
                    LIMIT 2
                    """,
                    (
                        company_id,
                        branch_id,
                        employee_id,
                        attendance_date,
                        attendance_date,
                        settings["working_days"],
                        company_id,
                        branch_id,
                        company_id,
                        branch_id,
                        employee_id,
                        company_id,
                        branch_id,
                        employee_id,
                    ),
                )
            )
            .mappings()
            .all()
        )
        return {
            "closed": False,
            "employee": employee,
            "settings": settings,
            "shift": shift,
            "roster": roster,
            "assignment": assignment,
            "events": events,
            "holiday": holiday,
            "leave": leave,
            "leaveSettings": leave_settings,
            "priorRequired": prior_required,
            "current": current,
        }

    async def save_calculation(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        values: dict[str, object],
    ) -> RowMapping:
        await self.connection.exec_driver_sql(
            "INSERT INTO public.attendance_periods(company_id,branch_id,period) "
            "VALUES (%s,%s,%s) ON CONFLICT (branch_id,period) DO NOTHING",
            (company_id, branch_id, attendance_date.strftime("%Y-%m")),
        )
        period_status = (
            await self.connection.execute(
                select(AttendancePeriod.status)
                .where(
                    AttendancePeriod.company_id == company_id,
                    AttendancePeriod.branch_id == branch_id,
                    AttendancePeriod.period == attendance_date.strftime("%Y-%m"),
                )
                .with_for_update()
            )
        ).scalar_one()
        if period_status != "open":
            raise ResourceNotFoundError
        current = await self.today_record(company_id, branch_id, employee_id, attendance_date)
        expected_digest = values.pop("expected_digest")
        expected_version = values.pop("expected_version")
        if current is None:
            from sqlalchemy import insert

            statement = (
                insert(AttendanceRecord)
                .values(
                    company_id=company_id,
                    branch_id=branch_id,
                    employee_id=employee_id,
                    date=attendance_date,
                    **values,
                )
                .returning(*RECORD_COLUMNS)
            )
        else:
            from sqlalchemy import update

            statement = (
                update(AttendanceRecord)
                .where(
                    AttendanceRecord.id == current["id"],
                    AttendanceRecord.source_digest == expected_digest,
                    AttendanceRecord.calculation_version == expected_version,
                )
                .values(**values)
                .returning(*RECORD_COLUMNS)
            )
        row = (await self.connection.execute(statement)).mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def resource_exists(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, record_id: uuid.UUID
    ) -> bool:
        return (
            await self.connection.execute(
                select(AttendanceRecord.id).where(
                    AttendanceRecord.id == record_id,
                    AttendanceRecord.company_id == company_id,
                    AttendanceRecord.branch_id == branch_id,
                )
            )
        ).scalar_one_or_none() is not None
