import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal

import httpx
from fastapi import FastAPI, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app import __version__
from app.auth.access_token import AccessTokenVerifier
from app.auth.application_user import ApplicationUserResolver
from app.auth.dependencies import AuthenticatedAuthorizationPrincipal
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.engine import create_database_engine, probe_database
from app.http.errors import (
    api_error,
    error_response_documentation,
    install_exception_handlers,
    success_response_documentation,
)
from app.http.middleware import ALLOWED_ORIGIN, HttpBoundaryMiddleware
from app.http.rate_limit import InactiveRateLimiter, RateLimiter
from app.http.sample_schemas import CurrentAccountResponse, PublicStatusResponse
from app.http.schemas import DataResponse
from app.sample_api import get_current_account, get_public_status
from app.services.execution import AuthorizedServiceExecutor

DatabaseProbe = Callable[[AsyncEngine], Awaitable[None]]

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]


async def check_access_token(_principal: AuthenticatedAuthorizationPrincipal) -> Response:
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Cache-Control": "no-store"},
    )


async def health(request: Request) -> HealthResponse:
    active_settings: Settings = request.app.state.settings
    engine: AsyncEngine = request.app.state.database_engine
    database_probe: DatabaseProbe = request.app.state.database_probe
    try:
        async with asyncio.timeout(active_settings.database_health_timeout_seconds):
            await database_probe(engine)
    except Exception:
        logger.warning("database_health_check_failed")
        raise api_error("service_unavailable") from None
    return HealthResponse(status="ok", database="ok")


def create_app(
    settings: Settings | None = None,
    database_probe: DatabaseProbe = probe_database,
    rate_limiter: RateLimiter | None = None,
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
        transaction_factory = AuthorizationTransactionFactory(
            engine=engine,
            setup_timeout_seconds=resolved_settings.authorization_context_setup_timeout_seconds,
        )
        application.state.authorization_transaction_factory = transaction_factory
        application.state.authorized_service_executor = AuthorizedServiceExecutor(
            transaction_factory,
            deadline_seconds=resolved_settings.api_request_timeout_seconds,
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
    resolved_rate_limiter = rate_limiter or InactiveRateLimiter()
    application.state.rate_limiter = resolved_rate_limiter
    install_exception_handlers(application)
    application.add_middleware(
        HttpBoundaryMiddleware,
        allowed_origins=(ALLOWED_ORIGIN,),
        request_timeout_seconds=(settings.api_request_timeout_seconds if settings else 15.0),
        health_timeout_seconds=(settings.database_health_timeout_seconds if settings else 5.0),
        rate_limiter=resolved_rate_limiter,
    )

    application.add_api_route(
        "/health",
        health,
        methods=["GET"],
        response_model=HealthResponse,
        operation_id="health_check",
        responses={
            **success_response_documentation(200, "Health check passed"),
            **error_response_documentation(
                "invalid_request",
                "origin_not_allowed",
                "method_not_allowed",
                "not_acceptable",
                "request_too_large",
                "unsupported_media_type",
                "rate_limit_exceeded",
                "service_unavailable",
                "request_timeout",
                "internal_error",
            ),
        },
        tags=["system"],
    )
    application.add_api_route(
        "/api/v1/auth/token-check",
        check_access_token,
        methods=["GET"],
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        operation_id="check_access_token",
        responses={
            **success_response_documentation(204, "Access token and account are valid"),
            **error_response_documentation(
                "invalid_request",
                "invalid_access_token",
                "application_account_unavailable",
                "origin_not_allowed",
                "method_not_allowed",
                "not_acceptable",
                "request_too_large",
                "unsupported_media_type",
                "rate_limit_exceeded",
                "application_account_lookup_unavailable",
                "request_timeout",
                "internal_error",
            ),
        },
        tags=["authentication"],
    )
    application.add_api_route(
        "/api/v1/public/status",
        get_public_status,
        methods=["GET"],
        response_model=DataResponse[PublicStatusResponse],
        operation_id="get_public_status",
        responses={
            **success_response_documentation(
                200,
                "Public API status",
                cache_control="no-store",
            ),
            **error_response_documentation(
                "invalid_request",
                "origin_not_allowed",
                "method_not_allowed",
                "not_acceptable",
                "request_too_large",
                "unsupported_media_type",
                "rate_limit_exceeded",
                "request_timeout",
                "internal_error",
            ),
        },
        tags=["system"],
    )
    application.add_api_route(
        "/api/v1/account/me",
        get_current_account,
        methods=["GET"],
        response_model=DataResponse[CurrentAccountResponse],
        operation_id="get_current_account",
        responses={
            **success_response_documentation(
                200,
                "Current application account",
                cache_control="no-store",
            ),
            **error_response_documentation(
                "invalid_request",
                "invalid_access_token",
                "application_account_unavailable",
                "operation_not_permitted",
                "origin_not_allowed",
                "resource_not_found",
                "method_not_allowed",
                "not_acceptable",
                "request_too_large",
                "unsupported_media_type",
                "validation_failed",
                "rate_limit_exceeded",
                "application_account_lookup_unavailable",
                "request_timeout",
                "internal_error",
            ),
        },
        tags=["account"],
    )

    return application


app = create_app()
