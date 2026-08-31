import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.auth.access_token import AccessTokenVerifier
from app.auth.application_user import ApplicationUserResolver
from app.auth.dependencies import VerifiedApplicationUser
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.engine import create_database_engine, probe_database

DatabaseProbe = Callable[[AsyncEngine], Awaitable[None]]

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


async def check_access_token(_app_user: VerifiedApplicationUser) -> Response:
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Cache-Control": "no-store"},
    )


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
        oidc_http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=resolved_settings.oidc_jwks_connect_timeout_seconds,
                read=resolved_settings.oidc_jwks_read_timeout_seconds,
                write=resolved_settings.oidc_jwks_read_timeout_seconds,
                pool=resolved_settings.oidc_jwks_connect_timeout_seconds,
            ),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            follow_redirects=False,
        )
        application.state.settings = resolved_settings
        application.state.database_engine = engine
        application.state.database_probe = database_probe
        application.state.application_user_resolver = ApplicationUserResolver(
            engine=engine,
            issuer=str(resolved_settings.oidc_issuer),
            timeout_seconds=resolved_settings.application_user_lookup_timeout_seconds,
        )
        application.state.access_token_verifier = AccessTokenVerifier(
            issuer=str(resolved_settings.oidc_issuer),
            audience=resolved_settings.oidc_audience,
            jwks_url=str(resolved_settings.oidc_jwks_url),
            http_client=oidc_http_client,
            total_timeout_seconds=resolved_settings.oidc_jwks_total_timeout_seconds,
            cache_ttl_seconds=resolved_settings.oidc_jwks_cache_ttl_seconds,
            refresh_cooldown_seconds=resolved_settings.oidc_jwks_refresh_cooldown_seconds,
        )
        logger.info("application_started")
        try:
            yield
        finally:
            await oidc_http_client.aclose()
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
    application.add_api_route(
        "/api/v1/auth/token-check",
        check_access_token,
        methods=["GET"],
        status_code=status.HTTP_204_NO_CONTENT,
        tags=["authentication"],
    )

    return application


app = create_app()
