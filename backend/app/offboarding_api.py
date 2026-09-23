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
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.offboarding import (
    OffboardingChecklistResponse,
    OffboardingLetterSource,
    OffboardingTaskCreateRequest,
    OffboardingTaskUpdateRequest,
    OffboardingVisaRequest,
    SettlementCompleteRequest,
    SettlementInputs,
    SettlementPreviewResponse,
)
from app.services.idempotency import IdempotentResponse
from app.services.offboarding import OffboardingService

router = APIRouter(prefix="/api/v1/offboarding", tags=["offboarding"])
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
    "employment_transition_conflict",
    "manager_reassignment_conflict",
    "offboarding_blocked",
    "settlement_policy_unavailable",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> OffboardingService:
    return OffboardingService(connection, request.app.state.employee_cursor_codec)


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
    mutate: Callable[[OffboardingService], Awaitable[IdempotentResponse]],
) -> JSONResponse:
    async def run(connection: AsyncConnection) -> IdempotentResponse:
        return await mutate(_service(request, connection))

    async def authorize(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        await _service(request, connection).authorize_replay(
            principal, branch_id, kind, resource_id
        )

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=branch_id,
        operation_id=operation_id,
        method=method,
        route_parameters=route_parameters,
        body=body,
        resource_authorizer=authorize,
        mutation=run,
    )


@router.get(
    "",
    response_model=CollectionResponse[OffboardingChecklistResponse],
    operation_id="list_offboarding_checklists",
    responses={
        **success_response_documentation(200, "Selected branch offboarding checklists"),
        **ERRORS,
    },
)
async def list_checklists(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[OffboardingChecklistResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list(principal, selected, limit),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.get(
    "/{checklist_id}",
    response_model=DataResponse[OffboardingChecklistResponse],
    operation_id="get_offboarding_checklist",
    responses={**success_response_documentation(200, "Offboarding checklist"), **ERRORS},
)
async def get_checklist(
    checklist_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[OffboardingChecklistResponse]:
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).get(
            principal, selected, checklist_id
        ),
    )
    return DataResponse(data=result)


@router.post(
    "/{employee_id}/initialize", operation_id="initialize_offboarding_checklist", responses=ERRORS
)
async def initialize(
    employee_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: OffboardingService) -> IdempotentResponse:
        result = await service.initialize(principal, selected, employee_id)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/offboarding/{result.id}",
            "offboarding_checklist",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="initialize_offboarding_checklist",
        method="POST",
        route_parameters={"employeeId": str(employee_id)},
        body={},
        mutate=mutate,
    )


@router.post("/{checklist_id}/tasks", operation_id="add_offboarding_task", responses=ERRORS)
async def add_task(
    checklist_id: uuid.UUID,
    body: OffboardingTaskCreateRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: OffboardingService) -> IdempotentResponse:
        result = await service.add_task(principal, selected, checklist_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "offboarding_checklist",
            checklist_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="add_offboarding_task",
        method="POST",
        route_parameters={"checklistId": str(checklist_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


async def _task_change(
    *,
    checklist_id: uuid.UUID,
    task_id: uuid.UUID,
    command: str,
    body: OffboardingTaskUpdateRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
) -> JSONResponse:
    async def mutate(service: OffboardingService) -> IdempotentResponse:
        if command == "delete":
            result = await service.delete_task(principal, selected, checklist_id, task_id, body)
        else:
            result = await service.update_task(
                principal, selected, checklist_id, task_id, body, complete=command == "complete"
            )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "offboarding_checklist",
            checklist_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=f"{command}_offboarding_task",
        method="DELETE" if command == "delete" else "POST",
        route_parameters={"checklistId": str(checklist_id), "taskId": str(task_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post(
    "/{checklist_id}/tasks/{task_id}/complete",
    operation_id="complete_offboarding_task",
    responses=ERRORS,
)
async def complete_task(
    checklist_id: uuid.UUID,
    task_id: uuid.UUID,
    body: OffboardingTaskUpdateRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _task_change(
        checklist_id=checklist_id,
        task_id=task_id,
        command="complete",
        body=body,
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
    )


@router.post(
    "/{checklist_id}/tasks/{task_id}/reopen",
    operation_id="reopen_offboarding_task",
    responses=ERRORS,
)
async def reopen_task(
    checklist_id: uuid.UUID,
    task_id: uuid.UUID,
    body: OffboardingTaskUpdateRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _task_change(
        checklist_id=checklist_id,
        task_id=task_id,
        command="reopen",
        body=body,
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
    )


@router.delete(
    "/{checklist_id}/tasks/{task_id}", operation_id="delete_offboarding_task", responses=ERRORS
)
async def delete_task(
    checklist_id: uuid.UUID,
    task_id: uuid.UUID,
    body: OffboardingTaskUpdateRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _task_change(
        checklist_id=checklist_id,
        task_id=task_id,
        command="delete",
        body=body,
        request=request,
        claims=claims,
        principal=principal,
        selected=selected,
    )


@router.post("/{checklist_id}/visa", operation_id="advance_offboarding_visa", responses=ERRORS)
async def update_visa(
    checklist_id: uuid.UUID,
    body: OffboardingVisaRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: OffboardingService) -> IdempotentResponse:
        result = await service.update_visa(principal, selected, checklist_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "offboarding_checklist",
            checklist_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="advance_offboarding_visa",
        method="POST",
        route_parameters={"checklistId": str(checklist_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post(
    "/{checklist_id}/settlement/preview",
    response_model=DataResponse[SettlementPreviewResponse],
    operation_id="preview_final_settlement",
    responses={**success_response_documentation(200, "Final settlement preview"), **ERRORS},
)
async def preview(
    checklist_id: uuid.UUID,
    body: SettlementInputs,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[SettlementPreviewResponse]:
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).preview(
            principal, selected, checklist_id, body
        ),
    )
    return DataResponse(data=result)


@router.post("/{checklist_id}/complete", operation_id="complete_offboarding", responses=ERRORS)
async def complete(
    checklist_id: uuid.UUID,
    body: SettlementCompleteRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: OffboardingService) -> IdempotentResponse:
        result = await service.complete(principal, selected, checklist_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "offboarding_checklist",
            checklist_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="complete_offboarding",
        method="POST",
        route_parameters={"checklistId": str(checklist_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.get(
    "/{checklist_id}/letter-source",
    response_model=DataResponse[OffboardingLetterSource],
    operation_id="get_offboarding_letter_source",
    responses={**success_response_documentation(200, "Offboarding letter source"), **ERRORS},
)
async def letter_source(
    checklist_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[OffboardingLetterSource]:
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).letter_source(
            principal, selected, checklist_id
        ),
    )
    return DataResponse(data=result)
