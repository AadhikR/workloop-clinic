from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.idempotency import IdempotencyRecord


class IdempotencyRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def try_lock(self, lock_key: int) -> bool:
        result = await self._connection.exec_driver_sql(
            "SELECT pg_try_advisory_xact_lock(%s)", (lock_key,)
        )
        return bool(result.scalar_one())

    async def fetch(self, app_user_id: uuid.UUID, key: uuid.UUID) -> RowMapping | None:
        result = await self._connection.execute(
            select(*IdempotencyRecord.__table__.c).where(
                IdempotencyRecord.app_user_id == app_user_id,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        return result.mappings().one_or_none()

    async def cleanup_expired(self) -> None:
        result = await self._connection.exec_driver_sql(
            "SELECT public.cleanup_expired_idempotency_records()"
        )
        deleted = result.scalar_one()
        if not isinstance(deleted, int) or not 0 <= deleted <= 100:
            raise RuntimeError("invalid idempotency cleanup result")

    async def reserve(
        self,
        *,
        app_user_id: uuid.UUID,
        key: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID | None,
        operation_id: str,
        method: str,
        route_parameters: dict[str, object],
        fingerprint_version: str,
        fingerprint: str,
    ) -> None:
        await self._connection.execute(
            insert(IdempotencyRecord).values(
                app_user_id=app_user_id,
                idempotency_key=key,
                company_id=company_id,
                branch_id=branch_id,
                operation_id=operation_id,
                http_method=method,
                route_parameters=route_parameters,
                fingerprint_version=fingerprint_version,
                request_fingerprint=fingerprint,
            )
        )

    async def complete(
        self,
        *,
        app_user_id: uuid.UUID,
        key: uuid.UUID,
        replay_resource_kind: str,
        replay_resource_id: uuid.UUID | None,
        response_status: int,
        response_body: dict[str, object] | None,
        response_location: str | None,
        completed_at: datetime,
        retain_until: datetime,
    ) -> None:
        result = await self._connection.execute(
            update(IdempotencyRecord)
            .where(
                IdempotencyRecord.app_user_id == app_user_id,
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.completed_at.is_(None),
            )
            .values(
                replay_resource_kind=replay_resource_kind,
                replay_resource_id=replay_resource_id,
                response_status=response_status,
                response_body=response_body,
                response_location=response_location,
                completed_at=completed_at,
                retain_until=retain_until,
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("idempotency completion did not update one reservation")
