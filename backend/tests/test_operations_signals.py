from __future__ import annotations

import json
import logging
import uuid
from typing import cast

import pytest

from app.core.logging import JsonFormatter
from app.storage import ObjectStorage, reconciler, scanner_worker
from app.storage.base import StorageError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attempt_count", "event", "condition"),
    [
        (2, "worker_retry_scheduled", "retry"),
        (8, "worker_terminal_failure", "terminal-failure"),
    ],
)
async def test_scanner_failure_emits_safe_worker_signal(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    attempt_count: int,
    event: str,
    condition: str,
) -> None:
    async def record_result(*_values: object, **_named: object) -> None:
        return None

    monkeypatch.setattr(scanner_worker, "_record_result", record_result)
    scan = scanner_worker.ClaimedScan(
        id=uuid.UUID("b4000000-0000-4000-8000-000000000001"),
        company_id=uuid.UUID("b4000000-0000-4000-8000-000000000002"),
        branch_id=uuid.UUID("b4000000-0000-4000-8000-000000000003"),
        entity_type="synthetic_document",
        object_key="not-logged",
        content_type="application/pdf",
        size_bytes=1,
        sha256="0" * 64,
        scanner_definition="synthetic-v1",
        attempt_count=attempt_count,
        queue_age_seconds=1,
        expired_lease_age_seconds=None,
    )

    with caplog.at_level(logging.INFO):
        await scanner_worker._scan_failed(  # pyright: ignore[reportPrivateUsage]
            cast(object, None),  # pyright: ignore[reportArgumentType]
            scan,
            "provider_error",
        )

    record = next(record for record in caplog.records if record.getMessage() == event)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["worker"] == "file_scanner"
    assert payload["condition"] == condition
    assert payload["attempt_count"] == attempt_count
    assert "object_key" not in payload


class FailingDeleteStorage:
    async def delete_object(self, *, key: str) -> None:
        del key
        raise StorageError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("attempt_count", "event", "condition"),
    [
        (2, "worker_retry_scheduled", "retry"),
        (8, "worker_terminal_failure", "terminal-failure"),
    ],
)
async def test_reconciler_failure_emits_safe_worker_signal(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    attempt_count: int,
    event: str,
    condition: str,
) -> None:
    async def complete(*_values: object, **_named: object) -> None:
        return None

    monkeypatch.setattr(reconciler, "complete_operation", complete)
    operation = reconciler.ClaimedOperation(
        id=uuid.UUID("b4000000-0000-4000-8000-000000000004"),
        company_id=uuid.UUID("b4000000-0000-4000-8000-000000000002"),
        branch_id=uuid.UUID("b4000000-0000-4000-8000-000000000003"),
        operation="delete",
        object_key="not-logged",
        attempt_count=attempt_count,
        queue_age_seconds=1,
        expired_lease_age_seconds=None,
    )

    with caplog.at_level(logging.INFO):
        await reconciler.process_operation(
            cast(object, None),  # pyright: ignore[reportArgumentType]
            cast(ObjectStorage, FailingDeleteStorage()),
            operation,
        )

    record = next(record for record in caplog.records if record.getMessage() == event)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["worker"] == "storage_reconciler"
    assert payload["condition"] == condition
    assert payload["attempt_count"] == attempt_count
    assert "object_key" not in payload
