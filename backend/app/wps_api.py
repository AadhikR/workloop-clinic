from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.db.output_audit import append_output_audit
from app.http.errors import error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.outputs import SifPreviewResponse
from app.schemas.wps import (
    PERIOD,
    ComplianceOverrideRequest,
    NafisReplaceRequest,
    NafisSnapshotResponse,
    SifInputResponse,
    WpsEntryRejectRequest,
    WpsEntryVersionRequest,
    WpsReasonRequest,
    WpsRunResponse,
    WpsSubmitRequest,
    WpsVersionRequest,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.outputs import delivery_headers, parse_sif_preview, render_sif
from app.services.wps import NafisListQuery, WpsService

router = APIRouter(prefix="/api/v1/payroll-runs", tags=["wps"])
nafis_router = APIRouter(prefix="/api/v1/nafis-snapshots", tags=["nafis"])

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
    "output_limit_exceeded",
    "internal_error",
)
ERRORS = error_response_documentation(*ERROR_CODES)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> WpsService:
    return WpsService(connection, request.app.state.payroll_cursor_codec)


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


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
    mutate: Callable[[WpsService], Awaitable[IdempotentResponse]],
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
    headers = {"Cache-Control": "no-store"}
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    if outcome.location is not None:
        headers["Location"] = outcome.location
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


async def _wps_command(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    run_id: uuid.UUID,
    operation_id: str,
    body: WpsVersionRequest | WpsSubmitRequest | WpsReasonRequest,
    mutate: Callable[[WpsService], Awaitable[WpsRunResponse]],
) -> JSONResponse:
    async def execute(service: WpsService) -> IdempotentResponse:
        result = await mutate(service)
        return IdempotentResponse(
            status=200,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=None,
            resource_kind="payroll_run",
            resource_id=run_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=operation_id,
        method="POST",
        route_parameters={"runId": str(run_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=execute,
    )


@router.get(
    "/{run_id}/wps",
    response_model=DataResponse[WpsRunResponse],
    responses={**success_response_documentation(200, "WPS state"), **ERRORS},
)
async def get_wps(
    run_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[WpsRunResponse]:
    result = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).get_wps(
            principal, selected, run_id
        ),
    )
    return DataResponse(data=result)


@router.get(
    "/{run_id}/sif-input",
    response_model=DataResponse[SifInputResponse],
    responses={**success_response_documentation(200, "Deterministic SIF input"), **ERRORS},
)
async def get_sif_input(
    run_id: uuid.UUID,
    response: Response,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    correction: Annotated[Literal["rejected"] | None, Query()] = None,
) -> DataResponse[SifInputResponse]:
    response.headers["Cache-Control"] = "no-store"
    result = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).sif_input(
            principal, selected, run_id, correction
        ),
    )
    return DataResponse(data=result)


async def _render_sif_output(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    run_id: uuid.UUID,
    scope: Literal["all", "rejected"],
    preview: bool,
):
    async def operation(connection: AsyncConnection):
        projection = await _service(request, connection).sif_input(
            principal,
            selected,
            run_id,
            "rejected" if scope == "rejected" else None,
        )
        output = render_sif(projection, scope=scope)
        records = parse_sif_preview(output) if preview else None
        await append_output_audit(
            connection,
            action="sif_previewed" if preview else "sif_exported",
            entity_type="payroll_run",
            entity_id=run_id,
            format="sif_preview" if preview else "sif",
            filter_digest=output.filter_digest,
            source_digest=output.source_digest,
            renderer_version=output.renderer_version,
            row_count=output.row_count,
            byte_count=len(output.content),
        )
        return output, records

    return await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=operation,
    )


@router.get(
    "/{run_id}/sif/preview",
    response_model=DataResponse[SifPreviewResponse],
    operation_id="preview_payroll_sif",
    responses={**success_response_documentation(200, "SIF preview"), **ERRORS},
)
async def preview_sif(
    run_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    scope: Annotated[Literal["all", "rejected"], Query()] = "all",
) -> DataResponse[SifPreviewResponse]:
    output, records = await _render_sif_output(
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        scope=scope,
        preview=True,
    )
    assert records is not None
    return DataResponse(
        data=SifPreviewResponse(
            filename=output.filename,
            source_digest=output.source_digest,
            renderer_version=output.renderer_version,
            byte_count=len(output.content),
            record_count=len(records),
            records=records,
        )
    )


@router.get(
    "/{run_id}/sif",
    response_class=Response,
    operation_id="download_payroll_sif",
    responses={**success_response_documentation(200, "SIF download"), **ERRORS},
)
async def download_sif(
    run_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    scope: Annotated[Literal["all", "rejected"], Query()] = "all",
) -> Response:
    output, _records = await _render_sif_output(
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        scope=scope,
        preview=False,
    )
    return Response(
        content=output.content,
        media_type=output.content_type,
        headers=delivery_headers(output, str(request.state.correlation_id)),
    )


@router.post("/{run_id}/wps/sif-generated", responses=ERRORS)
async def record_sif_projection(
    run_id: uuid.UUID,
    request: Request,
    body: WpsVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _wps_command(
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="record_sif_projection",
        body=body,
        mutate=lambda service: service.record_sif_projection(principal, selected, run_id, body),
    )


@router.post("/{run_id}/wps/submit", responses=ERRORS)
async def submit_wps(
    run_id: uuid.UUID,
    request: Request,
    body: WpsSubmitRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _wps_command(
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="submit_wps",
        body=body,
        mutate=lambda service: service.submit(principal, selected, run_id, body),
    )


@router.post("/{run_id}/wps/confirm", responses=ERRORS)
async def confirm_wps(
    run_id: uuid.UUID,
    request: Request,
    body: WpsVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _wps_command(
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="confirm_wps",
        body=body,
        mutate=lambda service: service.confirm(principal, selected, run_id, body),
    )


@router.post("/{run_id}/wps/fail", responses=ERRORS)
async def fail_wps(
    run_id: uuid.UUID,
    request: Request,
    body: WpsReasonRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _wps_command(
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
        run_id=run_id,
        operation_id="fail_wps",
        body=body,
        mutate=lambda service: service.fail(principal, selected, run_id, body),
    )


async def _entry_command(
    *,
    run_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: Request,
    body: WpsEntryVersionRequest | WpsEntryRejectRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    action: str,
) -> JSONResponse:
    async def execute(service: WpsService) -> IdempotentResponse:
        if action == "paid":
            result = await service.mark_entry_paid(
                principal,
                selected,
                run_id,
                entry_id,
                cast(WpsEntryVersionRequest, body),
            )
        else:
            result = await service.reject_entry(
                principal, selected, run_id, entry_id, cast(WpsEntryRejectRequest, body)
            )
        return IdempotentResponse(
            status=200,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=None,
            resource_kind="payroll_run",
            resource_id=run_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=f"mark_wps_entry_{action}",
        method="POST",
        route_parameters={"runId": str(run_id), "entryId": str(entry_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=execute,
    )


@router.post("/{run_id}/wps/entries/{entry_id}/paid", responses=ERRORS)
async def mark_wps_entry_paid(
    run_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: Request,
    body: WpsEntryVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _entry_command(
        run_id=run_id,
        entry_id=entry_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        action="paid",
    )


@router.post("/{run_id}/wps/entries/{entry_id}/reject", responses=ERRORS)
async def reject_wps_entry(
    run_id: uuid.UUID,
    entry_id: uuid.UUID,
    request: Request,
    body: WpsEntryRejectRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _entry_command(
        run_id=run_id,
        entry_id=entry_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        action="rejected",
    )


@router.post("/{run_id}/compliance-overrides", status_code=201, responses=ERRORS)
async def create_compliance_override(
    run_id: uuid.UUID,
    request: Request,
    body: ComplianceOverrideRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def execute(service: WpsService) -> IdempotentResponse:
        result = await service.create_compliance_override(principal, selected, run_id, body)
        return IdempotentResponse(
            status=201,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=f"/api/v1/payroll-runs/{run_id}/compliance-overrides/{result.id}",
            resource_kind="compliance_override",
            resource_id=result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_payroll_compliance_override",
        method="POST",
        route_parameters={"runId": str(run_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=execute,
    )


@nafis_router.get(
    "",
    response_model=CollectionResponse[NafisSnapshotResponse],
    responses={**success_response_documentation(200, "Selected-branch Nafis snapshots"), **ERRORS},
)
async def list_nafis_snapshots(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    period: Annotated[str | None, Query(max_length=7)] = None,
) -> CollectionResponse[NafisSnapshotResponse]:
    if period is not None and PERIOD.fullmatch(period) is None:
        raise ServiceExecutionError("validation_failed")
    items, next_cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_nafis(
            principal, selected, NafisListQuery(limit, cursor, period)
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@nafis_router.put("/{period}", responses=ERRORS)
async def replace_nafis_snapshot(
    period: str,
    request: Request,
    body: NafisReplaceRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    if PERIOD.fullmatch(period) is None:
        raise ServiceExecutionError("validation_failed")

    async def execute(service: WpsService) -> IdempotentResponse:
        result = await service.replace_nafis_snapshot(principal, selected, period, body)
        return IdempotentResponse(
            status=200,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=None,
            resource_kind="nafis_snapshot",
            resource_id=result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="replace_nafis_snapshot",
        method="PUT",
        route_parameters={"period": period},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=execute,
    )
