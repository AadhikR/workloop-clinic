from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
    operation_not_permitted_error,
    resource_not_found_error,
)
from app.http.errors import (
    api_error,
    error_response_documentation,
    success_response_documentation,
)
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.http.validation import parse_pagination, parse_sort, validate_query_parameters
from app.models.identity import AppRole
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.organization import (
    BranchAdminResponse,
    BranchCreateRequest,
    BranchSafeResponse,
    BranchUpdateRequest,
    CompanyAdminResponse,
    CompanyUpdateRequest,
    ExpectedUpdatedAt,
    SafeEmployerResponse,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
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
    "state_conflict",
    "branch_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
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


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


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


def _delete_expected(request: Request) -> datetime:
    validate_query_parameters(request, allowed={"expectedUpdatedAt"})
    value = request.query_params.get("expectedUpdatedAt")
    try:
        return ExpectedUpdatedAt.model_validate({"expectedUpdatedAt": value}).expected_updated_at
    except ValidationError:
        raise api_error(
            "validation_failed",
            details=[
                {
                    "path": "query.expectedUpdatedAt",
                    "code": "invalid_format" if value is not None else "required",
                    "message": (
                        "Value has an invalid format" if value is not None else "Field is required"
                    ),
                }
            ],
        ) from None


DeleteExpected = Annotated[datetime, Depends(_delete_expected)]


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


@router.patch(
    "/company",
    response_model=DataResponse[CompanyAdminResponse],
    operation_id="update_company",
    responses={
        **success_response_documentation(200, "Updated legal company", cache_control="no-store"),
        **ORGANIZATION_ERRORS,
    },
)
async def update_company(
    request: Request,
    body: CompanyUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> DataResponse[CompanyAdminResponse]:
    _reject_branch_header(request)
    _require_role(principal, AppRole.ADMIN)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> CompanyAdminResponse:
        return await _service(request, connection).update_company(principal, body)

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


@router.post(
    "/branches",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[BranchAdminResponse],
    operation_id="create_branch",
    responses={
        **success_response_documentation(201, "Created branch", cache_control="no-store"),
        **ORGANIZATION_ERRORS,
    },
)
async def create_branch(
    request: Request,
    body: BranchCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> Response:
    _reject_branch_header(request)
    _require_role(principal, AppRole.ADMIN)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    body_values = body.model_dump(mode="json", by_alias=True)
    command = IdempotencyCommand(
        key=key,
        operation_id="create_branch",
        method="POST",
        route_parameters={},
        fingerprint=request_fingerprint(
            operation_id="create_branch",
            method="POST",
            route_parameters={},
            effective_query_parameters={},
            body=body_values,
        ),
    )
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutate() -> IdempotentResponse:
            branch = await service.create_branch(principal, body)
            response_body = DataResponse(data=branch).model_dump(mode="json", by_alias=True)
            return IdempotentResponse(
                status=201,
                body=response_body,
                location=f"/api/v1/branches/{branch.id}",
                resource_kind="branch",
                resource_id=branch.id,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=command,
            authorize_replay=lambda kind, resource_id: service.authorize_branch_replay(
                principal, kind, resource_id
            ),
            mutation=mutate,
        )

    outcome = await executor.execute(claims=claims, principal=principal, operation=operation)
    headers = {"Cache-Control": "no-store"}
    if outcome.location is not None:
        headers["Location"] = outcome.location
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


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


@router.patch(
    "/branches/{branch_id}",
    response_model=DataResponse[BranchAdminResponse],
    operation_id="update_branch",
    responses={
        **success_response_documentation(200, "Updated branch", cache_control="no-store"),
        **ORGANIZATION_ERRORS,
    },
)
async def update_branch(
    request: Request,
    body: BranchUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
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
        return await _service(request, connection).update_branch(principal, path_branch_id, body)

    data = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return DataResponse(data=data)


@router.delete(
    "/branches/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="delete_branch",
    responses={
        **success_response_documentation(204, "Deleted branch"),
        **ORGANIZATION_ERRORS,
    },
)
async def delete_branch(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    branch_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
    expected_updated_at: DeleteExpected,
) -> Response:
    if not _CANONICAL_UUID.fullmatch(branch_id):
        raise api_error("validation_failed")
    path_branch_id = uuid.UUID(branch_id)
    if path_branch_id != selected_branch_id:
        raise resource_not_found_error()
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> None:
        await _service(request, connection).delete_branch(
            principal, path_branch_id, expected_updated_at
        )

    await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})
