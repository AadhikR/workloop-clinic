from __future__ import annotations

import uuid
from typing import Literal

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.shift_swaps import ShiftSwapRepository
from app.schemas.shift_swaps import (
    ShiftSwapApproveRequest,
    ShiftSwapResponse,
    ShiftSwapSubmitRequest,
    ShiftSwapTransitionRequest,
)
from app.services.execution import ServiceExecutionError


class ShiftSwapService:
    def __init__(self, repository: ShiftSwapRepository) -> None:
        self.repository = repository

    @staticmethod
    def _staff(principal: AuthorizationPrincipal) -> tuple[uuid.UUID, uuid.UUID]:
        if (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.branch_id is None
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        return principal.branch_id, principal.employee_id

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    async def personal(
        self, principal: AuthorizationPrincipal, status: str | None, limit: int
    ) -> list[ShiftSwapResponse]:
        branch_id, employee_id = self._staff(principal)
        return await self.repository.personal(
            principal.company_id, branch_id, employee_id, status, limit
        )

    async def admin(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        status: str | None,
        limit: int,
    ) -> list[ShiftSwapResponse]:
        self._admin(principal)
        return await self.repository.admin(principal.company_id, branch_id, status, limit)

    async def submit(
        self, principal: AuthorizationPrincipal, request: ShiftSwapSubmitRequest
    ) -> ShiftSwapResponse:
        branch_id, employee_id = self._staff(principal)
        return await self.repository.submit(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            employee_id,
            request,
        )

    async def cancel(
        self,
        principal: AuthorizationPrincipal,
        swap_id: uuid.UUID,
        request: ShiftSwapTransitionRequest,
    ) -> ShiftSwapResponse:
        branch_id, employee_id = self._staff(principal)
        return await self.repository.transition(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            swap_id,
            "cancelled",
            request,
            requester_employee_id=employee_id,
        )

    async def reject(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        swap_id: uuid.UUID,
        request: ShiftSwapTransitionRequest,
    ) -> ShiftSwapResponse:
        self._admin(principal)
        return await self.repository.transition(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            swap_id,
            "rejected",
            request,
        )

    async def approve(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        swap_id: uuid.UUID,
        request: ShiftSwapApproveRequest,
    ) -> ShiftSwapResponse:
        self._admin(principal)
        return await self.repository.approve(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            swap_id,
            request,
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "shift_swap_request" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        employee_id: uuid.UUID | None
        if principal.role is AppRole.ADMIN:
            employee_id = None
        else:
            staff_branch, employee_id = self._staff(principal)
            if staff_branch != branch_id:
                raise ServiceExecutionError("resource_not_found")
        if not await self.repository.exists(
            principal.company_id, branch_id, resource_id, employee_id
        ):
            raise ServiceExecutionError("resource_not_found")


ShiftSwapStatus = Literal["pending", "approved", "rejected", "cancelled"]
