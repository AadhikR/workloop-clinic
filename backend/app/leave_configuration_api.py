from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.models.identity import AppRole
from app.schemas.leave_configuration import (
    LeaveSettingsRequest,
    LeaveSettingsResponse,
    LeaveTypeRequest,
    LeaveTypeResponse,
    PublicHolidayRequest,
    PublicHolidayResponse,
    SeedHolidaysRequest,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.leave_configuration import LeaveConfigurationService

router = APIRouter(prefix="/api/v1/leave", tags=["leave-configuration"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "request_too_large",
    "unsupported_media_type",
    "validation_failed",
    "invalid_branch",
    "branch_required",
    "state_conflict",
    "branch_conflict",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> LeaveConfigurationService:
    return LeaveConfigurationService(connection)


def _branch(principal: AuthorizationPrincipal, selected: uuid.UUID | None) -> uuid.UUID:
    if principal.role is AppRole.ADMIN:
        assert selected is not None
        return selected
    if principal.branch_id is None:
        raise RuntimeError("staff principal has no branch")
    return principal.branch_id


async def _selected_branch(
    principal: AuthenticatedReadPrincipal,
    header: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> uuid.UUID | None:
    if principal.role is not AppRole.ADMIN:
        if header is not None:
            raise api_error("operation_not_permitted")
        return principal.branch_id
    if header is None:
        raise api_error("branch_required")
    try:
        branch_id = uuid.UUID(header)
    except ValueError:
        raise api_error("invalid_branch") from None
    if str(branch_id) != header:
        raise api_error("invalid_branch")
    return branch_id


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


@router.get(
    "/settings",
    response_model=DataResponse[LeaveSettingsResponse],
    operation_id="get_leave_settings",
    responses={**success_response_documentation(200, "Leave settings"), **ERRORS},
)
async def get_settings(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: Annotated[uuid.UUID | None, Depends(_selected_branch)],
) -> DataResponse[LeaveSettingsResponse]:
    branch_id = _branch(principal, selected)
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected if principal.role is AppRole.ADMIN else None,
        operation=lambda connection: _service(request, connection).get_settings(
            principal, branch_id
        ),
    )
    return DataResponse(data=data)


@router.put(
    "/settings",
    response_model=DataResponse[LeaveSettingsResponse],
    operation_id="update_leave_settings",
    responses={**success_response_documentation(200, "Updated leave settings"), **ERRORS},
)
async def update_settings(
    request: Request,
    body: LeaveSettingsRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[LeaveSettingsResponse]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).update_settings(
            principal, selected, body
        ),
    )
    return DataResponse(data=data)


@router.get(
    "/types",
    response_model=CollectionResponse[LeaveTypeResponse],
    operation_id="list_leave_types",
    responses={**success_response_documentation(200, "Leave types"), **ERRORS},
)
async def list_types(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: Annotated[uuid.UUID | None, Depends(_selected_branch)],
) -> CollectionResponse[LeaveTypeResponse]:
    branch_id = _branch(principal, selected)
    active_only = principal.role is not AppRole.ADMIN
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected if principal.role is AppRole.ADMIN else None,
        operation=lambda connection: _service(request, connection).list_types(
            principal, branch_id, active_only=active_only
        ),
    )
    return CollectionResponse(data=data, page=Page(limit=100, next_cursor=None, has_more=False))


@router.post(
    "/types",
    response_model=DataResponse[LeaveTypeResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_leave_type",
    responses={**success_response_documentation(201, "Created leave type"), **ERRORS},
)
async def create_type(
    request: Request,
    body: LeaveTypeRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[LeaveTypeResponse]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).create_type(
            principal, selected, body
        ),
    )
    return DataResponse(data=data)


@router.patch(
    "/types/{type_id}",
    response_model=DataResponse[LeaveTypeResponse],
    operation_id="update_leave_type",
    responses={**success_response_documentation(200, "Updated leave type"), **ERRORS},
)
async def update_type(
    request: Request,
    body: LeaveTypeRequest,
    type_id: uuid.UUID,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[LeaveTypeResponse]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).update_type(
            principal, selected, type_id, body
        ),
    )
    return DataResponse(data=data)


@router.post(
    "/types/seed",
    response_model=DataResponse[list[LeaveTypeResponse]],
    operation_id="seed_leave_types",
    responses={**success_response_documentation(200, "Seeded leave types"), **ERRORS},
)
async def seed_types(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[list[LeaveTypeResponse]]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).seed_types(principal, selected),
    )
    return DataResponse(data=data)


@router.get(
    "/holidays",
    response_model=CollectionResponse[PublicHolidayResponse],
    operation_id="list_public_holidays",
    responses={**success_response_documentation(200, "Public holidays"), **ERRORS},
)
async def list_holidays(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: Annotated[uuid.UUID | None, Depends(_selected_branch)],
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> CollectionResponse[PublicHolidayResponse]:
    branch_id = _branch(principal, selected)
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected if principal.role is AppRole.ADMIN else None,
        operation=lambda connection: _service(request, connection).list_holidays(
            principal, branch_id, year
        ),
    )
    return CollectionResponse(data=data, page=Page(limit=100, next_cursor=None, has_more=False))


@router.post(
    "/holidays",
    response_model=DataResponse[PublicHolidayResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_public_holiday",
    responses={**success_response_documentation(201, "Created public holiday"), **ERRORS},
)
async def create_holiday(
    request: Request,
    body: PublicHolidayRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[PublicHolidayResponse]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).create_holiday(
            principal, selected, body
        ),
    )
    return DataResponse(data=data)


@router.patch(
    "/holidays/{holiday_id}",
    response_model=DataResponse[PublicHolidayResponse],
    operation_id="update_public_holiday",
    responses={**success_response_documentation(200, "Updated public holiday"), **ERRORS},
)
async def update_holiday(
    request: Request,
    body: PublicHolidayRequest,
    holiday_id: uuid.UUID,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[PublicHolidayResponse]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).update_holiday(
            principal, selected, holiday_id, body
        ),
    )
    return DataResponse(data=data)


@router.delete(
    "/holidays/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    operation_id="delete_public_holiday",
    responses={**success_response_documentation(204, "Deleted public holiday"), **ERRORS},
)
async def delete_holiday(
    request: Request,
    holiday_id: uuid.UUID,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> Response:
    await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).delete_holiday(
            principal, selected, holiday_id
        ),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/holidays/seed",
    response_model=DataResponse[list[PublicHolidayResponse]],
    operation_id="seed_public_holidays",
    responses={**success_response_documentation(200, "Seeded public holidays"), **ERRORS},
)
async def seed_holidays(
    request: Request,
    body: SeedHolidaysRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[list[PublicHolidayResponse]]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).seed_holidays(
            principal, selected, body
        ),
    )
    return DataResponse(data=data)
