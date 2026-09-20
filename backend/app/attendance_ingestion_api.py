from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
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
from app.schemas.attendance_ingestion import (
    BiometricImportRequest,
    BiometricImportResponse,
    BiometricMappingRequest,
    BiometricMappingResponse,
    ClockEventResponse,
    ManualClockEventRequest,
)
from app.services.attendance_ingestion import (
    AttendanceIngestionService,
    EventListQuery,
    MappingListQuery,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

router = APIRouter(prefix="/api/v1", tags=["attendance-ingestion"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "validation_failed",
    "clock_event_conflict",
    "invalid_cursor",
    "invalid_branch",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "request_too_large",
    "request_timeout",
    "internal_error",
)
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ResourceResponse(Protocol):
    id: uuid.UUID


def _service(request: Request, connection: AsyncConnection) -> AttendanceIngestionService:
    factory = getattr(request.app.state, "attendance_ingestion_service_factory", None)
    if factory is not None:
        return cast(AttendanceIngestionService, factory(connection))
    return AttendanceIngestionService(
        connection, request.app.state.attendance_ingestion_cursor_codec
    )


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _query(request: Request, *, allow_employee: bool) -> EventListQuery:
    validate_query_parameters(request, allowed={"employeeId", "from", "to", "limit", "cursor"})
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        raw = request.query_params.get("employeeId")
        employee = (
            None
            if raw is None
            else uuid.UUID(raw)
            if _UUID.fullmatch(raw)
            else (_ for _ in ()).throw(ValueError)
        )

        def instant(value: str | None) -> datetime | None:
            if value is None:
                return None
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError
            return parsed.astimezone(UTC)

        if employee is not None and not allow_employee:
            raise ValueError
        return EventListQuery(
            employee_id=employee,
            start=instant(request.query_params.get("from")),
            end=instant(request.query_params.get("to")),
            limit=page.limit,
            cursor=page.cursor,
        )
    except (ValueError, TypeError):
        raise api_error("validation_failed") from None


def _admin_event_query(request: Request) -> EventListQuery:
    return _query(request, allow_employee=True)


def _self_event_query(request: Request) -> EventListQuery:
    return _query(request, allow_employee=False)


def _mapping_query(request: Request) -> MappingListQuery:
    validate_query_parameters(request, allowed={"limit", "cursor"})
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
    except (ValueError, TypeError):
        raise api_error("validation_failed") from None
    return MappingListQuery(limit=page.limit, cursor=page.cursor)


AdminEventQuery = Annotated[EventListQuery, Depends(_admin_event_query)]
SelfEventQuery = Annotated[EventListQuery, Depends(_self_event_query)]
MappingQuery = Annotated[MappingListQuery, Depends(_mapping_query)]


async def _mutation(
    request: Request,
    connection: AsyncConnection,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    operation_id: str,
    body: dict[str, object],
    kind: str,
    call: Callable[[AttendanceIngestionService], Awaitable[ResourceResponse]],
    status: int = 200,
    location_prefix: str | None = None,
) -> IdempotentResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    service = _service(request, connection)

    async def mutate() -> IdempotentResponse:
        item = await call(service)
        return IdempotentResponse(
            status=status,
            body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
            location=None if location_prefix is None else f"{location_prefix}/{item.id}",
            resource_kind=kind,
            resource_id=item.id,
        )

    return await _idempotency(request, connection).execute(
        principal=principal,
        command=IdempotencyCommand(
            key=key,
            operation_id=operation_id,
            method=request.method,
            route_parameters={},
            fingerprint=request_fingerprint(
                operation_id=operation_id,
                method=request.method,
                route_parameters={},
                effective_query_parameters={},
                body=body,
            ),
            branch_id=branch_id,
        ),
        authorize_replay=lambda kind, resource_id: service.authorize_replay(
            principal, branch_id, kind, resource_id
        ),
        mutation=mutate,
    )


def _response(outcome: IdempotentResponse) -> Response:
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


@router.get(
    "/clock-events",
    response_model=CollectionResponse[ClockEventResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch clock events", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def list_events(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
    query: AdminEventQuery,
) -> CollectionResponse[ClockEventResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).list_events(
            principal, branch_id, query
        ),
    )
    return CollectionResponse(
        data=data,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.get(
    "/attendance/me/events",
    response_model=CollectionResponse[ClockEventResponse],
    responses={
        **success_response_documentation(200, "Personal clock events", cache_control="no-store"),
        **ERRORS,
    },
)
async def self_events(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    query: SelfEventQuery,
) -> CollectionResponse[ClockEventResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).self_events(principal, query),
    )
    return CollectionResponse(
        data=data,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.post(
    "/clock-events/manual",
    status_code=201,
    response_model=DataResponse[ClockEventResponse],
    responses={
        **success_response_documentation(
            201, "Manual clock event recorded", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def manual(
    request: Request,
    body: ManualClockEventRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> Response:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    result = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal,
            branch_id,
            "create_manual_clock_event",
            body.model_dump(mode="json", by_alias=True),
            "clock_event",
            lambda service: service.manual(principal, branch_id, body),
            201,
            "/api/v1/clock-events",
        ),
    )
    return _response(result)


@router.get(
    "/biometric-mappings",
    response_model=CollectionResponse[BiometricMappingResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch biometric mappings", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def mappings(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
    query: MappingQuery,
) -> CollectionResponse[BiometricMappingResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data, cursor = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).mappings(
            principal, branch_id, query
        ),
    )
    return CollectionResponse(
        data=data,
        page=Page(limit=query.limit, next_cursor=cursor, has_more=cursor is not None),
    )


@router.put(
    "/biometric-mappings/{badge_no}",
    response_model=DataResponse[BiometricMappingResponse],
    responses=ERRORS,
)
async def replace_mapping(
    badge_no: str,
    request: Request,
    body: BiometricMappingRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> Response:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    result = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal,
            branch_id,
            "replace_biometric_mapping",
            body.model_dump(mode="json", by_alias=True),
            "biometric_mapping",
            lambda service: service.replace_mapping(principal, branch_id, badge_no, body),
        ),
    )
    return _response(result)


@router.delete("/biometric-mappings/{badge_no}", status_code=204, responses=ERRORS)
async def delete_mapping(
    badge_no: str,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> Response:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> Response:
        service = _service(request, connection)

        async def mutate() -> IdempotentResponse:
            await service.delete_mapping(principal, branch_id, badge_no)
            return IdempotentResponse(
                status=204,
                body=None,
                location=None,
                resource_kind="tenant",
                resource_id=None,
            )

        outcome = await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="delete_biometric_mapping",
                method="DELETE",
                route_parameters={"badgeNo": badge_no},
                fingerprint=request_fingerprint(
                    operation_id="delete_biometric_mapping",
                    method="DELETE",
                    route_parameters={"badgeNo": badge_no},
                    effective_query_parameters={},
                    body={},
                ),
                branch_id=branch_id,
            ),
            authorize_replay=lambda kind, resource_id: service.authorize_replay(
                principal, branch_id, kind, resource_id
            ),
            mutation=mutate,
        )
        return Response(status_code=outcome.status, headers={"Cache-Control": "no-store"})

    return await executor.execute(
        claims=claims, principal=principal, selected_admin_branch_id=branch_id, operation=operation
    )


@router.post(
    "/biometric-imports",
    status_code=201,
    response_model=DataResponse[BiometricImportResponse],
    responses=ERRORS,
)
async def biometric_import(
    request: Request,
    body: BiometricImportRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> Response:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    result = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _mutation(
            request,
            connection,
            principal,
            branch_id,
            "import_biometric_events",
            body.model_dump(mode="json", by_alias=True),
            "attendance_import_batch",
            lambda service: service.import_candidates(principal, branch_id, body),
            201,
            "/api/v1/biometric-imports",
        ),
    )
    return _response(result)
