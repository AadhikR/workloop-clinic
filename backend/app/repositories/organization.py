from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, and_, asc, delete, desc, func, insert, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import Branch, Company
from app.repositories.scoped import ResourceNotFoundError

COMPANY_COLUMNS = (
    Company.id,
    Company.name,
    Company.sector,
    Company.nafis_quota_percent,
    Company.enable_nafis,
    Company.created_at,
    Company.updated_at,
)

BRANCH_ADMIN_COLUMNS = (
    Branch.id,
    Branch.name,
    Branch.mol_employer_id,
    Branch.default_bank_routing_code,
    Branch.address,
    Branch.contact_email,
    Branch.default_salary_day,
    Branch.work_location_type,
    Branch.free_zone_name,
    Branch.logo_url,
    Branch.enable_staffing_rules,
    Branch.enable_biometric_import,
    Branch.created_at,
    Branch.updated_at,
)

BRANCH_SAFE_COLUMNS = (
    Branch.id,
    Branch.name,
    Branch.address,
    Branch.contact_email,
    Branch.work_location_type,
    Branch.free_zone_name,
    Branch.logo_url,
    Branch.created_at,
)


def _same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        utc_value = value.astimezone(UTC)
        return utc_value.replace(microsecond=utc_value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


def _after_position(sort: tuple[tuple[str, bool], ...], values: tuple[object, ...]) -> Any:
    sort_columns = {"name": Branch.name, "createdAt": Branch.created_at}
    components: list[tuple[Any, bool]] = [
        (sort_columns[field], descending) for field, descending in sort
    ]
    components.append((Branch.id, False))
    alternatives: list[Any] = []
    for index, ((column, descending), value) in enumerate(zip(components, values, strict=True)):
        equals = [components[prior][0] == values[prior] for prior in range(index)]
        comparison = column < value if descending else column > value
        alternatives.append(and_(*equals, comparison))
    return or_(*alternatives)


class OrganizationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def fetch_company(self, company_id: uuid.UUID) -> RowMapping:
        statement = select(*COMPANY_COLUMNS).where(Company.id == company_id).limit(1)
        result = await self._connection.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def update_company(
        self,
        *,
        company_id: uuid.UUID,
        expected_updated_at: datetime,
        changes: dict[str, object],
    ) -> RowMapping:
        current = await self._connection.execute(
            select(Company.updated_at).where(Company.id == company_id).with_for_update().limit(1)
        )
        updated_at = current.scalar_one_or_none()
        if updated_at is None:
            raise ResourceNotFoundError
        if not _same_version(updated_at, expected_updated_at):
            raise ValueError("state conflict")
        result = await self._connection.execute(
            update(Company)
            .where(Company.id == company_id)
            .values(**changes)
            .returning(*COMPANY_COLUMNS)
        )
        return result.mappings().one()

    async def fetch_employer(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> RowMapping:
        statement = (
            select(
                Company.name.label("company_name"),
                Branch.name.label("branch_name"),
                Branch.contact_email.label("branch_contact_email"),
                Branch.address.label("branch_address"),
                Branch.work_location_type,
                Branch.free_zone_name,
                Branch.logo_url,
            )
            .select_from(Branch)
            .join(Company, Company.id == Branch.company_id)
            .where(Company.id == company_id, Branch.id == branch_id)
            .limit(1)
        )
        result = await self._connection.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def fetch_branch(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> RowMapping:
        statement = (
            select(*BRANCH_ADMIN_COLUMNS)
            .where(Branch.company_id == company_id, Branch.id == branch_id)
            .limit(1)
        )
        result = await self._connection.execute(statement)
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        return row

    async def create_branch(
        self, *, company_id: uuid.UUID, values: dict[str, object]
    ) -> RowMapping:
        result = await self._connection.execute(
            insert(Branch).values(company_id=company_id, **values).returning(*BRANCH_ADMIN_COLUMNS)
        )
        return result.mappings().one()

    async def update_branch(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        expected_updated_at: datetime,
        changes: dict[str, object],
    ) -> RowMapping:
        current = await self._connection.execute(
            select(Branch.updated_at)
            .where(Branch.company_id == company_id, Branch.id == branch_id)
            .with_for_update()
            .limit(1)
        )
        updated_at = current.scalar_one_or_none()
        if updated_at is None:
            raise ResourceNotFoundError
        if not _same_version(updated_at, expected_updated_at):
            raise ValueError("state conflict")
        result = await self._connection.execute(
            update(Branch)
            .where(Branch.company_id == company_id, Branch.id == branch_id)
            .values(**changes)
            .returning(*BRANCH_ADMIN_COLUMNS)
        )
        return result.mappings().one()

    async def append_branch_audit(self, action: str, branch_id: uuid.UUID) -> None:
        await self._connection.exec_driver_sql(
            "SELECT public.append_audit_event(%s, 'branch', %s, "
            "ARRAY['id']::text[], %s, '{}'::jsonb)",
            (action, branch_id, action.replace("_", " ").capitalize()),
        )

    async def delete_branch(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> None:
        current = await self._connection.execute(
            select(Branch.updated_at)
            .where(Branch.company_id == company_id, Branch.id == branch_id)
            .with_for_update()
            .limit(1)
        )
        updated_at = current.scalar_one_or_none()
        if updated_at is None:
            raise ResourceNotFoundError
        if not _same_version(updated_at, expected_updated_at):
            raise ValueError("state conflict")
        await self.append_branch_audit("branch_deleted", branch_id)
        result = await self._connection.execute(
            delete(Branch).where(Branch.company_id == company_id, Branch.id == branch_id)
        )
        if result.rowcount != 1:
            raise ResourceNotFoundError
        await self._connection.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")

    async def fetch_branch_position(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        cursor_branch_id: uuid.UUID,
        sort: tuple[tuple[str, bool], ...],
    ) -> tuple[object, ...]:
        sort_columns = {"name": Branch.name, "createdAt": Branch.created_at}
        columns = [sort_columns[field] for field, _descending in sort]
        statement = select(*columns, Branch.id).where(
            Branch.company_id == company_id,
            Branch.id == cursor_branch_id,
        )
        if branch_id is not None:
            statement = statement.where(Branch.id == branch_id)
        result = await self._connection.execute(statement.limit(1))
        row = result.mappings().one_or_none()
        if row is None:
            raise ResourceNotFoundError
        keys = ["name" if field == "name" else "created_at" for field, _descending in sort]
        return (*tuple(row[key] for key in keys), row["id"])

    async def fetch_branches(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        admin_projection: bool,
        search: str | None,
        sort: tuple[tuple[str, bool], ...],
        after: tuple[object, ...] | None,
        limit: int,
    ) -> Sequence[RowMapping]:
        columns = BRANCH_ADMIN_COLUMNS if admin_projection else BRANCH_SAFE_COLUMNS
        statement: Select[Any] = select(*columns).where(Branch.company_id == company_id)
        if branch_id is not None:
            statement = statement.where(Branch.id == branch_id)
        if search is not None:
            statement = statement.where(
                func.lower(Branch.name).contains(search.lower(), autoescape=True)
            )
        sort_columns = {"name": Branch.name, "createdAt": Branch.created_at}
        order_by: list[Any] = []
        for field, descending in sort:
            column = sort_columns[field]
            order_by.append(desc(column) if descending else asc(column))
        order_by.append(asc(Branch.id))
        if after is not None:
            statement = statement.where(_after_position(sort, after))
        result = await self._connection.execute(statement.order_by(*order_by).limit(limit + 1))
        return result.mappings().all()
