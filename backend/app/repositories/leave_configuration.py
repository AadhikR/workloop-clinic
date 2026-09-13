from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, asc, delete, exists, func, or_, select, update
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
            select(*SETTINGS_COLUMNS)
            .where(LeaveSettings.company_id == company_id, LeaveSettings.branch_id == branch_id)
            .with_for_update()
        )
        row = current.mappings().one_or_none()
        if row is None:
            if expected is not None:
                raise ValueError("state conflict")
            result = await self._connection.execute(
                insert(LeaveSettings)
                .values(company_id=company_id, branch_id=branch_id, **values)
                .returning(*SETTINGS_COLUMNS)
            )
            return result.mappings().one()
        if expected is None or not _same_version(row["updated_at"], expected):
            raise ValueError("state conflict")
        result = await self._connection.execute(
            update(LeaveSettings)
            .where(LeaveSettings.id == row["id"])
            .values(
                **values,
                updated_at=func.greatest(
                    func.clock_timestamp(), row["updated_at"] + timedelta(milliseconds=1)
                ),
            )
            .returning(*SETTINGS_COLUMNS)
        )
        return result.mappings().one()

    async def list_types(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        *,
        active_only: bool,
        after: tuple[int, str, uuid.UUID] | None = None,
        limit: int | None = None,
    ) -> Sequence[RowMapping]:
        statement = select(*TYPE_COLUMNS).where(
            LeaveType.company_id == company_id, LeaveType.branch_id == branch_id
        )
        if active_only:
            statement = statement.where(LeaveType.is_active.is_(True))
        if after is not None:
            sort_order, name, type_id = after
            statement = statement.where(
                or_(
                    LeaveType.sort_order > sort_order,
                    and_(LeaveType.sort_order == sort_order, LeaveType.name > name),
                    and_(
                        LeaveType.sort_order == sort_order,
                        LeaveType.name == name,
                        LeaveType.id > type_id,
                    ),
                )
            )
        statement = statement.order_by(
            asc(LeaveType.sort_order), asc(LeaveType.name), asc(LeaveType.id)
        )
        if limit is not None:
            statement = statement.limit(limit + 1)
        result = await self._connection.execute(statement)
        return result.mappings().all()

    async def fetch_type_position(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        type_id: uuid.UUID,
        *,
        active_only: bool,
    ) -> tuple[int, str, uuid.UUID]:
        statement = select(LeaveType.sort_order, LeaveType.name, LeaveType.id).where(
            LeaveType.company_id == company_id,
            LeaveType.branch_id == branch_id,
            LeaveType.id == type_id,
        )
        if active_only:
            statement = statement.where(LeaveType.is_active.is_(True))
        row = (await self._connection.execute(statement.limit(1))).tuples().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row[0], row[1], row[2]

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
        criteria = (
            LeaveType.company_id == company_id,
            LeaveType.branch_id == branch_id,
            LeaveType.id == type_id,
        )
        if values.get("is_active") is False:
            visible = await self._connection.execute(
                select(*TYPE_COLUMNS).where(*criteria).limit(1)
            )
            candidate = visible.mappings().one_or_none()
            if candidate is None:
                raise ResourceNotFoundError
            if expected is None or not _same_version(candidate["updated_at"], expected):
                raise ValueError("state conflict")
            if candidate["is_active"]:
                await self._connection.exec_driver_sql(
                    "LOCK TABLE public.leave_requests IN SHARE ROW EXCLUSIVE MODE"
                )

        current = await self._connection.execute(
            select(*TYPE_COLUMNS).where(*criteria).with_for_update()
        )
        row = current.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        if expected is None or not _same_version(row["updated_at"], expected):
            raise ValueError("state conflict")
        carry_forward_allowed = values.get("carry_forward_allowed", row["carry_forward_allowed"])
        carry_forward_max_days = values.get("carry_forward_max_days", row["carry_forward_max_days"])
        once_per_career = values.get("once_per_career", row["once_per_career"])
        accrual_type = values.get("accrual_type", row["accrual_type"])
        if carry_forward_allowed and carry_forward_max_days == 0:
            raise ValueError("invalid leave type")
        if once_per_career and accrual_type != "once_per_career":
            raise ValueError("invalid leave type")
        if values.get("is_active") is False and row["is_active"]:
            open_request = await self._connection.execute(
                select(
                    exists().where(
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                        LeaveRequest.leave_type_id == type_id,
                        LeaveRequest.status.in_(("Pending", "ManagerApproved")),
                    )
                )
            )
            if open_request.scalar():
                raise ValueError("unsafe deactivation")
        result = await self._connection.execute(
            update(LeaveType)
            .where(LeaveType.id == type_id)
            .values(
                **values,
                updated_at=func.greatest(
                    func.clock_timestamp(), row["updated_at"] + timedelta(milliseconds=1)
                ),
            )
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
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        year: int | None,
        *,
        after: tuple[date, uuid.UUID] | None = None,
        limit: int | None = None,
    ) -> Sequence[RowMapping]:
        statement = select(*HOLIDAY_COLUMNS).where(
            PublicHoliday.company_id == company_id, PublicHoliday.branch_id == branch_id
        )
        if year is not None:
            statement = statement.where(PublicHoliday.year == year)
        if after is not None:
            holiday_date, holiday_id = after
            statement = statement.where(
                or_(
                    PublicHoliday.date > holiday_date,
                    and_(PublicHoliday.date == holiday_date, PublicHoliday.id > holiday_id),
                )
            )
        statement = statement.order_by(asc(PublicHoliday.date), asc(PublicHoliday.id))
        if limit is not None:
            statement = statement.limit(limit + 1)
        result = await self._connection.execute(statement)
        return result.mappings().all()

    async def fetch_holiday_position(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        year: int | None,
    ) -> tuple[date, uuid.UUID]:
        statement = select(PublicHoliday.date, PublicHoliday.id).where(
            PublicHoliday.company_id == company_id,
            PublicHoliday.branch_id == branch_id,
            PublicHoliday.id == holiday_id,
        )
        if year is not None:
            statement = statement.where(PublicHoliday.year == year)
        row = (await self._connection.execute(statement.limit(1))).tuples().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row[0], row[1]

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

    async def _lock_holiday_for_mutation(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        expected: dict[str, Any],
    ) -> RowMapping:
        criteria = (
            PublicHoliday.company_id == company_id,
            PublicHoliday.branch_id == branch_id,
            PublicHoliday.id == holiday_id,
        )
        visible = await self._connection.execute(select(*HOLIDAY_COLUMNS).where(*criteria).limit(1))
        candidate = visible.mappings().one_or_none()
        if candidate is None:
            raise ResourceNotFoundError
        if any(candidate[field] != value for field, value in expected.items()):
            raise ValueError("state conflict")

        locked = await self._connection.execute(
            select(*HOLIDAY_COLUMNS).where(*criteria).with_for_update()
        )
        row = locked.mappings().one_or_none()
        if row is None:
            raise ValueError("holiday is immutable")
        if any(row[field] != value for field, value in expected.items()):
            raise ValueError("state conflict")
        return row

    async def update_holiday(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        expected: dict[str, Any],
        values: dict[str, Any],
    ) -> RowMapping:
        row = await self._lock_holiday_for_mutation(
            company_id=company_id,
            branch_id=branch_id,
            holiday_id=holiday_id,
            expected=expected,
        )
        await self._connection.exec_driver_sql(
            "LOCK TABLE public.leave_requests, public.attendance_records "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
        business_date = (
            await self._connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()
        if row["date"] <= business_date or await self._holiday_used(
            company_id, branch_id, row["date"]
        ):
            raise ValueError("holiday is immutable")
        new_date = values.get("date", row["date"])
        if new_date <= business_date or await self._holiday_used(company_id, branch_id, new_date):
            raise ValueError("holiday is immutable")
        result = await self._connection.execute(
            update(PublicHoliday)
            .where(PublicHoliday.id == holiday_id)
            .values(**values, year=new_date.year)
            .returning(*HOLIDAY_COLUMNS)
        )
        updated = result.mappings().one_or_none()
        if updated is None:
            raise ValueError("holiday is immutable")
        return updated

    async def delete_holiday(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        expected: dict[str, Any],
    ) -> None:
        row = await self._lock_holiday_for_mutation(
            company_id=company_id,
            branch_id=branch_id,
            holiday_id=holiday_id,
            expected=expected,
        )
        await self._connection.exec_driver_sql(
            "LOCK TABLE public.leave_requests, public.attendance_records "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
        business_date = (
            await self._connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()
        if row["date"] <= business_date or await self._holiday_used(
            company_id, branch_id, row["date"]
        ):
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
