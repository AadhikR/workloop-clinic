from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Path, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
    operation_not_permitted_error,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.http.validation import parse_pagination, parse_sort, validate_query_parameters
from app.models.identity import AppRole
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.departments import (
    DepartmentCreateRequest,
    DepartmentDeleteRequest,
    DepartmentResponse,
    DepartmentUpdateRequest,
    StaffingRuleCreateRequest,
    StaffingRuleDeleteRequest,
    StaffingRuleResponse,
    StaffingRuleUpdateRequest,
)
from app.services.departments import (
    DepartmentListQuery,
    DepartmentService,
    StaffingRuleListQuery,
    normalize_department,
    normalize_search,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

router = APIRouter(prefix="/api/v1", tags=["departments"])
CANONICAL_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_CANONICAL_UUID = re.compile(CANONICAL_UUID_PATTERN)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DEPARTMENT_ERRORS = error_response_documentation(
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
    "department_conflict",
    "staffing_rule_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> DepartmentService:
    factory = getattr(request.app.state, "department_service_factory", None)
    if factory is not None:
        return cast(DepartmentService, factory(connection))
    return DepartmentService(connection, request.app.state.department_cursor_codec)


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _require_admin(principal: AuthorizationPrincipal) -> None:
    if principal.role is not AppRole.ADMIN:
        raise operation_not_permitted_error()


def _nullable_uuid(value: str | None) -> uuid.UUID | Literal["null"] | None:
    if value is None or value == "null":
        return value
    if not _CANONICAL_UUID.fullmatch(value):
        raise ValueError("invalid UUID")
    return uuid.UUID(value)


def _department_query(request: Request) -> DepartmentListQuery:
    validate_query_parameters(
        request, allowed={"limit", "cursor", "search", "parentId", "headEmployeeId", "sort"}
    )
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        return DepartmentListQuery(
            limit=pagination.limit,
            search=normalize_search(request.query_params.get("search")),
            parent_id=_nullable_uuid(request.query_params.get("parentId")),
            head_employee_id=_nullable_uuid(request.query_params.get("headEmployeeId")),
            sort=parse_sort(
                request.query_params.get("sort"),
                allowed_fields={"sortOrder", "name", "createdAt"},
                default=("sortOrder", "name"),
            ),
            cursor=pagination.cursor,
        )
    except ValueError:
        raise api_error("validation_failed") from None


def _staffing_query(request: Request) -> StaffingRuleListQuery:
    validate_query_parameters(
        request,
        allowed={"limit", "cursor", "department", "shiftCategory", "effectiveOn", "sort"},
    )
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        effective_on_raw = request.query_params.get("effectiveOn")
        effective_on = None
        if effective_on_raw is not None:
            if _DATE.fullmatch(effective_on_raw) is None:
                raise ValueError("invalid date")
            effective_on = date.fromisoformat(effective_on_raw)
        category = request.query_params.get("shiftCategory")
        if category is not None and category not in {"morning", "afternoon", "night", "flexible"}:
            raise ValueError("invalid category")
        return StaffingRuleListQuery(
            limit=pagination.limit,
            department=normalize_department(request.query_params.get("department")),
            shift_category=category,
            effective_on=effective_on,
            sort=parse_sort(
                request.query_params.get("sort"),
                allowed_fields={"department", "shiftCategory", "effectiveFrom", "effectiveTo"},
                default=("department", "shiftCategory"),
            ),
            cursor=pagination.cursor,
        )
    except ValueError:
        raise api_error("validation_failed") from None


DepartmentQuery = Annotated[DepartmentListQuery, Depends(_department_query)]
StaffingQuery = Annotated[StaffingRuleListQuery, Depends(_staffing_query)]


def _path_id(value: str) -> uuid.UUID:
    if not _CANONICAL_UUID.fullmatch(value):
        raise api_error("validation_failed")
    return uuid.UUID(value)


@router.get(
    "/departments",
    response_model=CollectionResponse[DepartmentResponse],
    operation_id="list_departments",
    responses={
        **success_response_documentation(
            200, "Selected branch departments", cache_control="no-store"
        ),
        **DEPARTMENT_ERRORS,
    },
)
async def list_departments(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    query: DepartmentQuery,
) -> CollectionResponse[DepartmentResponse]:
    _require_admin(principal)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> tuple[list[DepartmentResponse], str | None]:
        return await _service(request, connection).list_departments(
            principal, selected_branch_id, query
        )

    items, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.post(
    "/departments",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[DepartmentResponse],
    operation_id="create_department",
    responses={
        **success_response_documentation(201, "Created department", cache_control="no-store"),
        **DEPARTMENT_ERRORS,
    },
)
async def create_department(
    request: Request,
    body: DepartmentCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> Response:
    _require_admin(principal)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> DepartmentResponse:
        return await _service(request, connection).create_department(
            principal, selected_branch_id, body
        )

    item = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return JSONResponse(
        status_code=201,
        content=DataResponse(data=item).model_dump(mode="json", by_alias=True),
        headers={"Cache-Control": "no-store", "Location": f"/api/v1/departments/{item.id}"},
    )


@router.patch(
    "/departments/{department_id}",
    response_model=DataResponse[DepartmentResponse],
    operation_id="update_department",
    responses={
        **success_response_documentation(200, "Updated department", cache_control="no-store"),
        **DEPARTMENT_ERRORS,
    },
)
async def update_department(
    request: Request,
    body: DepartmentUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    department_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> Response:
    _require_admin(principal)
    parsed_id = _path_id(department_id)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    name_supplied = "name" in body.model_fields_set
    key = parse_idempotency_key(request, required=name_supplied)

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutate() -> IdempotentResponse:
            item = await service.update_department(principal, selected_branch_id, parsed_id, body)
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=None,
                resource_kind="department",
                resource_id=item.id,
            )

        if key is None:
            return await mutate()
        route_parameters: dict[str, object] = {"departmentId": str(parsed_id)}
        command = IdempotencyCommand(
            key=key,
            operation_id="update_department",
            method="PATCH",
            route_parameters=route_parameters,
            fingerprint=request_fingerprint(
                operation_id="update_department",
                method="PATCH",
                route_parameters=route_parameters,
                effective_query_parameters={},
                body=body.model_dump(mode="json", by_alias=True),
            ),
            branch_id=selected_branch_id,
        )
        return await _idempotency(request, connection).execute(
            principal=principal,
            command=command,
            authorize_replay=lambda kind, resource_id: service.authorize_department_replay(
                principal, selected_branch_id, kind, resource_id
            ),
            mutation=mutate,
        )

    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    headers = {"Cache-Control": "no-store"}
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


@router.delete(
    "/departments/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="delete_department",
    responses={
        **success_response_documentation(204, "Deleted department"),
        **DEPARTMENT_ERRORS,
    },
)
async def delete_department(
    request: Request,
    body: DepartmentDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    department_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> Response:
    _require_admin(principal)
    parsed_id = _path_id(department_id)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> None:
        await _service(request, connection).delete_department(
            principal, selected_branch_id, parsed_id, body
        )

    await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get(
    "/department-staffing-rules",
    response_model=CollectionResponse[StaffingRuleResponse],
    operation_id="list_department_staffing_rules",
    responses={
        **success_response_documentation(
            200, "Selected branch staffing rules", cache_control="no-store"
        ),
        **DEPARTMENT_ERRORS,
    },
)
async def list_staffing_rules(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    query: StaffingQuery,
) -> CollectionResponse[StaffingRuleResponse]:
    _require_admin(principal)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(
        connection: AsyncConnection,
    ) -> tuple[list[StaffingRuleResponse], str | None]:
        return await _service(request, connection).list_staffing_rules(
            principal, selected_branch_id, query
        )

    items, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.post(
    "/department-staffing-rules",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[StaffingRuleResponse],
    operation_id="create_department_staffing_rule",
    responses={
        **success_response_documentation(201, "Created staffing rule", cache_control="no-store"),
        **DEPARTMENT_ERRORS,
    },
)
async def create_staffing_rule(
    request: Request,
    body: StaffingRuleCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> Response:
    _require_admin(principal)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> StaffingRuleResponse:
        return await _service(request, connection).create_staffing_rule(
            principal, selected_branch_id, body
        )

    item = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return JSONResponse(
        status_code=201,
        content=DataResponse(data=item).model_dump(mode="json", by_alias=True),
        headers={
            "Cache-Control": "no-store",
            "Location": f"/api/v1/department-staffing-rules/{item.id}",
        },
    )


@router.patch(
    "/department-staffing-rules/{rule_id}",
    response_model=DataResponse[StaffingRuleResponse],
    operation_id="update_department_staffing_rule",
    responses={
        **success_response_documentation(200, "Updated staffing rule", cache_control="no-store"),
        **DEPARTMENT_ERRORS,
    },
)
async def update_staffing_rule(
    request: Request,
    body: StaffingRuleUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    rule_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> DataResponse[StaffingRuleResponse]:
    _require_admin(principal)
    parsed_id = _path_id(rule_id)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> StaffingRuleResponse:
        return await _service(request, connection).update_staffing_rule(
            principal, selected_branch_id, parsed_id, body
        )

    item = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return DataResponse(data=item)


@router.delete(
    "/department-staffing-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="delete_department_staffing_rule",
    responses={
        **success_response_documentation(204, "Deleted staffing rule"),
        **DEPARTMENT_ERRORS,
    },
)
async def delete_staffing_rule(
    request: Request,
    body: StaffingRuleDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    rule_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> Response:
    _require_admin(principal)
    parsed_id = _path_id(rule_id)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> None:
        await _service(request, connection).delete_staffing_rule(
            principal, selected_branch_id, parsed_id, body
        )

    await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
