from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    StaffAuthorizationPrincipal,
    VerifiedAccessToken,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.http.validation import parse_pagination, validate_query_parameters
from app.schemas.leave_balance import (
    LeaveBalanceResponse,
    LeaveBalanceYearRequest,
    LeaveRequestResponse,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.leave_balance_service import (
    BalanceListQuery,
    LeaveBalanceService,
    RequestCalendarQuery,
)

router = APIRouter(prefix="/api/v1/leave", tags=["leave-balances"])
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
    "invalid_cursor",
    "branch_conflict",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)
STATUSES = {
    "Pending",
    "ManagerApproved",
    "ManagerRejected",
    "Approved",
    "Rejected",
    "Cancelled",
}


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> LeaveBalanceService:
    return LeaveBalanceService(connection, request.app.state.leave_balance_cursor_codec)


def _uuid_parameter(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise ValueError("invalid UUID") from None
    if str(parsed) != value:
        raise ValueError("invalid UUID")
    return parsed


def _year(value: str | None) -> int:
    if value is None or not value.isascii() or len(value) != 4 or not value.isdigit():
        raise ValueError("invalid year")
    year = int(value)
    if not 2000 <= year <= 2100:
        raise ValueError("invalid year")
    return year


def _balance_query(request: Request) -> BalanceListQuery:
    validate_query_parameters(
        request, allowed={"limit", "cursor", "year", "employeeId", "leaveTypeId"}
    )
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"),
            cursor=request.query_params.get("cursor"),
        )
        return BalanceListQuery(
            limit=pagination.limit,
            leave_year=_year(request.query_params.get("year")),
            employee_id=_uuid_parameter(request.query_params.get("employeeId")),
            leave_type_id=_uuid_parameter(request.query_params.get("leaveTypeId")),
            cursor=pagination.cursor,
        )
    except ValueError:
        raise api_error("validation_failed") from None


def _request_query(request: Request) -> RequestCalendarQuery:
    validate_query_parameters(
        request,
        allowed={"limit", "cursor", "year", "employeeId", "leaveTypeId", "status"},
    )
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"),
            cursor=request.query_params.get("cursor"),
        )
        raw_status = request.query_params.get("status")
        if raw_status is not None and raw_status not in STATUSES:
            raise ValueError("invalid status")
        status: (
            Literal[
                "Pending",
                "ManagerApproved",
                "ManagerRejected",
                "Approved",
                "Rejected",
                "Cancelled",
            ]
            | None
        ) = raw_status  # pyright: ignore[reportAssignmentType]
        return RequestCalendarQuery(
            limit=pagination.limit,
            leave_year=_year(request.query_params.get("year")),
            employee_id=_uuid_parameter(request.query_params.get("employeeId")),
            leave_type_id=_uuid_parameter(request.query_params.get("leaveTypeId")),
            status=status,
            cursor=pagination.cursor,
        )
    except ValueError:
        raise api_error("validation_failed") from None


BalanceQuery = Annotated[BalanceListQuery, Depends(_balance_query)]
CalendarQuery = Annotated[RequestCalendarQuery, Depends(_request_query)]


def _self_balance_query(request: Request) -> BalanceListQuery:
    query = _balance_query(request)
    if query.employee_id is not None:
        raise api_error("validation_failed")
    return query


def _self_request_query(request: Request) -> RequestCalendarQuery:
    query = _request_query(request)
    if query.employee_id is not None:
        raise api_error("validation_failed")
    return query


def _approver_balance_query(request: Request) -> BalanceListQuery:
    query = _balance_query(request)
    if query.employee_id is None:
        raise api_error("validation_failed")
    return query


SelfBalanceQuery = Annotated[BalanceListQuery, Depends(_self_balance_query)]
SelfCalendarQuery = Annotated[RequestCalendarQuery, Depends(_self_request_query)]
ApproverBalanceQuery = Annotated[BalanceListQuery, Depends(_approver_balance_query)]


def _collection[ResponseType: (LeaveBalanceResponse, LeaveRequestResponse)](
    data: list[ResponseType], next_cursor: str | None, limit: int
) -> CollectionResponse[ResponseType]:
    return CollectionResponse(
        data=data,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/balances/self",
    response_model=CollectionResponse[LeaveBalanceResponse],
    operation_id="get_employee_leave_balances",
    responses={**success_response_documentation(200, "Employee leave balances"), **ERRORS},
)
async def employee_balances(
    request: Request,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
    query: SelfBalanceQuery,
) -> CollectionResponse[LeaveBalanceResponse]:
    data, cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_self_balances(
            principal, query
        ),
    )
    return _collection(data, cursor, query.limit)


@router.get(
    "/requests/calendar/self",
    response_model=CollectionResponse[LeaveRequestResponse],
    operation_id="get_employee_leave_request_calendar",
    responses={**success_response_documentation(200, "Employee leave request calendar"), **ERRORS},
)
async def employee_request_calendar(
    request: Request,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
    query: SelfCalendarQuery,
) -> CollectionResponse[LeaveRequestResponse]:
    data, cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_self_requests(
            principal, query
        ),
    )
    return _collection(data, cursor, query.limit)


@router.get(
    "/balances/branch",
    response_model=CollectionResponse[LeaveBalanceResponse],
    operation_id="get_admin_leave_balances",
    responses={**success_response_documentation(200, "Branch leave balances"), **ERRORS},
)
async def admin_balances(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    query: BalanceQuery,
) -> CollectionResponse[LeaveBalanceResponse]:
    data, cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_admin_balances(
            principal, selected, query
        ),
    )
    return _collection(data, cursor, query.limit)


@router.get(
    "/requests/calendar/branch",
    response_model=CollectionResponse[LeaveRequestResponse],
    operation_id="get_admin_leave_request_calendar",
    responses={**success_response_documentation(200, "Branch leave request calendar"), **ERRORS},
)
async def admin_request_calendar(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    query: CalendarQuery,
) -> CollectionResponse[LeaveRequestResponse]:
    data, cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_admin_requests(
            principal, selected, query
        ),
    )
    return _collection(data, cursor, query.limit)


@router.get(
    "/balances/approver",
    response_model=CollectionResponse[LeaveBalanceResponse],
    operation_id="get_approver_leave_balances",
    responses={**success_response_documentation(200, "Approver leave balances"), **ERRORS},
)
async def approver_balances(
    request: Request,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
    query: ApproverBalanceQuery,
) -> CollectionResponse[LeaveBalanceResponse]:
    data, cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_approver_balances(
            principal, query
        ),
    )
    return _collection(data, cursor, query.limit)


@router.post(
    "/balances/initialize",
    response_model=DataResponse[list[LeaveBalanceResponse]],
    operation_id="initialize_leave_balances",
    responses={**success_response_documentation(200, "Initialized leave balances"), **ERRORS},
)
async def initialize_balances(
    request: Request,
    body: LeaveBalanceYearRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[list[LeaveBalanceResponse]]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).initialize(
            principal, selected, body.leave_year
        ),
    )
    return DataResponse(data=data)


@router.post(
    "/balances/recalculate",
    response_model=DataResponse[list[LeaveBalanceResponse]],
    operation_id="recalculate_leave_balances",
    responses={**success_response_documentation(200, "Recalculated leave balances"), **ERRORS},
)
async def recalculate_balances(
    request: Request,
    body: LeaveBalanceYearRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[list[LeaveBalanceResponse]]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).recalculate(
            principal, selected, body.leave_year
        ),
    )
    return DataResponse(data=data)
