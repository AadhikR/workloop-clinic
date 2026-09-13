from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import asc, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import Employee
from app.models.leave import LeaveBalance, LeaveRequest, LeaveSettings, LeaveType, PublicHoliday
from app.repositories.scoped import ResourceNotFoundError


@dataclass(frozen=True, slots=True)
class LockedBalanceState:
    settings: RowMapping
    employees: list[RowMapping]
    leave_types: list[RowMapping]
    requests: list[RowMapping]
    balances: list[RowMapping]
    holidays: list[date]


class LeaveBalanceRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        result = await self.connection.exec_driver_sql("SELECT public.workloop_business_date()")
        return result.scalar_one()

    async def employee_in_branch(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> bool:
        row = await self.connection.execute(
            select(Employee.id).where(
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
                Employee.id == employee_id,
                Employee.active.is_(True),
                Employee.employment_status != "Terminated",
            )
        )
        return row.scalar_one_or_none() is not None

    async def approver_can_read_employee(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_employee_id: uuid.UUID,
        target_employee_id: uuid.UUID,
    ) -> bool:
        allowed = await self.connection.execute(
            select(
                or_(
                    exists().where(
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                        Employee.id == target_employee_id,
                        Employee.active.is_(True),
                        Employee.employment_status != "Terminated",
                        Employee.reporting_manager_id == actor_employee_id,
                    ),
                    func.public.can_act_for_delegated_leave(target_employee_id),
                )
            )
        )
        return allowed.scalar_one() is True

    async def list_balances(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        year: int,
        *,
        employee_id: uuid.UUID | None,
        leave_type_id: uuid.UUID | None,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        criteria = [
            LeaveBalance.company_id == company_id,
            LeaveBalance.branch_id == branch_id,
            LeaveBalance.leave_year == year,
        ]
        if employee_id is not None:
            criteria.append(LeaveBalance.employee_id == employee_id)
        if leave_type_id is not None:
            criteria.append(LeaveBalance.leave_type_id == leave_type_id)
        if after_id is not None:
            criteria.append(LeaveBalance.id > after_id)
        result = await self.connection.execute(
            select(
                LeaveBalance.id,
                LeaveBalance.employee_id,
                LeaveBalance.leave_type_id,
                LeaveBalance.leave_year,
                LeaveBalance.entitled_days,
                LeaveBalance.accrued_days,
                LeaveBalance.used_days,
                LeaveBalance.pending_days,
                LeaveBalance.carried_forward,
                LeaveBalance.remaining_days,
                LeaveBalance.sick_full_pay_used,
                LeaveBalance.sick_half_pay_used,
                LeaveBalance.sick_unpaid_used,
            )
            .where(*criteria)
            .order_by(asc(LeaveBalance.id))
            .limit(limit + 1)
        )
        return list(result.mappings().all())

    async def balance_cursor_exists(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        year: int,
        balance_id: uuid.UUID,
        *,
        employee_id: uuid.UUID | None,
        leave_type_id: uuid.UUID | None,
    ) -> bool:
        criteria = [
            LeaveBalance.company_id == company_id,
            LeaveBalance.branch_id == branch_id,
            LeaveBalance.leave_year == year,
            LeaveBalance.id == balance_id,
        ]
        if employee_id is not None:
            criteria.append(LeaveBalance.employee_id == employee_id)
        if leave_type_id is not None:
            criteria.append(LeaveBalance.leave_type_id == leave_type_id)
        return (
            await self.connection.execute(select(LeaveBalance.id).where(*criteria))
        ).scalar_one_or_none() is not None

    async def list_requests(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        year: int,
        *,
        employee_id: uuid.UUID | None,
        leave_type_id: uuid.UUID | None,
        status: str | None,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        criteria = [
            LeaveRequest.company_id == company_id,
            LeaveRequest.branch_id == branch_id,
            LeaveRequest.start_date <= date(year, 12, 31),
            LeaveRequest.end_date >= date(year, 1, 1),
        ]
        if employee_id is not None:
            criteria.append(LeaveRequest.employee_id == employee_id)
        if leave_type_id is not None:
            criteria.append(LeaveRequest.leave_type_id == leave_type_id)
        if status is not None:
            criteria.append(LeaveRequest.status == status)
        if after_id is not None:
            criteria.append(LeaveRequest.id > after_id)
        result = await self.connection.execute(
            select(
                LeaveRequest.id,
                LeaveRequest.branch_id,
                LeaveRequest.employee_id,
                LeaveRequest.leave_type_id,
                LeaveRequest.start_date,
                LeaveRequest.end_date,
                LeaveRequest.is_half_day,
                LeaveRequest.half_day_period,
                LeaveRequest.status,
                LeaveRequest.reason,
                LeaveRequest.rejection_reason,
                LeaveRequest.manager_rejection_reason,
                LeaveRequest.relationship,
                LeaveRequest.deceased_name,
                LeaveRequest.date_of_death,
                LeaveRequest.child_birth_date,
                LeaveRequest.child_name,
                LeaveRequest.expected_due_date,
                LeaveRequest.institution_name,
                LeaveRequest.exam_dates,
                LeaveRequest.substitute_employee_id,
                LeaveRequest.approval_level_required,
                LeaveRequest.approval_comment,
                LeaveRequest.warnings,
                LeaveRequest.submitted_at,
                LeaveRequest.created_at,
                LeaveRequest.updated_at,
                LeaveType.day_count_type,
            )
            .join(
                LeaveType,
                (LeaveType.id == LeaveRequest.leave_type_id)
                & (LeaveType.company_id == LeaveRequest.company_id)
                & (LeaveType.branch_id == LeaveRequest.branch_id),
            )
            .where(*criteria)
            .order_by(asc(LeaveRequest.id))
            .limit(limit + 1)
        )
        return list(result.mappings().all())

    async def request_cursor_exists(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        year: int,
        request_id: uuid.UUID,
        *,
        employee_id: uuid.UUID | None,
        leave_type_id: uuid.UUID | None,
        status: str | None,
    ) -> bool:
        criteria = [
            LeaveRequest.company_id == company_id,
            LeaveRequest.branch_id == branch_id,
            LeaveRequest.id == request_id,
            LeaveRequest.start_date <= date(year, 12, 31),
            LeaveRequest.end_date >= date(year, 1, 1),
        ]
        if employee_id is not None:
            criteria.append(LeaveRequest.employee_id == employee_id)
        if leave_type_id is not None:
            criteria.append(LeaveRequest.leave_type_id == leave_type_id)
        if status is not None:
            criteria.append(LeaveRequest.status == status)
        return (
            await self.connection.execute(select(LeaveRequest.id).where(*criteria))
        ).scalar_one_or_none() is not None

    async def holidays(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, years: set[int]
    ) -> list[date]:
        result = await self.connection.execute(
            select(PublicHoliday.date).where(
                PublicHoliday.company_id == company_id,
                PublicHoliday.branch_id == branch_id,
                PublicHoliday.year.in_(sorted(years)),
            )
        )
        return list(result.scalars().all())

    async def settings(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> RowMapping:
        row = (
            (
                await self.connection.execute(
                    select(LeaveSettings.weekend_definition).where(
                        LeaveSettings.company_id == company_id,
                        LeaveSettings.branch_id == branch_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ResourceNotFoundError
        return row

    async def lock_recalculation_state(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, year: int
    ) -> LockedBalanceState:
        for table in ("employees", "leave_types", "leave_requests", "leave_balances"):
            await self.connection.exec_driver_sql(
                f"LOCK TABLE public.{table} IN SHARE ROW EXCLUSIVE MODE"
            )

        settings = (
            (
                await self.connection.execute(
                    select(LeaveSettings)
                    .where(
                        LeaveSettings.company_id == company_id,
                        LeaveSettings.branch_id == branch_id,
                    )
                    .with_for_update(read=True)
                )
            )
            .mappings()
            .one_or_none()
        )
        if settings is None:
            raise ResourceNotFoundError

        employees = list(
            (
                await self.connection.execute(
                    select(
                        Employee.id,
                        Employee.employment_start_date,
                        Employee.employment_status,
                        Employee.gender,
                    )
                    .where(
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                        Employee.active.is_(True),
                        Employee.employment_status != "Terminated",
                    )
                    .order_by(asc(Employee.id))
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )
        employee_ids = [row["id"] for row in employees]
        leave_types = list(
            (
                await self.connection.execute(
                    select(LeaveType)
                    .where(
                        LeaveType.company_id == company_id,
                        LeaveType.branch_id == branch_id,
                        LeaveType.is_active.is_(True),
                    )
                    .order_by(asc(LeaveType.id))
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )
        requests = []
        balances = []
        if employee_ids:
            requests = list(
                (
                    await self.connection.execute(
                        select(
                            LeaveRequest.id,
                            LeaveRequest.employee_id,
                            LeaveRequest.leave_type_id,
                            LeaveRequest.start_date,
                            LeaveRequest.end_date,
                            LeaveRequest.is_half_day,
                            LeaveRequest.status,
                        )
                        .where(
                            LeaveRequest.company_id == company_id,
                            LeaveRequest.branch_id == branch_id,
                            LeaveRequest.employee_id.in_(employee_ids),
                        )
                        .order_by(asc(LeaveRequest.id))
                        .with_for_update()
                    )
                )
                .mappings()
                .all()
            )
            balances = list(
                (
                    await self.connection.execute(
                        select(LeaveBalance)
                        .where(
                            LeaveBalance.company_id == company_id,
                            LeaveBalance.branch_id == branch_id,
                            LeaveBalance.employee_id.in_(employee_ids),
                            LeaveBalance.leave_year.in_([year - 1, year]),
                        )
                        .order_by(asc(LeaveBalance.id))
                        .with_for_update()
                    )
                )
                .mappings()
                .all()
            )
        holidays = await self.holidays(company_id, branch_id, {year - 1, year})
        return LockedBalanceState(
            settings=settings,
            employees=employees,
            leave_types=leave_types,
            requests=requests,
            balances=balances,
            holidays=holidays,
        )

    async def write_balances(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        year: int,
        values: list[dict[str, Any]],
        *,
        replace_existing: bool,
    ) -> None:
        for value in values:
            statement = insert(LeaveBalance).values(
                company_id=company_id,
                branch_id=branch_id,
                leave_year=year,
                **value,
            )
            if replace_existing:
                update_values: dict[str, Any] = {
                    key: statement.excluded[key]
                    for key in value
                    if key not in {"employee_id", "leave_type_id"}
                }
                update_values["updated_at"] = func.clock_timestamp()
                statement = statement.on_conflict_do_update(
                    index_elements=["employee_id", "leave_type_id", "leave_year"],
                    set_=update_values,
                )
            else:
                statement = statement.on_conflict_do_nothing(
                    index_elements=["employee_id", "leave_type_id", "leave_year"]
                )
            await self.connection.execute(statement)
