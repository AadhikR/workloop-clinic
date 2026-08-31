import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.engine import create_database_engine, probe_database

DatabaseProbe = Callable[[AsyncEngine], Awaitable[None]]

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


async def health(request: Request) -> HealthResponse | JSONResponse:
    active_settings: Settings = request.app.state.settings
    engine: AsyncEngine = request.app.state.database_engine
    database_probe: DatabaseProbe = request.app.state.database_probe
    try:
        async with asyncio.timeout(active_settings.database_health_timeout_seconds):
            await database_probe(engine)
    except Exception:
        logger.warning("database_health_check_failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "unavailable",
            },
        )
    return HealthResponse(status="ok", database="ok")


def create_app(
    settings: Settings | None = None,
    database_probe: DatabaseProbe = probe_database,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
        resolved_settings = settings or Settings()  # pyright: ignore[reportCallIssue]
        configure_logging(resolved_settings.log_level)
        engine = create_database_engine(resolved_settings.database_url.get_secret_value())
        application.state.settings = resolved_settings
        application.state.database_engine = engine
        application.state.database_probe = database_probe
        logger.info("application_started")
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("application_stopped")

    application = FastAPI(
        title="Workloop API",
        version=__version__,
        lifespan=lifespan,
    )

    application.add_api_route(
        "/health",
        health,
        methods=["GET"],
        response_model=HealthResponse,
        tags=["system"],
    )

    return application


app = create_app()
