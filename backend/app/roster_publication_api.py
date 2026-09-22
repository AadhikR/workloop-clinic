from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    StaffAuthorizationPrincipal,
    VerifiedAccessToken,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.http.validation import validate_query_parameters
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.roster_publication import RosterPublicationRepository
from app.schemas.roster import validate_roster_period
from app.schemas.roster_publication import (
    ColleagueScheduleEntryResponse,
    PublishedScheduleEntryResponse,
    RosterActualHoursRequest,
    RosterOvertimeApprovalRequest,
    RosterPublicationResponse,
    RosterPublishRequest,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.roster_publication import RosterPublicationService

publication_router = APIRouter(prefix="/api/v1/roster/months", tags=["roster-publication"])
schedule_router = APIRouter(prefix="/api/v1/roster/schedules", tags=["roster-schedules"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "validation_failed",
    "invalid_branch",
    "state_conflict",
    "roster_publication_not_ready",
    "payroll_input_not_ready",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> RosterPublicationService:
    factory = getattr(request.app.state, "roster_publication_service_factory", None)
    if factory is not None:
        return cast(RosterPublicationService, factory(connection))
    return RosterPublicationService(RosterPublicationRepository(connection))


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _period(value: str) -> str:
    try:
        return validate_roster_period(value)
    except ValueError:
        raise api_error("resource_not_found") from None


def _json(outcome: IdempotentResponse) -> JSONResponse:
    return JSONResponse(
        outcome.body,
        status_code=outcome.status,
        headers={
            "Cache-Control": "no-store",
            **({"Location": outcome.location} if outcome.location else {}),
            **({"Idempotency-Replayed": "true"} if outcome.replayed else {}),
        },
    )


async def _mutation(
    *,
    request: Request,
    claims: AccessTokenClaims,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    operation_id: str,
    route: dict[str, object],
    body: dict[str, object],
    callback: Callable[[RosterPublicationService], Awaitable[RosterPublicationResponse]],
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def execute_mutation() -> IdempotentResponse:
            item = await callback(service)
            assert item.current_version_id is not None
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=f"/api/v1/roster/months/{item.period}/publication",
                resource_kind="roster_publication_version",
                resource_id=item.current_version_id,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id=operation_id,
                method=request.method,
                route_parameters=route,
                fingerprint=request_fingerprint(
                    operation_id=operation_id,
                    method=request.method,
                    route_parameters=route,
                    effective_query_parameters={},
                    body=body,
                ),
                branch_id=branch_id,
            ),
            authorize_replay=lambda kind, resource_id: service.authorize_replay(
                principal, branch_id, kind, resource_id
            ),
            mutation=execute_mutation,
        )

    return _json(
        await executor.execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=operation,
        )
    )


@publication_router.get(
    "/{period}/publication",
    response_model=DataResponse[RosterPublicationResponse],
    responses={
        **success_response_documentation(200, "Roster publication state", cache_control="no-store"),
        **ERRORS,
    },
)
async def publication_detail(
    request: Request,
    period: Annotated[str, Path()],
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
) -> DataResponse[RosterPublicationResponse]:
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


@publication_router.post("/{period}/publish", response_model=None, responses=ERRORS)
async def publish_roster(
    request: Request,
    period: Annotated[str, Path()],
    body: RosterPublishRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    value = _period(period)
    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="publish_roster_month",
        route={"period": value},
        body=body.model_dump(mode="json", by_alias=True),
        callback=lambda service: service.publish(principal, branch_id, value, body),
    )


@publication_router.post(
    "/{period}/assignments/{assignment_id}/actual-hours",
    response_model=None,
    responses=ERRORS,
)
async def record_actual_hours(
    request: Request,
    period: Annotated[str, Path()],
    assignment_id: uuid.UUID,
    body: RosterActualHoursRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    value = _period(period)
    route: dict[str, object] = {"period": value, "assignmentId": str(assignment_id)}
    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="record_roster_actual_hours",
        route=route,
        body=body.model_dump(mode="json", by_alias=True),
        callback=lambda service: service.record_actual_hours(
            principal, branch_id, value, assignment_id, body
        ),
    )


@publication_router.post(
    "/{period}/assignments/{assignment_id}/overtime-approval",
    response_model=None,
    responses=ERRORS,
)
async def approve_roster_overtime(
    request: Request,
    period: Annotated[str, Path()],
    assignment_id: uuid.UUID,
    body: RosterOvertimeApprovalRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    value = _period(period)
    route: dict[str, object] = {"period": value, "assignmentId": str(assignment_id)}
    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="approve_roster_overtime",
        route=route,
        body=body.model_dump(mode="json", by_alias=True),
        callback=lambda service: service.approve_overtime(
            principal, branch_id, value, assignment_id, body
        ),
    )


@schedule_router.get(
    "/self",
    response_model=CollectionResponse[PublishedScheduleEntryResponse],
    responses={
        **success_response_documentation(
            200, "Personal published schedule", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def personal_schedule(
    request: Request,
    period: Annotated[str, Query()],
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
) -> CollectionResponse[PublishedScheduleEntryResponse]:
    validate_query_parameters(request, allowed={"period"})
    value = _period(period)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data = await executor.execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).personal_schedule(
            principal, value
        ),
    )
    return CollectionResponse(
        data=data, page=Page(limit=min(100, max(1, len(data))), next_cursor=None, has_more=False)
    )


@schedule_router.get(
    "/colleagues",
    response_model=CollectionResponse[ColleagueScheduleEntryResponse],
    responses={
        **success_response_documentation(
            200, "Same-branch colleague selector", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def colleague_schedule(
    request: Request,
    day: Annotated[date, Query(alias="date")],
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
) -> CollectionResponse[ColleagueScheduleEntryResponse]:
    validate_query_parameters(request, allowed={"date"})
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data = await executor.execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).colleagues(principal, day),
    )
    return CollectionResponse(
        data=data, page=Page(limit=min(100, max(1, len(data))), next_cursor=None, has_more=False)
    )
