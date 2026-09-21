from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.attendance_periods import AttendancePeriodRepository
from app.schemas.attendance_periods import AttendancePeriodCloseRequest, AttendancePeriodResponse
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class AttendancePeriodListQuery:
    limit: int
    cursor: str | None


class AttendancePeriodService:
    def __init__(
        self, repository: AttendancePeriodRepository, cursor_codec: EmployeeCursorCodec
    ) -> None:
        self.repository = repository
        self.cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: AttendancePeriodListQuery,
    ) -> tuple[list[AttendancePeriodResponse], str | None]:
        self._admin(principal)
        after = None
        if query.cursor is not None:
            try:
                cursor_id = self.cursor_codec.decode(
                    principal=principal,
                    branch_id=branch_id,
                    operation_id="list_attendance_periods",
                    query=query,
                    cursor=query.cursor,
                )
                if cursor_id is None:
                    raise ValueError
                after = await self.repository.position(principal.company_id, branch_id, cursor_id)
            except (ValueError, ServiceExecutionError):
                raise ServiceExecutionError("invalid_cursor") from None
        rows = await self.repository.list_responses(
            principal.company_id, branch_id, after, query.limit + 1
        )
        page = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit and page:
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_attendance_periods",
                query=query,
                last_id=page[-1].id,
            )
        return page, next_cursor

    async def detail(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, period: str
    ) -> AttendancePeriodResponse:
        self._admin(principal)
        return await self.repository.response(principal.company_id, branch_id, period)

    async def close(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        request: AttendancePeriodCloseRequest,
    ) -> AttendancePeriodResponse:
        self._admin(principal)
        return await self.repository.close(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            period,
            request.expected_version,
            request.amendment_reason,
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if (
            kind != "attendance_period"
            or resource_id is None
            or not await self.repository.exists(principal.company_id, branch_id, resource_id)
        ):
            raise ServiceExecutionError("resource_not_found")
