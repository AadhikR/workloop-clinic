from __future__ import annotations

import asyncio
import json
import logging

import pytest

from app.core.logging import JsonFormatter
from app.storage import worker_control


@pytest.mark.asyncio
async def test_worker_gate_stops_claims_before_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.delenv("WORKLOOP_WORKER_PROCESSING_ENABLED", raising=False)

    async def claim() -> str | None:
        calls.append("claim")
        return "claim"

    async def nothing(*_values: object) -> None:
        calls.append("mutation")

    await worker_control.run_claim_loop(
        worker_name="test_worker",
        logger=logging.getLogger(__name__),
        claim_next=claim,
        process_claim=nothing,
        release_claim=nothing,
        maintenance=lambda: nothing(),
        once=True,
        stop_event=asyncio.Event(),
    )

    assert calls == []


@pytest.mark.asyncio
async def test_worker_finishes_current_claim_then_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    stop = asyncio.Event()
    monkeypatch.setenv("WORKLOOP_WORKER_PROCESSING_ENABLED", "true")

    async def claim() -> str | None:
        calls.append("claim")
        return "one"

    async def process(value: str) -> None:
        calls.append(f"process:{value}")
        stop.set()

    async def release(value: str) -> None:
        calls.append(f"release:{value}")

    async def maintenance() -> None:
        calls.append("maintenance")

    await worker_control.run_claim_loop(
        worker_name="test_worker",
        logger=logging.getLogger(__name__),
        claim_next=claim,
        process_claim=process,
        release_claim=release,
        maintenance=maintenance,
        once=False,
        stop_event=stop,
    )

    assert calls == ["maintenance", "claim", "process:one"]


@pytest.mark.asyncio
async def test_worker_releases_claim_when_drain_window_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    stop = asyncio.Event()
    monkeypatch.setenv("WORKLOOP_WORKER_PROCESSING_ENABLED", "true")
    monkeypatch.setattr(worker_control, "DRAIN_SECONDS", 0.01)

    async def claim() -> str | None:
        return "one"

    async def process(_value: str) -> None:
        stop.set()
        await asyncio.Event().wait()

    async def release(value: str) -> None:
        calls.append(f"release:{value}")

    async def maintenance() -> None:
        return None

    await worker_control.run_claim_loop(
        worker_name="test_worker",
        logger=logging.getLogger(__name__),
        claim_next=claim,
        process_claim=process,
        release_claim=release,
        maintenance=maintenance,
        once=False,
        stop_event=stop,
    )

    assert calls == ["release:one"]


@pytest.mark.asyncio
async def test_worker_heartbeat_is_safe_and_structured(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("WORKLOOP_WORKER_PROCESSING_ENABLED", raising=False)
    monkeypatch.setattr(worker_control, "HEARTBEAT_SECONDS", 0)

    async def nothing(*_values: object) -> None:
        return None

    with caplog.at_level(logging.INFO):
        await worker_control.run_claim_loop(
            worker_name="file_scanner",
            logger=logging.getLogger("workloop.worker.test"),
            claim_next=lambda: nothing(),
            process_claim=nothing,
            release_claim=nothing,
            maintenance=lambda: nothing(),
            once=True,
            stop_event=asyncio.Event(),
        )

    record = next(record for record in caplog.records if record.getMessage() == "worker_heartbeat")
    payload = json.loads(JsonFormatter().format(record))
    assert payload["worker"] == "file_scanner"
    assert payload["processing_enabled"] is False


def test_worker_queue_and_expired_lease_signals_are_structured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("workloop.worker.test")
    with caplog.at_level(logging.INFO):
        worker_control.emit_queue_observed(logger, worker="file_scanner", queue_age_seconds=901)
        worker_control.emit_expired_lease(logger, worker="file_scanner", lease_age_seconds=1)

    payloads = [json.loads(JsonFormatter().format(record)) for record in caplog.records]
    assert any(payload.get("condition") == "queue-age" for payload in payloads)
    assert any(payload.get("condition") == "expired-lease" for payload in payloads)
