from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import asc, delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.attendance import AttendanceRecord
from app.models.leave import LeaveRequest, LeaveSettings, LeaveType, PublicHoliday
from app.repositories.scoped import ResourceNotFoundError

SETTINGS_COLUMNS = (
    LeaveSettings.id,
    LeaveSettings.branch_id,
    LeaveSettings.leave_year_type,
    LeaveSettings.weekend_definition,
    LeaveSettings.carry_forward_enabled,
    LeaveSettings.carry_forward_max_days,
    LeaveSettings.approval_chain,
    LeaveSettings.ramadan_active,
    LeaveSettings.ramadan_start,
    LeaveSettings.ramadan_end,
    LeaveSettings.created_at,
    LeaveSettings.updated_at,
)
TYPE_COLUMNS = (
    LeaveType.id,
    LeaveType.branch_id,
    LeaveType.code,
    LeaveType.name,
    LeaveType.color,
    LeaveType.is_paid,
    LeaveType.is_unlimited,
    LeaveType.requires_approval,
    LeaveType.requires_attachment,
    LeaveType.requires_reason,
    LeaveType.min_notice_days,
    LeaveType.annual_entitlement_days,
    LeaveType.accrual_type,
    LeaveType.day_count_type,
    LeaveType.auto_approve,
    LeaveType.carry_forward_allowed,
    LeaveType.carry_forward_max_days,
    LeaveType.gender_restriction,
    LeaveType.min_service_months,
    LeaveType.once_per_career,
    LeaveType.not_deducted_from_annual,
    LeaveType.affects_payroll,
    LeaveType.law_reference,
    LeaveType.is_active,
    LeaveType.sort_order,
    LeaveType.probation_eligible,
    LeaveType.created_at,
    LeaveType.updated_at,
)
HOLIDAY_COLUMNS = (
    PublicHoliday.id,
    PublicHoliday.branch_id,
    PublicHoliday.date,
    PublicHoliday.name,
    PublicHoliday.type,
    PublicHoliday.year,
    PublicHoliday.created_at,
)


def _same_version(actual: datetime, expected: datetime) -> bool:
    return actual.astimezone().replace(
        microsecond=actual.microsecond // 1000 * 1000
    ) == expected.astimezone().replace(microsecond=expected.microsecond // 1000 * 1000)


class LeaveConfigurationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def get_settings(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> RowMapping:
        result = await self._connection.execute(
            select(*SETTINGS_COLUMNS)
            .where(LeaveSettings.company_id == company_id, LeaveSettings.branch_id == branch_id)
            .limit(1)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def upsert_settings(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        expected: datetime | None,
        values: dict[str, Any],
    ) -> RowMapping:
        current = await self._connection.execute(
            select(LeaveSettings)
            .where(LeaveSettings.company_id == company_id, LeaveSettings.branch_id == branch_id)
            .with_for_update()
        )
        row = current.scalar_one_or_none()
        if row is None:
            if expected is not None:
                raise ValueError("state conflict")
            result = await self._connection.execute(
                insert(LeaveSettings)
                .values(company_id=company_id, branch_id=branch_id, **values)
                .returning(*SETTINGS_COLUMNS)
            )
            return result.mappings().one()
        if expected is not None and not _same_version(row.updated_at, expected):
            raise ValueError("state conflict")
        result = await self._connection.execute(
            update(LeaveSettings)
            .where(LeaveSettings.id == row.id)
            .values(**values, updated_at=func.now())
            .returning(*SETTINGS_COLUMNS)
        )
        return result.mappings().one()

    async def list_types(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, *, active_only: bool
    ) -> Sequence[RowMapping]:
        statement = select(*TYPE_COLUMNS).where(
            LeaveType.company_id == company_id, LeaveType.branch_id == branch_id
        )
        if active_only:
            statement = statement.where(LeaveType.is_active.is_(True))
        result = await self._connection.execute(
            statement.order_by(asc(LeaveType.sort_order), asc(LeaveType.name), asc(LeaveType.id))
        )
        return result.mappings().all()

    async def get_type(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, type_id: uuid.UUID
    ) -> RowMapping:
        result = await self._connection.execute(
            select(*TYPE_COLUMNS)
            .where(
                LeaveType.company_id == company_id,
                LeaveType.branch_id == branch_id,
                LeaveType.id == type_id,
            )
            .limit(1)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def create_type(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, values: dict[str, Any]
    ) -> RowMapping:
        result = await self._connection.execute(
            insert(LeaveType)
            .values(company_id=company_id, branch_id=branch_id, **values)
            .returning(*TYPE_COLUMNS)
        )
        return result.mappings().one()

    async def update_type(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        type_id: uuid.UUID,
        expected: datetime | None,
        values: dict[str, Any],
    ) -> RowMapping:
        current = await self._connection.execute(
            select(LeaveType)
            .where(
                LeaveType.company_id == company_id,
                LeaveType.branch_id == branch_id,
                LeaveType.id == type_id,
            )
            .with_for_update()
        )
        row = current.scalar_one_or_none()
        if row is None:
            raise ResourceNotFoundError
        if expected is not None and not _same_version(row.updated_at, expected):
            raise ValueError("state conflict")
        result = await self._connection.execute(
            update(LeaveType)
            .where(LeaveType.id == type_id)
            .values(**values, updated_at=func.now())
            .returning(*TYPE_COLUMNS)
        )
        return result.mappings().one()

    async def seed_types(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, defaults: Sequence[dict[str, Any]]
    ) -> Sequence[RowMapping]:
        for values in defaults:
            await self._connection.execute(
                insert(LeaveType)
                .values(company_id=company_id, branch_id=branch_id, **values)
                .on_conflict_do_nothing(index_elements=["branch_id", "code"])
            )
        return await self.list_types(company_id, branch_id, active_only=False)

    async def list_holidays(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, year: int | None
    ) -> Sequence[RowMapping]:
        statement = select(*HOLIDAY_COLUMNS).where(
            PublicHoliday.company_id == company_id, PublicHoliday.branch_id == branch_id
        )
        if year is not None:
            statement = statement.where(PublicHoliday.year == year)
        result = await self._connection.execute(
            statement.order_by(asc(PublicHoliday.date), asc(PublicHoliday.id))
        )
        return result.mappings().all()

    async def get_holiday(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, holiday_id: uuid.UUID
    ) -> RowMapping:
        result = await self._connection.execute(
            select(*HOLIDAY_COLUMNS)
            .where(
                PublicHoliday.company_id == company_id,
                PublicHoliday.branch_id == branch_id,
                PublicHoliday.id == holiday_id,
            )
            .limit(1)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def _holiday_used(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, holiday_date: date
    ) -> bool:
        leave = await self._connection.execute(
            select(
                exists().where(
                    LeaveRequest.company_id == company_id,
                    LeaveRequest.branch_id == branch_id,
                    LeaveRequest.start_date <= holiday_date,
                    LeaveRequest.end_date >= holiday_date,
                    LeaveRequest.status.not_in(("Rejected", "Cancelled")),
                )
            )
        )
        if leave.scalar():
            return True
        attendance = await self._connection.execute(
            select(
                exists().where(
                    AttendanceRecord.company_id == company_id,
                    AttendanceRecord.branch_id == branch_id,
                    AttendanceRecord.date == holiday_date,
                )
            )
        )
        return bool(attendance.scalar())

    async def create_holiday(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, values: dict[str, Any]
    ) -> RowMapping:
        result = await self._connection.execute(
            insert(PublicHoliday)
            .values(company_id=company_id, branch_id=branch_id, year=values["date"].year, **values)
            .returning(*HOLIDAY_COLUMNS)
        )
        return result.mappings().one()

    async def update_holiday(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        values: dict[str, Any],
    ) -> RowMapping:
        current = await self._connection.execute(
            select(PublicHoliday)
            .where(
                PublicHoliday.company_id == company_id,
                PublicHoliday.branch_id == branch_id,
                PublicHoliday.id == holiday_id,
            )
            .with_for_update()
        )
        row = current.scalar_one_or_none()
        if row is None:
            raise ResourceNotFoundError
        business_date = (
            await self._connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()
        if row.date <= business_date or await self._holiday_used(company_id, branch_id, row.date):
            raise ValueError("holiday is immutable")
        new_date = values.get("date", row.date)
        if new_date <= business_date or await self._holiday_used(company_id, branch_id, new_date):
            raise ValueError("holiday is immutable")
        result = await self._connection.execute(
            update(PublicHoliday)
            .where(PublicHoliday.id == holiday_id)
            .values(**values, year=new_date.year)
            .returning(*HOLIDAY_COLUMNS)
        )
        return result.mappings().one()

    async def delete_holiday(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, holiday_id: uuid.UUID
    ) -> None:
        current = await self._connection.execute(
            select(PublicHoliday)
            .where(
                PublicHoliday.company_id == company_id,
                PublicHoliday.branch_id == branch_id,
                PublicHoliday.id == holiday_id,
            )
            .with_for_update()
        )
        row = current.scalar_one_or_none()
        if row is None:
            raise ResourceNotFoundError
        business_date = (
            await self._connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()
        if row.date <= business_date or await self._holiday_used(company_id, branch_id, row.date):
            raise ValueError("holiday is immutable")
        await self._connection.execute(delete(PublicHoliday).where(PublicHoliday.id == holiday_id))

    async def seed_holidays(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, holidays: Sequence[dict[str, Any]]
    ) -> Sequence[RowMapping]:
        for values in holidays:
            await self._connection.execute(
                insert(PublicHoliday)
                .values(
                    company_id=company_id, branch_id=branch_id, year=values["date"].year, **values
                )
                .on_conflict_do_nothing(index_elements=["branch_id", "date"])
            )
        years = sorted({item["date"].year for item in holidays})
        rows: list[RowMapping] = []
        for year in years:
            rows.extend(await self.list_holidays(company_id, branch_id, year))
        return rows
