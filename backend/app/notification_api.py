from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, cast

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
    branch_required_error,
    invalid_branch_error,
)
from app.http.errors import error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import DataResponse
from app.models.identity import AppRole
from app.repositories.idempotency import IdempotencyRepository
from app.repositories.notifications import NotificationRepository
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationReadAllResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.notifications import NotificationListQuery, NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

ERRORS = error_response_documentation(
    "invalid_request",
    "validation_failed",
    "invalid_access_token",
    "application_account_unavailable",
    "resource_not_found",
    "invalid_branch",
    "branch_required",
    "invalid_cursor",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> NotificationService:
    factory = getattr(request.app.state, "notification_service_factory", None)
    if factory is not None:
        return cast(NotificationService, factory(connection))
    return NotificationService(
        NotificationRepository(connection), request.app.state.notification_cursor_codec
    )


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _inbox_branch(request: Request, principal: AuthorizationPrincipal) -> uuid.UUID:
    values = request.headers.getlist("x-workloop-branch-id")
    if principal.role is not AppRole.ADMIN:
        if values:
            raise invalid_branch_error()
        if principal.branch_id is None:
            raise ServiceExecutionError("resource_not_found")
        return principal.branch_id
    if not values:
        raise branch_required_error()
    if len(values) != 1 or values[0] != values[0].strip():
        raise invalid_branch_error()
    try:
        branch_id = uuid.UUID(values[0])
    except (AttributeError, ValueError):
        raise invalid_branch_error() from None
    if branch_id.version is None or str(branch_id) != values[0]:
        raise invalid_branch_error()
    return branch_id


async def _execute(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    operation: Callable[[NotificationService, uuid.UUID], Awaitable[object]],
) -> object:
    branch_id = _inbox_branch(request, principal)
    return await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation=lambda connection: operation(_service(request, connection), branch_id),
    )


@router.get(
    "",
    response_model=DataResponse[NotificationListResponse],
    operation_id="list_notifications",
    responses={**success_response_documentation(200, "Recipient notification inbox"), **ERRORS},
)
async def list_notifications(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> DataResponse[NotificationListResponse]:
    result = await _execute(
        request=request,
        claims=claims,
        principal=principal,
        operation=lambda service, branch_id: service.list(
            principal, branch_id, NotificationListQuery(limit=limit, cursor=cursor)
        ),
    )
    return DataResponse(data=cast(NotificationListResponse, result))


@router.get(
    "/unread-count",
    response_model=DataResponse[NotificationUnreadCountResponse],
    operation_id="get_notification_unread_count",
    responses={**success_response_documentation(200, "Recipient unread count"), **ERRORS},
)
async def unread_count(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[NotificationUnreadCountResponse]:
    result = await _execute(
        request=request,
        claims=claims,
        principal=principal,
        operation=lambda service, branch_id: service.unread_count(principal, branch_id),
    )
    return DataResponse(data=cast(NotificationUnreadCountResponse, result))


@router.put(
    "/{notification_id}/read",
    response_model=DataResponse[NotificationResponse],
    operation_id="read_notification",
    responses={**success_response_documentation(200, "Notification marked read"), **ERRORS},
)
async def read_notification(
    notification_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> DataResponse[NotificationResponse]:
    result = await _execute(
        request=request,
        claims=claims,
        principal=principal,
        operation=lambda service, branch_id: service.read_one(
            principal, branch_id, notification_id
        ),
    )
    return DataResponse(data=cast(NotificationResponse, result))


@router.post(
    "/read-all",
    response_model=DataResponse[NotificationReadAllResponse],
    operation_id="read_all_notifications",
    responses={**success_response_documentation(200, "Inbox marked read"), **ERRORS},
)
async def read_all_notifications(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    branch_id = _inbox_branch(request, principal)
    command = IdempotencyCommand(
        key=key,
        operation_id="read_all_notifications",
        method="POST",
        route_parameters={},
        fingerprint=request_fingerprint(
            operation_id="read_all_notifications",
            method="POST",
            route_parameters={},
            effective_query_parameters={},
            body={},
        ),
        branch_id=branch_id,
    )

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def authorize(kind: str, resource_id: uuid.UUID | None) -> None:
            await service.authorize_replay(principal, branch_id, kind, resource_id)

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=command,
            authorize_replay=authorize,
            mutation=lambda: _read_all_outcome(service, principal, branch_id),
        )

    outcome = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation=operation,
    )
    headers = {"Cache-Control": "no-store"}
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


async def _read_all_outcome(
    service: NotificationService,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
) -> IdempotentResponse:
    response = await service.read_all(principal, branch_id)
    return IdempotentResponse(
        status=200,
        body={"data": response.model_dump(mode="json", by_alias=True)},
        location=None,
        resource_kind="notification_inbox",
        resource_id=None,
    )
