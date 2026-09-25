from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


class NotificationRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    @staticmethod
    def _branch_clause(include_tenant: bool, *, qualifier: str = "") -> str:
        column = f"{qualifier}branch_id"
        if include_tenant:
            return f"({column} IS NULL OR {column}=:branch_id)"
        return f"{column}=:branch_id"

    async def list(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        recipient_id: uuid.UUID,
        include_tenant: bool,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        branch_clause = self._branch_clause(include_tenant)
        anchor_branch_clause = self._branch_clause(include_tenant, qualifier="anchor.")
        statement = text(
            f"""
SELECT id,type,title,body,related_entity_type,related_entity_id,read_at,created_at
FROM public.notifications
WHERE company_id=:company_id AND recipient_app_user_id=:recipient_id
  AND {branch_clause}
  AND (CAST(:cursor_id AS uuid) IS NULL OR (created_at,id)<(
    SELECT anchor.created_at,anchor.id FROM public.notifications AS anchor
    WHERE anchor.id=CAST(:cursor_id AS uuid) AND anchor.company_id=:company_id
      AND anchor.recipient_app_user_id=:recipient_id
      AND {anchor_branch_clause}))
ORDER BY created_at DESC,id DESC
LIMIT :limit
"""
        )
        return list(
            (
                await self.connection.execute(
                    statement,
                    {
                        "branch_id": branch_id,
                        "company_id": company_id,
                        "cursor_id": cursor_id,
                        "limit": limit,
                        "recipient_id": recipient_id,
                    },
                )
            ).mappings()
        )

    async def snapshot(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        recipient_id: uuid.UUID,
        include_tenant: bool,
    ) -> RowMapping:
        branch_clause = self._branch_clause(include_tenant)
        return (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT statement_timestamp() AS as_of,count(*) AS total,
       count(*) FILTER (WHERE read_at IS NULL) AS unread,
       max(created_at) AS newest_created_at,max(read_at) AS newest_read_at
FROM public.notifications
WHERE company_id=:company_id AND recipient_app_user_id=:recipient_id
  AND {branch_clause}
"""
                    ),
                    {
                        "branch_id": branch_id,
                        "company_id": company_id,
                        "recipient_id": recipient_id,
                    },
                )
            )
            .mappings()
            .one()
        )

    async def read_one(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        recipient_id: uuid.UUID,
        include_tenant: bool,
        notification_id: uuid.UUID,
    ) -> RowMapping | None:
        branch_clause = self._branch_clause(include_tenant)
        return (
            (
                await self.connection.execute(
                    text(
                        f"""
UPDATE public.notifications
SET read_at=COALESCE(read_at,statement_timestamp())
WHERE id=:notification_id AND company_id=:company_id
  AND recipient_app_user_id=:recipient_id AND {branch_clause}
RETURNING id,type,title,body,related_entity_type,related_entity_id,read_at,created_at
"""
                    ),
                    {
                        "branch_id": branch_id,
                        "company_id": company_id,
                        "notification_id": notification_id,
                        "recipient_id": recipient_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )

    async def read_all(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        recipient_id: uuid.UUID,
        include_tenant: bool,
    ) -> tuple[int, datetime]:
        branch_clause = self._branch_clause(include_tenant)
        result = await self.connection.execute(
            text(
                f"""
UPDATE public.notifications
SET read_at=statement_timestamp()
WHERE company_id=:company_id AND recipient_app_user_id=:recipient_id
  AND {branch_clause} AND read_at IS NULL
"""
            ),
            {
                "branch_id": branch_id,
                "company_id": company_id,
                "recipient_id": recipient_id,
            },
        )
        as_of = (await self.connection.execute(text("SELECT statement_timestamp()"))).scalar_one()
        return result.rowcount, as_of

    async def exists_in_partition(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        recipient_id: uuid.UUID,
        include_tenant: bool,
    ) -> bool:
        branch_clause = self._branch_clause(include_tenant)
        return bool(
            await self.connection.scalar(
                text(
                    f"""
SELECT EXISTS(SELECT 1 FROM public.notifications
WHERE company_id=:company_id AND recipient_app_user_id=:recipient_id
  AND {branch_clause})
"""
                ),
                {
                    "branch_id": branch_id,
                    "company_id": company_id,
                    "recipient_id": recipient_id,
                },
            )
        )
