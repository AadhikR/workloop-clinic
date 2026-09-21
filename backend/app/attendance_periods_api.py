from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse
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
from app.repositories.attendance_periods import AttendancePeriodRepository
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.attendance_periods import (
    AttendancePeriodCloseRequest,
    AttendancePeriodResponse,
    validate_period,
)
from app.services.attendance_periods import AttendancePeriodListQuery, AttendancePeriodService
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

router = APIRouter(prefix="/api/v1/attendance/periods", tags=["attendance-periods"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "validation_failed",
    "invalid_branch",
    "state_conflict",
    "attendance_period_not_ready",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "invalid_cursor",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> AttendancePeriodService:
    factory = getattr(request.app.state, "attendance_period_service_factory", None)
    if factory is not None:
        return cast(AttendancePeriodService, factory(connection))
    return AttendancePeriodService(
        AttendancePeriodRepository(connection),
        request.app.state.attendance_calculation_cursor_codec,
    )


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _query(request: Request) -> AttendancePeriodListQuery:
    validate_query_parameters(request, allowed={"limit", "cursor"})
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
    except (TypeError, ValueError):
        raise api_error("validation_failed") from None
    return AttendancePeriodListQuery(limit=page.limit, cursor=page.cursor)


def _period(value: str) -> str:
    try:
        return validate_period(value)
    except ValueError:
        raise api_error("resource_not_found") from None


PeriodQuery = Annotated[AttendancePeriodListQuery, Depends(_query)]


@router.get(
    "",
    response_model=CollectionResponse[AttendancePeriodResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch attendance periods", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def list_periods(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
    query: PeriodQuery,
) -> CollectionResponse[AttendancePeriodResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).list(
            principal, branch_id, query
        ),
    )
    return CollectionResponse(
        data=data,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.get(
    "/{period}",
    response_model=DataResponse[AttendancePeriodResponse],
    responses={
        **success_response_documentation(
            200, "Attendance period readiness", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def period_detail(
    request: Request,
    period: Annotated[str, Path()],
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
) -> DataResponse[AttendancePeriodResponse]:
    validate_query_parameters(request, allowed=set())
    value = _period(period)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).detail(
            principal, branch_id, value
        ),
    )
    return DataResponse(data=data)


@router.post(
    "/{period}/close",
    response_model=None,
    responses={
        **success_response_documentation(200, "Attendance period closed", cache_control="no-store"),
        **ERRORS,
    },
)
async def close_period(
    request: Request,
    period: Annotated[str, Path()],
    body: AttendancePeriodCloseRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    value = _period(period)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutation() -> IdempotentResponse:
            item = await service.close(principal, branch_id, value, body)
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=f"/api/v1/attendance/periods/{value}",
                resource_kind="attendance_period",
                resource_id=item.id,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="close_attendance_period",
                method=request.method,
                route_parameters={"period": value},
                fingerprint=request_fingerprint(
                    operation_id="close_attendance_period",
                    method=request.method,
                    route_parameters={"period": value},
                    effective_query_parameters={},
                    body=body.model_dump(mode="json", by_alias=True),
                ),
                branch_id=branch_id,
            ),
            authorize_replay=lambda kind, resource_id: service.authorize_replay(
                principal, branch_id, kind, resource_id
            ),
            mutation=mutation,
        )

    outcome = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
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
