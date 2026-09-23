from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import date
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
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.incidents import (
    IncidentCorrectiveActionRequest,
    IncidentCreateRequest,
    IncidentInvestigationRequest,
    IncidentResponse,
    IncidentUpdateRequest,
    IncidentVersionRequest,
)
from app.services.idempotency import IdempotentResponse
from app.services.incidents import IncidentListQuery, IncidentService

router = APIRouter(prefix="/api/v1/clinical-incidents", tags=["clinical-incidents"])
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
    mutate: Callable[[IncidentService], Awaitable[IdempotentResponse]],
) -> JSONResponse:
    async def run(connection: AsyncConnection) -> IdempotentResponse:
        return await mutate(IncidentService(connection))

    async def authorize_replay(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        await IncidentService(connection).authorize_replay(principal, branch_id, kind, resource_id)

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
        resource_authorizer=authorize_replay,
        mutation=run,
    )


@router.get(
    "",
    response_model=CollectionResponse[IncidentResponse],
    operation_id="list_clinical_incidents",
    responses={**success_response_documentation(200, "Clinical incidents"), **ERRORS},
)
async def list_clinical_incidents(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    incident_type: Annotated[str | None, Query(alias="type")] = None,
    severity: str | None = None,
    incident_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[IncidentResponse]:
    if date_from is not None and date_to is not None and date_to < date_from:
        raise api_error("validation_failed")
    if (
        incident_type
        not in {
            None,
            "patient_safety",
            "medication_error",
            "injury",
            "needlestick",
            "infection",
            "equipment",
            "near_miss",
            "workplace",
            "other",
        }
        or severity not in {None, "low", "moderate", "high", "critical"}
        or incident_status
        not in {
            None,
            "open",
            "investigating",
            "closed",
        }
    ):
        raise api_error("validation_failed")
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: IncidentService(connection).list(
            principal,
            selected,
            IncidentListQuery(date_from, date_to, incident_type, severity, incident_status, limit),
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.post("", operation_id="create_clinical_incident", responses=ERRORS)
async def create_clinical_incident(
    request: Request,
    body: IncidentCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: IncidentService) -> IdempotentResponse:
        result = await service.create(principal, selected, body)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/clinical-incidents/{result.id}",
            "incident_report",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_clinical_incident",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.patch("/{incident_id}", operation_id="update_clinical_incident", responses=ERRORS)
async def update_clinical_incident(
    incident_id: uuid.UUID,
    request: Request,
    body: IncidentUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: IncidentService) -> IdempotentResponse:
        result = await service.update(principal, selected, incident_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "incident_report",
            incident_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="update_clinical_incident",
        method="PATCH",
        route_parameters={"incidentId": str(incident_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


async def _incident_command(
    *,
    incident_id: uuid.UUID,
    request: Request,
    body: IncidentInvestigationRequest | IncidentCorrectiveActionRequest | IncidentVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID,
    command: str,
) -> JSONResponse:
    async def mutate(service: IncidentService) -> IdempotentResponse:
        if isinstance(body, IncidentInvestigationRequest):
            result = await service.investigate(principal, selected, incident_id, body)
        elif isinstance(body, IncidentCorrectiveActionRequest):
            result = await service.corrective_action(principal, selected, incident_id, body)
        else:
            result = await service.close(principal, selected, incident_id, body.expected_updated_at)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "incident_report",
            incident_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id=f"{command}_clinical_incident",
        method="POST",
        route_parameters={"incidentId": str(incident_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post(
    "/{incident_id}/investigate", operation_id="investigate_clinical_incident", responses=ERRORS
)
async def investigate_clinical_incident(
    incident_id: uuid.UUID,
    request: Request,
    body: IncidentInvestigationRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _incident_command(
        incident_id=incident_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="investigate",
    )


@router.post(
    "/{incident_id}/corrective-action",
    operation_id="record_clinical_incident_corrective_action",
    responses=ERRORS,
)
async def record_clinical_incident_corrective_action(
    incident_id: uuid.UUID,
    request: Request,
    body: IncidentCorrectiveActionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _incident_command(
        incident_id=incident_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="corrective_action",
    )


@router.post("/{incident_id}/close", operation_id="close_clinical_incident", responses=ERRORS)
async def close_clinical_incident(
    incident_id: uuid.UUID,
    request: Request,
    body: IncidentVersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _incident_command(
        incident_id=incident_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        selected=selected,
        command="close",
    )
