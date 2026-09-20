from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, asc, exists, func, insert, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.attendance import (
    AttendanceRecord,
    AttendanceSettings,
    RosterAssignment,
    Shift,
    ShiftAssignment,
)
from app.models.identity import Employee
from app.repositories.scoped import ResourceNotFoundError

SETTINGS_COLUMNS = (
    AttendanceSettings.id,
    AttendanceSettings.working_days,
    AttendanceSettings.weekend_days,
    AttendanceSettings.default_hours_per_day,
    AttendanceSettings.late_grace_minutes,
    AttendanceSettings.early_departure_grace_minutes,
    AttendanceSettings.overtime_requires_approval,
    AttendanceSettings.max_daily_overtime_hours,
    AttendanceSettings.late_deduction_policy,
    AttendanceSettings.late_deduction_amount,
    AttendanceSettings.wfh_enabled,
    AttendanceSettings.regularisation_max_days_per_month,
    AttendanceSettings.regularisation_window_days,
    AttendanceSettings.biometric_api_enabled,
    AttendanceSettings.biometric_api_key,
    AttendanceSettings.created_at,
    AttendanceSettings.updated_at,
)
SHIFT_COLUMNS = (
    Shift.id,
    Shift.name,
    Shift.shift_type,
    Shift.start_time,
    Shift.end_time,
    Shift.break_minutes,
    Shift.expected_hours,
    Shift.late_grace_minutes,
    Shift.early_departure_grace_minutes,
    Shift.split_start_time,
    Shift.split_end_time,
    Shift.is_overnight,
    Shift.min_hours_flexible,
    Shift.is_active,
    Shift.color,
    Shift.code,
    Shift.shift_category,
    Shift.min_staff,
    Shift.created_at,
    Shift.updated_at,
)
ASSIGNMENT_COLUMNS = (
    ShiftAssignment.id,
    ShiftAssignment.employee_id,
    ShiftAssignment.shift_id,
    ShiftAssignment.effective_from,
    ShiftAssignment.effective_to,
    ShiftAssignment.created_at,
    ShiftAssignment.updated_at,
)


class AttendanceConfigurationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def business_date(self) -> date:
        result = await self._connection.exec_driver_sql("SELECT public.workloop_business_date()")
        return result.scalar_one()

    async def fetch_settings(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, lock: bool = False
    ) -> RowMapping:
        statement = select(*SETTINGS_COLUMNS).where(
            AttendanceSettings.company_id == company_id, AttendanceSettings.branch_id == branch_id
        )
        if lock:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement.limit(1))).mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def update_settings(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, values: dict[str, object]
    ) -> RowMapping:
        result = await self._connection.execute(
            update(AttendanceSettings)
            .where(
                AttendanceSettings.company_id == company_id,
                AttendanceSettings.branch_id == branch_id,
            )
            .values(**values)
            .returning(*SETTINGS_COLUMNS)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def fetch_shift(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        shift_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> RowMapping:
        statement = select(*SHIFT_COLUMNS).where(
            Shift.company_id == company_id, Shift.branch_id == branch_id, Shift.id == shift_id
        )
        if lock:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement.limit(1))).mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def fetch_shift_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, shift_id: uuid.UUID
    ) -> tuple[str, uuid.UUID]:
        row = (
            await self._connection.execute(
                select(Shift.name, Shift.id).where(
                    Shift.company_id == company_id,
                    Shift.branch_id == branch_id,
                    Shift.id == shift_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row[0], row[1]

    async def fetch_shifts(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        active: bool | None,
        shift_type: str | None,
        shift_category: str | None,
        search: str | None,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        statement = select(*SHIFT_COLUMNS).where(
            Shift.company_id == company_id, Shift.branch_id == branch_id
        )
        if active is not None:
            statement = statement.where(Shift.is_active == active)
        if shift_type is not None:
            statement = statement.where(Shift.shift_type == shift_type)
        if shift_category is not None:
            statement = statement.where(Shift.shift_category == shift_category)
        if search is not None:
            pattern = f"%{search.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Shift.name).like(pattern),
                    func.lower(func.coalesce(Shift.code, "")).like(pattern),
                )
            )
        if after is not None:
            statement = statement.where(
                or_(Shift.name > after[0], and_(Shift.name == after[0], Shift.id > after[1]))
            )
        return (
            (
                await self._connection.execute(
                    statement.order_by(asc(Shift.name), asc(Shift.id)).limit(limit + 1)
                )
            )
            .mappings()
            .all()
        )

    async def create_shift(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, values: dict[str, object]
    ) -> RowMapping:
        return (
            (
                await self._connection.execute(
                    insert(Shift)
                    .values(company_id=company_id, branch_id=branch_id, **values)
                    .returning(*SHIFT_COLUMNS)
                )
            )
            .mappings()
            .one()
        )

    async def update_shift(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        shift_id: uuid.UUID,
        values: dict[str, object],
    ) -> RowMapping:
        row = (
            (
                await self._connection.execute(
                    update(Shift)
                    .where(
                        Shift.company_id == company_id,
                        Shift.branch_id == branch_id,
                        Shift.id == shift_id,
                    )
                    .values(**values)
                    .returning(*SHIFT_COLUMNS)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ResourceNotFoundError
        return row

    async def shift_has_any_reference(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, shift_id: uuid.UUID
    ) -> bool:
        checks = (
            select(
                exists().where(
                    ShiftAssignment.company_id == company_id,
                    ShiftAssignment.branch_id == branch_id,
                    ShiftAssignment.shift_id == shift_id,
                )
            ),
            select(
                exists().where(
                    AttendanceRecord.company_id == company_id,
                    AttendanceRecord.branch_id == branch_id,
                    AttendanceRecord.shift_id == shift_id,
                )
            ),
            select(
                exists().where(
                    RosterAssignment.company_id == company_id,
                    RosterAssignment.branch_id == branch_id,
                    RosterAssignment.shift_id == shift_id,
                )
            ),
        )
        for statement in checks:
            if (await self._connection.execute(statement)).scalar_one():
                return True
        return False

    async def shift_has_current_or_future_assignment(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, shift_id: uuid.UUID, business_date: date
    ) -> bool:
        return bool(
            (
                await self._connection.execute(
                    select(
                        exists().where(
                            ShiftAssignment.company_id == company_id,
                            ShiftAssignment.branch_id == branch_id,
                            ShiftAssignment.shift_id == shift_id,
                            or_(
                                ShiftAssignment.effective_to.is_(None),
                                ShiftAssignment.effective_to >= business_date,
                            ),
                        )
                    )
                )
            ).scalar_one()
        )

    async def fetch_employee_for_assignment(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping:
        row = (
            (
                await self._connection.execute(
                    select(Employee.id, Employee.active, Employee.employment_status)
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
        if row is None:
            raise ResourceNotFoundError
        return row

    async def lock_assignments(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> Sequence[RowMapping]:
        return (
            (
                await self._connection.execute(
                    select(*ASSIGNMENT_COLUMNS)
                    .where(
                        ShiftAssignment.company_id == company_id,
                        ShiftAssignment.branch_id == branch_id,
                        ShiftAssignment.employee_id == employee_id,
                    )
                    .order_by(ShiftAssignment.id)
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )

    async def fetch_assignments(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        effective_on: date | None,
        after: tuple[date, uuid.UUID] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        statement = select(*ASSIGNMENT_COLUMNS).where(
            ShiftAssignment.company_id == company_id,
            ShiftAssignment.branch_id == branch_id,
            ShiftAssignment.employee_id == employee_id,
        )
        if effective_on is not None:
            statement = statement.where(
                ShiftAssignment.effective_from <= effective_on,
                or_(
                    ShiftAssignment.effective_to.is_(None),
                    ShiftAssignment.effective_to >= effective_on,
                ),
            )
        if after is not None:
            statement = statement.where(
                or_(
                    ShiftAssignment.effective_from < after[0],
                    and_(
                        ShiftAssignment.effective_from == after[0],
                        ShiftAssignment.id > after[1],
                    ),
                )
            )
        return (
            (
                await self._connection.execute(
                    statement.order_by(
                        ShiftAssignment.effective_from.desc(),
                        ShiftAssignment.id,
                    ).limit(limit + 1)
                )
            )
            .mappings()
            .all()
        )

    async def fetch_assignment_position(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> tuple[date, uuid.UUID]:
        row = (
            await self._connection.execute(
                select(ShiftAssignment.effective_from, ShiftAssignment.id).where(
                    ShiftAssignment.company_id == company_id,
                    ShiftAssignment.branch_id == branch_id,
                    ShiftAssignment.employee_id == employee_id,
                    ShiftAssignment.id == assignment_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row[0], row[1]

    async def fetch_assignment(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, assignment_id: uuid.UUID
    ) -> RowMapping:
        row = (
            (
                await self._connection.execute(
                    select(*ASSIGNMENT_COLUMNS)
                    .where(
                        ShiftAssignment.company_id == company_id,
                        ShiftAssignment.branch_id == branch_id,
                        ShiftAssignment.id == assignment_id,
                    )
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ResourceNotFoundError
        return row

    async def close_assignment(self, assignment_id: uuid.UUID, effective_to: date) -> None:
        await self._connection.execute(
            update(ShiftAssignment)
            .where(ShiftAssignment.id == assignment_id)
            .values(effective_to=effective_to, updated_at=func.now())
        )

    async def create_assignment(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        shift_id: uuid.UUID,
        effective_from: date,
        effective_to: date | None,
    ) -> RowMapping:
        try:
            return (
                (
                    await self._connection.execute(
                        insert(ShiftAssignment)
                        .values(
                            company_id=company_id,
                            branch_id=branch_id,
                            employee_id=employee_id,
                            shift_id=shift_id,
                            effective_from=effective_from,
                            effective_to=effective_to,
                        )
                        .returning(*ASSIGNMENT_COLUMNS)
                    )
                )
                .mappings()
                .one()
            )
        except IntegrityError:
            raise
