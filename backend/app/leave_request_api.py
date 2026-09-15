from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from typing import cast

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import DataResponse
from app.models.identity import AppRole
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.leave_balance import LeaveRequestResponse
from app.schemas.leave_request import (
    AdminLeaveSubmissionRequest,
    LeaveCancellationRequest,
    LeaveSubmissionRequest,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.leave_attachment import ClaimedCleanup, LeaveAttachmentService
from app.services.leave_request import LeaveRequestService
from app.storage.base import StorageNotFoundError

router = APIRouter(prefix="/api/v1/leave/requests", tags=["leave-requests"])
logger = logging.getLogger(__name__)
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


def _service(connection: AsyncConnection) -> LeaveRequestService:
    return LeaveRequestService(connection)


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _response(outcome: IdempotentResponse) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if outcome.location is not None:
        headers["Location"] = outcome.location
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


async def _submit(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    body: LeaveSubmissionRequest,
    employee_id: uuid.UUID,
    selected_branch_id: uuid.UUID | None,
    operation_id: str,
    fingerprint_body: dict[str, object] | None = None,
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    body_values = cast(dict[str, object], body.model_dump(mode="json", by_alias=True))
    if fingerprint_body is None:
        fingerprint_body = body_values
    branch_id = selected_branch_id if principal.role is AppRole.ADMIN else principal.branch_id
    if branch_id is None:
        raise RuntimeError("authorized leave submission has no branch")
    command = IdempotencyCommand(
        key=key,
        operation_id=operation_id,
        method="POST",
        route_parameters={},
        fingerprint=request_fingerprint(
            operation_id=operation_id,
            method="POST",
            route_parameters={},
            effective_query_parameters={},
            body=fingerprint_body,
        ),
        branch_id=branch_id,
    )

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(connection)

        async def mutate() -> IdempotentResponse:
            leave_request = await service.submit(
                principal,
                body,
                employee_id=employee_id,
                selected_branch_id=selected_branch_id,
            )
            response_body = DataResponse(data=leave_request).model_dump(mode="json", by_alias=True)
            return IdempotentResponse(
                status=201,
                body=response_body,
                location=f"/api/v1/leave/requests/{leave_request.id}",
                resource_kind="leave_request",
                resource_id=leave_request.id,
            )

        return await _idempotency(request, connection).execute(
            principal=principal,
            command=command,
            authorize_replay=lambda kind, resource_id: service.authorize_replay(
                principal, branch_id, kind, resource_id
            ),
            mutation=mutate,
        )

    outcome = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=operation,
    )
    return _response(outcome)


@router.post(
    "/self",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[LeaveRequestResponse],
    operation_id="submit_employee_leave_request",
    responses={
        **success_response_documentation(201, "Submitted leave request", cache_control="no-store"),
        **ERRORS,
    },
)
async def submit_employee_leave_request(
    request: Request,
    body: LeaveSubmissionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER} or principal.employee_id is None:
        raise api_error("operation_not_permitted")
    return await _submit(
        request=request,
        claims=claims,
        principal=principal,
        body=body,
        employee_id=principal.employee_id,
        selected_branch_id=None,
        operation_id="submit_employee_leave_request",
    )


@router.post(
    "/branch",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[LeaveRequestResponse],
    operation_id="submit_admin_leave_request",
    responses={
        **success_response_documentation(
            201, "Submitted branch leave request", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def submit_admin_leave_request(
    request: Request,
    body: AdminLeaveSubmissionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> JSONResponse:
    if principal.role is not AppRole.ADMIN:
        raise api_error("operation_not_permitted")
    base = LeaveSubmissionRequest.model_validate(
        body.model_dump(exclude={"employee_id"}, by_alias=True)
    )
    return await _submit(
        request=request,
        claims=claims,
        principal=principal,
        body=base,
        employee_id=body.employee_id,
        selected_branch_id=selected_branch_id,
        operation_id="submit_admin_leave_request",
        fingerprint_body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
    )


async def _finish_cleanup(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected_branch_id: uuid.UUID | None,
    claimed: ClaimedCleanup,
) -> None:
    try:
        async with asyncio.timeout(45):
            with suppress(StorageNotFoundError):
                await request.app.state.object_storage.delete_object(key=claimed.object_key)
        await _executor(request).execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=selected_branch_id,
            operation=lambda connection: LeaveAttachmentService(
                connection,
                object_key_hmac_key=(
                    request.app.state.settings.decoded_attachment_object_key_hmac_key()
                ),
            ).complete_cleanup(claimed),
        )
    except Exception:
        logger.error(
            "leave_request_cancellation_cleanup_deferred",
            extra={"operation_id": str(claimed.operation_id), "error_code": "provider_error"},
        )


async def _cancel(
    *,
    request: Request,
    body: LeaveCancellationRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    request_id: uuid.UUID,
    selected_branch_id: uuid.UUID | None,
    operation_id: str,
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    branch_id = selected_branch_id if principal.role is AppRole.ADMIN else principal.branch_id
    if branch_id is None:
        raise RuntimeError("authorized leave cancellation has no branch")
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

    async def operation(
        connection: AsyncConnection,
    ) -> tuple[IdempotentResponse, ClaimedCleanup | None]:
        service = _service(connection)
        claimed_cleanup: ClaimedCleanup | None = None

        async def mutate() -> IdempotentResponse:
            nonlocal claimed_cleanup
            leave_request, claimed_cleanup = await service.cancel_with_cleanup(
                principal, request_id, selected_branch_id=selected_branch_id
            )
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=leave_request).model_dump(mode="json", by_alias=True),
                location=None,
                resource_kind="leave_request",
                resource_id=leave_request.id,
            )

        outcome = await _idempotency(request, connection).execute(
            principal=principal,
            command=command,
            authorize_replay=lambda kind, resource_id: service.authorize_replay(
                principal, branch_id, kind, resource_id
            ),
            mutation=mutate,
        )
        return outcome, claimed_cleanup

    outcome, claimed = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected_branch_id,
        operation=operation,
    )
    if claimed is not None:
        await _finish_cleanup(request, claims, principal, selected_branch_id, claimed)
    return _response(outcome)


@router.post(
    "/{request_id}/cancel/self",
    response_model=DataResponse[LeaveRequestResponse],
    operation_id="cancel_employee_leave_request",
    responses={
        **success_response_documentation(200, "Cancelled leave request", cache_control="no-store"),
        **ERRORS,
    },
)
async def cancel_employee_leave_request(
    request_id: uuid.UUID,
    request: Request,
    body: LeaveCancellationRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}:
        raise api_error("operation_not_permitted")
    return await _cancel(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        request_id=request_id,
        selected_branch_id=None,
        operation_id="cancel_employee_leave_request",
    )


@router.post(
    "/{request_id}/cancel/branch",
    response_model=DataResponse[LeaveRequestResponse],
    operation_id="cancel_admin_leave_request",
    responses={
        **success_response_documentation(
            200, "Cancelled approved leave request", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def cancel_admin_leave_request(
    request_id: uuid.UUID,
    request: Request,
    body: LeaveCancellationRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
) -> JSONResponse:
    if principal.role is not AppRole.ADMIN:
        raise api_error("operation_not_permitted")
    return await _cancel(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        request_id=request_id,
        selected_branch_id=selected_branch_id,
        operation_id="cancel_admin_leave_request",
    )
