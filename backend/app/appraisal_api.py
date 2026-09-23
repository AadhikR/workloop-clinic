from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, cast

from fastapi import APIRouter, Query, Request
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
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.models.identity import AppRole
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.appraisals import (
    AppraisalCalibrationRequest,
    AppraisalCycleCreateRequest,
    AppraisalCycleResponse,
    AppraisalCycleUpdateRequest,
    AppraisalGenerationResponse,
    AppraisalResponse,
    AppraisalReviewRequest,
    AppraisalSectionRatingRequest,
    AppraisalVersionRequest,
    DeletedAppraisalCycleResponse,
)
from app.services.appraisals import AppraisalCycleListQuery, AppraisalService
from app.services.execution import ServiceExecutionError
from app.services.idempotency import IdempotentResponse

cycle_router = APIRouter(prefix="/api/v1/appraisal-cycles", tags=["appraisals"])
appraisal_router = APIRouter(prefix="/api/v1/appraisals", tags=["appraisals"])
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
    mutate: Callable[[AppraisalService], Awaitable[IdempotentResponse]],
    selected_admin_branch_id: uuid.UUID | None,
    authorize: bool = True,
) -> JSONResponse:
    async def run(connection: AsyncConnection) -> IdempotentResponse:
        return await mutate(AppraisalService(connection))

    async def authorize_replay(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        if authorize:
            await AppraisalService(connection).authorize_replay(
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


@cycle_router.get(
    "",
    response_model=CollectionResponse[AppraisalCycleResponse],
    operation_id="list_appraisal_cycles",
    responses={**success_response_documentation(200, "Appraisal cycles"), **ERRORS},
)
async def list_appraisal_cycles(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[AppraisalCycleResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: AppraisalService(connection).list_cycles(
            principal, selected, AppraisalCycleListQuery(limit)
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@cycle_router.post("", operation_id="create_appraisal_cycle", responses=ERRORS)
async def create_appraisal_cycle(
    request: Request,
    body: AppraisalCycleCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AppraisalService) -> IdempotentResponse:
        result = await service.create_cycle(principal, selected, body)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/appraisal-cycles/{result.id}",
            "appraisal_cycle",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_appraisal_cycle",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=selected,
    )


@cycle_router.patch("/{cycle_id}", operation_id="update_appraisal_cycle", responses=ERRORS)
async def update_appraisal_cycle(
    cycle_id: uuid.UUID,
    request: Request,
    body: AppraisalCycleUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AppraisalService) -> IdempotentResponse:
        result = await service.update_cycle(principal, selected, cycle_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "appraisal_cycle",
            cycle_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="update_appraisal_cycle",
        method="PATCH",
        route_parameters={"cycleId": str(cycle_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=selected,
    )


async def _cycle_command(
    *,
    cycle_id: uuid.UUID,
    request: Request,
    body: AppraisalVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    command: str,
) -> JSONResponse:
    async def mutate(service: AppraisalService) -> IdempotentResponse:
        if command == "activate":
            result = await service.activate_cycle(
                principal, selected, cycle_id, body.expected_updated_at
            )
        elif command == "generate":
            result = await service.generate(principal, selected, cycle_id, body.expected_updated_at)
        elif command == "close":
            result = await service.close_cycle(
                principal, selected, cycle_id, body.expected_updated_at
            )
        else:
            raise ServiceExecutionError("operation_not_permitted")
        resource_id = (
            result.cycle_id if isinstance(result, AppraisalGenerationResponse) else result.id
        )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "appraisal_cycle",
            resource_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=f"{command}_appraisal_cycle",
        method="POST",
        route_parameters={"cycleId": str(cycle_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=selected,
    )


@cycle_router.post(
    "/{cycle_id}/activate", operation_id="activate_appraisal_cycle", responses=ERRORS
)
async def activate_appraisal_cycle(
    cycle_id: uuid.UUID,
    request: Request,
    body: AppraisalVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _cycle_command(
        cycle_id=cycle_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="activate",
    )


@cycle_router.post("/{cycle_id}/generate", operation_id="generate_appraisals", responses=ERRORS)
async def generate_appraisals(
    cycle_id: uuid.UUID,
    request: Request,
    body: AppraisalVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _cycle_command(
        cycle_id=cycle_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="generate",
    )


@cycle_router.post("/{cycle_id}/close", operation_id="close_appraisal_cycle", responses=ERRORS)
async def close_appraisal_cycle(
    cycle_id: uuid.UUID,
    request: Request,
    body: AppraisalVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _cycle_command(
        cycle_id=cycle_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="close",
    )


@cycle_router.delete("/{cycle_id}", operation_id="delete_appraisal_cycle", responses=ERRORS)
async def delete_appraisal_cycle(
    cycle_id: uuid.UUID,
    request: Request,
    body: AppraisalVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AppraisalService) -> IdempotentResponse:
        await service.delete_cycle(principal, selected, cycle_id, body.expected_updated_at)
        response = DataResponse(data=DeletedAppraisalCycleResponse(id=cycle_id, deleted=True))
        return IdempotentResponse(
            200,
            response.model_dump(mode="json", by_alias=True),
            None,
            "appraisal_cycle",
            cycle_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="delete_appraisal_cycle",
        method="DELETE",
        route_parameters={"cycleId": str(cycle_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=selected,
        authorize=False,
    )


async def _staff_list(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    scope: str,
    limit: int,
) -> CollectionResponse[AppraisalResponse]:
    if principal.branch_id is None:
        raise ServiceExecutionError("operation_not_permitted")
    branch_id = principal.branch_id
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: AppraisalService(connection).list_appraisals(
            principal, branch_id, scope=scope, limit=limit
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@appraisal_router.get("/self", operation_id="list_self_appraisals", responses=ERRORS)
async def list_self_appraisals(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[AppraisalResponse]:
    return await _staff_list(
        request=request, claims=claims, principal=principal, scope="self", limit=limit
    )


@appraisal_router.get(
    "/direct-reports", operation_id="list_direct_report_appraisals", responses=ERRORS
)
async def list_direct_report_appraisals(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[AppraisalResponse]:
    return await _staff_list(
        request=request, claims=claims, principal=principal, scope="direct_report", limit=limit
    )


@appraisal_router.put(
    "/{appraisal_id}/sections/{section_id}",
    operation_id="rate_appraisal_section",
    responses=ERRORS,
)
async def rate_appraisal_section(
    appraisal_id: uuid.UUID,
    section_id: uuid.UUID,
    request: Request,
    body: AppraisalSectionRatingRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None or principal.role is not AppRole.MANAGER:
        raise ServiceExecutionError("operation_not_permitted")
    branch_id = principal.branch_id

    async def mutate(service: AppraisalService) -> IdempotentResponse:
        result = await service.rate_section(principal, branch_id, appraisal_id, section_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "appraisal",
            appraisal_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="rate_appraisal_section",
        method="PUT",
        route_parameters={"appraisalId": str(appraisal_id), "sectionId": str(section_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=None,
    )


async def _admin_appraisal_command(
    *,
    appraisal_id: uuid.UUID,
    request: Request,
    body: AppraisalReviewRequest | AppraisalCalibrationRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    command: str,
) -> JSONResponse:
    async def mutate(service: AppraisalService) -> IdempotentResponse:
        result = (
            await service.review(principal, selected, appraisal_id, body)
            if isinstance(body, AppraisalReviewRequest)
            else await service.calibrate(principal, selected, appraisal_id, body)
        )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "appraisal",
            appraisal_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=f"{command}_appraisal",
        method="POST",
        route_parameters={"appraisalId": str(appraisal_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        selected_admin_branch_id=selected,
    )


@appraisal_router.post("/{appraisal_id}/review", operation_id="review_appraisal", responses=ERRORS)
async def review_appraisal(
    appraisal_id: uuid.UUID,
    request: Request,
    body: AppraisalReviewRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _admin_appraisal_command(
        appraisal_id=appraisal_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="review",
    )


@appraisal_router.post(
    "/{appraisal_id}/calibrate", operation_id="calibrate_appraisal", responses=ERRORS
)
async def calibrate_appraisal(
    appraisal_id: uuid.UUID,
    request: Request,
    body: AppraisalCalibrationRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _admin_appraisal_command(
        appraisal_id=appraisal_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="calibrate",
    )
