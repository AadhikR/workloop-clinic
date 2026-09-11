from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import Select, and_, asc, delete, desc, func, insert, literal, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import Employee
from app.models.people import Department, DepartmentStaffingRule, EmployeeJobHistory
from app.models.records import AuditEvent
from app.repositories.scoped import ResourceNotFoundError

DEPARTMENT_COLUMNS = (
    Department.id,
    Department.name,
    Department.parent_id,
    Department.head_employee_id,
    Department.color,
    Department.description,
    Department.sort_order,
    Department.created_at,
)

STAFFING_COLUMNS = (
    DepartmentStaffingRule.id,
    DepartmentStaffingRule.department,
    DepartmentStaffingRule.shift_category,
    DepartmentStaffingRule.min_staff,
    DepartmentStaffingRule.effective_from,
    DepartmentStaffingRule.effective_to,
)

DepartmentSort = tuple[tuple[str, bool], ...]
StaffingSort = tuple[tuple[str, bool], ...]


def _after(components: list[tuple[Any, bool]], values: tuple[object, ...]) -> Any:
    alternatives: list[Any] = []
    for index, ((column, descending), value) in enumerate(zip(components, values, strict=True)):
        equals = [components[prior][0] == values[prior] for prior in range(index)]
        comparison = column < value if descending else column > value
        alternatives.append(and_(*equals, comparison))
    return or_(*alternatives)


def _department_components(sort: DepartmentSort) -> list[tuple[Any, bool]]:
    columns = {
        "sortOrder": Department.sort_order,
        "name": Department.name,
        "createdAt": Department.created_at,
    }
    components: list[tuple[Any, bool]] = [
        (columns[field], descending) for field, descending in sort
    ]
    components.append((Department.id, False))
    return components


def _staffing_expression(field: str, descending: bool) -> Any:
    columns = {
        "department": DepartmentStaffingRule.department,
        "shiftCategory": DepartmentStaffingRule.shift_category,
        "effectiveFrom": DepartmentStaffingRule.effective_from,
        "effectiveTo": DepartmentStaffingRule.effective_to,
    }
    column = columns[field]
    if field in {"effectiveFrom", "effectiveTo"}:
        fallback = date.min if descending else date.max
        return func.coalesce(column, literal(fallback, type_=column.type))
    return column


def _staffing_components(sort: StaffingSort) -> list[tuple[Any, bool]]:
    components: list[tuple[Any, bool]] = [
        (_staffing_expression(field, descending), descending) for field, descending in sort
    ]
    components.append((DepartmentStaffingRule.id, False))
    return components


class DepartmentRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def fetch_department(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, department_id: uuid.UUID
    ) -> RowMapping:
        result = await self._connection.execute(
            select(*DEPARTMENT_COLUMNS)
            .where(
                Department.company_id == company_id,
                Department.branch_id == branch_id,
                Department.id == department_id,
            )
            .limit(1)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def fetch_department_position(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        department_id: uuid.UUID,
        sort: DepartmentSort,
    ) -> tuple[object, ...]:
        components = _department_components(sort)
        result = await self._connection.execute(
            select(*(column for column, _descending in components))
            .where(
                Department.company_id == company_id,
                Department.branch_id == branch_id,
                Department.id == department_id,
            )
            .limit(1)
        )
        row = result.tuples().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return tuple(row)

    async def fetch_departments(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        search: str | None,
        parent_id: uuid.UUID | str | None,
        head_employee_id: uuid.UUID | str | None,
        sort: DepartmentSort,
        after: tuple[object, ...] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        statement: Select[Any] = select(*DEPARTMENT_COLUMNS).where(
            Department.company_id == company_id,
            Department.branch_id == branch_id,
        )
        if search is not None:
            statement = statement.where(
                func.lower(Department.name).contains(search.lower(), autoescape=True)
            )
        if parent_id == "null":
            statement = statement.where(Department.parent_id.is_(None))
        elif isinstance(parent_id, uuid.UUID):
            statement = statement.where(Department.parent_id == parent_id)
        if head_employee_id == "null":
            statement = statement.where(Department.head_employee_id.is_(None))
        elif isinstance(head_employee_id, uuid.UUID):
            statement = statement.where(Department.head_employee_id == head_employee_id)
        components = _department_components(sort)
        if after is not None:
            statement = statement.where(_after(components, after))
        ordering = [
            desc(column) if descending else asc(column) for column, descending in components
        ]
        result = await self._connection.execute(statement.order_by(*ordering).limit(limit + 1))
        return result.mappings().all()

    async def lock_hierarchy(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> Sequence[RowMapping]:
        result = await self._connection.execute(
            select(*DEPARTMENT_COLUMNS)
            .where(Department.company_id == company_id, Department.branch_id == branch_id)
            .order_by(Department.id)
            .with_for_update()
        )
        return result.mappings().all()

    async def fetch_head(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping:
        result = await self._connection.execute(
            select(Employee.id, Employee.active, Employee.employment_status)
            .where(
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
                Employee.id == employee_id,
            )
            .limit(1)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def create_department(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, values: dict[str, object]
    ) -> RowMapping:
        result = await self._connection.execute(
            insert(Department)
            .values(company_id=company_id, branch_id=branch_id, **values)
            .returning(*DEPARTMENT_COLUMNS)
        )
        return result.mappings().one()

    async def update_department(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        department_id: uuid.UUID,
        changes: dict[str, object],
    ) -> RowMapping:
        result = await self._connection.execute(
            update(Department)
            .where(
                Department.company_id == company_id,
                Department.branch_id == branch_id,
                Department.id == department_id,
            )
            .values(**changes)
            .returning(*DEPARTMENT_COLUMNS)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def rename_dependents(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        old_name: str,
        new_name: str,
        actor_id: uuid.UUID,
    ) -> None:
        employee_result = await self._connection.execute(
            select(Employee.id)
            .where(
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
                Employee.department == old_name,
            )
            .order_by(Employee.id)
            .with_for_update()
        )
        employee_ids = list(employee_result.scalars().all())
        await self._connection.execute(
            select(DepartmentStaffingRule.id)
            .where(
                DepartmentStaffingRule.company_id == company_id,
                DepartmentStaffingRule.branch_id == branch_id,
                DepartmentStaffingRule.department == old_name,
            )
            .order_by(DepartmentStaffingRule.id)
            .with_for_update()
        )
        if employee_ids:
            await self._connection.execute(
                update(Employee)
                .where(Employee.id.in_(employee_ids))
                .values(department=new_name, updated_at=func.now())
            )
        await self._connection.execute(
            update(DepartmentStaffingRule)
            .where(
                DepartmentStaffingRule.company_id == company_id,
                DepartmentStaffingRule.branch_id == branch_id,
                DepartmentStaffingRule.department == old_name,
            )
            .values(department=new_name)
        )
        if employee_ids:
            await self._connection.execute(
                insert(EmployeeJobHistory),
                [
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "changed_by_app_user_id": actor_id,
                        "change_type": "department_change",
                        "old_value": old_name,
                        "new_value": new_name,
                        "reason": "Department renamed",
                    }
                    for employee_id in employee_ids
                ],
            )

    async def delete_guarded_department(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        department_id: uuid.UUID,
        name: str,
    ) -> bool:
        guards = (
            select(Department.id).where(
                Department.company_id == company_id,
                Department.branch_id == branch_id,
                Department.parent_id == department_id,
            ),
            select(Employee.id).where(
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
                Employee.department == name,
            ),
            select(DepartmentStaffingRule.id).where(
                DepartmentStaffingRule.company_id == company_id,
                DepartmentStaffingRule.branch_id == branch_id,
                DepartmentStaffingRule.department == name,
            ),
            select(AuditEvent.id).where(
                AuditEvent.company_id == company_id,
                AuditEvent.branch_id == branch_id,
                AuditEvent.entity_type == "department",
                AuditEvent.entity_id == department_id,
            ),
        )
        for guard in guards:
            result = await self._connection.execute(select(guard.exists()))
            if result.scalar_one():
                return False
        result = await self._connection.execute(
            delete(Department).where(
                Department.company_id == company_id,
                Department.branch_id == branch_id,
                Department.id == department_id,
            )
        )
        if result.rowcount != 1:
            raise ResourceNotFoundError
        await self._connection.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
        return True

    async def fetch_staffing_position(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        rule_id: uuid.UUID,
        sort: StaffingSort,
    ) -> tuple[object, ...]:
        components = _staffing_components(sort)
        result = await self._connection.execute(
            select(*(column for column, _descending in components))
            .where(
                DepartmentStaffingRule.company_id == company_id,
                DepartmentStaffingRule.branch_id == branch_id,
                DepartmentStaffingRule.id == rule_id,
            )
            .limit(1)
        )
        row = result.tuples().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return tuple(row)

    async def fetch_staffing_rules(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        department: str | None,
        shift_category: str | None,
        effective_on: date | None,
        sort: StaffingSort,
        after: tuple[object, ...] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        statement: Select[Any] = select(*STAFFING_COLUMNS).where(
            DepartmentStaffingRule.company_id == company_id,
            DepartmentStaffingRule.branch_id == branch_id,
        )
        if department is not None:
            statement = statement.where(DepartmentStaffingRule.department == department)
        if shift_category is not None:
            statement = statement.where(DepartmentStaffingRule.shift_category == shift_category)
        if effective_on is not None:
            statement = statement.where(
                or_(
                    DepartmentStaffingRule.effective_from.is_(None),
                    DepartmentStaffingRule.effective_from <= effective_on,
                ),
                or_(
                    DepartmentStaffingRule.effective_to.is_(None),
                    DepartmentStaffingRule.effective_to >= effective_on,
                ),
            )
        components = _staffing_components(sort)
        if after is not None:
            statement = statement.where(_after(components, after))
        ordering = [
            desc(column) if descending else asc(column) for column, descending in components
        ]
        result = await self._connection.execute(statement.order_by(*ordering).limit(limit + 1))
        return result.mappings().all()

    async def fetch_staffing_rule(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, rule_id: uuid.UUID, *, lock: bool = False
    ) -> RowMapping:
        statement = select(*STAFFING_COLUMNS).where(
            DepartmentStaffingRule.company_id == company_id,
            DepartmentStaffingRule.branch_id == branch_id,
            DepartmentStaffingRule.id == rule_id,
        )
        if lock:
            statement = statement.with_for_update()
        result = await self._connection.execute(statement.limit(1))
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def create_staffing_rule(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, values: dict[str, object]
    ) -> RowMapping:
        result = await self._connection.execute(
            insert(DepartmentStaffingRule)
            .values(company_id=company_id, branch_id=branch_id, **values)
            .returning(*STAFFING_COLUMNS)
        )
        return result.mappings().one()

    async def update_staffing_rule(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        rule_id: uuid.UUID,
        changes: dict[str, object],
    ) -> RowMapping:
        result = await self._connection.execute(
            update(DepartmentStaffingRule)
            .where(
                DepartmentStaffingRule.company_id == company_id,
                DepartmentStaffingRule.branch_id == branch_id,
                DepartmentStaffingRule.id == rule_id,
            )
            .values(**changes)
            .returning(*STAFFING_COLUMNS)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def delete_staffing_rule(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, rule_id: uuid.UUID
    ) -> None:
        result = await self._connection.execute(
            delete(DepartmentStaffingRule).where(
                DepartmentStaffingRule.company_id == company_id,
                DepartmentStaffingRule.branch_id == branch_id,
                DepartmentStaffingRule.id == rule_id,
            )
        )
        if result.rowcount != 1:
            raise ResourceNotFoundError
