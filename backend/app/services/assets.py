from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.schemas.assets import (
    AssetAssignmentResponse,
    AssetAssignRequest,
    AssetCreateRequest,
    AssetResponse,
    AssetReturnRequest,
    AssetUpdateRequest,
)
from app.services.execution import ServiceExecutionError

ASSET_COLUMNS = """
id,name,asset_code,category,brand,model,serial_number,purchase_date,purchase_cost,
status,notes,created_at,updated_at
"""


@dataclass(frozen=True, slots=True)
class AssetListQuery:
    status: str | None
    category: str | None
    search: str | None
    limit: int


class AssetService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: AssetListQuery,
    ) -> list[AssetResponse]:
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {ASSET_COLUMNS} FROM public.assets
WHERE company_id=:company_id AND branch_id=:branch_id
  AND (CAST(:status AS text) IS NULL OR status=:status)
  AND (CAST(:category AS text) IS NULL OR category=:category)
  AND (CAST(:search AS text) IS NULL OR name ILIKE '%'||:search||'%'
       OR asset_code ILIKE '%'||:search||'%' OR serial_number ILIKE '%'||:search||'%')
ORDER BY asset_code ASC,name ASC,id ASC LIMIT :limit
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "status": query.status,
                        "category": query.category,
                        "search": query.search,
                        "limit": query.limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [AssetResponse.model_validate(row) for row in rows]

    async def get(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, asset_id: uuid.UUID
    ) -> AssetResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {ASSET_COLUMNS} FROM public.assets "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id"
                    ),
                    {"id": asset_id, "company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return AssetResponse.model_validate(row)

    async def create(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: AssetCreateRequest,
    ) -> AssetResponse:
        try:
            asset_id = (
                await self.connection.execute(
                    text(
                        """
INSERT INTO public.assets(
 company_id,branch_id,name,asset_code,category,brand,model,serial_number,
 purchase_date,purchase_cost,status,notes)
VALUES(:company_id,:branch_id,:name,:asset_code,:category,:brand,:model,:serial_number,
 :purchase_date,:purchase_cost,'available',:notes) RETURNING id
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        **request.model_dump(by_alias=False),
                    },
                )
            ).scalar_one()
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        await self._audit("asset_created", "asset", asset_id, ["id"], "Asset created")
        return await self.get(principal, branch_id, asset_id)

    async def update(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        asset_id: uuid.UUID,
        request: AssetUpdateRequest,
    ) -> AssetResponse:
        current = await self._lock(principal, branch_id, asset_id)
        if current.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        try:
            await self.connection.execute(
                text(
                    """
UPDATE public.assets SET name=:name,asset_code=:asset_code,category=:category,
 brand=:brand,model=:model,serial_number=:serial_number,purchase_date=:purchase_date,
 purchase_cost=:purchase_cost,notes=:notes WHERE id=:id
"""
                ),
                {
                    "id": asset_id,
                    **request.model_dump(exclude={"expected_updated_at"}, by_alias=False),
                },
            )
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        await self._audit(
            "asset_updated",
            "asset",
            asset_id,
            [
                "name",
                "asset_code",
                "category",
                "brand",
                "model",
                "serial_number",
                "purchase_date",
                "purchase_cost",
                "notes",
            ],
            "Asset updated",
        )
        return await self.get(principal, branch_id, asset_id)

    async def transition(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        asset_id: uuid.UUID,
        status: str,
        expected_updated_at: object,
    ) -> AssetResponse:
        current = await self._lock(principal, branch_id, asset_id)
        if current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        allowed: dict[str, set[str]] = {
            "available": {"under_repair", "retired", "lost"},
            "under_repair": {"available", "retired", "lost"},
            "assigned": set(),
            "retired": set(),
            "lost": set(),
        }
        if status not in allowed[current.status]:
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text("UPDATE public.assets SET status=:status WHERE id=:id"),
            {"id": asset_id, "status": status},
        )
        await self._audit(
            "asset_status_changed",
            "asset",
            asset_id,
            ["status"],
            "Asset status changed",
            {"transition": f"{current.status}_to_{status}"},
        )
        return await self.get(principal, branch_id, asset_id)

    async def assign(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        asset_id: uuid.UUID,
        request: AssetAssignRequest,
    ) -> AssetAssignmentResponse:
        current = await self._lock(principal, branch_id, asset_id)
        if current.updated_at != request.expected_updated_at or current.status != "available":
            raise ServiceExecutionError("state_conflict")
        employee = (
            await self.connection.execute(
                text(
                    "SELECT id FROM public.employees WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id AND active AND employment_status IN "
                    "('Active','Probation','On Leave') FOR UPDATE"
                ),
                {
                    "id": request.employee_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                },
            )
        ).scalar_one_or_none()
        if employee is None:
            raise ServiceExecutionError("resource_not_found")
        assigned_date = (
            await self.connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()
        try:
            assignment_id = (
                await self.connection.execute(
                    text(
                        """
INSERT INTO public.asset_assignments(
 company_id,branch_id,asset_id,employee_id,assigned_date,condition_at_handover,
 notes,assigned_by_app_user_id)
VALUES(:company_id,:branch_id,:asset_id,:employee_id,:assigned_date,:condition,:notes,:actor)
RETURNING id
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "asset_id": asset_id,
                        "employee_id": request.employee_id,
                        "assigned_date": assigned_date,
                        "condition": request.condition_at_handover,
                        "notes": request.notes,
                        "actor": principal.app_user_id,
                    },
                )
            ).scalar_one()
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        await self.connection.execute(
            text("UPDATE public.assets SET status='assigned' WHERE id=:id"), {"id": asset_id}
        )
        await self._audit(
            "asset_assigned",
            "asset_assignment",
            assignment_id,
            ["employee_id", "assigned_date", "condition_at_handover"],
            "Asset assigned",
        )
        return await self._assignment(principal, branch_id, assignment_id)

    async def return_asset(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        asset_id: uuid.UUID,
        request: AssetReturnRequest,
    ) -> AssetAssignmentResponse:
        current = await self._lock(principal, branch_id, asset_id)
        if current.updated_at != request.expected_updated_at or current.status != "assigned":
            raise ServiceExecutionError("state_conflict")
        assignment = (
            await self.connection.execute(
                text(
                    "SELECT id,assigned_date FROM public.asset_assignments "
                    "WHERE asset_id=:asset_id AND company_id=:company_id AND branch_id=:branch_id "
                    "AND return_date IS NULL FOR UPDATE"
                ),
                {
                    "asset_id": asset_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                },
            )
        ).one_or_none()
        if assignment is None:
            raise ServiceExecutionError("state_conflict")
        return_date = (
            await self.connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()
        if return_date < assignment.assigned_date:
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text(
                "UPDATE public.asset_assignments SET return_date=:return_date,"
                "condition_at_return=:condition,notes=:notes WHERE id=:id"
            ),
            {
                "id": assignment.id,
                "return_date": return_date,
                "condition": request.condition_at_return,
                "notes": request.notes,
            },
        )
        await self.connection.execute(
            text("UPDATE public.assets SET status='available' WHERE id=:id"), {"id": asset_id}
        )
        await self._audit(
            "asset_returned",
            "asset_assignment",
            assignment.id,
            ["return_date", "condition_at_return"],
            "Asset returned",
        )
        return await self._assignment(principal, branch_id, assignment.id)

    async def delete(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        asset_id: uuid.UUID,
        expected_updated_at: object,
    ) -> None:
        current = await self._lock(principal, branch_id, asset_id)
        if current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        history = (
            await self.connection.execute(
                text("SELECT 1 FROM public.asset_assignments WHERE asset_id=:id LIMIT 1"),
                {"id": asset_id},
            )
        ).scalar_one_or_none()
        if history is not None:
            raise ServiceExecutionError("state_conflict")
        await self._audit("asset_deleted", "asset", asset_id, ["id"], "Asset deleted")
        await self.connection.execute(
            text("DELETE FROM public.assets WHERE id=:id"), {"id": asset_id}
        )

    async def list_self(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, limit: int
    ) -> list[AssetAssignmentResponse]:
        if principal.employee_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        rows = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT assignment.id,assignment.asset_id,assignment.employee_id,asset.name asset_name,
 asset.asset_code,asset.status,assignment.assigned_date,assignment.return_date,
 assignment.condition_at_handover,assignment.condition_at_return,assignment.notes,
 assignment.created_at
FROM public.asset_assignments assignment
JOIN public.assets asset ON asset.id=assignment.asset_id
WHERE assignment.company_id=:company_id AND assignment.branch_id=:branch_id
  AND assignment.employee_id=:employee_id
ORDER BY assignment.assigned_date DESC,assignment.id DESC LIMIT :limit
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": principal.employee_id,
                        "limit": limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [AssetAssignmentResponse.model_validate(row) for row in rows]

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        table = {"asset": "assets", "asset_assignment": "asset_assignments"}.get(kind)
        if table is None or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        exists = (
            await self.connection.execute(
                text(
                    f"SELECT 1 FROM public.{table} WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id"
                ),
                {"id": resource_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ServiceExecutionError("resource_not_found")

    async def _lock(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, asset_id: uuid.UUID
    ) -> Any:
        row = (
            await self.connection.execute(
                text(
                    "SELECT id,status,updated_at FROM public.assets WHERE id=:id "
                    "AND company_id=:company_id AND branch_id=:branch_id FOR UPDATE"
                ),
                {"id": asset_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def _assignment(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> AssetAssignmentResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT assignment.id,assignment.asset_id,assignment.employee_id,asset.name asset_name,
 asset.asset_code,asset.status,assignment.assigned_date,assignment.return_date,
 assignment.condition_at_handover,assignment.condition_at_return,assignment.notes,
 assignment.created_at
FROM public.asset_assignments assignment JOIN public.assets asset ON asset.id=assignment.asset_id
WHERE assignment.id=:id AND assignment.company_id=:company_id
  AND assignment.branch_id=:branch_id
"""
                    ),
                    {
                        "id": assignment_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        return AssetAssignmentResponse.model_validate(row)

    async def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        fields: list[str],
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        await append_audit_event(
            self.connection,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changed_fields=fields,
            reason=reason,
            metadata=metadata or {},
        )
