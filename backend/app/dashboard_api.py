from __future__ import annotations

import uuid
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
from app.http.errors import error_response_documentation, success_response_documentation
from app.http.schemas import DataResponse
from app.http.validation import validate_query_parameters
from app.models.identity import AppRole
from app.repositories.dashboards import DashboardKind, SqlDashboardRepository
from app.schemas.dashboards import DashboardResponse
from app.services.dashboards import DashboardService
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])

ERRORS = error_response_documentation(
    "validation_failed",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "invalid_branch",
    "branch_required",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "dashboard_source_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> DashboardService:
    factory = getattr(request.app.state, "dashboard_service_factory", None)
    if factory is not None:
        return cast(DashboardService, factory(connection))
    return DashboardService(
        SqlDashboardRepository(connection, request.app.state.settings.malware_scanner_definition)
    )


def _branch(request: Request, principal: AuthorizationPrincipal) -> uuid.UUID:
    values = request.headers.getlist("x-workloop-branch-id")
    if principal.role is not AppRole.ADMIN:
        if values:
            raise invalid_branch_error()
        if principal.branch_id is None:
            raise ServiceExecutionError("resource_not_found")
        return principal.branch_id
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


async def _read(
    kind: DashboardKind,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
) -> DataResponse[DashboardResponse]:
    validate_query_parameters(request, allowed=())
    branch_id = _branch(request, principal)

    async def operation(service: DashboardService) -> DashboardResponse:
        return await service.read(kind, principal, branch_id)

    result = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation=lambda connection: operation(_service(request, connection)),
    )
    response.headers["Cache-Control"] = "no-store"
    return DataResponse(data=result)


@router.get(
    "/admin",
    response_model=DataResponse[DashboardResponse],
    operation_id="read_admin_dashboard",
    responses={
        **success_response_documentation(200, "Administrator dashboard", cache_control="no-store"),
        **ERRORS,
    },
)
async def read_admin_dashboard(
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[DashboardResponse]:
    return await _read("admin", request, response, claims, principal)


@router.get(
    "/clinical",
    response_model=DataResponse[DashboardResponse],
    operation_id="read_clinical_dashboard",
    responses={
        **success_response_documentation(200, "Clinical dashboard", cache_control="no-store"),
        **ERRORS,
    },
)
async def read_clinical_dashboard(
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[DashboardResponse]:
    return await _read("clinical", request, response, claims, principal)


@router.get(
    "/self",
    response_model=DataResponse[DashboardResponse],
    operation_id="read_self_dashboard",
    responses={
        **success_response_documentation(200, "Self dashboard", cache_control="no-store"),
        **ERRORS,
    },
)
async def read_self_dashboard(
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[DashboardResponse]:
    return await _read("self", request, response, claims, principal)
