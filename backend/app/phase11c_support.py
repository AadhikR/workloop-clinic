from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.repositories.idempotency import IdempotencyRepository
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse


def executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def coordinator(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def json_response(outcome: IdempotentResponse) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if outcome.location is not None:
        headers["Location"] = outcome.location
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


async def idempotent_mutation(
    *,
    request: Request,
    claims: AccessTokenClaims,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    selected_admin_branch_id: uuid.UUID | None,
    operation_id: str,
    method: str,
    route_parameters: dict[str, object],
    body: dict[str, object],
    resource_authorizer: Callable[[AsyncConnection, str, uuid.UUID | None], Awaitable[None]],
    mutation: Callable[[AsyncConnection], Awaitable[IdempotentResponse]],
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
        return await coordinator(request, connection).execute(
            principal=principal,
            command=command,
            authorize_replay=lambda kind, resource_id: resource_authorizer(
                connection, kind, resource_id
            ),
            mutation=lambda: mutation(connection),
        )

    outcome = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_admin_branch_id,
        operation=operation,
    )
    return json_response(outcome)
