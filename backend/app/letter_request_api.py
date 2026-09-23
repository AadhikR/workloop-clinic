from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
    branch_required_error,
    invalid_branch_error,
)
from app.http.errors import error_response_documentation, success_response_documentation
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.models.identity import AppRole
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.letter_requests import (
    LetterRequestCreateRequest,
    LetterRequestDecisionRequest,
    LetterRequestPrintSource,
    LetterRequestRejectRequest,
    LetterRequestResponse,
)
from app.services.idempotency import IdempotentResponse
from app.services.letter_requests import LetterRequestListQuery, LetterRequestService

router = APIRouter(prefix="/api/v1/requests", tags=["letter-requests"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "validation_failed",
    "invalid_branch",
    "branch_required",
    "state_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


async def _mutation(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    operation_id: str,
    method: str,
    route_parameters: dict[str, object],
    body: dict[str, object],
    mutate: Callable[[LetterRequestService], Awaitable[IdempotentResponse]],
    selected_admin_branch_id: uuid.UUID | None,
) -> JSONResponse:
    async def run(connection: AsyncConnection) -> IdempotentResponse:
        return await mutate(LetterRequestService(connection))

    async def authorize_replay(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        await LetterRequestService(connection).authorize_replay(
            principal, branch_id, kind, resource_id
        )

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=selected_admin_branch_id,
        operation_id=operation_id,
        method=method,
        route_parameters=route_parameters,
        body=body,
        resource_authorizer=authorize_replay,
        mutation=run,
    )


def _selected_scope(
    request: Request, principal: AuthorizationPrincipal
) -> tuple[uuid.UUID, uuid.UUID | None]:
    if principal.role is not AppRole.ADMIN:
        if principal.branch_id is None:
            raise branch_required_error()
        return principal.branch_id, None
    values = request.headers.getlist("x-workloop-branch-id")
    if not values:
        raise branch_required_error()
    if len(values) != 1 or not values[0] or values[0] != values[0].strip():
        raise invalid_branch_error()
    try:
        branch_id = uuid.UUID(values[0])
    except ValueError:
        raise invalid_branch_error() from None
    if branch_id.version is None or str(branch_id) != values[0]:
        raise invalid_branch_error()
    return branch_id, branch_id


@router.get(
    "/self",
    response_model=CollectionResponse[LetterRequestResponse],
    operation_id="list_self_letter_requests",
    responses={**success_response_documentation(200, "Own requests"), **ERRORS},
)
async def list_self_requests(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    status: Annotated[Literal["pending", "completed", "rejected"] | None, Query()] = None,
    kind: Annotated[Literal["letter", "custom"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[LetterRequestResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: LetterRequestService(connection).list_self(
            principal, status=status, kind=kind, limit=limit
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.post("/self", operation_id="submit_letter_request", responses=ERRORS)
async def submit_request(
    request: Request,
    body: LetterRequestCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None:
        raise branch_required_error()

    async def mutate(service: LetterRequestService) -> IdempotentResponse:
        result = await service.submit(principal, body)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/requests/{result.id}",
            "letter_request",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=principal.branch_id,
        operation_id="submit_letter_request",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=None,
    )


@router.get(
    "",
    response_model=CollectionResponse[LetterRequestResponse],
    operation_id="list_letter_requests",
    responses={**success_response_documentation(200, "Selected branch requests"), **ERRORS},
)
async def list_requests(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    status: Annotated[Literal["pending", "completed", "rejected"] | None, Query()] = None,
    kind: Annotated[Literal["letter", "custom"] | None, Query()] = None,
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[LetterRequestResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: LetterRequestService(connection).list_admin(
            principal,
            selected,
            LetterRequestListQuery(status, kind, employee_id, limit),
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.get(
    "/{request_id}",
    response_model=DataResponse[LetterRequestResponse],
    operation_id="get_letter_request",
    responses={**success_response_documentation(200, "Request detail"), **ERRORS},
)
async def get_request(
    request_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[LetterRequestResponse]:
    branch_id, selected = _selected_scope(request, principal)
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: LetterRequestService(connection).get(
            principal, branch_id, request_id
        ),
    )
    return DataResponse(data=result)


async def _decision(
    *,
    request_id: uuid.UUID,
    request: Request,
    body: LetterRequestDecisionRequest | LetterRequestRejectRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    command: Literal["complete", "reject"],
) -> JSONResponse:
    async def mutate(service: LetterRequestService) -> IdempotentResponse:
        if command == "complete":
            result = await service.complete(
                principal, selected, request_id, body.expected_requested_at
            )
        else:
            assert isinstance(body, LetterRequestRejectRequest)
            result = await service.reject(
                principal,
                selected,
                request_id,
                body.expected_requested_at,
                body.reason,
            )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "letter_request",
            request_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=f"{command}_letter_request",
        method="POST",
        route_parameters={"requestId": str(request_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=selected,
    )


@router.post("/{request_id}/complete", operation_id="complete_letter_request", responses=ERRORS)
async def complete_request(
    request_id: uuid.UUID,
    request: Request,
    body: LetterRequestDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decision(
        request_id=request_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="complete",
    )


@router.post("/{request_id}/reject", operation_id="reject_letter_request", responses=ERRORS)
async def reject_request(
    request_id: uuid.UUID,
    request: Request,
    body: LetterRequestRejectRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decision(
        request_id=request_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="reject",
    )


@router.get(
    "/{request_id}/print-source",
    response_model=DataResponse[LetterRequestPrintSource],
    operation_id="get_letter_request_print_source",
    responses={**success_response_documentation(200, "Completed request source"), **ERRORS},
)
async def get_print_source(
    request_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[LetterRequestPrintSource]:
    branch_id, selected = _selected_scope(request, principal)
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: LetterRequestService(connection).print_source(
            principal, branch_id, request_id
        ),
    )
    return DataResponse(data=result)
