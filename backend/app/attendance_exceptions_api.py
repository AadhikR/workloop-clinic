from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, Literal, Protocol, cast

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.http.validation import parse_pagination, validate_query_parameters
from app.repositories.attendance_exceptions import SqlAttendanceExceptionRepository
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.attendance_exceptions import (
    AbsenceResolutionRequest,
    AttendanceAuditResponse,
    OvertimeApprovalRequest,
    RegularisationDecisionRequest,
    RegularisationResponse,
    RegularisationSubmitRequest,
)
from app.services.attendance_exceptions import (
    AttendanceAuditListQuery,
    AttendanceExceptionService,
    RegularisationListQuery,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

router = APIRouter(prefix="/api/v1", tags=["attendance-exceptions"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "validation_failed",
    "invalid_branch",
    "state_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "invalid_cursor",
    "request_timeout",
    "internal_error",
)


class ResourceResponse(Protocol):
    id: uuid.UUID


def _service(request: Request, connection: AsyncConnection) -> AttendanceExceptionService:
    factory = getattr(request.app.state, "attendance_exception_service_factory", None)
    if factory is not None:
        return cast(AttendanceExceptionService, factory(connection))
    return AttendanceExceptionService(
        SqlAttendanceExceptionRepository(connection),
        request.app.state.attendance_calculation_cursor_codec,
    )


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


async def _mutation_response(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: uuid.UUID,
    operation_id: str,
    route_parameters: dict[str, object],
    body: BaseModel,
    status_code: int,
    resource_kind: str,
    mutate: Callable[[AttendanceExceptionService], Awaitable[ResourceResponse]],
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutation() -> IdempotentResponse:
            item = await mutate(service)
            resource_id = item.id
            location = (
                f"/api/v1/attendance/regularisations/{resource_id}"
                if resource_kind == "regularisation_request"
                else f"/api/v1/attendance-records/{resource_id}"
            )
            return IdempotentResponse(
                status=status_code,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=location,
                resource_kind=resource_kind,
                resource_id=resource_id,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id=operation_id,
                method=request.method,
                route_parameters=route_parameters,
                fingerprint=request_fingerprint(
                    operation_id=operation_id,
                    method=request.method,
                    route_parameters=route_parameters,
                    effective_query_parameters={},
                    body=body.model_dump(mode="json", by_alias=True),
                ),
                branch_id=branch_id,
            ),
            authorize_replay=lambda kind, resource_id: service.authorize_replay(
                principal, kind, resource_id
            ),
            mutation=mutation,
        )

    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id if principal.employee_id is None else None,
        operation=operation,
    )
    return JSONResponse(
        outcome.body,
        status_code=outcome.status,
        headers={
            "Cache-Control": "no-store",
            **({"Location": outcome.location} if outcome.location else {}),
            **({"Idempotency-Replayed": "true"} if outcome.replayed else {}),
        },
    )


def _date(value: str | None) -> date | None:
    return None if value is None else date.fromisoformat(value)


def _employee(value: str | None) -> uuid.UUID | None:
    if value is None:
        return None
    parsed = uuid.UUID(value)
    if str(parsed) != value:
        raise ValueError
    return parsed


def _regularisation_query(
    request: Request, *, allow_employee: bool, default_pending: bool
) -> RegularisationListQuery:
    allowed = {"status", "from", "to", "limit", "cursor"}
    if allow_employee:
        allowed.add("employeeId")
    validate_query_parameters(request, allowed=allowed)
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        raw_status = request.query_params.get("status")
        if raw_status is None and default_pending:
            raw_status = "Pending"
        if raw_status not in {None, "Pending", "Approved", "Rejected"}:
            raise ValueError
        from_date = _date(request.query_params.get("from"))
        to_date = _date(request.query_params.get("to"))
        if from_date is not None and to_date is not None and from_date > to_date:
            raise ValueError
        return RegularisationListQuery(
            employee_id=_employee(request.query_params.get("employeeId")),
            status=cast(Literal["Pending", "Approved", "Rejected"] | None, raw_status),
            from_date=from_date,
            to_date=to_date,
            limit=page.limit,
            cursor=page.cursor,
        )
    except (TypeError, ValueError):
        raise api_error("validation_failed") from None


def _personal_query(request: Request) -> RegularisationListQuery:
    return _regularisation_query(request, allow_employee=False, default_pending=False)


def _queue_query(request: Request) -> RegularisationListQuery:
    return _regularisation_query(request, allow_employee=True, default_pending=True)


def _audit_query(request: Request) -> AttendanceAuditListQuery:
    validate_query_parameters(
        request, allowed={"employeeId", "action", "from", "to", "limit", "cursor"}
    )
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        action = request.query_params.get("action")
        if action not in {
            None,
            "REGULARISATION_APPROVED",
            "REGULARISATION_REJECTED",
            "ABSENCE_RESOLVED",
            "OVERTIME_APPROVED",
        }:
            raise ValueError
        from_date = _date(request.query_params.get("from"))
        to_date = _date(request.query_params.get("to"))
        if from_date is not None and to_date is not None and from_date > to_date:
            raise ValueError
        return AttendanceAuditListQuery(
            employee_id=_employee(request.query_params.get("employeeId")),
            action=action,
            from_date=from_date,
            to_date=to_date,
            limit=page.limit,
            cursor=page.cursor,
        )
    except (TypeError, ValueError):
        raise api_error("validation_failed") from None


PersonalRegularisationQuery = Annotated[RegularisationListQuery, Depends(_personal_query)]
AdminRegularisationQuery = Annotated[RegularisationListQuery, Depends(_queue_query)]
AuditQuery = Annotated[AttendanceAuditListQuery, Depends(_audit_query)]


@router.get(
    "/attendance/regularisations/me",
    response_model=CollectionResponse[RegularisationResponse],
    responses={
        **success_response_documentation(
            200, "Personal correction history", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def personal_regularisations(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    query: PersonalRegularisationQuery,
) -> CollectionResponse[RegularisationResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).personal(principal, query),
    )
    return CollectionResponse(
        data=data,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.post(
    "/attendance/regularisations",
    response_model=None,
    responses={
        **success_response_documentation(201, "Correction submitted", cache_control="no-store"),
        **ERRORS,
    },
)
async def submit_regularisation(
    request: Request,
    body: RegularisationSubmitRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    return await _mutation_response(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=principal.branch_id,
        operation_id="submit_attendance_regularisation",
        route_parameters={},
        body=body,
        status_code=201,
        resource_kind="regularisation_request",
        mutate=lambda service: service.submit(principal, body),
    )


@router.get(
    "/attendance/regularisations",
    response_model=CollectionResponse[RegularisationResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch correction queue", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def regularisation_queue(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
    query: AdminRegularisationQuery,
) -> CollectionResponse[RegularisationResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).queue(
            principal, branch_id, query
        ),
    )
    return CollectionResponse(
        data=data,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.post(
    "/attendance/regularisations/{request_id}/{action}",
    response_model=None,
    responses={
        **success_response_documentation(
            200, "Correction decision recorded", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def decide_regularisation(
    request: Request,
    request_id: Annotated[uuid.UUID, Path()],
    action: str,
    body: RegularisationDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    if action not in {"approve", "reject"}:
        raise api_error("resource_not_found")
    return await _mutation_response(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id=f"{action}_attendance_regularisation",
        route_parameters={"requestId": str(request_id)},
        body=body,
        status_code=200,
        resource_kind="regularisation_request",
        mutate=lambda service: service.decide(principal, branch_id, request_id, action, body),
    )


@router.post(
    "/attendance-records/{record_id}/absence-resolution",
    response_model=None,
    responses={
        **success_response_documentation(200, "Absence resolved", cache_control="no-store"),
        **ERRORS,
    },
)
async def resolve_absence(
    request: Request,
    record_id: Annotated[uuid.UUID, Path()],
    body: AbsenceResolutionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    return await _mutation_response(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="resolve_attendance_absence",
        route_parameters={"recordId": str(record_id)},
        body=body,
        status_code=200,
        resource_kind="attendance_record",
        mutate=lambda service: service.resolve_absence(principal, branch_id, record_id, body),
    )


@router.post(
    "/attendance-records/{record_id}/overtime-approval",
    response_model=None,
    responses={
        **success_response_documentation(200, "Overtime approved", cache_control="no-store"),
        **ERRORS,
    },
)
async def approve_overtime(
    request: Request,
    record_id: Annotated[uuid.UUID, Path()],
    body: OvertimeApprovalRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    return await _mutation_response(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="approve_attendance_overtime",
        route_parameters={"recordId": str(record_id)},
        body=body,
        status_code=200,
        resource_kind="attendance_record",
        mutate=lambda service: service.approve_overtime(principal, branch_id, record_id, body),
    )


@router.get(
    "/attendance/audit",
    response_model=CollectionResponse[AttendanceAuditResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch attendance audit", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def attendance_audit(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
    query: AuditQuery,
) -> CollectionResponse[AttendanceAuditResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).audit(
            principal, branch_id, query
        ),
    )
    return CollectionResponse(
        data=data,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )
