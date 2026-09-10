from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.dependencies import (
    AuthenticatedReadPrincipal,
    VerifiedAccessToken,
    operation_not_permitted_error,
)
from app.http.errors import error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.schemas import ApiSchema, DataResponse
from app.repositories.idempotency import IdempotencyRepository
from app.services.execution import AuthorizedServiceExecutor
from app.services.idempotency import IdempotencyCoordinator, IdempotencyStatus, RecoveryNamespaces

router = APIRouter(prefix="/api/v1", tags=["idempotency"])

IDEMPOTENCY_ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "origin_not_allowed",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "request_too_large",
    "unsupported_media_type",
    "validation_failed",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


class RecoveryNamespacesResponse(ApiSchema):
    current: str
    accepted: list[str]


class IdempotencyStatusResponse(ApiSchema):
    status: IdempotencyStatus


def _reject_branch_header(request: Request) -> None:
    if request.headers.getlist("x-workloop-branch-id"):
        raise operation_not_permitted_error()


@router.get(
    "/idempotency-recovery-namespaces",
    response_model=DataResponse[RecoveryNamespacesResponse],
    operation_id="get_idempotency_recovery_namespaces",
    responses={
        **success_response_documentation(
            200, "Accepted recovery namespaces", cache_control="no-store"
        ),
        **IDEMPOTENCY_ERRORS,
    },
)
async def get_recovery_namespaces(
    request: Request,
    _claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[RecoveryNamespacesResponse]:
    _reject_branch_header(request)
    namespaces: RecoveryNamespaces = request.app.state.idempotency_recovery_namespaces
    current, accepted = namespaces.for_user(principal.app_user_id)
    return DataResponse(data=RecoveryNamespacesResponse(current=current, accepted=accepted))


@router.get(
    "/idempotency-status",
    response_model=DataResponse[IdempotencyStatusResponse],
    operation_id="get_idempotency_status",
    responses={
        **success_response_documentation(
            200, "Idempotency request status", cache_control="no-store"
        ),
        **IDEMPOTENCY_ERRORS,
    },
)
async def get_idempotency_status(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[IdempotencyStatusResponse]:
    _reject_branch_header(request)
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotencyStatus:
        factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
        coordinator = (
            factory(connection)
            if factory is not None
            else IdempotencyCoordinator(IdempotencyRepository(connection))
        )
        return await coordinator.status(principal=principal, key=key)

    result = await executor.execute(claims=claims, principal=principal, operation=operation)
    return DataResponse(data=IdempotencyStatusResponse(status=result))
