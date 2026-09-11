from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.execution import ServiceDeadlineExceeded, ServiceExecutionError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    status_code: int
    message: str
    required_headers: tuple[tuple[str, str], ...] = ()


ERROR_REGISTRY: dict[str, ErrorSpec] = {
    "invalid_request": ErrorSpec(400, "Invalid request"),
    "branch_required": ErrorSpec(400, "Branch selection required"),
    "invalid_cursor": ErrorSpec(400, "Invalid pagination cursor"),
    "idempotency_key_required": ErrorSpec(400, "Idempotency key required"),
    "invalid_idempotency_key": ErrorSpec(400, "Invalid idempotency key"),
    "invalid_access_token": ErrorSpec(
        401, "Authentication required", (("WWW-Authenticate", "Bearer"),)
    ),
    "application_account_unavailable": ErrorSpec(403, "Application account unavailable"),
    "operation_not_permitted": ErrorSpec(403, "Operation not permitted"),
    "origin_not_allowed": ErrorSpec(403, "Origin not allowed"),
    "resource_not_found": ErrorSpec(404, "Resource not found"),
    "method_not_allowed": ErrorSpec(405, "Method not allowed"),
    "not_acceptable": ErrorSpec(406, "Requested response type is not available"),
    "state_conflict": ErrorSpec(409, "Resource state changed"),
    "branch_conflict": ErrorSpec(409, "Branch state prevents this operation"),
    "department_conflict": ErrorSpec(409, "Department state prevents this operation"),
    "staffing_rule_conflict": ErrorSpec(409, "Staffing rule state prevents this operation"),
    "idempotency_conflict": ErrorSpec(409, "Idempotency key already used"),
    "idempotency_in_progress": ErrorSpec(
        409,
        "Request with this idempotency key is in progress",
        (("Retry-After", "1"),),
    ),
    "request_too_large": ErrorSpec(413, "Request is too large"),
    "unsupported_media_type": ErrorSpec(415, "Unsupported request content type"),
    "validation_failed": ErrorSpec(422, "Request validation failed"),
    "invalid_branch": ErrorSpec(422, "Invalid branch selection"),
    "rate_limit_exceeded": ErrorSpec(429, "Too many requests", (("Retry-After", "60"),)),
    "internal_error": ErrorSpec(500, "Unexpected server error"),
    "application_account_lookup_unavailable": ErrorSpec(503, "Service temporarily unavailable"),
    "service_unavailable": ErrorSpec(503, "Service temporarily unavailable"),
    "request_timeout": ErrorSpec(504, "Request timed out"),
}


class ValidationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    code: str
    message: str


class ErrorContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    correlation_id: UUID = Field(alias="correlationId")
    details: list[ValidationDetail]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorContent


def api_error(
    code: str,
    *,
    headers: dict[str, str] | None = None,
    details: list[dict[str, str]] | None = None,
) -> HTTPException:
    spec = ERROR_REGISTRY[code]
    combined_headers = dict(spec.required_headers)
    if headers:
        combined_headers.update(headers)
    detail: dict[str, object] = {"code": code, "message": spec.message}
    if details is not None:
        detail["details"] = details
    return HTTPException(
        status_code=spec.status_code,
        detail=detail,
        headers=combined_headers or None,
    )


def correlation_id_for(request: Request) -> str:
    value = getattr(request.state, "correlation_id", None)
    if isinstance(value, str):
        try:
            parsed = UUID(value)
        except ValueError:
            pass
        else:
            if parsed.version == 4 and str(parsed) == value:
                return value
    return str(uuid4())


def error_response(
    *,
    code: str,
    correlation_id: str,
    details: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    spec = ERROR_REGISTRY[code]
    response_headers = dict(spec.required_headers)
    if headers:
        response_headers.update(headers)
    response_headers["Cache-Control"] = "no-store"
    return JSONResponse(
        status_code=spec.status_code,
        content={
            "error": {
                "code": code,
                "message": spec.message,
                "correlationId": correlation_id,
                "details": details or [],
            }
        },
        headers=response_headers,
    )


def _uses_api_error_contract(request: Request) -> bool:
    return request.url.path == "/health" or request.url.path.startswith("/api/v1")


def _validation_path(location: tuple[Any, ...]) -> str:
    if not location:
        return "body"
    source = str(location[0])
    if source not in {"body", "path", "query", "header"}:
        source = "body"
    result = source
    for item in location[1:]:
        if isinstance(item, int):
            result += f"[{item}]"
        else:
            result += f".{item}"
    return result


def _validation_code(error_type: str) -> tuple[str, str]:
    if error_type == "missing":
        return "required", "Field is required"
    if error_type == "extra_forbidden":
        return "unknown_field", "Field is not allowed"
    if error_type in {"greater_than", "greater_than_equal", "less_than", "less_than_equal"}:
        return "out_of_range", "Value is outside the allowed range"
    if error_type.endswith("_type") or error_type in {
        "dict_type",
        "list_type",
        "string_type",
        "bool_type",
    }:
        return "invalid_type", "Value has an invalid type"
    return "invalid_format", "Value has an invalid format"


def validation_details(exception: RequestValidationError) -> list[dict[str, str]]:
    mapped: list[dict[str, str]] = []
    for error in exception.errors():
        code, message = _validation_code(str(error.get("type", "")))
        location = tuple(error.get("loc", ()))
        mapped.append(
            {
                "path": _validation_path(location),
                "code": code,
                "message": message,
            }
        )
    mapped.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    return mapped[:20]


async def http_exception_handler(
    request: Request, exception: StarletteHTTPException
) -> JSONResponse:
    if not _uses_api_error_contract(request):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": exception.detail},
            headers=exception.headers,
        )
    code: str | None = None
    if isinstance(exception.detail, dict):
        typed_detail = cast(dict[object, object], exception.detail)
        supplied_code = typed_detail.get("code")
        if (
            isinstance(supplied_code, str)
            and supplied_code in ERROR_REGISTRY
            and ERROR_REGISTRY[supplied_code].status_code == exception.status_code
        ):
            code = supplied_code
    if code is None:
        code = {
            400: "invalid_request",
            401: "invalid_access_token",
            403: "operation_not_permitted",
            404: "resource_not_found",
            405: "method_not_allowed",
            406: "not_acceptable",
            413: "request_too_large",
            415: "unsupported_media_type",
            422: "validation_failed",
            429: "rate_limit_exceeded",
            503: "service_unavailable",
            504: "request_timeout",
        }.get(exception.status_code, "internal_error")
    details: list[dict[str, str]] | None = None
    if code == "validation_failed" and isinstance(exception.detail, dict):
        typed_detail = cast(dict[object, object], exception.detail)
        supplied_details = typed_detail.get("details")
        if isinstance(supplied_details, list):
            details = []
            for raw_item in cast(list[object], supplied_details)[:20]:
                if not isinstance(raw_item, dict):
                    continue
                item = cast(dict[object, object], raw_item)
                if set(item) != {"path", "code", "message"}:
                    continue
                if not all(isinstance(value, str) for value in item.values()):
                    continue
                details.append(cast(dict[str, str], item))
    return error_response(
        code=code,
        correlation_id=correlation_id_for(request),
        details=details,
        headers=exception.headers,
    )


async def request_validation_exception_handler(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    if not _uses_api_error_contract(request):
        return JSONResponse(status_code=422, content={"detail": exception.errors()})
    if any(error.get("type") == "json_invalid" for error in exception.errors()):
        return error_response(code="invalid_request", correlation_id=correlation_id_for(request))
    return error_response(
        code="validation_failed",
        correlation_id=correlation_id_for(request),
        details=validation_details(exception),
    )


async def unexpected_exception_handler(request: Request, _exception: Exception) -> JSONResponse:
    correlation_id = correlation_id_for(request)
    logger.error("http_request_failed", extra={"error_code": "internal_error"})
    if not _uses_api_error_contract(request):
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    return error_response(code="internal_error", correlation_id=correlation_id)


async def service_execution_exception_handler(
    request: Request, exception: ServiceExecutionError
) -> JSONResponse:
    return error_response(code=exception.code, correlation_id=correlation_id_for(request))


async def service_deadline_exception_handler(
    request: Request, _exception: ServiceDeadlineExceeded
) -> JSONResponse:
    return error_response(code="request_timeout", correlation_id=correlation_id_for(request))


def install_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(RequestValidationError, request_validation_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(ServiceExecutionError, service_execution_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(ServiceDeadlineExceeded, service_deadline_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(Exception, unexpected_exception_handler)


def error_response_documentation(*codes: str) -> dict[int | str, dict[str, Any]]:
    documented: dict[int | str, dict[str, Any]] = {}
    correlation_header = {
        "description": "Server-generated lowercase UUIDv4 for this request.",
        "schema": {"type": "string", "format": "uuid"},
    }
    cache_header = {
        "description": "Prevents storage of error responses.",
        "schema": {"type": "string", "const": "no-store"},
    }
    for code in codes:
        spec = ERROR_REGISTRY[code]
        entry = documented.setdefault(
            spec.status_code,
            {
                "model": ErrorResponse,
                "description": spec.message,
                "headers": {
                    "X-Correlation-ID": correlation_header,
                    "Cache-Control": cache_header,
                },
                "content": {"application/json": {"examples": {}}},
            },
        )
        headers = entry["headers"]
        for name, value in spec.required_headers:
            headers[name] = {"schema": {"type": "string", "example": value}}
        examples = entry["content"]["application/json"]["examples"]
        examples[code] = {
            "summary": spec.message,
            "value": {
                "error": {
                    "code": code,
                    "message": spec.message,
                    "correlationId": "00f202d5-2ef0-4d6f-9553-830e5dcfb833",
                    "details": [],
                }
            },
        }
    return documented


def success_response_documentation(
    status_code: int,
    description: str,
    *,
    cache_control: str | None = None,
) -> dict[str, Any]:
    headers: dict[str, Any] = {
        "X-Correlation-ID": {
            "description": "Server-generated lowercase UUIDv4 for this request.",
            "schema": {"type": "string", "format": "uuid"},
        }
    }
    if cache_control is not None:
        headers["Cache-Control"] = {
            "description": "Response cache policy.",
            "schema": {"type": "string", "const": cache_control},
        }
    return {
        str(status_code): {
            "description": description,
            "headers": headers,
        }
    }
