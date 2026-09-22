from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import APIRouter, Request
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
from app.repositories.shift_swaps import ShiftSwapRepository
from app.schemas.shift_swaps import (
    ShiftSwapApproveRequest,
    ShiftSwapResponse,
    ShiftSwapSubmitRequest,
    ShiftSwapTransitionRequest,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.shift_swaps import ShiftSwapService

router = APIRouter(prefix="/api/v1/roster/shift-swaps", tags=["shift-swaps"])
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
    "request_timeout",
    "internal_error",
)
STATUSES = {"pending", "approved", "rejected", "cancelled"}


def _service(request: Request, connection: AsyncConnection) -> ShiftSwapService:
    factory = getattr(request.app.state, "shift_swap_service_factory", None)
    if factory is not None:
        return cast(ShiftSwapService, factory(connection))
    return ShiftSwapService(ShiftSwapRepository(connection))


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _query(request: Request) -> tuple[str | None, int]:
    validate_query_parameters(request, allowed={"status", "limit"})
    raw_status = request.query_params.get("status")
    if raw_status not in STATUSES | {None}:
        raise api_error("validation_failed")
    raw_limit = request.query_params.get("limit", "100")
    try:
        limit = int(raw_limit)
    except ValueError:
        raise api_error("validation_failed") from None
    if not 1 <= limit <= 100 or str(limit) != raw_limit:
        raise api_error("validation_failed")
    return raw_status, limit


async def _mutation(
    *,
    request: Request,
    claims: AccessTokenClaims,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    operation_id: str,
    route: dict[str, object],
    body: dict[str, object],
    status_code: int,
    callback: Callable[[ShiftSwapService], Awaitable[ShiftSwapResponse]],
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutate() -> IdempotentResponse:
            item = await callback(service)
            return IdempotentResponse(
                status=status_code,
                body=DataResponse(data=item).model_dump(mode="json", by_alias=True),
                location=f"/api/v1/roster/shift-swaps/{item.id}",
                resource_kind="shift_swap_request",
                resource_id=item.id,
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
            mutation=mutate,
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
            "Location": outcome.location or "",
            **({"Idempotency-Replayed": "true"} if outcome.replayed else {}),
        },
    )


@router.get(
    "/self",
    response_model=CollectionResponse[ShiftSwapResponse],
    responses={
        **success_response_documentation(200, "Personal shift swaps", cache_control="no-store"),
        **ERRORS,
    },
)
async def personal_swaps(
    request: Request,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
) -> CollectionResponse[ShiftSwapResponse]:
    status, limit = _query(request)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data = await executor.execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).personal(
            principal, status, limit
        ),
    )
    return CollectionResponse(data=data, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.get(
    "",
    response_model=CollectionResponse[ShiftSwapResponse],
    responses={
        **success_response_documentation(
            200, "Selected-branch shift swaps", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def admin_swaps(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    branch_id: AdminSelectedBranch,
) -> CollectionResponse[ShiftSwapResponse]:
    status, limit = _query(request)
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor
    data = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=lambda connection: _service(request, connection).admin(
            principal, branch_id, status, limit
        ),
    )
    return CollectionResponse(data=data, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.post("", response_model=None, responses=ERRORS)
async def submit_swap(
    request: Request,
    body: ShiftSwapSubmitRequest,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    assert principal.branch_id is not None
    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=principal.branch_id,
        operation_id="submit_shift_swap",
        route={},
        body=body.model_dump(mode="json", by_alias=True),
        status_code=201,
        callback=lambda service: service.submit(principal, body),
    )


@router.post("/{swap_id}/cancel", response_model=None, responses=ERRORS)
async def cancel_swap(
    request: Request,
    swap_id: uuid.UUID,
    body: ShiftSwapTransitionRequest,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    if body.reason is not None:
        raise api_error("validation_failed")
    assert principal.branch_id is not None
    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=principal.branch_id,
        operation_id="cancel_shift_swap",
        route={"swapId": str(swap_id)},
        body=body.model_dump(mode="json", by_alias=True),
        status_code=200,
        callback=lambda service: service.cancel(principal, swap_id, body),
    )


@router.post("/{swap_id}/reject", response_model=None, responses=ERRORS)
async def reject_swap(
    request: Request,
    swap_id: uuid.UUID,
    body: ShiftSwapTransitionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="reject_shift_swap",
        route={"swapId": str(swap_id)},
        body=body.model_dump(mode="json", by_alias=True),
        status_code=200,
        callback=lambda service: service.reject(principal, branch_id, swap_id, body),
    )


@router.post("/{swap_id}/approve", response_model=None, responses=ERRORS)
async def approve_swap(
    request: Request,
    swap_id: uuid.UUID,
    body: ShiftSwapApproveRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    branch_id: AdminSelectedBranch,
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="approve_shift_swap",
        route={"swapId": str(swap_id)},
        body=body.model_dump(mode="json", by_alias=True),
        status_code=200,
        callback=lambda service: service.approve(principal, branch_id, swap_id, body),
    )
