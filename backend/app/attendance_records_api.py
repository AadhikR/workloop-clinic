from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response
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
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.attendance_calculation import (
    AttendanceCalculationBatchRequest,
    AttendanceCalculationRequest,
    AttendanceRecordResponse,
    PersonalAttendanceResponse,
)
from app.services.attendance_records import AttendanceRecordService, RecordListQuery
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

router = APIRouter(prefix="/api/v1", tags=["attendance-calculation"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "validation_failed",
    "invalid_cursor",
    "invalid_branch",
    "state_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "request_timeout",
    "internal_error",
)
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _service(request: Request, connection: AsyncConnection) -> AttendanceRecordService:
    factory = getattr(request.app.state, "attendance_record_service_factory", None)
    if factory is not None:
        return cast(AttendanceRecordService, factory(connection))
    return AttendanceRecordService(
        connection, request.app.state.attendance_calculation_cursor_codec
    )


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _admin_query(request: Request) -> RecordListQuery:
    validate_query_parameters(request, allowed={"employeeId", "from", "to", "limit", "cursor"})
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        employee = request.query_params.get("employeeId")
        query = RecordListQuery(
            employee_id=None
            if employee is None
            else uuid.UUID(employee)
            if _UUID.fullmatch(employee)
            else (_ for _ in ()).throw(ValueError),
            from_date=None
            if request.query_params.get("from") is None
            else date.fromisoformat(request.query_params["from"]),
            to_date=None
            if request.query_params.get("to") is None
            else date.fromisoformat(request.query_params["to"]),
            limit=page.limit,
            cursor=page.cursor,
        )
        if (
            query.from_date is not None
            and query.to_date is not None
            and query.from_date > query.to_date
        ):
            raise ValueError
        return query
    except (KeyError, TypeError, ValueError):
        raise api_error("validation_failed") from None


AdminRecordQuery = Annotated[RecordListQuery, Depends(_admin_query)]


def _self_query(request: Request) -> RecordListQuery:
    validate_query_parameters(request, allowed={"from", "to", "limit", "cursor"})
    return _admin_query(request)


SelfRecordQuery = Annotated[RecordListQuery, Depends(_self_query)]


@router.get(
    "/attendance-records",
    response_model=CollectionResponse[AttendanceRecordResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch calculated attendance", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def list_records(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
    query: AdminRecordQuery,
) -> CollectionResponse[AttendanceRecordResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).list_admin(
            principal, branch_id, query
        ),
    )
    return CollectionResponse(
        data=data, page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None)
    )


@router.get(
    "/attendance/me/today",
    response_model=DataResponse[PersonalAttendanceResponse],
    responses={
        **success_response_documentation(
            200, "Personal calculated attendance", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def personal_today(
    request: Request, claims: VerifiedAccessToken, principal: AuthenticatedReadPrincipal
) -> DataResponse[PersonalAttendanceResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    item = await executor.execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).personal_today(principal),
    )
    return DataResponse(data=item)


@router.get(
    "/attendance/me",
    response_model=CollectionResponse[AttendanceRecordResponse],
    responses={
        **success_response_documentation(
            200, "Personal attendance history", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def personal_history(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    query: SelfRecordQuery,
) -> CollectionResponse[AttendanceRecordResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).personal_history(
            principal, query
        ),
    )
    return CollectionResponse(
        data=data, page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None)
    )


@router.post(
    "/attendance/calculations",
    response_model=None,
    responses={
        **success_response_documentation(
            200, "One calculated attendance record", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def calculate_record(
    request: Request,
    body: AttendanceCalculationRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> Response:
    validate_query_parameters(request, allowed=set())
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    key = parse_idempotency_key(request, required=True)
    assert key is not None

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutation() -> IdempotentResponse:
            item = await service.calculate_one(principal, branch_id, body)
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=f"/api/v1/attendance-records/{item.id}",
                resource_kind="attendance_record",
                resource_id=item.id,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="calculate_attendance_record",
                method=request.method,
                route_parameters={},
                fingerprint=request_fingerprint(
                    operation_id="calculate_attendance_record",
                    method=request.method,
                    route_parameters={},
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
        claims=claims, principal=principal, selected_admin_branch_id=branch_id, operation=operation
    )
    from fastapi.responses import JSONResponse

    return JSONResponse(
        outcome.body,
        status_code=outcome.status,
        headers={
            "Cache-Control": "no-store",
            **({"Location": outcome.location} if outcome.location else {}),
            **({"Idempotency-Replayed": "true"} if outcome.replayed else {}),
        },
    )


@router.post(
    "/attendance/calculations/batch",
    response_model=None,
    responses={
        **success_response_documentation(
            200, "Bounded daily attendance calculation", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def calculate_record_batch(
    request: Request,
    body: AttendanceCalculationBatchRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> Response:
    validate_query_parameters(request, allowed=set())
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    key = parse_idempotency_key(request, required=True)
    assert key is not None

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutation() -> IdempotentResponse:
            items = await service.calculate_batch(principal, branch_id, body)
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=items).model_dump(mode="json", by_alias=True),
                location=None,
                resource_kind="tenant",
                resource_id=None,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="calculate_attendance_batch",
                method=request.method,
                route_parameters={},
                fingerprint=request_fingerprint(
                    operation_id="calculate_attendance_batch",
                    method=request.method,
                    route_parameters={},
                    effective_query_parameters={},
                    body=body.model_dump(mode="json", by_alias=True),
                ),
                branch_id=branch_id,
            ),
            authorize_replay=lambda kind, resource_id: service.authorize_batch_replay(
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
    from fastapi.responses import JSONResponse

    return JSONResponse(
        outcome.body,
        status_code=outcome.status,
        headers={
            "Cache-Control": "no-store",
            **({"Idempotency-Replayed": "true"} if outcome.replayed else {}),
        },
    )
