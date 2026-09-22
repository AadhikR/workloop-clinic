from __future__ import annotations

import uuid
from datetime import date

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.roster_publication import RosterPublicationRepository
from app.schemas.roster_publication import (
    ColleagueScheduleEntryResponse,
    PublishedScheduleEntryResponse,
    RosterActualHoursRequest,
    RosterOvertimeApprovalRequest,
    RosterPublicationResponse,
    RosterPublishRequest,
)
from app.services.execution import ServiceExecutionError


class RosterPublicationService:
    def __init__(self, repository: RosterPublicationRepository) -> None:
        self.repository = repository

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    @staticmethod
    def _staff(principal: AuthorizationPrincipal) -> tuple[uuid.UUID, uuid.UUID]:
        if (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.branch_id is None
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        return principal.branch_id, principal.employee_id

    async def detail(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, period: str
    ) -> RosterPublicationResponse:
        self._admin(principal)
        return await self.repository.detail(principal.company_id, branch_id, period)

    async def publish(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        request: RosterPublishRequest,
    ) -> RosterPublicationResponse:
        self._admin(principal)
        return await self.repository.publish(
            principal.company_id, branch_id, principal.app_user_id, period, request
        )

    async def record_actual_hours(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        request: RosterActualHoursRequest,
    ) -> RosterPublicationResponse:
        self._admin(principal)
        return await self.repository.record_actual_hours(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            period,
            assignment_id,
            request,
        )

    async def approve_overtime(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        request: RosterOvertimeApprovalRequest,
    ) -> RosterPublicationResponse:
        self._admin(principal)
        return await self.repository.approve_overtime(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            period,
            assignment_id,
            request,
        )

    async def personal_schedule(
        self, principal: AuthorizationPrincipal, period: str
    ) -> list[PublishedScheduleEntryResponse]:
        branch_id, employee_id = self._staff(principal)
        return await self.repository.personal_schedule(
            principal.company_id, branch_id, employee_id, period
        )

    async def colleagues(
        self, principal: AuthorizationPrincipal, day: date
    ) -> list[ColleagueScheduleEntryResponse]:
        self._staff(principal)
        return await self.repository.colleagues(day)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if (
            kind != "roster_publication_version"
            or resource_id is None
            or not await self.repository.exists(principal.company_id, branch_id, resource_id)
        ):
            raise ServiceExecutionError("resource_not_found")
