from __future__ import annotations

import uuid
from typing import Literal

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.schemas.shift_swaps import (
    ShiftSwapApproveRequest,
    ShiftSwapResponse,
    ShiftSwapSubmitRequest,
    ShiftSwapTransitionRequest,
)
from app.services.execution import ServiceExecutionError


def _response(row: object) -> ShiftSwapResponse:
    return ShiftSwapResponse.model_validate(row)


SELECT_SWAP = """
SELECT swap.id,swap.requester_employee_id,
       public.shift_swap_participant_name(swap.id,swap.requester_employee_id)
         requester_employee_name,
       swap.target_employee_id,
       public.shift_swap_participant_name(swap.id,swap.target_employee_id)
         target_employee_name,swap.requester_date,
       swap.target_date,swap.reason,swap.status,swap.rejection_reason,
       swap.expected_roster_source_version expected_source_version,
       swap.requester_assignment_id,swap.target_assignment_id,
       swap.expected_requester_assignment_version requester_assignment_version,
       swap.expected_target_assignment_version target_assignment_version,
       swap.approved_publication_version_id,swap.decided_at,
       swap.decided_by_app_user_id,swap.created_at,swap.updated_at,swap.version
FROM public.shift_swap_requests swap
"""


class ShiftSwapRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def personal(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        status: str | None,
        limit: int,
    ) -> list[ShiftSwapResponse]:
        rows = (
            await self.connection.execute(
                text(
                    SELECT_SWAP + " WHERE swap.company_id=:company AND swap.branch_id=:branch "
                    "AND swap.contract_version=1 "
                    "AND :employee IN (swap.requester_employee_id,swap.target_employee_id) "
                    "AND (CAST(:status AS text) IS NULL OR swap.status=:status) "
                    "ORDER BY swap.created_at DESC,swap.id DESC LIMIT :limit"
                ),
                {
                    "company": company_id,
                    "branch": branch_id,
                    "employee": employee_id,
                    "status": status,
                    "limit": limit,
                },
            )
        ).mappings()
        return [_response(dict(row)) for row in rows]

    async def admin(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        status: str | None,
        limit: int,
    ) -> list[ShiftSwapResponse]:
        rows = (
            await self.connection.execute(
                text(
                    SELECT_SWAP + " WHERE swap.company_id=:company AND swap.branch_id=:branch "
                    "AND swap.contract_version=1 "
                    "AND (CAST(:status AS text) IS NULL OR swap.status=:status) "
                    "ORDER BY swap.created_at DESC,swap.id DESC LIMIT :limit"
                ),
                {"company": company_id, "branch": branch_id, "status": status, "limit": limit},
            )
        ).mappings()
        return [_response(dict(row)) for row in rows]

    async def submit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: ShiftSwapSubmitRequest,
    ) -> ShiftSwapResponse:
        if request.target_employee_id == employee_id:
            raise ServiceExecutionError("validation_failed")
        try:
            swap_id = await self.connection.scalar(
                text(
                    "SELECT public.staff_submit_shift_swap("
                    ":target,:requester_date,:target_date,:reason,:source_version)"
                ),
                {
                    "target": request.target_employee_id,
                    "requester_date": request.requester_date,
                    "target_date": request.target_date,
                    "reason": request.reason,
                    "source_version": request.expected_source_version,
                },
            )
        except (DBAPIError, IntegrityError):
            raise ServiceExecutionError("state_conflict") from None
        if not isinstance(swap_id, uuid.UUID):
            raise ServiceExecutionError("state_conflict")
        return await self.detail(company_id, branch_id, swap_id)

    async def transition(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        swap_id: uuid.UUID,
        action: Literal["cancelled", "rejected"],
        request: ShiftSwapTransitionRequest,
        requester_employee_id: uuid.UUID | None = None,
    ) -> ShiftSwapResponse:
        if action == "rejected" and request.reason is None:
            raise ServiceExecutionError("validation_failed")
        clauses = " AND requester_employee_id=:requester" if requester_employee_id else ""
        try:
            result = await self.connection.execute(
                text(
                    "UPDATE public.shift_swap_requests SET status=:status,"
                    "rejection_reason=:reason,decided_at=clock_timestamp(),"
                    "decided_by_app_user_id=:actor,"
                    "admin_approved_at=CASE WHEN :status='rejected' "
                    "THEN clock_timestamp() ELSE admin_approved_at END,"
                    "admin_approved_by_app_user_id=CASE WHEN :status='rejected' "
                    "THEN :actor ELSE admin_approved_by_app_user_id END,version=version+1 "
                    "WHERE id=:id AND company_id=:company AND branch_id=:branch "
                    "AND contract_version=1 AND status='pending' AND version=:version" + clauses
                ),
                {
                    "status": action,
                    "reason": request.reason or "",
                    "actor": actor_id,
                    "id": swap_id,
                    "company": company_id,
                    "branch": branch_id,
                    "version": request.expected_version,
                    "requester": requester_employee_id,
                },
            )
        except DBAPIError:
            raise ServiceExecutionError("state_conflict") from None
        if result.rowcount != 1:
            raise ServiceExecutionError("state_conflict")
        await self._history(
            swap_id,
            company_id,
            branch_id,
            actor_id,
            action,
            "pending",
            action,
            request.reason or "Employee cancelled pending request",
        )
        return await self.detail(company_id, branch_id, swap_id)

    async def approve(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        swap_id: uuid.UUID,
        request: ShiftSwapApproveRequest,
    ) -> ShiftSwapResponse:
        current = await self.detail(company_id, branch_id, swap_id)
        if (
            current.status != "pending"
            or current.version != request.expected_version
            or current.expected_source_version != request.expected_source_version
        ):
            raise ServiceExecutionError("state_conflict")
        try:
            await self.connection.execute(
                text("SELECT public.admin_execute_shift_swap(:id,:actor)"),
                {"id": swap_id, "actor": actor_id},
            )
        except DBAPIError:
            raise ServiceExecutionError("state_conflict") from None
        return await self.detail(company_id, branch_id, swap_id)

    async def detail(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, swap_id: uuid.UUID
    ) -> ShiftSwapResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        SELECT_SWAP + " WHERE swap.id=:id AND swap.company_id=:company "
                        "AND swap.branch_id=:branch AND swap.contract_version=1"
                    ),
                    {"id": swap_id, "company": company_id, "branch": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return _response(dict(row))

    async def exists(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        swap_id: uuid.UUID,
        employee_id: uuid.UUID | None,
    ) -> bool:
        participant = (
            " AND :employee IN (requester_employee_id,target_employee_id)" if employee_id else ""
        )
        return bool(
            await self.connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM public.shift_swap_requests "
                    "WHERE id=:id AND company_id=:company AND branch_id=:branch "
                    "AND contract_version=1" + participant + ")"
                ),
                {
                    "id": swap_id,
                    "company": company_id,
                    "branch": branch_id,
                    "employee": employee_id,
                },
            )
        )

    async def _history(
        self,
        swap_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        from_status: str | None,
        to_status: str,
        reason: str,
    ) -> None:
        await self.connection.execute(
            text(
                "INSERT INTO public.shift_swap_history("
                "company_id,branch_id,shift_swap_request_id,action,from_status,to_status,"
                "actor_app_user_id,reason) VALUES ("
                ":company,:branch,:swap,:action,:from_status,:to_status,:actor,:reason)"
            ),
            {
                "company": company_id,
                "branch": branch_id,
                "swap": swap_id,
                "action": action,
                "from_status": from_status,
                "to_status": to_status,
                "actor": actor_id,
                "reason": reason,
            },
        )
