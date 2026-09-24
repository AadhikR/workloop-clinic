from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.notifications import NotificationRepository
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationReadAllResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class NotificationListQuery:
    limit: int
    cursor: str | None


def _timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


def _item(row: object) -> NotificationResponse:
    values = cast(dict[str, object], row)
    return NotificationResponse.model_validate(values)


class NotificationService:
    def __init__(
        self, repository: NotificationRepository, cursor_codec: EmployeeCursorCodec
    ) -> None:
        self.repository = repository
        self.cursor_codec = cursor_codec

    @staticmethod
    def _include_tenant(principal: AuthorizationPrincipal) -> bool:
        return principal.role is AppRole.ADMIN

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: NotificationListQuery,
    ) -> NotificationListResponse:
        try:
            cursor_id = self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_notifications",
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        include_tenant = self._include_tenant(principal)
        rows = await self.repository.list(
            company_id=principal.company_id,
            branch_id=branch_id,
            recipient_id=principal.app_user_id,
            include_tenant=include_tenant,
            cursor_id=cursor_id,
            limit=query.limit + 1,
        )
        if cursor_id is not None and not rows:
            raise ServiceExecutionError("invalid_cursor")
        visible = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit:
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_notifications",
                query=query,
                last_id=visible[-1]["id"],
            )
        snapshot = await self.repository.snapshot(
            company_id=principal.company_id,
            branch_id=branch_id,
            recipient_id=principal.app_user_id,
            include_tenant=include_tenant,
        )
        version_material = "|".join(
            (
                str(snapshot["total"]),
                str(snapshot["unread"]),
                _timestamp(snapshot["newest_created_at"]),
                _timestamp(snapshot["newest_read_at"]),
            )
        )
        return NotificationListResponse(
            items=[_item(row) for row in visible],
            next_cursor=next_cursor,
            as_of=snapshot["as_of"],
            source_version="sha256:" + hashlib.sha256(version_material.encode()).hexdigest(),
        )

    async def unread_count(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> NotificationUnreadCountResponse:
        snapshot = await self.repository.snapshot(
            company_id=principal.company_id,
            branch_id=branch_id,
            recipient_id=principal.app_user_id,
            include_tenant=self._include_tenant(principal),
        )
        return NotificationUnreadCountResponse(count=snapshot["unread"], as_of=snapshot["as_of"])

    async def read_one(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> NotificationResponse:
        row = await self.repository.read_one(
            company_id=principal.company_id,
            branch_id=branch_id,
            recipient_id=principal.app_user_id,
            include_tenant=self._include_tenant(principal),
            notification_id=notification_id,
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return _item(row)

    async def read_all(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> NotificationReadAllResponse:
        changed, as_of = await self.repository.read_all(
            company_id=principal.company_id,
            branch_id=branch_id,
            recipient_id=principal.app_user_id,
            include_tenant=self._include_tenant(principal),
        )
        return NotificationReadAllResponse(
            changed_count=changed,
            unread_count=0,
            as_of=as_of,
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "notification_inbox" or resource_id is not None:
            raise ServiceExecutionError("resource_not_found")
        if principal.role is AppRole.ADMIN:
            return
        if principal.branch_id != branch_id:
            raise ServiceExecutionError("resource_not_found")
