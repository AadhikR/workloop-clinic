from __future__ import annotations

import re
import uuid
from datetime import date
from typing import cast

from fastapi import APIRouter, Request, Response
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AuthenticatedReadPrincipal,
    VerifiedAccessToken,
    branch_required_error,
    invalid_branch_error,
)
from app.db.output_audit import append_output_audit
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import DataResponse
from app.models.identity import AppRole
from app.repositories.reports import SqlReportRepository
from app.schemas.reports import ReportResponse
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.outputs import delivery_headers, render_report_csv
from app.services.reports import REPORT_SPECS, ReportQuery, ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

ERRORS = error_response_documentation(
    "invalid_cursor",
    "unknown_filter",
    "validation_failed",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "invalid_branch",
    "branch_required",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "report_source_unavailable",
    "output_limit_exceeded",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)

PERIOD = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> ReportService:
    factory = getattr(request.app.state, "report_service_factory", None)
    if factory is not None:
        return cast(ReportService, factory(connection))
    return ReportService(SqlReportRepository(connection), request.app.state.report_cursor_codec)


def _branch(request: Request, principal: AuthorizationPrincipal) -> uuid.UUID:
    if principal.role is not AppRole.ADMIN:
        raise ServiceExecutionError("operation_not_permitted")
    values = request.headers.getlist("x-workloop-branch-id")
    if not values:
        raise branch_required_error()
    if len(values) != 1 or values[0] != values[0].strip():
        raise invalid_branch_error()
    try:
        branch_id = uuid.UUID(values[0])
    except (AttributeError, ValueError):
        raise invalid_branch_error() from None
    if branch_id.version is None or str(branch_id) != values[0]:
        raise invalid_branch_error()
    return branch_id


def _uuid(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise api_error("validation_failed") from None
    if parsed.version is None or str(parsed) != value:
        raise api_error("validation_failed")
    return parsed


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise api_error("validation_failed") from None
    if parsed.isoformat() != value:
        raise api_error("validation_failed")
    return parsed


def _query(report_id: str, request: Request) -> ReportQuery:
    spec = REPORT_SPECS.get(report_id)
    if spec is None:
        raise api_error("resource_not_found")
    seen: set[str] = set()
    for name, _value in request.query_params.multi_items():
        if name not in spec.filters:
            raise api_error("unknown_filter")
        if name in seen:
            raise api_error("validation_failed")
        seen.add(name)
    raw = request.query_params
    date_from = _date(raw.get("from"))
    date_to = _date(raw.get("to"))
    if (
        date_from is not None
        and date_to is not None
        and (date_from > date_to or (date_to - date_from).days > 366)
    ):
        raise api_error("validation_failed")
    period = raw.get("period")
    if period is not None and PERIOD.fullmatch(period) is None:
        raise api_error("validation_failed")
    status = raw.get("status")
    if status is not None and (not status or len(status) > 64 or status != status.strip()):
        raise api_error("validation_failed")
    raw_limit = raw.get("limit")
    limit = 50
    if raw_limit is not None:
        if (
            not raw_limit.isascii()
            or not raw_limit.isdigit()
            or (len(raw_limit) > 1 and raw_limit.startswith("0"))
        ):
            raise api_error("validation_failed")
        limit = int(raw_limit)
        if not 1 <= limit <= 200:
            raise api_error("validation_failed")
    cursor = raw.get("cursor")
    if cursor is not None and (not cursor or len(cursor) > 512 or not cursor.isascii()):
        raise api_error("invalid_cursor")
    return ReportQuery(
        date_from=date_from,
        date_to=date_to,
        period=period,
        status=status,
        employee_id=_uuid(raw.get("employeeId")),
        department_id=_uuid(raw.get("departmentId")),
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/{report_id}.csv",
    response_class=Response,
    operation_id="download_report_csv",
    responses={
        **success_response_documentation(200, "Administrator report CSV", cache_control="no-store"),
        **ERRORS,
    },
)
async def download_report_csv(
    report_id: str,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    query = _query(report_id, request)
    branch_id = _branch(request, principal)

    async def operation(connection: AsyncConnection):
        report = await _service(request, connection).read_export(
            report_id, principal, branch_id, query
        )
        output = render_report_csv(report)
        await append_output_audit(
            connection,
            action="report_csv_exported",
            entity_type="report",
            entity_id=branch_id,
            format="csv",
            filter_digest=output.filter_digest,
            source_digest=output.source_digest,
            renderer_version=output.renderer_version,
            row_count=output.row_count,
            byte_count=len(output.content),
        )
        return output

    output = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=operation,
    )
    request_id = str(request.state.correlation_id)
    return Response(
        content=output.content,
        media_type=output.content_type,
        headers=delivery_headers(output, request_id),
    )


@router.get(
    "/{report_id}",
    response_model=DataResponse[ReportResponse],
    operation_id="read_report",
    responses={
        **success_response_documentation(200, "Administrator report", cache_control="no-store"),
        **ERRORS,
    },
)
async def read_report(
    report_id: str,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[ReportResponse]:
    query = _query(report_id, request)
    branch_id = _branch(request, principal)

    async def operation(service: ReportService) -> ReportResponse:
        return await service.read(report_id, principal, branch_id, query)

    result = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: operation(_service(request, connection)),
    )
    response.headers["Cache-Control"] = "no-store"
    return DataResponse(data=result)
