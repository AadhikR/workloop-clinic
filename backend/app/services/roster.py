from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.roster import RosterRepository
from app.schemas.roster import (
    RosterAssignmentResponse,
    RosterComplianceOverrideRequest,
    RosterComplianceOverrideResponse,
    RosterDraftCreateRequest,
    RosterDraftReplaceRequest,
    RosterValidationResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class RosterListQuery:
    period: str
    department: str | None
    employee_id: uuid.UUID | None
    limit: int
    cursor: str | None


class RosterService:
    def __init__(self, repository: RosterRepository, cursor_codec: EmployeeCursorCodec) -> None:
        self.repository = repository
        self.cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    @staticmethod
    def _period_date(period: str, value: date) -> None:
        if value.strftime("%Y-%m") != period:
            raise ServiceExecutionError("validation_failed")

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: RosterListQuery,
    ) -> tuple[list[RosterAssignmentResponse], str | None]:
        self._admin(principal)
        after = None
        if query.cursor is not None:
            try:
                cursor_id = self.cursor_codec.decode(
                    principal=principal,
                    branch_id=branch_id,
                    operation_id="list_roster_drafts",
                    query=query,
                    cursor=query.cursor,
                )
                if cursor_id is None:
                    raise ValueError
                after = await self.repository.position(principal.company_id, branch_id, cursor_id)
            except (ValueError, ServiceExecutionError):
                raise ServiceExecutionError("invalid_cursor") from None
        rows = await self.repository.list(
            principal.company_id,
            branch_id,
            query.period,
            query.department,
            query.employee_id,
            after,
            query.limit + 1,
        )
        page = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit and page:
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_roster_drafts",
                query=query,
                last_id=page[-1].id,
            )
        return page, next_cursor

    async def create(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        request: RosterDraftCreateRequest,
    ) -> RosterAssignmentResponse:
        self._admin(principal)
        self._period_date(period, request.date)
        return await self.repository.create(principal.company_id, branch_id, request)

    async def replace(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        request: RosterDraftReplaceRequest,
    ) -> RosterAssignmentResponse:
        self._admin(principal)
        self._period_date(period, request.date)
        return await self.repository.replace(
            principal.company_id, branch_id, period, assignment_id, request
        )

    async def delete(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        assignment_id: uuid.UUID,
        expected_version: int,
    ) -> None:
        self._admin(principal)
        await self.repository.delete(
            principal.company_id, branch_id, period, assignment_id, expected_version
        )

    async def validation(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, period: str
    ) -> RosterValidationResponse:
        self._admin(principal)
        return await self.repository.validation(principal.company_id, branch_id, period)

    async def override(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        request: RosterComplianceOverrideRequest,
    ) -> RosterComplianceOverrideResponse:
        self._admin(principal)
        return await self.repository.create_override(
            principal.company_id,
            branch_id,
            period,
            request.violation_digest,
            request.reason,
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if kind == "tenant" and resource_id is None:
            return
        if resource_id is None or not await self.repository.exists(
            principal.company_id, branch_id, kind, resource_id
        ):
            raise ServiceExecutionError("resource_not_found")
