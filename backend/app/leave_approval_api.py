from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncConnection

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
from app.http.validation import parse_pagination, validate_query_parameters
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.leave_approval import (
    LeaveApprovalDelegateCreate,
    LeaveApprovalDelegateDelete,
    LeaveApprovalDelegateResponse,
    LeaveApprovalDelegateUpdate,
    LeaveAuditEntryResponse,
    LeaveDecisionRequest,
    LeaveQueueItemResponse,
)
from app.schemas.leave_balance import LeaveRequestResponse
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.leave_approval import ApprovalQueueQuery, LeaveApprovalService

router = APIRouter(prefix="/api/v1/leave", tags=["leave-approvals"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "request_too_large",
    "unsupported_media_type",
    "validation_failed",
    "invalid_branch",
    "branch_required",
    "state_conflict",
    "invalid_cursor",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> LeaveApprovalService:
    return LeaveApprovalService(connection, request.app.state.leave_balance_cursor_codec)


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _queue_query(request: Request) -> ApprovalQueueQuery:
    validate_query_parameters(request, allowed={"limit", "cursor"})
    try:
        pagination = parse_pagination(
            limit=request.query_params.get("limit"), cursor=request.query_params.get("cursor")
        )
    except ValueError:
        raise api_error("validation_failed") from None
    return ApprovalQueueQuery(limit=pagination.limit, cursor=pagination.cursor)


QueueQuery = Annotated[ApprovalQueueQuery, Depends(_queue_query)]


def _collection(
    data: list[LeaveQueueItemResponse], next_cursor: str | None, limit: int
) -> CollectionResponse[LeaveQueueItemResponse]:
    return CollectionResponse(
        data=data,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/approvals/queue",
    response_model=CollectionResponse[LeaveQueueItemResponse],
    operation_id="get_leave_approver_queue",
    responses={**success_response_documentation(200, "Leave approval queue"), **ERRORS},
)
async def approver_queue(
    request: Request,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
    query: QueueQuery,
) -> CollectionResponse[LeaveQueueItemResponse]:
    data, cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_staff_queue(
            principal, query
        ),
    )
    return _collection(data, cursor, query.limit)


@router.get(
    "/approvals/branch",
    response_model=CollectionResponse[LeaveQueueItemResponse],
    operation_id="get_admin_leave_approval_queue",
    responses={**success_response_documentation(200, "Branch leave approval queue"), **ERRORS},
)
async def admin_queue(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    query: QueueQuery,
) -> CollectionResponse[LeaveQueueItemResponse]:
    data, cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_admin_queue(
            principal, selected, query
        ),
    )
    return _collection(data, cursor, query.limit)


async def _decide(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    request_id: uuid.UUID,
    body: LeaveDecisionRequest,
    selected_branch_id: uuid.UUID | None,
    operation_id: str,
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    branch_id = selected_branch_id if selected_branch_id is not None else principal.branch_id
    if branch_id is None:
        raise api_error("operation_not_permitted")
    route_parameters: dict[str, object] = {"requestId": str(request_id)}
    command = IdempotencyCommand(
        key=key,
        operation_id=operation_id,
        method="POST",
        route_parameters=route_parameters,
        fingerprint=request_fingerprint(
            operation_id=operation_id,
            method="POST",
            route_parameters=route_parameters,
            effective_query_parameters={},
            body=body.model_dump(mode="json", by_alias=True),
        ),
        branch_id=branch_id,
    )

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def mutate() -> IdempotentResponse:
            result = (
                await service.decide_admin(principal, branch_id, request_id, body)
                if selected_branch_id is not None
                else await service.decide_staff(principal, request_id, body)
            )
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
                location=None,
                resource_kind="leave_request",
                resource_id=request_id,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=command,
            authorize_replay=lambda kind, resource_id: service.authorize_replay(
                principal, branch_id, kind, resource_id
            ),
            mutation=mutate,
        )

    result = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=operation,
    )
    headers = {"Cache-Control": "no-store"}
    if result.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=result.status, content=result.body, headers=headers)


@router.post(
    "/approvals/{request_id}/decision",
    response_model=DataResponse[LeaveRequestResponse],
    operation_id="decide_leave_as_approver",
    responses={**success_response_documentation(200, "Leave decision recorded"), **ERRORS},
)
async def decide_as_approver(
    request_id: uuid.UUID,
    request: Request,
    body: LeaveDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    return await _decide(
        request=request,
        claims=claims,
        principal=principal,
        request_id=request_id,
        body=body,
        selected_branch_id=None,
        operation_id="decide_leave_as_approver",
    )


@router.post(
    "/approvals/{request_id}/decision/branch",
    response_model=DataResponse[LeaveRequestResponse],
    operation_id="decide_leave_as_admin",
    responses={
        **success_response_documentation(200, "Administrator leave decision recorded"),
        **ERRORS,
    },
)
async def decide_as_admin(
    request_id: uuid.UUID,
    request: Request,
    body: LeaveDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decide(
        request=request,
        claims=claims,
        principal=principal,
        request_id=request_id,
        body=body,
        selected_branch_id=selected,
        operation_id="decide_leave_as_admin",
    )


@router.get(
    "/approvals/{request_id}/audit",
    response_model=DataResponse[list[LeaveAuditEntryResponse]],
    operation_id="get_leave_approval_audit",
    responses={**success_response_documentation(200, "Leave request audit"), **ERRORS},
)
async def staff_audit(
    request_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: StaffAuthorizationPrincipal,
) -> DataResponse[list[LeaveAuditEntryResponse]]:
    branch_id = principal.branch_id
    if branch_id is None:
        raise api_error("operation_not_permitted")
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_audit(
            principal, branch_id, request_id
        ),
    )
    return DataResponse(data=data)


@router.get(
    "/approvals/{request_id}/audit/branch",
    response_model=DataResponse[list[LeaveAuditEntryResponse]],
    operation_id="get_admin_leave_approval_audit",
    responses={**success_response_documentation(200, "Branch leave request audit"), **ERRORS},
)
async def admin_audit(
    request_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[list[LeaveAuditEntryResponse]]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_audit(
            principal, selected, request_id
        ),
    )
    return DataResponse(data=data)


@router.get(
    "/delegations/branch",
    response_model=DataResponse[list[LeaveApprovalDelegateResponse]],
    operation_id="get_leave_delegations",
    responses={**success_response_documentation(200, "Branch leave delegations"), **ERRORS},
)
async def list_delegations(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[list[LeaveApprovalDelegateResponse]]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_delegations(
            principal, selected
        ),
    )
    return DataResponse(data=data)


@router.post(
    "/delegations/branch",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[LeaveApprovalDelegateResponse],
    operation_id="create_leave_delegation",
    responses={**success_response_documentation(201, "Leave delegation created"), **ERRORS},
)
async def create_delegation(
    request: Request,
    body: LeaveApprovalDelegateCreate,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[LeaveApprovalDelegateResponse]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).create_delegation(
            principal, selected, body
        ),
    )
    return DataResponse(data=data)


@router.put(
    "/delegations/{delegation_id}/branch",
    response_model=DataResponse[LeaveApprovalDelegateResponse],
    operation_id="update_leave_delegation",
    responses={**success_response_documentation(200, "Leave delegation updated"), **ERRORS},
)
async def update_delegation(
    delegation_id: uuid.UUID,
    request: Request,
    body: LeaveApprovalDelegateUpdate,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[LeaveApprovalDelegateResponse]:
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).update_delegation(
            principal, selected, delegation_id, body
        ),
    )
    return DataResponse(data=data)


@router.delete(
    "/delegations/{delegation_id}/branch",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_leave_delegation",
    responses={204: {"description": "Leave delegation deleted"}, **ERRORS},
)
async def delete_delegation(
    delegation_id: uuid.UUID,
    request: Request,
    body: LeaveApprovalDelegateDelete,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> Response:
    await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).delete_delegation(
            principal, selected, delegation_id, body.expected_updated_at
        ),
    )
    return Response(status_code=204)
