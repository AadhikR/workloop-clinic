from __future__ import annotations

import asyncio
import logging
import os
import signal
from collections.abc import Awaitable, Callable
from contextlib import suppress
from time import monotonic

from app.core.logging import safe_event

IDLE_POLL_SECONDS = 5
HEARTBEAT_SECONDS = 60
DRAIN_SECONDS = 105


def emit_queue_observed(
    logger: logging.Logger,
    *,
    worker: str,
    queue_age_seconds: int,
) -> None:
    safe_event(
        logger,
        logging.INFO,
        "worker_queue_observed",
        worker=worker,
        condition="queue-age",
        queue_age_seconds=queue_age_seconds,
    )


def emit_expired_lease(
    logger: logging.Logger,
    *,
    worker: str,
    lease_age_seconds: int,
) -> None:
    safe_event(
        logger,
        logging.WARNING,
        "worker_lease_expired",
        worker=worker,
        condition="expired-lease",
        lease_age_seconds=lease_age_seconds,
    )


def processing_enabled() -> bool:
    return os.environ.get("WORKLOOP_WORKER_PROCESSING_ENABLED", "").lower() in {
        "1",
        "true",
    }


def install_shutdown_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def stop() -> None:
        stop_event.set()

    for event in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(event, stop)


async def _wait_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
    with suppress(TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)


async def run_disabled_loop(
    *,
    worker_name: str,
    logger: logging.Logger,
    stop_event: asyncio.Event | None = None,
) -> None:
    stop = stop_event or asyncio.Event()
    if stop_event is None:
        install_shutdown_handlers(stop)
    while not stop.is_set():
        safe_event(
            logger,
            logging.INFO,
            "worker_heartbeat",
            worker=worker_name,
            condition="heartbeat",
            processing_enabled=False,
        )
        await _wait_or_stop(stop, HEARTBEAT_SECONDS)


async def _process_claim[Claim](
    *,
    claim: Claim,
    process_claim: Callable[[Claim], Awaitable[None]],
    release_claim: Callable[[Claim], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    process_task = asyncio.ensure_future(process_claim(claim))
    stop_task = asyncio.create_task(stop_event.wait())
    done, _ = await asyncio.wait(
        {process_task, stop_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    if process_task in done:
        stop_task.cancel()
        with suppress(asyncio.CancelledError):
            await stop_task
        await process_task
        return

    try:
        await asyncio.wait_for(asyncio.shield(process_task), timeout=DRAIN_SECONDS)
    except TimeoutError:
        process_task.cancel()
        with suppress(asyncio.CancelledError):
            await process_task
        await release_claim(claim)


async def run_claim_loop[Claim](
    *,
    worker_name: str,
    logger: logging.Logger,
    claim_next: Callable[[], Awaitable[Claim | None]],
    process_claim: Callable[[Claim], Awaitable[None]],
    release_claim: Callable[[Claim], Awaitable[None]],
    maintenance: Callable[[], Awaitable[None]],
    once: bool,
    stop_event: asyncio.Event | None = None,
) -> None:
    stop = stop_event or asyncio.Event()
    if stop_event is None:
        install_shutdown_handlers(stop)
    last_heartbeat = 0.0
    while not stop.is_set():
        now = monotonic()
        if now - last_heartbeat >= HEARTBEAT_SECONDS:
            safe_event(
                logger,
                logging.INFO,
                "worker_heartbeat",
                worker=worker_name,
                condition="heartbeat",
                processing_enabled=processing_enabled(),
            )
            last_heartbeat = now
        if not processing_enabled():
            if once:
                return
            await _wait_or_stop(stop, IDLE_POLL_SECONDS)
            continue
        await maintenance()
        if stop.is_set():
            break
        claim = await claim_next()
        if claim is None:
            if once:
                return
            await _wait_or_stop(stop, IDLE_POLL_SECONDS)
            continue
        await _process_claim(
            claim=claim,
            process_claim=process_claim,
            release_claim=release_claim,
            stop_event=stop,
        )
        if once:
            return
