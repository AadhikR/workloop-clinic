from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Path, Request, Response, status
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
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.roster import RosterRepository
from app.schemas.roster import (
    RosterAssignmentResponse,
    RosterComplianceOverrideRequest,
    RosterDraftCreateRequest,
    RosterDraftDeleteRequest,
    RosterDraftReplaceRequest,
    RosterValidationResponse,
    validate_roster_period,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.roster import RosterListQuery, RosterService

router = APIRouter(prefix="/api/v1/roster/months", tags=["roster-drafts"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "validation_failed",
    "invalid_branch",
    "invalid_cursor",
    "state_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> RosterService:
    factory = getattr(request.app.state, "roster_service_factory", None)
    if factory is not None:
        return cast(RosterService, factory(connection))
    return RosterService(
        RosterRepository(connection), request.app.state.attendance_calculation_cursor_codec
    )


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


def _query(request: Request, period: str) -> RosterListQuery:
    validate_query_parameters(request, allowed={"department", "employeeId", "limit", "cursor"})
    try:
        page = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
        department = request.query_params.get("department")
        if department is not None:
            department = department.strip()
            if not department or len(department) > 100:
                raise ValueError
        raw_employee = request.query_params.get("employeeId")
        employee_id = uuid.UUID(raw_employee) if raw_employee else None
    except (TypeError, ValueError):
        raise api_error("validation_failed") from None
    return RosterListQuery(
        period=_period(period),
        department=department,
        employee_id=employee_id,
        limit=page.limit,
        cursor=page.cursor,
    )


RosterQuery = Annotated[RosterListQuery, Depends(_query)]


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


@router.get(
    "/{period}",
    response_model=CollectionResponse[RosterAssignmentResponse],
    responses={
        **success_response_documentation(
            200, "Selected branch roster month", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def list_roster(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
    query: RosterQuery,
) -> CollectionResponse[RosterAssignmentResponse]:
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
    "/{period}/validation",
    response_model=DataResponse[RosterValidationResponse],
    responses={
        **success_response_documentation(200, "Roster publication gates", cache_control="no-store"),
        **ERRORS,
    },
)
async def roster_validation(
    request: Request,
    period: Annotated[str, Path()],
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
) -> DataResponse[RosterValidationResponse]:
    validate_query_parameters(request, allowed=set())
    value = _period(period)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).validation(
            principal, branch_id, value
        ),
    )
    return DataResponse(data=data)


@router.post(
    "/{period}/drafts",
    response_model=None,
    responses={
        **success_response_documentation(201, "Created roster draft", cache_control="no-store"),
        **ERRORS,
    },
)
async def create_draft(
    request: Request,
    period: Annotated[str, Path()],
    body: RosterDraftCreateRequest,
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
            item = await service.create(principal, branch_id, value, body)
            return IdempotentResponse(
                status=201,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=f"/api/v1/roster/months/{value}/drafts/{item.id}",
                resource_kind="roster_assignment",
                resource_id=item.id,
            )

        route: dict[str, object] = {"period": value}
        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="create_roster_draft",
                method=request.method,
                route_parameters=route,
                fingerprint=request_fingerprint(
                    operation_id="create_roster_draft",
                    method=request.method,
                    route_parameters=route,
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

    return _json(
        await executor.execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=operation,
        )
    )


@router.put(
    "/{period}/drafts/{assignment_id}",
    response_model=None,
    responses={
        **success_response_documentation(200, "Replaced roster draft", cache_control="no-store"),
        **ERRORS,
    },
)
async def replace_draft(
    request: Request,
    period: Annotated[str, Path()],
    assignment_id: uuid.UUID,
    body: RosterDraftReplaceRequest,
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
            item = await service.replace(principal, branch_id, value, assignment_id, body)
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=f"/api/v1/roster/months/{value}/drafts/{item.id}",
                resource_kind="roster_assignment",
                resource_id=item.id,
            )

        route: dict[str, object] = {
            "period": value,
            "assignmentId": str(assignment_id),
        }
        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="replace_roster_draft",
                method=request.method,
                route_parameters=route,
                fingerprint=request_fingerprint(
                    operation_id="replace_roster_draft",
                    method=request.method,
                    route_parameters=route,
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

    return _json(
        await executor.execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=operation,
        )
    )


@router.delete(
    "/{period}/drafts/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    responses={**success_response_documentation(204, "Deleted roster draft"), **ERRORS},
)
async def delete_draft(
    request: Request,
    period: Annotated[str, Path()],
    assignment_id: uuid.UUID,
    body: RosterDraftDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> Response:
    validate_query_parameters(request, allowed=set())
    value = _period(period)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutation() -> IdempotentResponse:
            await service.delete(principal, branch_id, value, assignment_id, body.expected_version)
            return IdempotentResponse(
                status=204,
                body=None,
                location=None,
                resource_kind="tenant",
                resource_id=None,
            )

        route: dict[str, object] = {
            "period": value,
            "assignmentId": str(assignment_id),
        }
        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="delete_roster_draft",
                method=request.method,
                route_parameters=route,
                fingerprint=request_fingerprint(
                    operation_id="delete_roster_draft",
                    method=request.method,
                    route_parameters=route,
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
    return Response(
        status_code=outcome.status,
        headers={
            "Cache-Control": "no-store",
            **({"Idempotency-Replayed": "true"} if outcome.replayed else {}),
        },
    )


@router.post(
    "/{period}/overrides",
    response_model=None,
    responses={
        **success_response_documentation(
            201, "Created roster compliance override", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def create_override(
    request: Request,
    period: Annotated[str, Path()],
    body: RosterComplianceOverrideRequest,
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
            item = await service.override(principal, branch_id, value, body)
            return IdempotentResponse(
                status=201,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=f"/api/v1/roster/months/{value}/overrides/{item.id}",
                resource_kind="compliance_override",
                resource_id=item.id,
            )

        route: dict[str, object] = {"period": value}
        return await _idempotency(request, connection).execute(
            principal=principal,
            command=IdempotencyCommand(
                key=key,
                operation_id="create_roster_compliance_override",
                method=request.method,
                route_parameters=route,
                fingerprint=request_fingerprint(
                    operation_id="create_roster_compliance_override",
                    method=request.method,
                    route_parameters=route,
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

    return _json(
        await executor.execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=branch_id,
            operation=operation,
        )
    )
