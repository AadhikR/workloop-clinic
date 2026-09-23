from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.schemas.employment_contract import (
    ContractCommandRequest,
    ContractNotRenewedRequest,
    EmployeeContractResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError

ContractAction = Literal["new", "renewed", "converted", "not_renewed"]


@dataclass(frozen=True, slots=True)
class EmploymentContractListQuery:
    employee_id: uuid.UUID
    limit: int
    cursor: str | None


class EmploymentContractService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: EmploymentContractListQuery,
        cursor_codec: EmployeeCursorCodec,
    ) -> tuple[list[EmployeeContractResponse], str | None]:
        employee_id = query.employee_id
        await self._employee(principal, branch_id, employee_id, lock=False)
        try:
            cursor_id = cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_employee_contracts",
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        parameters: dict[str, object] = {
            "company_id": principal.company_id,
            "branch_id": branch_id,
            "employee_id": employee_id,
            "limit": query.limit + 1,
        }
        cursor_clause = ""
        if cursor_id is not None:
            anchor = (
                await self.connection.execute(
                    text(
                        "SELECT created_at FROM public.employee_contracts "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id "
                        "AND employee_id=:employee_id"
                    ),
                    {**parameters, "id": cursor_id},
                )
            ).scalar_one_or_none()
            if anchor is None:
                raise ServiceExecutionError("invalid_cursor")
            parameters.update({"cursor_created_at": anchor, "cursor_id": cursor_id})
            cursor_clause = (
                " AND (contract.created_at,contract.id) < (:cursor_created_at,:cursor_id)"
            )
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT contract.id,contract.employee_id,contract.contract_type,contract.start_date,
 contract.end_date,contract.action,contract.notes,
 CASE WHEN profile.employee_id IS NULL THEN 'Administrator' ELSE actor.name END actor_name,
 contract.created_at
FROM public.employee_contracts contract
LEFT JOIN public.user_profiles profile
  ON profile.app_user_id=contract.renewed_by_app_user_id
LEFT JOIN public.employees actor ON actor.id=profile.employee_id
WHERE contract.company_id=:company_id AND contract.branch_id=:branch_id
 AND contract.employee_id=:employee_id
{cursor_clause}
ORDER BY contract.created_at DESC,contract.id DESC LIMIT :limit
"""
                    ),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        visible = rows[: query.limit]
        items = [EmployeeContractResponse.model_validate(row) for row in visible]
        next_cursor = (
            cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_employee_contracts",
                query=query,
                last_id=visible[-1]["id"],
            )
            if len(rows) > query.limit
            else None
        )
        return items, next_cursor

    async def get(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, contract_id: uuid.UUID
    ) -> EmployeeContractResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT contract.id,contract.employee_id,contract.contract_type,contract.start_date,
 contract.end_date,contract.action,contract.notes,
 CASE WHEN profile.employee_id IS NULL THEN 'Administrator' ELSE actor.name END actor_name,
 contract.created_at
FROM public.employee_contracts contract
LEFT JOIN public.user_profiles profile
 ON profile.app_user_id=contract.renewed_by_app_user_id
LEFT JOIN public.employees actor ON actor.id=profile.employee_id
WHERE contract.id=:id AND contract.company_id=:company_id AND contract.branch_id=:branch_id
"""
                    ),
                    {"id": contract_id, "company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return EmployeeContractResponse.model_validate(row)

    async def record(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        action: ContractAction,
        request: ContractCommandRequest | ContractNotRenewedRequest,
    ) -> EmployeeContractResponse:
        employee = await self._employee(principal, branch_id, employee_id, lock=True)
        latest = (
            await self.connection.execute(
                text(
                    """
SELECT id,contract_type,start_date,end_date FROM public.employee_contracts
WHERE company_id=:company_id AND branch_id=:branch_id AND employee_id=:employee_id
ORDER BY created_at DESC,id DESC LIMIT 1
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                },
            )
        ).one_or_none()
        expected = request.expected
        if (
            employee.updated_at != expected.employee_updated_at
            or employee.contract_type != expected.current_contract_type
            or employee.contract_end_date != expected.current_contract_end_date
            or (latest.id if latest is not None else None) != expected.latest_contract_event_id
        ):
            raise ServiceExecutionError("state_conflict")
        if action == "new" and latest is not None:
            raise ServiceExecutionError("state_conflict")
        if action == "renewed" and (
            latest is None
            or not isinstance(request, ContractCommandRequest)
            or request.contract_type != employee.contract_type
        ):
            raise ServiceExecutionError("validation_failed")
        if action == "converted" and (
            latest is None
            or not isinstance(request, ContractCommandRequest)
            or request.contract_type == employee.contract_type
        ):
            raise ServiceExecutionError("validation_failed")
        if action == "not_renewed":
            if latest is None or not isinstance(request, ContractNotRenewedRequest):
                raise ServiceExecutionError("state_conflict")
            contract_type = employee.contract_type
            start_date = latest.start_date
            end_date = employee.contract_end_date
        else:
            assert isinstance(request, ContractCommandRequest)
            contract_type = request.contract_type
            start_date = request.start_date
            end_date = request.end_date
            await self.connection.execute(
                text(
                    "UPDATE public.employees SET contract_type=:contract_type,"
                    "contract_end_date=:end_date WHERE id=:id"
                ),
                {"id": employee_id, "contract_type": contract_type, "end_date": end_date},
            )
        contract_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.employee_contracts(
 company_id,branch_id,employee_id,contract_type,start_date,end_date,
 renewed_at,renewed_by_app_user_id,action,notes)
VALUES(:company_id,:branch_id,:employee_id,:contract_type,:start_date,:end_date,
 statement_timestamp(),:actor,:action,:notes) RETURNING id
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "contract_type": contract_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "actor": principal.app_user_id,
                    "action": action,
                    "notes": request.notes,
                },
            )
        ).scalar_one()
        old_value = f"{employee.contract_type}:{employee.contract_end_date or ''}"
        new_value = f"{contract_type}:{end_date or ''}:{action}"
        await self.connection.execute(
            text(
                """
INSERT INTO public.employee_job_history(
 company_id,branch_id,employee_id,changed_at,changed_by_app_user_id,
 change_type,old_value,new_value,reason)
VALUES(:company_id,:branch_id,:employee_id,statement_timestamp(),:actor,
 'status_change',:old_value,:new_value,:reason)
"""
            ),
            {
                "company_id": principal.company_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
                "actor": principal.app_user_id,
                "old_value": old_value,
                "new_value": new_value,
                "reason": f"Employment contract {action}",
            },
        )
        await append_audit_event(
            self.connection,
            action="employment_contract_recorded",
            entity_type="employee_contract",
            entity_id=contract_id,
            changed_fields=["contract_type", "start_date", "end_date", "action"],
            reason="Employment contract recorded",
            metadata={"action": action},
        )
        return await self.get(principal, branch_id, contract_id)

    async def _employee(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        *,
        lock: bool,
    ):
        suffix = " FOR UPDATE" if lock else ""
        row = (
            await self.connection.execute(
                text(
                    "SELECT id,contract_type,contract_end_date,updated_at FROM public.employees "
                    "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id" + suffix
                ),
                {"id": employee_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "employee_contract" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        exists = (
            await self.connection.execute(
                text(
                    "SELECT 1 FROM public.employee_contracts WHERE id=:id "
                    "AND company_id=:company_id AND branch_id=:branch_id"
                ),
                {"id": resource_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ServiceExecutionError("resource_not_found")
