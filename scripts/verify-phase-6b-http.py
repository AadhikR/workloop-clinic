from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

API_BASE_URL = os.environ.get("WORKLOOP_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ALLOWED_ORIGIN = "http://127.0.0.1:5174"


def request(
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    data: bytes | None = None,
) -> tuple[int, Any, bytes]:
    outgoing = urllib.request.Request(
        f"{API_BASE_URL}{path}", data=data, headers=headers or {}, method=method
    )
    try:
        response = urllib.request.urlopen(outgoing, timeout=20)
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()
    with response:
        return response.status, response.headers, response.read()


def correlation_id(headers: Any) -> str:
    value = headers["X-Correlation-ID"]
    parsed = uuid.UUID(value)
    assert parsed.version == 4
    assert str(parsed) == value
    return value


def assert_api_error(
    result: tuple[int, Any, bytes],
    *,
    status: int,
    code: str,
    message: str,
) -> None:
    actual_status, headers, body = result
    request_id = correlation_id(headers)
    assert actual_status == status
    assert headers["Cache-Control"] == "no-store"
    assert json.loads(body) == {
        "error": {
            "code": code,
            "message": message,
            "correlationId": request_id,
            "details": [],
        }
    }


def main() -> None:
    caller_id = str(uuid.uuid4())
    status, headers, body = request("/health", headers={"X-Correlation-ID": caller_id})
    assert status == 200
    assert json.loads(body) == {"status": "ok", "database": "ok"}
    assert correlation_id(headers) != caller_id

    status, headers, body = request(
        "/api/v1/not-routed",
        method="OPTIONS",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Authorization,Content-Type,Idempotency-Key",
        },
    )
    assert status == 200 and body == b""
    assert correlation_id(headers)
    assert headers["Access-Control-Allow-Origin"] == ALLOWED_ORIGIN
    assert headers["Access-Control-Allow-Methods"] == "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    assert headers["Access-Control-Max-Age"] == "600"
    assert headers.get("Access-Control-Allow-Credentials") is None

    rejected_origin = request(
        "/health", headers={"Origin": "http://localhost:5174"}
    )
    assert_api_error(
        rejected_origin,
        status=403,
        code="origin_not_allowed",
        message="Origin not allowed",
    )
    assert rejected_origin[1].get("Access-Control-Allow-Origin") is None

    assert_api_error(
        request("/api/v1/not-routed"),
        status=404,
        code="resource_not_found",
        message="Resource not found",
    )
    missing_token = request("/api/v1/auth/token-check")
    assert_api_error(
        missing_token,
        status=401,
        code="invalid_access_token",
        message="Authentication required",
    )
    assert missing_token[1]["WWW-Authenticate"] == "Bearer"

    oversized = request(
        "/api/v1/auth/token-check",
        headers={"Content-Length": "1048577", "Content-Type": "application/json"},
    )
    assert_api_error(
        oversized,
        status=413,
        code="request_too_large",
        message="Request is too large",
    )

    status, headers, body = request("/openapi.json")
    assert status == 200
    assert correlation_id(headers)
    document = json.loads(body)
    health = document["paths"]["/health"]["get"]
    token_check = document["paths"]["/api/v1/auth/token-check"]["get"]
    assert health["operationId"] == "health_check"
    assert token_check["operationId"] == "check_access_token"
    assert "X-Correlation-ID" in health["responses"]["200"]["headers"]
    assert "X-Correlation-ID" in token_check["responses"]["204"]["headers"]
    assert "422" not in token_check["responses"]

    print("Phase 6B HTTP boundary checks passed")


if __name__ == "__main__":
    main()
