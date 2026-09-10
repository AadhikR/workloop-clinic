from __future__ import annotations

import re
import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    VerifiedAccessToken,
    operation_not_permitted_error,
    resource_not_found_error,
)
from app.http.errors import (
    api_error,
    error_response_documentation,
    success_response_documentation,
)
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.http.validation import parse_pagination, parse_sort, validate_query_parameters
from app.models.identity import AppRole
from app.schemas.organization import (
    BranchAdminResponse,
    BranchSafeResponse,
    CompanyAdminResponse,
    SafeEmployerResponse,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.organization import BranchListQuery, OrganizationService, normalize_search

router = APIRouter(prefix="/api/v1", tags=["organization"])
CANONICAL_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_CANONICAL_UUID = re.compile(CANONICAL_UUID_PATTERN)

ORGANIZATION_ERRORS = error_response_documentation(
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
    "invalid_branch",
    "invalid_cursor",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> OrganizationService:
    factory = getattr(request.app.state, "organization_service_factory", None)
    if factory is not None:
        return cast(OrganizationService, factory(connection))
    return OrganizationService(connection, request.app.state.organization_cursor_codec)


def _reject_branch_header(request: Request) -> None:
    if request.headers.getlist("x-workloop-branch-id"):
        raise operation_not_permitted_error()


def _require_role(principal: AuthorizationPrincipal, *roles: AppRole) -> None:
    if principal.role not in roles:
        raise operation_not_permitted_error()


def _branch_query(request: Request) -> BranchListQuery:
    validate_query_parameters(request, allowed={"limit", "cursor", "search", "sort"})
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        search = normalize_search(request.query_params.get("search"))
        sort = parse_sort(
            request.query_params.get("sort"),
            allowed_fields={"name", "createdAt"},
            default=("name",),
        )
    except ValueError:
        raise api_error(
            "validation_failed",
            details=[
                {
                    "path": "query",
                    "code": "invalid_format",
                    "message": "Query value has an invalid format",
                }
            ],
        ) from None
    return BranchListQuery(
        limit=pagination.limit,
        search=search,
        sort=sort,
        cursor=pagination.cursor,
    )


BranchQuery = Annotated[BranchListQuery, Depends(_branch_query)]


@router.get(
    "/company",
    response_model=DataResponse[CompanyAdminResponse],
    operation_id="get_company",
    responses={
        **success_response_documentation(200, "Current legal company", cache_control="no-store"),
        **ORGANIZATION_ERRORS,
    },
)
async def get_company(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[CompanyAdminResponse]:
    _reject_branch_header(request)
    _require_role(principal, AppRole.ADMIN)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> CompanyAdminResponse:
        return await _service(request, connection).get_company(principal)

    data = await executor.execute(claims=claims, principal=principal, operation=operation)
    return DataResponse(data=data)


@router.get(
    "/employer",
    response_model=DataResponse[SafeEmployerResponse],
    operation_id="get_safe_employer",
    responses={
        **success_response_documentation(200, "Current safe employer", cache_control="no-store"),
        **ORGANIZATION_ERRORS,
    },
)
async def get_employer(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[SafeEmployerResponse]:
    _reject_branch_header(request)
    _require_role(principal, AppRole.MANAGER, AppRole.EMPLOYEE)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> SafeEmployerResponse:
        return await _service(request, connection).get_employer(principal)

    data = await executor.execute(claims=claims, principal=principal, operation=operation)
    return DataResponse(data=data)


@router.get(
    "/branches",
    response_model=CollectionResponse[BranchAdminResponse | BranchSafeResponse],
    operation_id="list_branches",
    responses={
        **success_response_documentation(200, "Visible branches", cache_control="no-store"),
        **ORGANIZATION_ERRORS,
    },
)
async def list_branches(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    query: BranchQuery,
) -> CollectionResponse[BranchAdminResponse | BranchSafeResponse]:
    _reject_branch_header(request)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(
        connection: AsyncConnection,
    ) -> tuple[list[BranchAdminResponse | BranchSafeResponse], str | None]:
        return await _service(request, connection).list_branches(principal, query)

    items, next_cursor = await executor.execute(
        claims=claims, principal=principal, operation=operation
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=query.limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/branches/{branch_id}",
    response_model=DataResponse[BranchAdminResponse],
    operation_id="get_branch",
    responses={
        **success_response_documentation(200, "Selected branch", cache_control="no-store"),
        **ORGANIZATION_ERRORS,
    },
)
async def get_branch(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    branch_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> DataResponse[BranchAdminResponse]:
    if not _CANONICAL_UUID.fullmatch(branch_id):
        raise api_error("validation_failed")
    path_branch_id = uuid.UUID(branch_id)
    if path_branch_id != selected_branch_id:
        raise resource_not_found_error()
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> BranchAdminResponse:
        return await _service(request, connection).get_branch(principal, path_branch_id)

    return DataResponse(
        data=await executor.execute(
            claims=claims,
            principal=principal,
            operation=operation,
            selected_admin_branch_id=selected_branch_id,
        )
    )
