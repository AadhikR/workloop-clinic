from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from uuid import uuid4

from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import correlation_context
from app.http.errors import error_response
from app.http.rate_limit import RateLimitClass, RateLimiter

logger = logging.getLogger(__name__)

ORDINARY_BODY_LIMIT_BYTES = 1_048_576
UPLOAD_FILE_LIMIT_BYTES = 10_485_760
UPLOAD_REQUEST_LIMIT_BYTES = 12_582_912
UPLOAD_METADATA_LIMIT_BYTES = 65_536
UPLOAD_FILES_PER_REQUEST = 1

ALLOWED_ORIGIN = "http://127.0.0.1:5174"
ALLOWED_METHODS = ("GET", "POST", "PATCH", "DELETE", "OPTIONS")
ALLOWED_HEADERS = (
    "Accept",
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "X-Workloop-Branch-ID",
)
EXPOSED_HEADERS = ("X-Correlation-ID", "Idempotency-Replayed", "Location", "Retry-After")


def ordinary_body_limit(_scope: Scope) -> int:
    return ORDINARY_BODY_LIMIT_BYTES


class HttpBoundaryMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        allowed_origins: tuple[str, ...],
        request_timeout_seconds: float,
        health_timeout_seconds: float,
        rate_limiter: RateLimiter,
        body_limit_resolver: Callable[[Scope], int] | None = None,
    ) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)
        self.request_timeout_seconds = request_timeout_seconds
        self.health_timeout_seconds = health_timeout_seconds
        self.rate_limiter = rate_limiter
        self.body_limit_resolver = body_limit_resolver or ordinary_body_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid4())
        state = scope.setdefault("state", {})
        state["correlation_id"] = correlation_id
        active_settings = getattr(getattr(scope.get("app"), "state", None), "settings", None)
        allowed_origins = (
            frozenset(active_settings.cors_allowed_origins)
            if active_settings is not None
            else self.allowed_origins
        )
        origin_values = self._header_values(scope, b"origin")
        origin = origin_values[0] if len(origin_values) == 1 else None
        response_started = False

        async def send_with_contract(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                self._replace_header(headers, b"x-correlation-id", correlation_id.encode("ascii"))
                path = str(scope.get("path", ""))
                if path.startswith("/api/v1"):
                    self._replace_header(headers, b"cache-control", b"no-store")
                if origin is not None and origin in allowed_origins:
                    self._replace_header(headers, b"access-control-allow-origin", origin.encode())
                    self._replace_header(
                        headers,
                        b"access-control-expose-headers",
                        ", ".join(EXPOSED_HEADERS).encode("ascii"),
                    )
                    self._append_vary_origin(headers)
                message["headers"] = headers
            await send(message)

        with correlation_context(correlation_id):
            try:
                if len(origin_values) > 1:
                    await error_response(code="invalid_request", correlation_id=correlation_id)(
                        scope, receive, send_with_contract
                    )
                    return
                if origin is not None and origin not in allowed_origins:
                    await error_response(code="origin_not_allowed", correlation_id=correlation_id)(
                        scope, receive, send_with_contract
                    )
                    return

                if self._is_preflight(scope):
                    await self._preflight(
                        scope, receive, send_with_contract, correlation_id, origin
                    )
                    return

                route_match = self._route_match(scope)
                if route_match is Match.FULL:
                    retry_after = await self.rate_limiter.check(
                        self._rate_limit_class(scope), self._client_ip(scope)
                    )
                    if retry_after is not None:
                        await error_response(
                            code="rate_limit_exceeded",
                            correlation_id=correlation_id,
                            headers={"Retry-After": str(max(1, int(retry_after)))},
                        )(scope, receive, send_with_contract)
                        return
                    rejection = self._check_transport_headers(scope)
                    if rejection is not None:
                        await error_response(code=rejection, correlation_id=correlation_id)(
                            scope, receive, send_with_contract
                        )
                        return
                    receive, rejection = await self._bounded_receive(scope, receive)
                    if rejection is not None:
                        await error_response(code=rejection, correlation_id=correlation_id)(
                            scope, receive, send_with_contract
                        )
                        return

                health_timeout = (
                    active_settings.database_health_timeout_seconds
                    if active_settings is not None
                    else self.health_timeout_seconds
                )
                request_timeout = (
                    active_settings.api_request_timeout_seconds
                    if active_settings is not None
                    else self.request_timeout_seconds
                )
                timeout_seconds = (
                    health_timeout if scope.get("path") == "/health" else request_timeout
                )
                async with asyncio.timeout(timeout_seconds):
                    await self.app(scope, receive, send_with_contract)
            except TimeoutError:
                logger.warning("http_request_timed_out", extra={"error_code": "request_timeout"})
                if not response_started:
                    await error_response(code="request_timeout", correlation_id=correlation_id)(
                        scope, receive, send_with_contract
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("http_request_failed", extra={"error_code": "internal_error"})
                if not response_started:
                    await error_response(code="internal_error", correlation_id=correlation_id)(
                        scope, receive, send_with_contract
                    )
            finally:
                logger.info("http_request_completed")

    def _route_match(self, scope: Scope) -> Match:
        application = scope.get("app")
        router = getattr(application, "router", None)
        routes = getattr(router, "routes", ())
        best = Match.NONE
        for route in routes:
            match, _child_scope = route.matches(scope)
            if match is Match.FULL:
                return match
            if match is Match.PARTIAL:
                best = match
        return best

    @staticmethod
    def _header_values(scope: Scope, name: bytes) -> list[str]:
        return [value.decode("latin-1") for key, value in scope["headers"] if key.lower() == name]

    @staticmethod
    def _replace_header(headers: list[tuple[bytes, bytes]], name: bytes, value: bytes) -> None:
        headers[:] = [(key, item) for key, item in headers if key.lower() != name]
        headers.append((name, value))

    @staticmethod
    def _append_vary_origin(headers: list[tuple[bytes, bytes]]) -> None:
        current = [value for key, value in headers if key.lower() == b"vary"]
        values = b", ".join(current).decode("latin-1").split(",") if current else []
        if "origin" not in {value.strip().lower() for value in values}:
            headers.append((b"vary", b"Origin"))

    @staticmethod
    def _is_preflight(scope: Scope) -> bool:
        return scope["method"] == "OPTIONS" and any(
            key.lower() == b"access-control-request-method" for key, _value in scope["headers"]
        )

    async def _preflight(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        correlation_id: str,
        origin: str | None,
    ) -> None:
        method_values = self._header_values(scope, b"access-control-request-method")
        header_values = self._header_values(scope, b"access-control-request-headers")
        valid = origin is not None and len(method_values) == 1 and len(header_values) <= 1
        requested_method = method_values[0] if method_values else ""
        requested_headers = (
            [item.strip().lower() for item in header_values[0].split(",")] if header_values else []
        )
        allowed_header_names = {item.lower() for item in ALLOWED_HEADERS}
        valid = (
            valid
            and requested_method in ALLOWED_METHODS
            and len(requested_headers) == len(set(requested_headers))
            and all(item and item in allowed_header_names for item in requested_headers)
        )
        if not valid:
            await error_response(code="invalid_request", correlation_id=correlation_id)(
                scope, receive, send
            )
            return
        assert origin is not None
        headers = [
            (b"content-length", b"0"),
            (b"access-control-allow-origin", origin.encode("ascii")),
            (b"access-control-allow-methods", ", ".join(ALLOWED_METHODS).encode("ascii")),
            (b"access-control-allow-headers", ", ".join(ALLOWED_HEADERS).encode("ascii")),
            (b"access-control-max-age", b"600"),
            (b"vary", b"Origin"),
        ]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": b""})

    def _check_transport_headers(self, scope: Scope) -> str | None:
        encodings = self._header_values(scope, b"content-encoding")
        if len(encodings) > 1 or (encodings and encodings[0].lower() != "identity"):
            return "unsupported_media_type"
        accept_values = self._header_values(scope, b"accept")
        if len(accept_values) > 1:
            return "invalid_request"
        if accept_values and not self._accepts_json(accept_values[0]):
            return "not_acceptable"
        lengths = self._header_values(scope, b"content-length")
        if len(lengths) > 1:
            return "invalid_request"
        if lengths:
            raw_length = lengths[0]
            if not raw_length.isascii() or not raw_length.isdigit():
                return "invalid_request"
            if int(raw_length) > self.body_limit_resolver(scope):
                return "request_too_large"
        return None

    @staticmethod
    def _accepts_json(value: str) -> bool:
        for part in value.split(","):
            media, *parameters = (item.strip().lower() for item in part.split(";"))
            quality = 1.0
            for parameter in parameters:
                if parameter.startswith("q="):
                    try:
                        quality = float(parameter[2:])
                    except ValueError:
                        quality = 0.0
            if quality <= 0:
                continue
            if media in {"*/*", "application/*", "application/json"}:
                return True
        return False

    async def _bounded_receive(self, scope: Scope, receive: Receive) -> tuple[Receive, str | None]:
        method = str(scope.get("method", ""))
        if method not in {"POST", "PATCH", "PUT", "DELETE"}:
            return receive, None
        body_parts: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                raise asyncio.CancelledError
            body = message.get("body", b"")
            total += len(body)
            if total > self.body_limit_resolver(scope):
                return receive, "request_too_large"
            body_parts.append(body)
            if not message.get("more_body", False):
                break
        body = b"".join(body_parts)
        if body:
            content_types = self._header_values(scope, b"content-type")
            if len(content_types) > 1:
                return receive, "invalid_request"
            if not content_types or not self._is_json_content_type(content_types[0]):
                return receive, "unsupported_media_type"
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        return replay, None

    @staticmethod
    def _is_json_content_type(value: str) -> bool:
        media, *parameters = (item.strip().lower() for item in value.split(";"))
        if media != "application/json":
            return False
        return all(parameter in {"charset=utf-8", 'charset="utf-8"'} for parameter in parameters)

    @staticmethod
    def _rate_limit_class(scope: Scope) -> RateLimitClass:
        path = str(scope.get("path", ""))
        if path == "/health":
            return RateLimitClass.PUBLIC
        if path == "/api/v1/auth/token-check":
            return RateLimitClass.AUTHENTICATION_CHECK
        return RateLimitClass.PROTECTED_ATTEMPT

    @staticmethod
    def _client_ip(scope: Scope) -> str:
        client = scope.get("client")
        if isinstance(client, tuple) and client and isinstance(client[0], str):
            return client[0]
        return "unknown"
