from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.departments import DepartmentRepository, DepartmentSort, StaffingSort
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.departments import (
    DepartmentCreateRequest,
    DepartmentDeleteRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
    StaffingRuleCreateRequest,
    StaffingRuleDeleteRequest,
    StaffingRuleResponse,
    StaffingRuleUpdateRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class DepartmentListQuery:
    limit: int
    search: str | None
    parent_id: uuid.UUID | Literal["null"] | None
    head_employee_id: uuid.UUID | Literal["null"] | None
    sort: DepartmentSort
    cursor: str | None


@dataclass(frozen=True, slots=True)
class StaffingRuleListQuery:
    limit: int
    department: str | None
    shift_category: str | None
    effective_on: date | None
    sort: StaffingSort
    cursor: str | None


def normalize_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(normalized) <= 100:
        raise ValueError("invalid search")
    return normalized


def normalize_department(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(normalized) <= 200:
        raise ValueError("invalid department")
    return normalized


def _department(row: RowMapping) -> DepartmentResponse:
    return DepartmentResponse(
        id=row["id"],
        name=row["name"],
        parent_id=row["parent_id"],
        head_employee_id=row["head_employee_id"],
        color=row["color"],
        description=row["description"],
        sort_order=row["sort_order"],
        created_at=row["created_at"],
    )


def _staffing_rule(row: RowMapping) -> StaffingRuleResponse:
    return StaffingRuleResponse(
        id=row["id"],
        department=row["department"],
        shift_category=row["shift_category"],
        min_staff=row["min_staff"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
    )


def _snapshot_matches(row: RowMapping, expected: BaseModel, fields: tuple[str, ...]) -> bool:
    values = expected.model_dump(by_alias=False)
    return all(row[field] == values[field] for field in fields)


def validate_department_hierarchy(rows: Sequence[Mapping[str, object]]) -> None:
    parents = {row["id"]: row["parent_id"] for row in rows}
    for department_id in parents:
        seen: set[object] = set()
        current: object | None = department_id
        depth = 0
        while current is not None:
            if current in seen:
                raise ServiceExecutionError("department_conflict")
            seen.add(current)
            depth += 1
            if depth > 20:
                raise ServiceExecutionError("department_conflict")
            current = parents.get(current)


class DepartmentService:
    def __init__(
        self,
        connection: AsyncConnection,
        cursor_codec: EmployeeCursorCodec,
        repository: DepartmentRepository | None = None,
    ) -> None:
        self._repository = repository or DepartmentRepository(connection)
        self._cursor_codec = cursor_codec

    @staticmethod
    def _require_admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")

    async def list_departments(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: DepartmentListQuery,
    ) -> tuple[list[DepartmentResponse], str | None]:
        self._require_admin(principal)
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_departments",
                query=query,
                cursor=query.cursor,
            )
            after = (
                None
                if after_id is None
                else await self._repository.fetch_department_position(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    department_id=after_id,
                    sort=query.sort,
                )
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.fetch_departments(
            company_id=principal.company_id,
            branch_id=branch_id,
            search=query.search,
            parent_id=query.parent_id,
            head_employee_id=query.head_employee_id,
            sort=query.sort,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        next_cursor = None
        if has_more:
            next_cursor = self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_departments",
                query=query,
                last_id=visible[-1]["id"],
            )
        return [_department(row) for row in visible], next_cursor

    async def get_department(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, department_id: uuid.UUID
    ) -> DepartmentResponse:
        self._require_admin(principal)
        try:
            return _department(
                await self._repository.fetch_department(
                    principal.company_id, branch_id, department_id
                )
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def _validate_head(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
    ) -> None:
        if employee_id is None:
            return
        try:
            row = await self._repository.fetch_head(principal.company_id, branch_id, employee_id)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if row["active"] is not True or row["employment_status"] == "Terminated":
            raise ServiceExecutionError("department_conflict")

    async def create_department(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: DepartmentCreateRequest,
    ) -> DepartmentResponse:
        self._require_admin(principal)
        hierarchy = list(await self._repository.lock_hierarchy(principal.company_id, branch_id))
        identifiers = {row["id"] for row in hierarchy}
        if request.parent_id is not None and request.parent_id not in identifiers:
            raise ServiceExecutionError("resource_not_found")
        if any(row["name"] == request.name for row in hierarchy):
            raise ServiceExecutionError("department_conflict")
        await self._validate_head(principal, branch_id, request.head_employee_id)
        candidate_id = uuid.uuid4()
        graph = [dict(row) for row in hierarchy]
        graph.append({"id": candidate_id, "parent_id": request.parent_id})
        validate_department_hierarchy(graph)
        try:
            return _department(
                await self._repository.create_department(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    values=request.values(),
                )
            )
        except IntegrityError:
            raise ServiceExecutionError("department_conflict") from None

    async def update_department(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        department_id: uuid.UUID,
        request: DepartmentUpdateRequest,
    ) -> DepartmentResponse:
        self._require_admin(principal)
        hierarchy = list(await self._repository.lock_hierarchy(principal.company_id, branch_id))
        current = next((row for row in hierarchy if row["id"] == department_id), None)
        if current is None:
            raise ServiceExecutionError("resource_not_found")
        snapshot_fields = (
            "name",
            "parent_id",
            "head_employee_id",
            "color",
            "description",
            "sort_order",
        )
        if not _snapshot_matches(current, request.expected, snapshot_fields):
            raise ServiceExecutionError("state_conflict")
        changes = request.changes()
        new_name = str(changes.get("name", current["name"]))
        parent_id = changes.get("parent_id", current["parent_id"])
        head_id = changes.get("head_employee_id", current["head_employee_id"])
        identifiers = {row["id"] for row in hierarchy}
        if parent_id is not None and parent_id not in identifiers:
            raise ServiceExecutionError("resource_not_found")
        if any(row["id"] != department_id and row["name"] == new_name for row in hierarchy):
            raise ServiceExecutionError("department_conflict")
        await self._validate_head(
            principal, branch_id, head_id if isinstance(head_id, uuid.UUID) else None
        )
        graph = [dict(row) for row in hierarchy]
        for row in graph:
            if row["id"] == department_id:
                row["parent_id"] = parent_id
        validate_department_hierarchy(graph)
        old_name = str(current["name"])
        try:
            if new_name != old_name:
                await self._repository.rename_dependents(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    old_name=old_name,
                    new_name=new_name,
                    actor_id=principal.app_user_id,
                )
            row = await self._repository.update_department(
                company_id=principal.company_id,
                branch_id=branch_id,
                department_id=department_id,
                changes=changes,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except IntegrityError:
            raise ServiceExecutionError("department_conflict") from None
        return _department(row)

    async def authorize_department_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._require_admin(principal)
        if kind != "department" or resource_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        await self.get_department(principal, branch_id, resource_id)

    async def delete_department(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        department_id: uuid.UUID,
        request: DepartmentDeleteRequest,
    ) -> None:
        self._require_admin(principal)
        hierarchy = list(await self._repository.lock_hierarchy(principal.company_id, branch_id))
        current = next((row for row in hierarchy if row["id"] == department_id), None)
        if current is None:
            raise ServiceExecutionError("resource_not_found")
        snapshot_fields = (
            "name",
            "parent_id",
            "head_employee_id",
            "color",
            "description",
            "sort_order",
        )
        if not _snapshot_matches(current, request.expected, snapshot_fields):
            raise ServiceExecutionError("state_conflict")
        if current["head_employee_id"] is not None:
            raise ServiceExecutionError("department_conflict")
        try:
            deleted = await self._repository.delete_guarded_department(
                company_id=principal.company_id,
                branch_id=branch_id,
                department_id=department_id,
                name=str(current["name"]),
            )
        except (IntegrityError, ValueError):
            raise ServiceExecutionError("department_conflict") from None
        if not deleted:
            raise ServiceExecutionError("department_conflict")

    async def list_staffing_rules(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: StaffingRuleListQuery,
    ) -> tuple[list[StaffingRuleResponse], str | None]:
        self._require_admin(principal)
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_department_staffing_rules",
                query=query,
                cursor=query.cursor,
            )
            after = (
                None
                if after_id is None
                else await self._repository.fetch_staffing_position(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    rule_id=after_id,
                    sort=query.sort,
                )
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.fetch_staffing_rules(
            company_id=principal.company_id,
            branch_id=branch_id,
            department=query.department,
            shift_category=query.shift_category,
            effective_on=query.effective_on,
            sort=query.sort,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        next_cursor = None
        if has_more:
            next_cursor = self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_department_staffing_rules",
                query=query,
                last_id=visible[-1]["id"],
            )
        return [_staffing_rule(row) for row in visible], next_cursor

    async def _department_name_exists(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, name: str
    ) -> bool:
        hierarchy = await self._repository.lock_hierarchy(principal.company_id, branch_id)
        return any(row["name"] == name for row in hierarchy)

    async def create_staffing_rule(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: StaffingRuleCreateRequest,
    ) -> StaffingRuleResponse:
        self._require_admin(principal)
        if not await self._department_name_exists(principal, branch_id, request.department):
            raise ServiceExecutionError("staffing_rule_conflict")
        try:
            return _staffing_rule(
                await self._repository.create_staffing_rule(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    values=request.values(),
                )
            )
        except IntegrityError:
            raise ServiceExecutionError("staffing_rule_conflict") from None

    async def update_staffing_rule(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        rule_id: uuid.UUID,
        request: StaffingRuleUpdateRequest,
    ) -> StaffingRuleResponse:
        self._require_admin(principal)
        try:
            current = await self._repository.fetch_staffing_rule(
                principal.company_id, branch_id, rule_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        snapshot_fields = (
            "department",
            "shift_category",
            "min_staff",
            "effective_from",
            "effective_to",
        )
        if not _snapshot_matches(current, request.expected, snapshot_fields):
            raise ServiceExecutionError("state_conflict")
        changes = request.changes()
        department = str(changes.get("department", current["department"]))
        if not await self._department_name_exists(principal, branch_id, department):
            raise ServiceExecutionError("staffing_rule_conflict")
        try:
            return _staffing_rule(
                await self._repository.update_staffing_rule(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    rule_id=rule_id,
                    changes=changes,
                )
            )
        except IntegrityError:
            raise ServiceExecutionError("staffing_rule_conflict") from None

    async def delete_staffing_rule(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        rule_id: uuid.UUID,
        request: StaffingRuleDeleteRequest,
    ) -> None:
        self._require_admin(principal)
        try:
            current = await self._repository.fetch_staffing_rule(
                principal.company_id, branch_id, rule_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        snapshot_fields = (
            "department",
            "shift_category",
            "min_staff",
            "effective_from",
            "effective_to",
        )
        if not _snapshot_matches(current, request.expected, snapshot_fields):
            raise ServiceExecutionError("state_conflict")
        try:
            await self._repository.delete_staffing_rule(
                company_id=principal.company_id, branch_id=branch_id, rule_id=rule_id
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
