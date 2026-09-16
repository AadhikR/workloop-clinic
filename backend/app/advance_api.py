from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, cast

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.http.errors import error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.advance import (
    ADVANCE_STATUSES,
    PERIOD,
    AdminAdvanceCreateRequest,
    AdvanceAdminResponse,
    AdvanceCreateRequest,
    AdvanceDecisionRequest,
    AdvanceRepaymentRequest,
    AdvanceResponse,
    AdvanceScheduleRequest,
    AdvanceVersionRequest,
)
from app.services.advances import AdvanceListQuery, AdvanceService
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

router = APIRouter(prefix="/api/v1/advances", tags=["advances"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "validation_failed",
    "invalid_branch",
    "branch_required",
    "invalid_cursor",
    "stale_financial_state",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_key_reused",
    "idempotency_in_progress",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> AdvanceService:
    return AdvanceService(connection, request.app.state.advance_cursor_codec)


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _query(
    limit: int,
    cursor: str | None,
    advance_status: str | None,
    employee_id: uuid.UUID | None,
    start_period: str | None,
) -> AdvanceListQuery:
    if (advance_status is not None and advance_status not in ADVANCE_STATUSES) or (
        start_period is not None and not PERIOD.fullmatch(start_period)
    ):
        raise ServiceExecutionError("validation_failed")
    return AdvanceListQuery(limit, cursor, advance_status, employee_id, start_period)


@router.get(
    "/self",
    response_model=CollectionResponse[AdvanceResponse],
    operation_id="list_self_advances",
    responses={**success_response_documentation(200, "Own salary advances"), **ERRORS},
)
async def list_self_advances(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    advance_status: Annotated[str | None, Query(alias="status")] = None,
) -> CollectionResponse[AdvanceResponse]:
    query = _query(limit, cursor, advance_status, None, None)
    items, next_cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_self(principal, query),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "",
    response_model=CollectionResponse[AdvanceAdminResponse],
    operation_id="list_admin_advances",
    responses={**success_response_documentation(200, "Selected-branch salary advances"), **ERRORS},
)
async def list_admin_advances(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    advance_status: Annotated[str | None, Query(alias="status")] = None,
    employee_id: Annotated[uuid.UUID | None, Query(alias="employeeId")] = None,
    start_period: Annotated[str | None, Query(alias="repaymentStartPeriod", max_length=7)] = None,
) -> CollectionResponse[AdvanceAdminResponse]:
    query = _query(limit, cursor, advance_status, employee_id, start_period)
    items, next_cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_admin(
            principal, selected, query
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


def _json_response(outcome: IdempotentResponse) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if outcome.location is not None:
        headers["Location"] = outcome.location
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


async def _idempotent_mutation(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    selected: uuid.UUID | None,
    operation_id: str,
    method: str,
    route_parameters: dict[str, object],
    body: dict[str, object],
    mutate: Callable[[AdvanceService, uuid.UUID], Awaitable[IdempotentResponse]],
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
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
            body=body,
        ),
        branch_id=branch_id,
    )

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def replay(kind: str, resource_id: uuid.UUID | None) -> None:
            await service.authorize_replay(principal, branch_id, kind, resource_id)

        try:
            return await _idempotency(request, connection).execute(
                principal=principal,
                command=command,
                authorize_replay=replay,
                mutation=lambda: mutate(service, key),
            )
        except ServiceExecutionError as error:
            if error.code == "idempotency_conflict":
                raise ServiceExecutionError("idempotency_key_reused") from None
            raise

    outcome = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=operation,
    )
    return _json_response(outcome)


async def _create(
    *,
    request: Request,
    body: AdvanceCreateRequest | AdminAdvanceCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    selected: uuid.UUID | None,
    admin: bool,
    operation_id: str,
) -> JSONResponse:
    async def mutate(service: AdvanceService, _key: uuid.UUID) -> IdempotentResponse:
        result = await service.create(principal, branch_id, body, admin=admin)
        return IdempotentResponse(
            status=201,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=f"/api/v1/advances/{result.id}",
            resource_kind="salary_advance",
            resource_id=result.id,
        )

    return await _idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected=selected,
        operation_id=operation_id,
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post(
    "/self",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[AdvanceResponse],
    operation_id="create_self_advance",
    responses={**success_response_documentation(201, "Salary advance requested"), **ERRORS},
)
async def create_self_advance(
    request: Request,
    body: AdvanceCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None:
        raise ServiceExecutionError("operation_not_permitted")
    return await _create(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=principal.branch_id,
        selected=None,
        admin=False,
        operation_id="create_self_advance",
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[AdvanceAdminResponse],
    operation_id="create_admin_advance",
    responses={**success_response_documentation(201, "Salary advance created"), **ERRORS},
)
async def create_admin_advance(
    request: Request,
    body: AdminAdvanceCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _create(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected=selected,
        admin=True,
        operation_id="create_admin_advance",
    )


async def _command(
    *,
    request: Request,
    body: (
        AdvanceDecisionRequest
        | AdvanceScheduleRequest
        | AdvanceRepaymentRequest
        | AdvanceVersionRequest
    ),
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    selected: uuid.UUID | None,
    advance_id: uuid.UUID,
    operation_id: str,
    method: str,
    mutate_result: Callable[
        [AdvanceService, uuid.UUID], Awaitable[AdvanceResponse | AdvanceAdminResponse]
    ],
) -> JSONResponse:
    async def mutate(service: AdvanceService, key: uuid.UUID) -> IdempotentResponse:
        result = await mutate_result(service, key)
        return IdempotentResponse(
            status=200,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=None,
            resource_kind="salary_advance",
            resource_id=result.id,
        )

    return await _idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected=selected,
        operation_id=operation_id,
        method=method,
        route_parameters={"advanceId": str(advance_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post(
    "/self/{advance_id}/withdraw",
    operation_id="withdraw_self_advance",
    responses=ERRORS,
)
async def withdraw_self_advance(
    advance_id: uuid.UUID,
    request: Request,
    body: AdvanceVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None:
        raise ServiceExecutionError("operation_not_permitted")
    branch_id = principal.branch_id
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected=None,
        advance_id=advance_id,
        operation_id="withdraw_self_advance",
        method="POST",
        mutate_result=lambda service, _key: service.withdraw(
            principal, branch_id, advance_id, body
        ),
    )


@router.put("/{advance_id}/schedule", operation_id="replace_advance_schedule", responses=ERRORS)
async def replace_advance_schedule(
    advance_id: uuid.UUID,
    request: Request,
    body: AdvanceScheduleRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected=selected,
        advance_id=advance_id,
        operation_id="replace_advance_schedule",
        method="PUT",
        mutate_result=lambda service, _key: service.schedule(principal, selected, advance_id, body),
    )


async def _decision(
    *,
    advance_id: uuid.UUID,
    request: Request,
    body: AdvanceDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    approve: bool,
) -> JSONResponse:
    operation_id = "approve_advance" if approve else "reject_advance"
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected=selected,
        advance_id=advance_id,
        operation_id=operation_id,
        method="POST",
        mutate_result=lambda service, _key: service.decide(
            principal, selected, advance_id, body, approve=approve
        ),
    )


@router.post("/{advance_id}/approve", operation_id="approve_advance", responses=ERRORS)
async def approve_advance(
    advance_id: uuid.UUID,
    request: Request,
    body: AdvanceDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decision(
        advance_id=advance_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        approve=True,
    )


@router.post("/{advance_id}/reject", operation_id="reject_advance", responses=ERRORS)
async def reject_advance(
    advance_id: uuid.UUID,
    request: Request,
    body: AdvanceDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decision(
        advance_id=advance_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        approve=False,
    )


@router.post("/{advance_id}/repayments", operation_id="record_advance_repayment", responses=ERRORS)
async def record_advance_repayment(
    advance_id: uuid.UUID,
    request: Request,
    body: AdvanceRepaymentRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected=selected,
        advance_id=advance_id,
        operation_id="record_advance_repayment",
        method="POST",
        mutate_result=lambda service, key: service.repay(
            principal, selected, advance_id, body, idempotency_key=key, settle=False
        ),
    )


@router.post("/{advance_id}/settle", operation_id="settle_advance", responses=ERRORS)
async def settle_advance(
    advance_id: uuid.UUID,
    request: Request,
    body: AdvanceVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected=selected,
        advance_id=advance_id,
        operation_id="settle_advance",
        method="POST",
        mutate_result=lambda service, key: service.repay(
            principal, selected, advance_id, body, idempotency_key=key, settle=True
        ),
    )
