from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.engine import create_database_engine
from app.storage import ObjectStorage, create_object_storage
from app.storage.base import StorageError, StorageNotFoundError

logger = logging.getLogger(__name__)
RETRY_DELAYS = (
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
    timedelta(hours=24),
    timedelta(hours=72),
)


@dataclass(frozen=True, slots=True)
class ClaimedOperation:
    id: UUID
    company_id: UUID
    branch_id: UUID
    operation: str
    object_key: str
    attempt_count: int


async def set_reconciler_context(
    connection: AsyncConnection,
    *,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> None:
    await connection.execute(
        text(
            """
SELECT pg_catalog.set_config('workloop.actor_kind','scheduled_job',true),
       pg_catalog.set_config('workloop.actor_key','storage_reconciliation',true),
       pg_catalog.set_config('workloop.company_id',:company_id,true),
       pg_catalog.set_config('workloop.branch_id',:branch_id,true)
"""
        ),
        {
            "company_id": "" if company_id is None else str(company_id),
            "branch_id": "" if branch_id is None else str(branch_id),
        },
    )


async def claim_operation(engine: AsyncEngine) -> ClaimedOperation | None:
    async with engine.begin() as connection:
        await set_reconciler_context(connection)
        row = (
            await connection.execute(
                text(
                    """
WITH candidate AS (
  SELECT id
  FROM public.storage_operations
  WHERE attempt_count < 8
    AND (
      status = 'pending'
      OR (status = 'failed' AND next_attempt_at <= statement_timestamp())
      OR (status = 'claimed' AND lease_expires_at <= statement_timestamp())
    )
  ORDER BY created_at,id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE public.storage_operations AS operation
SET status='claimed', attempt_count=operation.attempt_count+1,
    last_error_code='', next_attempt_at=NULL,
    claimed_at=statement_timestamp(),
    lease_expires_at=statement_timestamp()+interval '15 minutes',
    completed_at=NULL, updated_at=statement_timestamp()
FROM candidate
WHERE operation.id=candidate.id
RETURNING operation.id,operation.company_id,operation.branch_id,
          operation.operation,operation.object_key,operation.attempt_count
"""
                )
            )
        ).one_or_none()
    if row is None:
        return None
    return ClaimedOperation(
        id=cast(UUID, row.id),
        company_id=cast(UUID, row.company_id),
        branch_id=cast(UUID, row.branch_id),
        operation=cast(str, row.operation),
        object_key=cast(str, row.object_key),
        attempt_count=cast(int, row.attempt_count),
    )


async def complete_operation(
    engine: AsyncEngine, operation: ClaimedOperation, *, status: str, error_code: str
) -> None:
    retry_delay: timedelta | None = None
    if status == "failed" and operation.attempt_count < 8:
        retry_delay = RETRY_DELAYS[operation.attempt_count - 1]
    async with engine.begin() as connection:
        await set_reconciler_context(
            connection, company_id=operation.company_id, branch_id=operation.branch_id
        )
        result = await connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status=:status,last_error_code=:error_code,
    next_attempt_at=CASE WHEN CAST(:retry_delay AS interval) IS NULL THEN NULL
      ELSE statement_timestamp()+CAST(:retry_delay AS interval) END,
    claimed_at=NULL,lease_expires_at=NULL,
    completed_at=CASE WHEN :status IN ('succeeded','reconciled')
      THEN statement_timestamp() ELSE NULL END,
    updated_at=statement_timestamp()
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND status='claimed' AND attempt_count=:attempt_count
"""
            ),
            {
                "id": operation.id,
                "company_id": operation.company_id,
                "branch_id": operation.branch_id,
                "attempt_count": operation.attempt_count,
                "status": status,
                "error_code": error_code,
                "retry_delay": retry_delay,
            },
        )
        if result.rowcount != 1:
            raise RuntimeError("storage operation lease changed")


async def process_operation(
    engine: AsyncEngine, storage: ObjectStorage, operation: ClaimedOperation
) -> None:
    try:
        if operation.operation == "delete":
            with suppress(StorageNotFoundError):
                await storage.delete_object(key=operation.object_key)
            status = "succeeded"
        elif operation.operation == "upload":
            try:
                await storage.head_object(key=operation.object_key)
            except StorageNotFoundError:
                pass
            else:
                await storage.delete_object(key=operation.object_key)
            status = "reconciled"
        else:
            raise StorageError
    except StorageError:
        log = logger.error if operation.attempt_count == 8 else logger.warning
        log(
            "storage_reconciliation_terminal"
            if operation.attempt_count == 8
            else "storage_reconciliation_failed",
            extra={"operation_id": str(operation.id), "error_code": "provider_error"},
        )
        await complete_operation(engine, operation, status="failed", error_code="provider_error")
        return
    await complete_operation(engine, operation, status=status, error_code="")


async def run_once(engine: AsyncEngine, storage: ObjectStorage) -> bool:
    operation = await claim_operation(engine)
    if operation is None:
        return False
    await process_operation(engine, storage, operation)
    return True


async def run_maintenance(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await set_reconciler_context(connection)
        terminal = list(
            (
                await connection.execute(
                    text(
                        """
UPDATE public.storage_operations
SET status='failed',last_error_code='retry_exhausted',claimed_at=NULL,
    lease_expires_at=NULL,next_attempt_at=NULL,updated_at=statement_timestamp()
WHERE status='claimed' AND attempt_count=8
  AND lease_expires_at<=statement_timestamp()
RETURNING id
"""
                    )
                )
            ).scalars()
        )
        await connection.execute(
            text(
                """
DELETE FROM public.storage_operations
WHERE status IN ('succeeded','reconciled')
  AND completed_at<statement_timestamp()-interval '90 days'
"""
            )
        )
    for operation_id in terminal:
        logger.error(
            "storage_reconciliation_terminal",
            extra={"operation_id": str(operation_id), "error_code": "retry_exhausted"},
        )


async def run() -> None:
    settings = Settings()  # pyright: ignore[reportCallIssue]
    configure_logging(settings.log_level)
    engine = create_database_engine(settings.database_url.get_secret_value())
    storage = create_object_storage(settings)
    once = os.environ.get("STORAGE_RECONCILER_ONCE") == "1"
    try:
        while True:
            await run_maintenance(engine)
            processed = await run_once(engine, storage)
            if once:
                return
            if not processed:
                await asyncio.sleep(5)
    finally:
        await storage.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
