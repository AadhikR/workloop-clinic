from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import Select, and_, asc, desc, func, insert, literal, or_, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import Employee, UserProfile
from app.models.people import Department, EmployeeJobHistory
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.mutations import GuardedMutationValues

EMPLOYEE_LIST_COLUMNS = (
    Employee.id,
    Employee.emp_no,
    Employee.name,
    Employee.photo_url,
    Employee.work_email,
    Employee.job_title,
    Employee.department,
    Employee.reporting_manager_id,
    Employee.employment_start_date,
    Employee.probation_end_date,
    Employee.employment_status,
    Employee.active,
    Employee.basic_salary,
    Employee.housing_allowance,
    Employee.transport_allowance,
    Employee.other_allowances,
    Employee.bank_name,
    Employee.updated_at,
)

EMPLOYEE_DETAIL_COLUMNS = (
    *EMPLOYEE_LIST_COLUMNS,
    Employee.mol_id,
    Employee.bank_routing_code,
    Employee.iban,
    Employee.allowance,
    Employee.personal_email,
    Employee.phone,
    Employee.date_of_birth,
    Employee.gender,
    Employee.marital_status,
    Employee.home_country_address,
    Employee.emergency_contact_name,
    Employee.emergency_contact_relationship,
    Employee.emergency_contact_phone,
    Employee.probation_extended,
    Employee.termination_date,
    Employee.termination_reason,
    Employee.other_allowances_label,
    Employee.bank_account_holder,
    Employee.nationality,
    Employee.visa_type,
    Employee.visa_number,
    Employee.visa_expiry,
    Employee.passport_number,
    Employee.passport_expiry,
    Employee.emirates_id,
    Employee.emirates_id_expiry,
    Employee.labour_card_number,
    Employee.labour_card_expiry,
    Employee.sponsoring_entity,
    Employee.work_location_type,
    Employee.free_zone_name,
    Employee.nafis_registration_no,
    Employee.licence_authority,
    Employee.licence_number,
    Employee.licence_expiry,
    Employee.created_at,
)


def _same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        utc_value = value.astimezone(UTC)
        return utc_value.replace(microsecond=utc_value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


DIRECT_REPORT_COLUMNS = (
    Employee.id,
    Employee.emp_no,
    Employee.name,
    Employee.photo_url,
    Employee.job_title,
    Employee.department,
    Employee.employment_start_date,
    Employee.probation_end_date,
    Employee.employment_status,
)

JOB_HISTORY_COLUMNS = (
    EmployeeJobHistory.id,
    EmployeeJobHistory.employee_id,
    EmployeeJobHistory.changed_at,
    EmployeeJobHistory.changed_by_app_user_id,
    EmployeeJobHistory.change_type,
    EmployeeJobHistory.old_value,
    EmployeeJobHistory.new_value,
    EmployeeJobHistory.reason,
)

EmployeeSort = tuple[tuple[str, bool], ...]


def _contains_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _employee_sort_expression(field: str, descending: bool) -> Any:
    columns = {
        "name": Employee.name,
        "empNo": Employee.emp_no,
        "employmentStartDate": Employee.employment_start_date,
        "basicSalary": Employee.basic_salary,
        "createdAt": Employee.created_at,
        "updatedAt": Employee.updated_at,
    }
    column = columns[field]
    if field == "employmentStartDate":
        fallback = date.min if descending else date.max
        return func.coalesce(column, literal(fallback, type_=column.type))
    return column


def _employee_order(sort: EmployeeSort) -> list[Any]:
    order = [
        desc(_employee_sort_expression(field, descending))
        if descending
        else asc(_employee_sort_expression(field, descending))
        for field, descending in sort
    ]
    order.append(asc(Employee.id))
    return order


def _after_employee(sort: EmployeeSort, values: tuple[object, ...]) -> Any:
    components = [
        (_employee_sort_expression(field, descending), descending) for field, descending in sort
    ]
    components.append((Employee.id, False))
    alternatives: list[Any] = []
    for index, ((column, descending), value) in enumerate(zip(components, values, strict=True)):
        equals = [components[prior][0] == values[prior] for prior in range(index)]
        comparison = column < value if descending else column > value
        alternatives.append(and_(*equals, comparison))
    return or_(*alternatives)


def _employee_filters(
    statement: Select[Any],
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    search: str | None,
    employment_status: str | None,
    department: str | None,
    active: bool | None,
    reporting_manager_id: uuid.UUID | Literal["null"] | None,
) -> Select[Any]:
    statement = statement.where(
        Employee.company_id == company_id,
        Employee.branch_id == branch_id,
    )
    if search is not None:
        pattern = _contains_pattern(search)
        statement = statement.where(
            or_(
                Employee.name.ilike(pattern, escape="\\"),
                Employee.emp_no.ilike(pattern, escape="\\"),
                Employee.work_email.ilike(pattern, escape="\\"),
                Employee.mol_id.ilike(pattern, escape="\\"),
                Employee.labour_card_number.ilike(pattern, escape="\\"),
            )
        )
    if employment_status is not None:
        statement = statement.where(Employee.employment_status == employment_status)
    if department is not None:
        statement = statement.where(Employee.department == department)
    if active is not None:
        statement = statement.where(Employee.active.is_(active))
    if reporting_manager_id == "null":
        statement = statement.where(Employee.reporting_manager_id.is_(None))
    elif reporting_manager_id is not None:
        statement = statement.where(Employee.reporting_manager_id == reporting_manager_id)
    return statement


class EmployeeRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def fetch_employees(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        search: str | None,
        employment_status: str | None,
        department: str | None,
        active: bool | None,
        reporting_manager_id: uuid.UUID | Literal["null"] | None,
        sort: EmployeeSort,
        after: tuple[object, ...] | None,
        limit: int,
    ) -> list[RowMapping]:
        statement = _employee_filters(
            select(*EMPLOYEE_LIST_COLUMNS),
            company_id=company_id,
            branch_id=branch_id,
            search=search,
            employment_status=employment_status,
            department=department,
            active=active,
            reporting_manager_id=reporting_manager_id,
        )
        if after is not None:
            statement = statement.where(_after_employee(sort, after))
        result = await self._connection.execute(
            statement.order_by(*_employee_order(sort)).limit(limit + 1)
        )
        return list(result.mappings().all())

    async def fetch_employee_position(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        cursor_id: uuid.UUID,
        search: str | None,
        employment_status: str | None,
        department: str | None,
        active: bool | None,
        reporting_manager_id: uuid.UUID | Literal["null"] | None,
        sort: EmployeeSort,
    ) -> tuple[object, ...]:
        expressions = [_employee_sort_expression(field, descending) for field, descending in sort]
        statement = _employee_filters(
            select(*expressions, Employee.id),
            company_id=company_id,
            branch_id=branch_id,
            search=search,
            employment_status=employment_status,
            department=department,
            active=active,
            reporting_manager_id=reporting_manager_id,
        ).where(Employee.id == cursor_id)
        row = (await self._connection.execute(statement.limit(1))).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return tuple(row)

    async def fetch_employee(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping:
        statement = select(*EMPLOYEE_DETAIL_COLUMNS).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.branch_id == branch_id,
        )
        row = (await self._connection.execute(statement.limit(1))).mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def lock_department(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, name: str
    ) -> None:
        statement = (
            select(Department.id)
            .where(
                Department.company_id == company_id,
                Department.branch_id == branch_id,
                Department.name == name,
            )
            .with_for_update(read=True)
            .limit(1)
        )
        if (await self._connection.execute(statement)).scalar_one_or_none() is None:
            raise ResourceNotFoundError

    async def lock_manager(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping:
        statement = (
            select(Employee.id, Employee.active, Employee.employment_status)
            .select_from(Employee)
            .where(
                Employee.id == employee_id,
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
            )
            .with_for_update(read=True, of=Employee)
            .limit(1)
        )
        row = (await self._connection.execute(statement)).mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def create_employee(self, values: GuardedMutationValues) -> RowMapping:
        result = await self._connection.execute(
            insert(Employee).values(**dict(values)).returning(*EMPLOYEE_DETAIL_COLUMNS)
        )
        return result.mappings().one()

    async def create_imported_employee(self, values: GuardedMutationValues) -> uuid.UUID:
        result = await self._connection.execute(
            insert(Employee).values(**dict(values)).returning(Employee.id)
        )
        return result.scalar_one()

    async def update_employee(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        expected_updated_at: datetime,
        values: GuardedMutationValues,
    ) -> RowMapping:
        current = await self._connection.execute(
            select(Employee.updated_at)
            .where(
                Employee.id == employee_id,
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
            )
            .with_for_update()
            .limit(1)
        )
        updated_at = current.scalar_one_or_none()
        if updated_at is None:
            raise ResourceNotFoundError
        if not _same_version(updated_at, expected_updated_at):
            raise ValueError("state conflict")
        result = await self._connection.execute(
            update(Employee)
            .where(
                Employee.id == employee_id,
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
            )
            .values(**dict(values))
            .returning(*EMPLOYEE_DETAIL_COLUMNS)
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def manager_is_eligible(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> bool:
        row = await self.lock_manager(
            company_id=company_id, branch_id=branch_id, employee_id=employee_id
        )
        return row["active"] is True and row["employment_status"] in {
            "Active",
            "Probation",
            "On Leave",
        }

    async def fetch_self(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> tuple[RowMapping, RowMapping | None]:
        statement = select(*EMPLOYEE_DETAIL_COLUMNS).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.branch_id == branch_id,
            Employee.active.is_(True),
            Employee.employment_status.in_(("Active", "Probation", "On Leave")),
        )
        row = (await self._connection.execute(statement.limit(1))).mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        manager = (
            (
                await self._connection.execute(
                    text(
                        "SELECT id, name, job_title "
                        "FROM public.current_employee_reporting_manager()"
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        return row, manager

    async def fetch_direct_reports(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        manager_id: uuid.UUID,
        search: str | None,
        employment_status: str | None,
        sort: EmployeeSort,
        after: tuple[object, ...] | None,
        limit: int,
    ) -> list[RowMapping]:
        statement = select(*DIRECT_REPORT_COLUMNS).where(
            Employee.company_id == company_id,
            Employee.branch_id == branch_id,
            Employee.reporting_manager_id == manager_id,
            Employee.active.is_(True),
            Employee.employment_status.in_(("Active", "Probation", "On Leave")),
        )
        if search is not None:
            pattern = _contains_pattern(search)
            statement = statement.where(
                or_(
                    Employee.name.ilike(pattern, escape="\\"),
                    Employee.emp_no.ilike(pattern, escape="\\"),
                    Employee.job_title.ilike(pattern, escape="\\"),
                    Employee.department.ilike(pattern, escape="\\"),
                )
            )
        if employment_status is not None:
            statement = statement.where(Employee.employment_status == employment_status)
        if after is not None:
            statement = statement.where(_after_employee(sort, after))
        result = await self._connection.execute(
            statement.order_by(*_employee_order(sort)).limit(limit + 1)
        )
        return list(result.mappings().all())

    async def fetch_direct_report_position(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        manager_id: uuid.UUID,
        cursor_id: uuid.UUID,
        search: str | None,
        employment_status: str | None,
        sort: EmployeeSort,
    ) -> tuple[object, ...]:
        expressions = [_employee_sort_expression(field, descending) for field, descending in sort]
        statement = select(*expressions, Employee.id).where(
            Employee.id == cursor_id,
            Employee.company_id == company_id,
            Employee.branch_id == branch_id,
            Employee.reporting_manager_id == manager_id,
            Employee.active.is_(True),
            Employee.employment_status.in_(("Active", "Probation", "On Leave")),
        )
        if search is not None:
            pattern = _contains_pattern(search)
            statement = statement.where(
                or_(
                    Employee.name.ilike(pattern, escape="\\"),
                    Employee.emp_no.ilike(pattern, escape="\\"),
                    Employee.job_title.ilike(pattern, escape="\\"),
                    Employee.department.ilike(pattern, escape="\\"),
                )
            )
        if employment_status is not None:
            statement = statement.where(Employee.employment_status == employment_status)
        row = (await self._connection.execute(statement.limit(1))).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return tuple(row)

    async def assert_employee_exists(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> None:
        statement = select(Employee.id).where(
            Employee.id == employee_id,
            Employee.company_id == company_id,
            Employee.branch_id == branch_id,
        )
        if (await self._connection.execute(statement.limit(1))).scalar_one_or_none() is None:
            raise ResourceNotFoundError

    async def fetch_job_history(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        change_type: str | None,
        changed_from: datetime | None,
        changed_to: datetime | None,
        descending: bool,
        after: tuple[datetime, uuid.UUID] | None,
        limit: int,
    ) -> list[RowMapping]:
        statement = select(*JOB_HISTORY_COLUMNS).where(
            EmployeeJobHistory.company_id == company_id,
            EmployeeJobHistory.branch_id == branch_id,
        )
        if employee_id is not None:
            statement = statement.where(EmployeeJobHistory.employee_id == employee_id)
        if change_type is not None:
            statement = statement.where(EmployeeJobHistory.change_type == change_type)
        if changed_from is not None:
            statement = statement.where(EmployeeJobHistory.changed_at >= changed_from)
        if changed_to is not None:
            statement = statement.where(EmployeeJobHistory.changed_at <= changed_to)
        if after is not None:
            changed_at, history_id = after
            statement = statement.where(
                or_(
                    EmployeeJobHistory.changed_at < changed_at
                    if descending
                    else EmployeeJobHistory.changed_at > changed_at,
                    and_(
                        EmployeeJobHistory.changed_at == changed_at,
                        EmployeeJobHistory.id > history_id,
                    ),
                )
            )
        result = await self._connection.execute(
            statement.order_by(
                desc(EmployeeJobHistory.changed_at)
                if descending
                else asc(EmployeeJobHistory.changed_at),
                asc(EmployeeJobHistory.id),
            ).limit(limit + 1)
        )
        return list(result.mappings().all())

    async def fetch_job_history_position(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        cursor_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        change_type: str | None,
        changed_from: datetime | None,
        changed_to: datetime | None,
    ) -> tuple[datetime, uuid.UUID]:
        statement = select(EmployeeJobHistory.changed_at, EmployeeJobHistory.id).where(
            EmployeeJobHistory.id == cursor_id,
            EmployeeJobHistory.company_id == company_id,
            EmployeeJobHistory.branch_id == branch_id,
        )
        if employee_id is not None:
            statement = statement.where(EmployeeJobHistory.employee_id == employee_id)
        if change_type is not None:
            statement = statement.where(EmployeeJobHistory.change_type == change_type)
        if changed_from is not None:
            statement = statement.where(EmployeeJobHistory.changed_at >= changed_from)
        if changed_to is not None:
            statement = statement.where(EmployeeJobHistory.changed_at <= changed_to)
        row = (await self._connection.execute(statement.limit(1))).one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row[0], row[1]

    async def lock_employee(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping:
        row = (
            (
                await self._connection.execute(
                    select(*EMPLOYEE_DETAIL_COLUMNS)
                    .where(
                        Employee.id == employee_id,
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                    )
                    .with_for_update()
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ResourceNotFoundError
        return row

    async def lock_employee_set(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, employee_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, RowMapping]:
        if not employee_ids:
            return {}
        rows = (
            (
                await self._connection.execute(
                    select(*EMPLOYEE_DETAIL_COLUMNS)
                    .where(
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                        Employee.id.in_(employee_ids),
                    )
                    .order_by(Employee.id)
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )
        return {row["id"]: row for row in rows}

    async def acquire_relationship_locks(self, employee_ids: set[uuid.UUID]) -> None:
        if employee_ids:
            await self._connection.exec_driver_sql(
                "SELECT public.lock_authorized_employee_relationships(%s::uuid[])",
                ([str(value) for value in sorted(employee_ids)],),
            )

    async def fetch_report_ids(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, manager_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await self._connection.execute(
            select(Employee.id)
            .where(
                Employee.company_id == company_id,
                Employee.branch_id == branch_id,
                Employee.reporting_manager_id == manager_id,
            )
            .order_by(Employee.id)
        )
        return list(result.scalars().all())

    async def update_workflow_employee(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        values: GuardedMutationValues,
    ) -> RowMapping:
        row = (
            (
                await self._connection.execute(
                    update(Employee)
                    .where(
                        Employee.id == employee_id,
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                    )
                    .values(**dict(values))
                    .returning(*EMPLOYEE_DETAIL_COLUMNS)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ResourceNotFoundError
        return row

    async def append_job_history(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        actor_id: uuid.UUID,
        change_type: str,
        old_value: str,
        new_value: str,
        reason: str,
    ) -> None:
        await self._connection.execute(
            insert(EmployeeJobHistory).values(
                company_id=company_id,
                branch_id=branch_id,
                employee_id=employee_id,
                changed_by_app_user_id=actor_id,
                change_type=change_type,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
            )
        )

    async def append_employee_audit(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        changed_fields: list[str],
        reason: str,
        metadata: dict[str, object],
    ) -> None:
        await self._connection.exec_driver_sql(
            "SELECT public.append_audit_event(%s,%s,%s,%s::text[],%s,%s::jsonb)",
            (action, entity_type, entity_id, changed_fields, reason, json.dumps(metadata)),
        )

    async def would_create_manager_cycle(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        new_manager_id: uuid.UUID,
    ) -> bool:
        return bool(
            (
                await self._connection.execute(
                    text(
                        """
WITH RECURSIVE manager_chain(id,reporting_manager_id) AS (
  SELECT id,reporting_manager_id FROM employees
  WHERE id=:new_manager_id AND company_id=:company_id AND branch_id=:branch_id
  UNION
  SELECT employee.id,employee.reporting_manager_id
  FROM employees AS employee
  JOIN manager_chain AS current ON employee.id=current.reporting_manager_id
  WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
)
SELECT EXISTS(SELECT 1 FROM manager_chain WHERE id=:employee_id)
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "new_manager_id": new_manager_id,
                    },
                )
            ).scalar_one()
        )

    async def fetch_portal_role(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        lock: bool = False,
    ) -> RowMapping | None:
        suffix = " FOR UPDATE OF profile" if lock else ""
        return (
            (
                await self._connection.execute(
                    text(
                        f"""
SELECT profile.app_user_id,profile.employee_id,profile.role::text AS role,
  public.is_scoped_active_app_user(profile.app_user_id) AS eligible
FROM user_profiles AS profile
JOIN employees AS employee ON employee.id=profile.employee_id
  AND employee.company_id=profile.company_id
WHERE profile.company_id=:company_id AND employee.branch_id=:branch_id
  AND profile.employee_id=:employee_id
LIMIT 1
{suffix}
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )

    async def update_portal_role(
        self, *, app_user_id: uuid.UUID, employee_id: uuid.UUID, role: str
    ) -> None:
        result = await self._connection.execute(
            update(UserProfile)
            .where(
                UserProfile.app_user_id == app_user_id,
                UserProfile.employee_id == employee_id,
            )
            .values(role=role)
            .returning(UserProfile.app_user_id)
        )
        if result.scalar_one_or_none() is None:
            raise ResourceNotFoundError

    async def business_date(self) -> date:
        return (
            await self._connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()
