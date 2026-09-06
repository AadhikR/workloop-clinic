from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import AnyHttpUrl, SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.main import create_app


def make_settings() -> Settings:
    return Settings(
        app_env="test",
        app_base_url=AnyHttpUrl("http://127.0.0.1:8000"),
        frontend_url=AnyHttpUrl("http://127.0.0.1:5173"),
        log_level="INFO",
        database_health_timeout_seconds=1,
        database_url=SecretStr(
            "postgresql+psycopg://workloop_runtime:test-secret@postgres/workloop"
        ),
        oidc_issuer=AnyHttpUrl("http://127.0.0.1:8080/realms/workloop-dev"),
        oidc_audience="workloop-api",
        oidc_jwks_url=AnyHttpUrl(
            "http://127.0.0.1:8080/realms/workloop-dev/protocol/openid-connect/certs"
        ),
    )


@asynccontextmanager
async def client_for(
    probe: Callable[[AsyncEngine], Awaitable[None]],
) -> AsyncGenerator[AsyncClient]:
    application = create_app(settings=make_settings(), database_probe=probe)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client,
    ):
        yield client


@pytest.mark.asyncio
async def test_health_reports_database_success() -> None:
    async def successful_probe(_engine: AsyncEngine) -> None:
        return None

    async with client_for(successful_probe) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert cast(dict[str, str], response.json()) == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_health_fails_closed_without_error_details() -> None:
    async def failed_probe(_engine: AsyncEngine) -> None:
        raise OSError("sensitive connection detail")

    async with client_for(failed_probe) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert cast(dict[str, str], response.json()) == {
        "status": "error",
        "database": "unavailable",
    }
    assert "sensitive" not in response.text


@pytest.mark.asyncio
async def test_authentication_cors_allows_only_migration_origin() -> None:
    async def successful_probe(_engine: AsyncEngine) -> None:
        return None

    async with client_for(successful_probe) as client:
        allowed = await client.options(
            "/api/v1/auth/token-check",
            headers={
                "Origin": "http://127.0.0.1:5174",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": ("Authorization,X-Workloop-Branch-ID"),
            },
        )
        rejected = await client.options(
            "/api/v1/auth/token-check",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        protected = await client.get(
            "/api/v1/auth/token-check",
            headers={"Origin": "http://127.0.0.1:5174"},
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"
    assert "x-workloop-branch-id" in allowed.headers["access-control-allow-headers"].lower()
    assert allowed.headers.get("access-control-allow-credentials") is None
    assert rejected.status_code == 400
    assert "access-control-allow-origin" not in rejected.headers
    assert protected.status_code == 401
    assert protected.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"
