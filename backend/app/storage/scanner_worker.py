from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.engine import create_database_engine
from app.storage import ObjectStorage, create_object_storage
from app.storage.base import StorageError, StorageIntegrityError, StorageNotFoundError
from app.storage.malware import MalwareScanner, ScanVerdict, SyntheticMalwareScanner

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
class ClaimedScan:
    id: UUID
    company_id: UUID
    branch_id: UUID
    entity_type: str
    object_key: str
    content_type: str
    size_bytes: int
    sha256: str
    scanner_definition: str
    attempt_count: int


async def set_scanner_context(
    connection: AsyncConnection,
    *,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> None:
    await connection.execute(
        text(
            """
SELECT pg_catalog.set_config('workloop.actor_kind','scheduled_job',true),
       pg_catalog.set_config('workloop.actor_key','file_security_scan',true),
       pg_catalog.set_config('workloop.company_id',:company_id,true),
       pg_catalog.set_config('workloop.branch_id',:branch_id,true)
"""
        ),
        {
            "company_id": "" if company_id is None else str(company_id),
            "branch_id": "" if branch_id is None else str(branch_id),
        },
    )


async def claim_scan(engine: AsyncEngine) -> ClaimedScan | None:
    async with engine.begin() as connection:
        await set_scanner_context(connection)
        row = (
            await connection.execute(
                text(
                    """
WITH candidate AS (
  SELECT id
  FROM public.file_security_scans
  WHERE (attempt_count<8 AND (
      status='pending'
      OR (status='failed' AND next_attempt_at<=statement_timestamp())
      OR (status='claimed' AND lease_expires_at<=statement_timestamp())))
    OR (status='clean' AND valid_until<=statement_timestamp())
  ORDER BY created_at,id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE public.file_security_scans AS scan
SET status='claimed',
    scanner_name='',result_signature='',last_error_code='',
    attempt_count=CASE WHEN scan.status='clean' THEN 1 ELSE scan.attempt_count+1 END,
    next_attempt_at=NULL,claimed_at=statement_timestamp(),
    lease_expires_at=statement_timestamp()+interval '15 minutes',
    scanned_at=NULL,valid_until=NULL,updated_at=statement_timestamp()
FROM candidate
WHERE scan.id=candidate.id
RETURNING scan.id,scan.company_id,scan.branch_id,scan.entity_type,scan.object_key,
          scan.content_type,scan.size_bytes,scan.sha256,scan.scanner_definition,
          scan.attempt_count
"""
                )
            )
        ).one_or_none()
    if row is None:
        return None
    return ClaimedScan(
        id=cast(UUID, row.id),
        company_id=cast(UUID, row.company_id),
        branch_id=cast(UUID, row.branch_id),
        entity_type=cast(str, row.entity_type),
        object_key=cast(str, row.object_key),
        content_type=cast(str, row.content_type),
        size_bytes=cast(int, row.size_bytes),
        sha256=cast(str, row.sha256),
        scanner_definition=cast(str, row.scanner_definition),
        attempt_count=cast(int, row.attempt_count),
    )


async def manual_requeue(
    engine: AsyncEngine,
    *,
    scan_id: UUID,
    company_id: UUID,
    branch_id: UUID,
) -> bool:
    async with engine.begin() as connection:
        await set_scanner_context(
            connection,
            company_id=company_id,
            branch_id=branch_id,
        )
        return bool(
            (
                await connection.execute(
                    text("SELECT public.requeue_file_security_scan(:scan_id)"),
                    {"scan_id": scan_id},
                )
            ).scalar_one()
        )


async def _record_result(
    engine: AsyncEngine,
    scan: ClaimedScan,
    *,
    status: str,
    scanner_name: str = "",
    result_signature: str = "",
    error_code: str = "",
    scanned_at: datetime | None = None,
) -> None:
    retry_delay: timedelta | None = None
    if status == "failed" and scan.attempt_count < 8:
        retry_delay = RETRY_DELAYS[scan.attempt_count - 1]
    async with engine.begin() as connection:
        await set_scanner_context(connection, company_id=scan.company_id, branch_id=scan.branch_id)
        result = await connection.execute(
            text(
                """
UPDATE public.file_security_scans
SET status=:status,scanner_name=:scanner_name,result_signature=:result_signature,
    last_error_code=:error_code,
    next_attempt_at=CASE WHEN CAST(:retry_delay AS interval) IS NULL THEN NULL
      ELSE statement_timestamp()+CAST(:retry_delay AS interval) END,
    claimed_at=NULL,lease_expires_at=NULL,
    scanned_at=CASE WHEN :status IN ('clean','infected')
      THEN CAST(:scanned_at AS timestamptz) ELSE NULL END,
    valid_until=CASE WHEN :status='clean'
      THEN CAST(:scanned_at AS timestamptz)+interval '30 days' ELSE NULL END,
    updated_at=statement_timestamp()
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND status='claimed' AND attempt_count=:attempt_count
"""
            ),
            {
                "id": scan.id,
                "company_id": scan.company_id,
                "branch_id": scan.branch_id,
                "attempt_count": scan.attempt_count,
                "status": status,
                "scanner_name": scanner_name,
                "result_signature": result_signature,
                "error_code": error_code,
                "retry_delay": retry_delay,
                "scanned_at": scanned_at,
            },
        )
        if result.rowcount != 1:
            raise RuntimeError("file security scan lease changed")
        action = {
            "clean": "file_scan_clean",
            "infected": "file_scan_infected",
            "failed": (
                "file_scan_terminal" if scan.attempt_count == 8 else "file_scan_retry_scheduled"
            ),
        }[status]
        await connection.execute(
            text("SELECT public.append_file_security_audit(:id,:action,:error_code)"),
            {"id": scan.id, "action": action, "error_code": error_code},
        )


async def process_scan(
    engine: AsyncEngine,
    storage: ObjectStorage,
    scanner: MalwareScanner,
    scan: ClaimedScan,
) -> None:
    try:
        stored = await storage.get_object(key=scan.object_key)
        if (
            stored.metadata.size_bytes != scan.size_bytes
            or stored.metadata.content_type != scan.content_type
            or stored.metadata.sha256 != scan.sha256
        ):
            raise StorageIntegrityError
        result = await scanner.scan_object(
            body=stored.body,
            size_bytes=scan.size_bytes,
            sha256=scan.sha256,
            content_type=scan.content_type,
            definition=scan.scanner_definition,
        )
    except StorageNotFoundError:
        await _scan_failed(engine, scan, "object_missing")
        return
    except StorageIntegrityError:
        await _scan_failed(engine, scan, "integrity_error")
        return
    except StorageError:
        await _scan_failed(engine, scan, "provider_error")
        return
    except Exception:
        await _scan_failed(engine, scan, "scanner_error")
        return
    if result.verdict is ScanVerdict.ERROR:
        await _scan_failed(engine, scan, "scanner_error")
        return
    await _record_result(
        engine,
        scan,
        status="clean" if result.verdict is ScanVerdict.CLEAN else "infected",
        scanner_name=result.scanner_name,
        result_signature=result.result_signature,
        scanned_at=result.scanned_at,
    )


async def _scan_failed(engine: AsyncEngine, scan: ClaimedScan, error_code: str) -> None:
    log = logger.error if scan.attempt_count == 8 else logger.warning
    log(
        "file_security_scan_terminal" if scan.attempt_count == 8 else "file_security_scan_failed",
        extra={
            "scan_id": str(scan.id),
            "entity_type": scan.entity_type,
            "attempt_count": scan.attempt_count,
            "error_code": error_code,
        },
    )
    await _record_result(engine, scan, status="failed", error_code=error_code)


async def run_once(engine: AsyncEngine, storage: ObjectStorage, scanner: MalwareScanner) -> bool:
    scan = await claim_scan(engine)
    if scan is None:
        return False
    await process_scan(engine, storage, scanner, scan)
    return True


async def run_maintenance(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await set_scanner_context(connection)
        rows = list(
            (
                await connection.execute(
                    text(
                        """
UPDATE public.file_security_scans
SET status='failed',scanner_name='',result_signature='',
    last_error_code='retry_exhausted',next_attempt_at=NULL,
    claimed_at=NULL,lease_expires_at=NULL,scanned_at=NULL,valid_until=NULL,
    updated_at=statement_timestamp()
WHERE status='claimed' AND attempt_count=8
  AND lease_expires_at<=statement_timestamp()
RETURNING id,company_id,branch_id
"""
                    )
                )
            ).all()
        )
    for row in rows:
        async with engine.begin() as connection:
            await set_scanner_context(
                connection,
                company_id=cast(UUID, row.company_id),
                branch_id=cast(UUID, row.branch_id),
            )
            await connection.execute(
                text(
                    "SELECT public.append_file_security_audit"
                    "(:id,'file_scan_terminal','retry_exhausted')"
                ),
                {"id": row.id},
            )
        logger.error(
            "file_security_scan_terminal",
            extra={"scan_id": str(row.id), "error_code": "retry_exhausted"},
        )


def create_scanner(settings: Settings) -> MalwareScanner:
    if settings.malware_scanner_backend != "synthetic":
        raise RuntimeError("malware scanner is disabled")
    return SyntheticMalwareScanner(signing_key=settings.decoded_malware_scanner_signing_key())


async def run() -> None:
    settings = Settings()  # pyright: ignore[reportCallIssue]
    configure_logging(settings.log_level)
    engine = create_database_engine(settings.database_url.get_secret_value())
    storage = create_object_storage(settings)
    scanner = create_scanner(settings)
    once = os.environ.get("FILE_SCANNER_ONCE") == "1"
    try:
        while True:
            await run_maintenance(engine)
            processed = await run_once(engine, storage, scanner)
            if once:
                return
            if not processed:
                await asyncio.sleep(5)
    finally:
        await storage.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
