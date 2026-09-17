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
from app.schemas.payroll import (
    PERIOD,
    PayrollCreateRequest,
    PayrollEntriesRequest,
    PayrollRepeatRequest,
    PayrollRunDetailResponse,
    PayrollRunResponse,
    PayrollVersionRequest,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.payroll import PayrollListQuery, PayrollService

router = APIRouter(prefix="/api/v1/payroll-runs", tags=["payroll"])

ERROR_CODES = (
    "invalid_request",
    "validation_failed",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "invalid_branch",
    "branch_required",
    "stale_financial_state",
    "invalid_cursor",
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
ERRORS = error_response_documentation(*ERROR_CODES)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> PayrollService:
    return PayrollService(connection, request.app.state.payroll_cursor_codec)


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


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
    operation_id: str,
    method: str,
    route_parameters: dict[str, object],
    body: dict[str, object],
    mutate: Callable[[PayrollService], Awaitable[IdempotentResponse]],
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
                mutation=lambda: mutate(service),
            )
        except ServiceExecutionError as error:
            if error.code == "idempotency_conflict":
                raise ServiceExecutionError("idempotency_key_reused") from None
            raise

    outcome = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=operation,
    )
    return _json_response(outcome)


@router.get(
    "",
    response_model=CollectionResponse[PayrollRunResponse],
    operation_id="list_payroll_runs",
    responses={**success_response_documentation(200, "Selected-branch payroll runs"), **ERRORS},
)
async def list_payroll_runs(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    period: Annotated[str | None, Query(max_length=7)] = None,
    run_status: Annotated[str | None, Query(alias="status")] = None,
    approval_status: Annotated[str | None, Query(alias="approvalStatus")] = None,
) -> CollectionResponse[PayrollRunResponse]:
    if (
        (period is not None and PERIOD.fullmatch(period) is None)
        or (run_status is not None and run_status not in {"draft", "generated"})
        or (
            approval_status is not None
            and approval_status not in {"draft", "pending_approval", "approved"}
        )
    ):
        raise ServiceExecutionError("validation_failed")
    query = PayrollListQuery(limit, cursor, period, run_status, approval_status)
    items, next_cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_runs(
            principal, selected, query
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/{run_id}",
    response_model=DataResponse[PayrollRunDetailResponse],
    operation_id="get_payroll_run",
    responses={**success_response_documentation(200, "Payroll draft detail"), **ERRORS},
)
async def get_payroll_run(
    run_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[PayrollRunDetailResponse]:
    result = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).detail(
            principal, selected, run_id
        ),
    )
    return DataResponse(data=result)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[PayrollRunDetailResponse],
    operation_id="create_payroll_run",
    responses={**success_response_documentation(201, "Payroll draft created"), **ERRORS},
)
async def create_payroll_run(
    request: Request,
    body: PayrollCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: PayrollService) -> IdempotentResponse:
        result = await service.create(principal, selected, body)
        return IdempotentResponse(
            status=201,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=f"/api/v1/payroll-runs/{result.id}",
            resource_kind="payroll_run",
            resource_id=result.id,
        )

    return await _idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_payroll_run",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


async def _command(
    *,
    request: Request,
    body: PayrollRepeatRequest | PayrollVersionRequest | PayrollEntriesRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    run_id: uuid.UUID,
    operation_id: str,
    method: str,
    mutate_result: Callable[[PayrollService], Awaitable[PayrollRunDetailResponse | None]],
    creates_resource: bool = False,
) -> JSONResponse:
    async def mutate(service: PayrollService) -> IdempotentResponse:
        result = await mutate_result(service)
        response_body: dict[str, object]
        if result is None:
            response_body = {"data": {"id": str(run_id), "deleted": True}}
        else:
            response_body = DataResponse(data=result).model_dump(mode="json", by_alias=True)
        resource_id = result.id if creates_resource and result is not None else run_id
        return IdempotentResponse(
            status=201 if creates_resource else 200,
            body=response_body,
            location=f"/api/v1/payroll-runs/{resource_id}" if creates_resource else None,
            resource_kind="payroll_run",
            resource_id=resource_id,
        )

    return await _idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=operation_id,
        method=method,
        route_parameters={"runId": str(run_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post("/{run_id}/repeat", operation_id="repeat_payroll_run", responses=ERRORS)
async def repeat_payroll_run(
    run_id: uuid.UUID,
    request: Request,
    body: PayrollRepeatRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="repeat_payroll_run",
        method="POST",
        mutate_result=lambda service: service.repeat(principal, selected, run_id, body),
        creates_resource=True,
    )


@router.post("/{run_id}/refresh", operation_id="refresh_payroll_run", responses=ERRORS)
async def refresh_payroll_run(
    run_id: uuid.UUID,
    request: Request,
    body: PayrollVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="refresh_payroll_run",
        method="POST",
        mutate_result=lambda service: service.refresh(principal, selected, run_id, body),
    )


@router.put("/{run_id}/entries", operation_id="replace_payroll_entries", responses=ERRORS)
async def replace_payroll_entries(
    run_id: uuid.UUID,
    request: Request,
    body: PayrollEntriesRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="replace_payroll_entries",
        method="PUT",
        mutate_result=lambda service: service.save_entries(principal, selected, run_id, body),
    )


@router.delete("/{run_id}", operation_id="delete_payroll_run", responses=ERRORS)
async def delete_payroll_run(
    run_id: uuid.UUID,
    request: Request,
    body: PayrollVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def delete(service: PayrollService) -> None:
        await service.delete(principal, selected, run_id, body)

    return await _command(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="delete_payroll_run",
        method="DELETE",
        mutate_result=delete,
    )
