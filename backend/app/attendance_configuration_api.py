from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Any, Protocol, cast

from fastapi import APIRouter, Depends, Path, Request, Response
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
from app.http.validation import parse_pagination, validate_query_parameters
from app.models.identity import AppRole
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.attendance_configuration import (
    AttendanceSettingsResponse,
    AttendanceSettingsUpdateRequest,
    ShiftAssignmentCreateRequest,
    ShiftAssignmentResponse,
    ShiftCreateRequest,
    ShiftDeactivateRequest,
    ShiftResponse,
    ShiftUpdateRequest,
)
from app.services.attendance_configuration import (
    AssignmentListQuery,
    AttendanceConfigurationService,
    ShiftListQuery,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

router = APIRouter(prefix="/api/v1", tags=["attendance-configuration"])
CANONICAL_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_UUID = re.compile(CANONICAL_UUID_PATTERN)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ERRORS = error_response_documentation(
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
    "attendance_configuration_conflict",
    "shift_conflict",
    "retained_shift",
    "shift_assignment_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> AttendanceConfigurationService:
    factory = getattr(request.app.state, "attendance_configuration_service_factory", None)
    if factory is not None:
        return cast(AttendanceConfigurationService, factory(connection))
    return AttendanceConfigurationService(
        connection, request.app.state.attendance_configuration_cursor_codec
    )


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _require_admin(principal: AuthorizationPrincipal) -> None:
    if principal.role is not AppRole.ADMIN:
        raise operation_not_permitted_error()


def _uuid(value: str) -> uuid.UUID:
    if not _UUID.fullmatch(value):
        raise api_error("validation_failed")
    return uuid.UUID(value)


def _boolean(value: str | None) -> bool | None:
    if value is None:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("invalid boolean")


def _shift_query(request: Request) -> ShiftListQuery:
    validate_query_parameters(
        request, allowed={"limit", "cursor", "active", "shiftType", "shiftCategory", "search"}
    )
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        shift_type = request.query_params.get("shiftType")
        category = request.query_params.get("shiftCategory")
        if shift_type is not None and shift_type not in {"fixed", "flexible", "split", "overnight"}:
            raise ValueError
        if category is not None and category not in {
            "morning",
            "afternoon",
            "night",
            "flexible",
            "split",
        }:
            raise ValueError
        search = request.query_params.get("search")
        if search is not None:
            search = search.strip()
            if not 1 <= len(search) <= 100:
                raise ValueError
        return ShiftListQuery(
            page.limit,
            _boolean(request.query_params.get("active")),
            shift_type,
            category,
            search,
            page.cursor,
        )
    except ValueError:
        raise api_error("validation_failed") from None


def _assignment_query(request: Request) -> AssignmentListQuery:
    validate_query_parameters(request, allowed={"limit", "cursor", "employeeId", "effectiveOn"})
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        employee = request.query_params.get("employeeId")
        if employee is None or not _UUID.fullmatch(employee):
            raise ValueError
        effective_raw = request.query_params.get("effectiveOn")
        if effective_raw is not None and not _DATE.fullmatch(effective_raw):
            raise ValueError
        return AssignmentListQuery(
            page.limit,
            uuid.UUID(employee),
            None if effective_raw is None else date.fromisoformat(effective_raw),
            page.cursor,
        )
    except ValueError:
        raise api_error("validation_failed") from None


ShiftQuery = Annotated[ShiftListQuery, Depends(_shift_query)]
AssignmentQuery = Annotated[AssignmentListQuery, Depends(_assignment_query)]


class ResourceResponse(Protocol):
    id: uuid.UUID


async def _mutation(
    request: Request,
    connection: AsyncConnection,
    *,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    key: uuid.UUID,
    operation_id: str,
    method: str,
    route_parameters: dict[str, object],
    body: object,
    resource_kind: str,
    call: Callable[[AttendanceConfigurationService], Awaitable[ResourceResponse]],
    status_code: int = 200,
    location_prefix: str | None = None,
) -> IdempotentResponse:
    service = _service(request, connection)

    async def mutate() -> IdempotentResponse:
        item = await call(service)
        item_id = item.id
        response_body = DataResponse(data=item).model_dump(mode="json", by_alias=True)
        return IdempotentResponse(
            status=status_code,
            body=response_body,
            location=None if location_prefix is None else f"{location_prefix}/{item_id}",
            resource_kind=resource_kind,
            resource_id=item_id,
        )

    command = IdempotencyCommand(
        key=key,
        operation_id=operation_id,
        method=method,
        route_parameters=route_parameters,
        fingerprint=request_fingerprint(
            operation_id=operation_id,
            method=method,
            route_parameters=route_parameters,
            effective_query_parameters={},
            body=cast(Any, body),
        ),
        branch_id=branch_id,
    )
    return await _idempotency(request, connection).execute(
        principal=principal,
        command=command,
        authorize_replay=lambda kind, resource_id: service.authorize_replay(
            principal, branch_id, kind, resource_id
        ),
        mutation=mutate,
    )


@router.get(
    "/attendance-settings",
    response_model=DataResponse[AttendanceSettingsResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch attendance settings", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def get_attendance_settings(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> DataResponse[AttendanceSettingsResponse]:
    _require_admin(principal)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    item = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _service(request, connection).get_settings(
            principal, selected_branch_id
        ),
    )
    return DataResponse(data=item)


@router.put(
    "/attendance-settings",
    response_model=DataResponse[AttendanceSettingsResponse],
    responses={
        **success_response_documentation(
            200, "Updated attendance settings", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def update_attendance_settings(
    request: Request,
    body: AttendanceSettingsUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> Response:
    _require_admin(principal)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal=principal,
            branch_id=selected_branch_id,
            key=key,
            operation_id="update_attendance_settings",
            method="PUT",
            route_parameters={},
            body=body.model_dump(mode="json", by_alias=True),
            resource_kind="attendance_settings",
            call=lambda service: service.update_settings(principal, selected_branch_id, body),
        ),
    )
    return _response(outcome)


@router.get(
    "/shifts",
    response_model=CollectionResponse[ShiftResponse],
    responses={
        **success_response_documentation(200, "Selected branch shifts", cache_control="no-store"),
        **ERRORS,
    },
)
async def list_shifts(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    query: ShiftQuery,
) -> CollectionResponse[ShiftResponse]:
    _require_admin(principal)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    items, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _service(request, connection).list_shifts(
            principal, selected_branch_id, query
        ),
    )
    return CollectionResponse(
        data=items, page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None)
    )


@router.post(
    "/shifts",
    status_code=201,
    response_model=DataResponse[ShiftResponse],
    responses={
        **success_response_documentation(201, "Created shift", cache_control="no-store"),
        **ERRORS,
    },
)
async def create_shift(
    request: Request,
    body: ShiftCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> Response:
    _require_admin(principal)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal=principal,
            branch_id=selected_branch_id,
            key=key,
            operation_id="create_shift",
            method="POST",
            route_parameters={},
            body=body.model_dump(mode="json", by_alias=True),
            resource_kind="shift",
            call=lambda service: service.create_shift(principal, selected_branch_id, body),
            status_code=201,
            location_prefix="/api/v1/shifts",
        ),
    )
    return _response(outcome)


@router.patch(
    "/shifts/{shift_id}",
    response_model=DataResponse[ShiftResponse],
    responses={
        **success_response_documentation(200, "Updated shift", cache_control="no-store"),
        **ERRORS,
    },
)
async def update_shift(
    request: Request,
    body: ShiftUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    shift_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> Response:
    _require_admin(principal)
    parsed = _uuid(shift_id)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal=principal,
            branch_id=selected_branch_id,
            key=key,
            operation_id="update_shift",
            method="PATCH",
            route_parameters={"shiftId": str(parsed)},
            body=body.model_dump(mode="json", by_alias=True),
            resource_kind="shift",
            call=lambda service: service.update_shift(principal, selected_branch_id, parsed, body),
        ),
    )
    return _response(outcome)


@router.post(
    "/shifts/{shift_id}/deactivate",
    response_model=DataResponse[ShiftResponse],
    responses={
        **success_response_documentation(200, "Deactivated shift", cache_control="no-store"),
        **ERRORS,
    },
)
async def deactivate_shift(
    request: Request,
    body: ShiftDeactivateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    shift_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> Response:
    _require_admin(principal)
    parsed = _uuid(shift_id)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal=principal,
            branch_id=selected_branch_id,
            key=key,
            operation_id="deactivate_shift",
            method="POST",
            route_parameters={"shiftId": str(parsed)},
            body=body.model_dump(mode="json", by_alias=True),
            resource_kind="shift",
            call=lambda service: service.deactivate_shift(
                principal, selected_branch_id, parsed, body.expected_updated_at
            ),
        ),
    )
    return _response(outcome)


@router.get(
    "/shift-assignments",
    response_model=CollectionResponse[ShiftAssignmentResponse],
    responses={
        **success_response_documentation(
            200, "Selected employee shift assignments", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def list_shift_assignments(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    query: AssignmentQuery,
) -> CollectionResponse[ShiftAssignmentResponse]:
    _require_admin(principal)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    items, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _service(request, connection).list_assignments(
            principal, selected_branch_id, query
        ),
    )
    return CollectionResponse(
        data=items, page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None)
    )


@router.post(
    "/shift-assignments",
    status_code=201,
    response_model=DataResponse[ShiftAssignmentResponse],
    responses={
        **success_response_documentation(201, "Created shift assignment", cache_control="no-store"),
        **ERRORS,
    },
)
async def create_shift_assignment(
    request: Request,
    body: ShiftAssignmentCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> Response:
    _require_admin(principal)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal=principal,
            branch_id=selected_branch_id,
            key=key,
            operation_id="create_shift_assignment",
            method="POST",
            route_parameters={},
            body=body.model_dump(mode="json", by_alias=True),
            resource_kind="shift_assignment",
            call=lambda service: service.assign_shift(principal, selected_branch_id, body),
            status_code=201,
            location_prefix="/api/v1/shift-assignments",
        ),
    )
    return _response(outcome)


def _response(outcome: IdempotentResponse) -> Response:
    headers = {"Cache-Control": "no-store"}
    if outcome.location is not None:
        headers["Location"] = outcome.location
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)
