from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Path, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    VerifiedAccessToken,
    operation_not_permitted_error,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.http.validation import parse_pagination, parse_sort, validate_query_parameters
from app.models.identity import AppRole
from app.schemas.employees import (
    DirectReportResponse,
    EmployeeAdminDetailResponse,
    EmployeeAdminListResponse,
    EmployeeJobHistoryResponse,
    EmployeeSelfResponse,
)
from app.services.employees import (
    DirectReportQuery,
    EmployeeListQuery,
    EmployeeService,
    JobHistoryQuery,
    database_employment_status,
    normalize_filter_text,
    normalize_search,
)
from app.services.execution import AuthorizedServiceExecutor

router = APIRouter(prefix="/api/v1", tags=["employees"])
CANONICAL_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
_CANONICAL_UUID = re.compile(CANONICAL_UUID_PATTERN)
_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

EMPLOYEE_ERRORS = error_response_documentation(
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
    "branch_required",
    "invalid_branch",
    "invalid_cursor",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> EmployeeService:
    factory = getattr(request.app.state, "employee_service_factory", None)
    if factory is not None:
        return cast(EmployeeService, factory(connection))
    return EmployeeService(connection, request.app.state.employee_cursor_codec)


def _reject_branch_header(request: Request) -> None:
    if request.headers.getlist("x-workloop-branch-id"):
        raise operation_not_permitted_error()


def _require_role(principal: AuthorizationPrincipal, *roles: AppRole) -> None:
    if principal.role not in roles:
        raise operation_not_permitted_error()


def _validation_error() -> Exception:
    return api_error(
        "validation_failed",
        details=[
            {
                "path": "query",
                "code": "invalid_format",
                "message": "Query value has an invalid format",
            }
        ],
    )


def _uuid(
    value: str | None, *, nullable_literal: bool = False
) -> uuid.UUID | Literal["null"] | None:
    if value is None:
        return None
    if nullable_literal and value == "null":
        return "null"
    if _CANONICAL_UUID.fullmatch(value) is None:
        raise ValueError("invalid UUID")
    return uuid.UUID(value)


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError("invalid boolean")


def _instant(value: str | None) -> datetime | None:
    if value is None:
        return None
    if _INSTANT.fullmatch(value) is None:
        raise ValueError("invalid instant")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _employee_query(request: Request) -> EmployeeListQuery:
    validate_query_parameters(
        request,
        allowed={
            "limit",
            "cursor",
            "search",
            "employmentStatus",
            "department",
            "active",
            "reportingManagerId",
            "sort",
        },
    )
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        search = normalize_search(request.query_params.get("search"))
        status = database_employment_status(request.query_params.get("employmentStatus"))
        department = normalize_filter_text(request.query_params.get("department"))
        active = _bool(request.query_params.get("active"))
        manager_id = _uuid(request.query_params.get("reportingManagerId"), nullable_literal=True)
        sort = parse_sort(
            request.query_params.get("sort"),
            allowed_fields={
                "name",
                "empNo",
                "employmentStartDate",
                "basicSalary",
                "createdAt",
                "updatedAt",
            },
            default=("name",),
        )
    except ValueError:
        raise _validation_error() from None
    return EmployeeListQuery(
        limit=pagination.limit,
        search=search,
        employment_status=status,
        department=department,
        active=active,
        reporting_manager_id=manager_id,
        sort=sort,
        cursor=pagination.cursor,
    )


EmployeeQuery = Annotated[EmployeeListQuery, Depends(_employee_query)]


def _direct_report_query(request: Request) -> DirectReportQuery:
    validate_query_parameters(
        request, allowed={"limit", "cursor", "search", "employmentStatus", "sort"}
    )
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        search = normalize_search(request.query_params.get("search"))
        status = database_employment_status(request.query_params.get("employmentStatus"))
        sort = parse_sort(
            request.query_params.get("sort"),
            allowed_fields={"name", "empNo", "employmentStartDate"},
            default=("name",),
        )
    except ValueError:
        raise _validation_error() from None
    return DirectReportQuery(
        limit=pagination.limit,
        search=search,
        employment_status=status,
        sort=sort,
        cursor=pagination.cursor,
    )


DirectReportsQuery = Annotated[DirectReportQuery, Depends(_direct_report_query)]


def _job_history_query(request: Request, *, path_scoped: bool = False) -> JobHistoryQuery:
    allowed = {"limit", "cursor", "sort"}
    if not path_scoped:
        allowed.update({"employeeId", "changeType", "changedFrom", "changedTo"})
    validate_query_parameters(request, allowed=allowed)
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        sort = parse_sort(
            request.query_params.get("sort"), allowed_fields={"changedAt"}, default=("-changedAt",)
        )
        employee_id = None if path_scoped else _uuid(request.query_params.get("employeeId"))
        change_type = None if path_scoped else request.query_params.get("changeType")
        if change_type not in {
            None,
            "title_change",
            "department_change",
            "salary_change",
            "status_change",
        }:
            raise ValueError("invalid change type")
        changed_from = None if path_scoped else _instant(request.query_params.get("changedFrom"))
        changed_to = None if path_scoped else _instant(request.query_params.get("changedTo"))
        if changed_from is not None and changed_to is not None and changed_from > changed_to:
            raise ValueError("invalid changed range")
    except ValueError:
        raise _validation_error() from None
    return JobHistoryQuery(
        limit=pagination.limit,
        employee_id=cast(uuid.UUID | None, employee_id),
        change_type=change_type,
        changed_from=changed_from,
        changed_to=changed_to,
        descending=sort[0][1],
        cursor=pagination.cursor,
    )


def _branch_job_history_query(request: Request) -> JobHistoryQuery:
    return _job_history_query(request)


def _employee_job_history_query(request: Request) -> JobHistoryQuery:
    return _job_history_query(request, path_scoped=True)


BranchJobHistoryQuery = Annotated[JobHistoryQuery, Depends(_branch_job_history_query)]
EmployeeJobHistoryQuery = Annotated[JobHistoryQuery, Depends(_employee_job_history_query)]
EmployeeId = Annotated[
    str,
    Path(pattern=CANONICAL_UUID_PATTERN, description="Canonical lowercase employee UUID"),
]


@router.get(
    "/employees/self",
    response_model=DataResponse[EmployeeSelfResponse],
    operation_id="get_employee_self",
    responses={
        **success_response_documentation(200, "Current employee", cache_control="no-store"),
        **EMPLOYEE_ERRORS,
    },
)
async def get_employee_self(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[EmployeeSelfResponse]:
    validate_query_parameters(request, allowed=set())
    _reject_branch_header(request)
    _require_role(principal, AppRole.MANAGER, AppRole.EMPLOYEE)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> EmployeeSelfResponse:
        return await _service(request, connection).get_self(principal)

    return DataResponse(
        data=await executor.execute(claims=claims, principal=principal, operation=operation)
    )


@router.get(
    "/employees/direct-reports",
    response_model=CollectionResponse[DirectReportResponse],
    operation_id="list_direct_reports",
    responses={
        **success_response_documentation(200, "Current direct reports", cache_control="no-store"),
        **EMPLOYEE_ERRORS,
    },
)
async def list_direct_reports(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    query: DirectReportsQuery,
) -> CollectionResponse[DirectReportResponse]:
    _reject_branch_header(request)
    _require_role(principal, AppRole.MANAGER)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(
        connection: AsyncConnection,
    ) -> tuple[list[DirectReportResponse], str | None]:
        return await _service(request, connection).list_direct_reports(principal, query)

    items, next_cursor = await executor.execute(
        claims=claims, principal=principal, operation=operation
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=query.limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/employees",
    response_model=CollectionResponse[EmployeeAdminListResponse],
    operation_id="list_employees",
    responses={
        **success_response_documentation(
            200, "Selected branch employees", cache_control="no-store"
        ),
        **EMPLOYEE_ERRORS,
    },
)
async def list_employees(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    query: EmployeeQuery,
) -> CollectionResponse[EmployeeAdminListResponse]:
    _require_role(principal, AppRole.ADMIN)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(
        connection: AsyncConnection,
    ) -> tuple[list[EmployeeAdminListResponse], str | None]:
        return await _service(request, connection).list_employees(
            principal, selected_branch_id, query
        )

    items, next_cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=query.limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/employee-job-history",
    response_model=CollectionResponse[EmployeeJobHistoryResponse],
    operation_id="list_employee_job_history",
    responses={
        **success_response_documentation(
            200, "Selected branch job history", cache_control="no-store"
        ),
        **EMPLOYEE_ERRORS,
    },
)
async def list_employee_job_history(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    query: BranchJobHistoryQuery,
) -> CollectionResponse[EmployeeJobHistoryResponse]:
    _require_role(principal, AppRole.ADMIN)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(
        connection: AsyncConnection,
    ) -> tuple[list[EmployeeJobHistoryResponse], str | None]:
        return await _service(request, connection).list_job_history(
            principal, selected_branch_id, query
        )

    items, next_cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=query.limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/employees/{employee_id}/job-history",
    response_model=CollectionResponse[EmployeeJobHistoryResponse],
    operation_id="list_one_employee_job_history",
    responses={
        **success_response_documentation(200, "Employee job history", cache_control="no-store"),
        **EMPLOYEE_ERRORS,
    },
)
async def list_one_employee_job_history(
    request: Request,
    employee_id: EmployeeId,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    query: EmployeeJobHistoryQuery,
) -> CollectionResponse[EmployeeJobHistoryResponse]:
    _require_role(principal, AppRole.ADMIN)
    parsed_employee_id = uuid.UUID(employee_id)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(
        connection: AsyncConnection,
    ) -> tuple[list[EmployeeJobHistoryResponse], str | None]:
        return await _service(request, connection).list_job_history(
            principal, selected_branch_id, query, path_employee_id=parsed_employee_id
        )

    items, next_cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=query.limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/employees/{employee_id}",
    response_model=DataResponse[EmployeeAdminDetailResponse],
    operation_id="get_employee",
    responses={
        **success_response_documentation(200, "Selected branch employee", cache_control="no-store"),
        **EMPLOYEE_ERRORS,
    },
)
async def get_employee(
    request: Request,
    employee_id: EmployeeId,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> DataResponse[EmployeeAdminDetailResponse]:
    validate_query_parameters(request, allowed=set())
    _require_role(principal, AppRole.ADMIN)
    parsed_employee_id = uuid.UUID(employee_id)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> EmployeeAdminDetailResponse:
        return await _service(request, connection).get_employee(
            principal, selected_branch_id, parsed_employee_id
        )

    data = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    return DataResponse(data=data)
