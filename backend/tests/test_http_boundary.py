import asyncio
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import pytest
from fastapi import Request
from httpx import ASGITransport, AsyncClient, Response
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.http.rate_limit import RateLimitClass, RateLimiter
from app.main import create_app


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "app_base_url": AnyHttpUrl("http://127.0.0.1:8000"),
        "frontend_url": AnyHttpUrl("http://127.0.0.1:5174"),
        "log_level": "INFO",
        "database_health_timeout_seconds": 0.05,
        "api_request_timeout_seconds": 0.05,
        "database_url": SecretStr(
            "postgresql+psycopg://workloop_runtime:test-secret@postgres/workloop"
        ),
        "oidc_issuer": AnyHttpUrl("http://127.0.0.1:8080/realms/workloop-dev"),
        "oidc_audience": "workloop-api",
        "oidc_jwks_url": AnyHttpUrl(
            "http://127.0.0.1:8080/realms/workloop-dev/protocol/openid-connect/certs"
        ),
    }
    values.update(overrides)
    return Settings.model_validate(values)


@asynccontextmanager
async def client_for(
    *,
    settings: Settings | None = None,
    probe: Callable[[AsyncEngine], Awaitable[None]] | None = None,
    rate_limiter: RateLimiter | None = None,
) -> AsyncGenerator[tuple[AsyncClient, object]]:
    async def successful_probe(_engine: AsyncEngine) -> None:
        return None

    application = create_app(
        settings=settings or make_settings(),
        database_probe=probe or successful_probe,
        rate_limiter=rate_limiter,
    )

    class EchoRequest(BaseModel):
        model_config = ConfigDict(extra="forbid", populate_by_name=False)

        display_name: str = Field(alias="displayName", min_length=1)

    class EchoResponse(BaseModel):
        model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

        display_name: str = Field(alias="displayName")

    async def echo(body: EchoRequest) -> dict[str, object]:
        return {"data": EchoResponse(displayName=body.display_name).model_dump(by_alias=True)}

    async def read_body(request: Request) -> dict[str, object]:
        body = await request.body()
        return {"data": {"size": len(body)}}

    async def slow() -> dict[str, object]:
        await asyncio.sleep(1)
        return {"data": {"finished": True}}

    async def fail() -> None:
        raise RuntimeError("database-url-and-private-record")

    application.add_api_route("/api/v1/test/echo", echo, methods=["POST"])
    application.add_api_route("/api/v1/test/body", read_body, methods=["POST"])
    application.add_api_route("/api/v1/test/slow", slow, methods=["GET"])
    application.add_api_route("/api/v1/test/fail", fail, methods=["GET"])

    async with (
        application.router.lifespan_context(application),
        AsyncClient(
            transport=ASGITransport(app=application, raise_app_exceptions=False),
            base_url="http://testserver",
        ) as client,
    ):
        yield client, application


def assert_error(response: Response, status_code: int, code: str, message: str) -> str:
    body = response.json()
    assert response.status_code == status_code
    correlation_id = body["error"]["correlationId"]
    assert body == {
        "error": {
            "code": code,
            "message": message,
            "correlationId": correlation_id,
            "details": [],
        }
    }
    parsed = uuid.UUID(correlation_id)
    assert parsed.version == 4
    assert str(parsed) == correlation_id
    assert response.headers["x-correlation-id"] == correlation_id
    return correlation_id


@pytest.mark.asyncio
async def test_server_generates_correlation_id_and_ignores_caller_values() -> None:
    supplied = str(uuid.uuid4())
    async with client_for() as (client, _application):
        first = await client.get(
            "/health",
            headers={"X-Correlation-ID": supplied, "X-Request-ID": supplied},
        )
        second = await client.get("/health")

    first_id = first.headers["x-correlation-id"]
    second_id = second.headers["x-correlation-id"]
    assert first.status_code == second.status_code == 200
    assert first_id != supplied
    assert first_id != second_id
    assert uuid.UUID(first_id).version == uuid.UUID(second_id).version == 4


@pytest.mark.asyncio
async def test_health_failure_uses_common_safe_error() -> None:
    async def failed_probe(_engine: AsyncEngine) -> None:
        raise OSError("database-url-and-private-record")

    async with client_for(probe=failed_probe) as (client, _application):
        response = await client.get("/health")

    assert_error(response, 503, "service_unavailable", "Service temporarily unavailable")
    assert "private-record" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_cors_uses_exact_contract_and_runs_before_routing() -> None:
    allowed_origin = "http://127.0.0.1:5174"
    async with client_for() as (client, _application):
        allowed = await client.options(
            "/api/v1/not-yet-routed",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Authorization,Idempotency-Key",
            },
        )
        rejected = await client.get(
            "/missing",
            headers={"Origin": "http://localhost:5174"},
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == allowed_origin
    assert allowed.headers["access-control-allow-methods"] == "GET, POST, PATCH, DELETE, OPTIONS"
    assert allowed.headers["access-control-max-age"] == "600"
    assert "access-control-allow-credentials" not in allowed.headers
    assert "idempotency-key" in allowed.headers["access-control-allow-headers"].lower()
    assert_error(rejected, 403, "origin_not_allowed", "Origin not allowed")
    assert "access-control-allow-origin" not in rejected.headers


@pytest.mark.asyncio
async def test_framework_routing_errors_use_contract() -> None:
    async with client_for() as (client, _application):
        missing = await client.get("/api/v1/missing")
        wrong_method = await client.post("/health")

    assert_error(missing, 404, "resource_not_found", "Resource not found")
    assert_error(wrong_method, 405, "method_not_allowed", "Method not allowed")
    assert "GET" in wrong_method.headers["allow"]


@pytest.mark.asyncio
async def test_authentication_error_uses_contract_and_required_header() -> None:
    async with client_for() as (client, _application):
        response = await client.get("/api/v1/auth/token-check")

    assert_error(response, 401, "invalid_access_token", "Authentication required")
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.asyncio
async def test_oversized_body_precedes_authentication_but_not_routing() -> None:
    headers = {"Content-Type": "application/json", "Content-Length": "1048577"}
    async with client_for() as (client, _application):
        protected = await client.request(
            "GET", "/api/v1/auth/token-check", content=b"x", headers=headers
        )
        missing = await client.post("/api/v1/missing", content=b"x", headers=headers)

    assert_error(protected, 413, "request_too_large", "Request is too large")
    assert_error(missing, 404, "resource_not_found", "Resource not found")


@pytest.mark.asyncio
async def test_duplicate_origin_is_invalid_request() -> None:
    async with client_for() as (client, _application):
        response = await client.get(
            "/health",
            headers=[
                ("Origin", "http://127.0.0.1:5174"),
                ("Origin", "http://127.0.0.1:5174"),
            ],
        )

    assert_error(response, 400, "invalid_request", "Invalid request")


@pytest.mark.asyncio
async def test_malformed_json_is_invalid_request_without_validation_details() -> None:
    async with client_for() as (client, _application):
        response = await client.post(
            "/api/v1/test/echo",
            content=b'{"displayName":',
            headers={"Content-Type": "application/json"},
        )

    assert_error(response, 400, "invalid_request", "Invalid request")


@pytest.mark.asyncio
async def test_validation_errors_are_safe_sorted_and_camel_case() -> None:
    async with client_for() as (client, _application):
        response = await client.post(
            "/api/v1/test/echo",
            json={"display_name": "", "other": "private-value"},
        )

    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert details == [
        {
            "path": "body.displayName",
            "code": "required",
            "message": "Field is required",
        },
        {
            "path": "body.display_name",
            "code": "unknown_field",
            "message": "Field is not allowed",
        },
        {
            "path": "body.other",
            "code": "unknown_field",
            "message": "Field is not allowed",
        },
    ]
    assert "private-value" not in response.text


class OversizedStream(AsyncIterator[bytes]):
    def __init__(self) -> None:
        self._sent = 0

    def __aiter__(self) -> "OversizedStream":
        return self

    async def __anext__(self) -> bytes:
        if self._sent >= 17:
            raise StopAsyncIteration
        self._sent += 1
        return b"x" * 65536


@pytest.mark.asyncio
async def test_body_limit_checks_declared_and_streamed_sizes() -> None:
    async with client_for() as (client, _application):
        declared = await client.post(
            "/api/v1/test/body",
            content=b"x",
            headers={"Content-Type": "application/json", "Content-Length": "1048577"},
        )
        streamed = await client.post(
            "/api/v1/test/body",
            content=OversizedStream(),
            headers={"Content-Type": "application/json"},
        )

    assert_error(declared, 413, "request_too_large", "Request is too large")
    assert_error(streamed, 413, "request_too_large", "Request is too large")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "status_code", "code", "message"),
    [
        (
            {"Content-Type": "text/plain"},
            415,
            "unsupported_media_type",
            "Unsupported request content type",
        ),
        (
            {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            415,
            "unsupported_media_type",
            "Unsupported request content type",
        ),
        (
            {"Content-Type": "application/json", "Accept": "text/plain"},
            406,
            "not_acceptable",
            "Requested response type is not available",
        ),
    ],
)
async def test_media_boundary_rejects_unsupported_requests(
    headers: dict[str, str], status_code: int, code: str, message: str
) -> None:
    async with client_for() as (client, _application):
        response = await client.post("/api/v1/test/body", content=b"{}", headers=headers)

    assert_error(response, status_code, code, message)


@pytest.mark.asyncio
async def test_deadline_and_unexpected_failure_use_safe_errors() -> None:
    async with client_for() as (client, _application):
        timeout = await client.get("/api/v1/test/slow")
        failure = await client.get("/api/v1/test/fail")

    assert_error(timeout, 504, "request_timeout", "Request timed out")
    assert_error(failure, 500, "internal_error", "Unexpected server error")
    assert "private-record" not in failure.text


class RejectingRateLimiter:
    def __init__(self) -> None:
        self.calls: list[tuple[RateLimitClass, str]] = []

    async def check(self, request_class: RateLimitClass, trusted_key: str) -> int | None:
        self.calls.append((request_class, trusted_key))
        return 7


@pytest.mark.asyncio
async def test_rate_limit_boundary_maps_429_with_retry_after() -> None:
    limiter = RejectingRateLimiter()
    async with client_for(rate_limiter=limiter) as (client, _application):
        response = await client.get("/health")

    assert_error(response, 429, "rate_limit_exceeded", "Too many requests")
    assert response.headers["retry-after"] == "7"
    assert limiter.calls == [(RateLimitClass.PUBLIC, "127.0.0.1")]


class InvalidTokenRateLimiter:
    def __init__(self) -> None:
        self.calls: list[tuple[RateLimitClass, str]] = []

    async def check(self, request_class: RateLimitClass, trusted_key: str) -> int | None:
        self.calls.append((request_class, trusted_key))
        if request_class is RateLimitClass.INVALID_ACCESS_TOKEN:
            return 11
        return None


@pytest.mark.asyncio
async def test_invalid_token_bucket_runs_after_route_attempt_bucket() -> None:
    limiter = InvalidTokenRateLimiter()
    async with client_for(rate_limiter=limiter) as (client, _application):
        response = await client.get("/api/v1/auth/token-check")

    assert_error(response, 429, "rate_limit_exceeded", "Too many requests")
    assert response.headers["retry-after"] == "11"
    assert limiter.calls == [
        (RateLimitClass.AUTHENTICATION_CHECK, "127.0.0.1"),
        (RateLimitClass.INVALID_ACCESS_TOKEN, "127.0.0.1"),
    ]


@pytest.mark.asyncio
async def test_openapi_names_operations_and_common_error_headers() -> None:
    async with client_for() as (client, _application):
        response = await client.get("/openapi.json")

    document = response.json()
    assert document["paths"]["/health"]["get"]["operationId"] == "health_check"
    assert "X-Correlation-ID" in document["paths"]["/health"]["get"]["responses"]["200"]["headers"]
    token_check = document["paths"]["/api/v1/auth/token-check"]["get"]
    assert token_check["operationId"] == "check_access_token"
    assert "X-Correlation-ID" in token_check["responses"]["204"]["headers"]
    assert "X-Correlation-ID" in token_check["responses"]["401"]["headers"]
    assert "ErrorResponse" in str(token_check["responses"]["401"])
    assert token_check["responses"]["503"]["content"]["application/json"]["examples"] == {
        "application_account_lookup_unavailable": {
            "summary": "Service temporarily unavailable",
            "value": {
                "error": {
                    "code": "application_account_lookup_unavailable",
                    "message": "Service temporarily unavailable",
                    "correlationId": "00f202d5-2ef0-4d6f-9553-830e5dcfb833",
                    "details": [],
                }
            },
        }
    }
    assert "422" not in token_check["responses"]
