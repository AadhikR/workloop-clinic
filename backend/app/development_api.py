from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, cast

from fastapi import APIRouter, Header, Query, Request
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
from app.models.identity import AppRole
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.development import (
    CertificationAdminCreateRequest,
    CertificationDecisionRequest,
    CertificationResponse,
    CertificationStaffCreateRequest,
    CmeRequirementRequest,
    CmeRequirementResponse,
    CmeSummaryResponse,
    DeletedDevelopmentResponse,
    TrainingAdminCreateRequest,
    TrainingCompleteRequest,
    TrainingResponse,
    TrainingStaffCreateRequest,
    TrainingUpdateRequest,
    VersionRequest,
)
from app.services.development import (
    CertificationListQuery,
    DevelopmentService,
    TrainingListQuery,
)
from app.services.idempotency import IdempotentResponse

training_router = APIRouter(prefix="/api/v1/training-records", tags=["training"])
certification_router = APIRouter(prefix="/api/v1/certifications", tags=["certifications"])
cme_router = APIRouter(prefix="/api/v1/cme", tags=["cme"])
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
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> DevelopmentService:
    return DevelopmentService(
        connection,
        scanner_definition=request.app.state.settings.malware_scanner_definition,
        object_key_hmac_key=request.app.state.settings.decoded_attachment_object_key_hmac_key(),
    )


def _staff_branch(principal: AuthorizationPrincipal, raw_branch: str | None) -> uuid.UUID:
    if principal.role is AppRole.ADMIN:
        if raw_branch is None:
            raise api_error("branch_required")
        try:
            branch_id = uuid.UUID(raw_branch)
        except ValueError:
            raise api_error("invalid_branch") from None
        if str(branch_id) != raw_branch:
            raise api_error("invalid_branch")
        return branch_id
    if raw_branch is not None or principal.branch_id is None:
        raise api_error("operation_not_permitted")
    return principal.branch_id


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
    mutate: Callable[[DevelopmentService], Awaitable[IdempotentResponse]],
    authorize: bool = True,
) -> JSONResponse:
    async def run(connection: AsyncConnection) -> IdempotentResponse:
        return await mutate(_service(request, connection))

    async def authorize_replay(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        if authorize:
            await _service(request, connection).authorize_replay(
                principal, branch_id, kind, resource_id
            )

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation_id=operation_id,
        method=method,
        route_parameters=route_parameters,
        body=body,
        resource_authorizer=authorize_replay,
        mutation=run,
    )


@training_router.get(
    "",
    response_model=CollectionResponse[TrainingResponse],
    operation_id="list_training_records",
    responses={**success_response_documentation(200, "Training records"), **ERRORS},
)
async def list_training_records(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    employee_id: Annotated[uuid.UUID | None, Query(alias="employeeId")] = None,
    year: Annotated[int | None, Query(ge=1900, le=9999)] = None,
    training_status: Annotated[str | None, Query(alias="status")] = None,
    training_type: Annotated[str | None, Query(alias="type", max_length=120)] = None,
    is_cme: Annotated[bool | None, Query(alias="isCme")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[TrainingResponse]:
    if training_status not in {None, "planned", "in_progress", "completed", "cancelled"}:
        raise api_error("validation_failed")
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_training(
            principal,
            selected,
            TrainingListQuery(employee_id, year, training_status, training_type, is_cme, limit),
            scope="admin",
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@training_router.post("", operation_id="create_training_record", responses=ERRORS)
async def create_training_record(
    request: Request,
    body: TrainingAdminCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.create_training(principal, selected, body, scope="admin")
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/training-records/{result.id}",
            "training_record",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_training_record",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


async def _staff_training_list(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    employee_id: uuid.UUID | None,
    limit: int,
    scope: str,
) -> CollectionResponse[TrainingResponse]:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    branch_id = principal.branch_id
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_training(
            principal,
            branch_id,
            TrainingListQuery(employee_id, None, None, None, None, limit),
            scope=scope,
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@training_router.get("/self", operation_id="list_self_training_records", responses=ERRORS)
async def list_self_training_records(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[TrainingResponse]:
    return await _staff_training_list(
        request=request,
        claims=claims,
        principal=principal,
        employee_id=None,
        limit=limit,
        scope="self",
    )


@training_router.post("/self", operation_id="create_self_training_record", responses=ERRORS)
async def create_self_training_record(
    request: Request,
    body: TrainingStaffCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None or body.employee_id is not None:
        raise api_error("operation_not_permitted")
    branch_id = principal.branch_id

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.create_training(principal, branch_id, body, scope="self")
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/training-records/{result.id}",
            "training_record",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="create_self_training_record",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@training_router.get(
    "/direct-reports", operation_id="list_direct_report_training_records", responses=ERRORS
)
async def list_direct_report_training_records(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    employee_id: Annotated[uuid.UUID, Query(alias="employeeId")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[TrainingResponse]:
    return await _staff_training_list(
        request=request,
        claims=claims,
        principal=principal,
        employee_id=employee_id,
        limit=limit,
        scope="direct_report",
    )


@training_router.post(
    "/direct-reports", operation_id="create_direct_report_training_record", responses=ERRORS
)
async def create_direct_report_training_record(
    request: Request,
    body: TrainingStaffCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None or body.employee_id is None:
        raise api_error("validation_failed")
    branch_id = principal.branch_id

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.create_training(principal, branch_id, body, scope="direct_report")
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/training-records/{result.id}",
            "training_record",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="create_direct_report_training_record",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@training_router.patch("/{record_id}", operation_id="update_training_record", responses=ERRORS)
async def update_training_record(
    record_id: uuid.UUID,
    request: Request,
    body: TrainingUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> JSONResponse:
    branch_id = _staff_branch(principal, selected_branch)
    scope = "admin" if principal.role is AppRole.ADMIN else "staff"

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.update_training(principal, branch_id, record_id, body, scope=scope)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "training_record",
            record_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="update_training_record",
        method="PATCH",
        route_parameters={"recordId": str(record_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@training_router.post(
    "/{record_id}/complete", operation_id="complete_training_record", responses=ERRORS
)
async def complete_training_record(
    record_id: uuid.UUID,
    request: Request,
    body: TrainingCompleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> JSONResponse:
    branch_id = _staff_branch(principal, selected_branch)
    scope = "admin" if principal.role is AppRole.ADMIN else "direct_report"

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.complete_training(principal, branch_id, record_id, body, scope=scope)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "training_record",
            record_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="complete_training_record",
        method="POST",
        route_parameters={"recordId": str(record_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@training_router.delete("/{record_id}", operation_id="delete_training_record", responses=ERRORS)
async def delete_training_record(
    record_id: uuid.UUID,
    request: Request,
    body: VersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> JSONResponse:
    branch_id = _staff_branch(principal, selected_branch)
    scope = "admin" if principal.role is AppRole.ADMIN else "staff"

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        await service.delete_training(
            principal,
            branch_id,
            record_id,
            body.expected_updated_at,
            scope=scope,
        )
        response = DataResponse(data=DeletedDevelopmentResponse(id=record_id, deleted=True))
        return IdempotentResponse(
            200,
            response.model_dump(mode="json", by_alias=True),
            None,
            "training_record",
            record_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="delete_training_record",
        method="DELETE",
        route_parameters={"recordId": str(record_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        authorize=False,
    )


@certification_router.get("", operation_id="list_certifications", responses=ERRORS)
async def list_certifications(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    employee_id: Annotated[uuid.UUID | None, Query(alias="employeeId")] = None,
    certification_status: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[CertificationResponse]:
    if certification_status not in {None, "pending_review", "verified", "rejected"}:
        raise api_error("validation_failed")
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_certifications(
            principal,
            selected,
            CertificationListQuery(employee_id, certification_status, limit),
            scope="admin",
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@certification_router.post("", operation_id="create_certification", responses=ERRORS)
async def create_certification(
    request: Request,
    body: CertificationAdminCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.create_certification(principal, selected, body, scope="admin")
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/certifications/{result.id}",
            "certification",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_certification",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


async def _staff_certification_list(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    employee_id: uuid.UUID | None,
    limit: int,
    scope: str,
) -> CollectionResponse[CertificationResponse]:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    branch_id = principal.branch_id
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_certifications(
            principal,
            branch_id,
            CertificationListQuery(employee_id, None, limit),
            scope=scope,
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@certification_router.get("/self", operation_id="list_self_certifications", responses=ERRORS)
async def list_self_certifications(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[CertificationResponse]:
    return await _staff_certification_list(
        request=request,
        claims=claims,
        principal=principal,
        employee_id=None,
        limit=limit,
        scope="self",
    )


async def _create_staff_certification(
    *,
    request: Request,
    body: CertificationStaffCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    scope: str,
) -> JSONResponse:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    if scope == "self" and body.employee_id is not None:
        raise api_error("operation_not_permitted")
    if scope == "direct_report" and body.employee_id is None:
        raise api_error("validation_failed")
    branch_id = principal.branch_id

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.create_certification(principal, branch_id, body, scope=scope)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/certifications/{result.id}",
            "certification",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id=f"create_{scope}_certification",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@certification_router.post("/self", operation_id="create_self_certification", responses=ERRORS)
async def create_self_certification(
    request: Request,
    body: CertificationStaffCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    return await _create_staff_certification(
        request=request, body=body, claims=claims, principal=principal, scope="self"
    )


@certification_router.get(
    "/direct-reports", operation_id="list_direct_report_certifications", responses=ERRORS
)
async def list_direct_report_certifications(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    employee_id: Annotated[uuid.UUID, Query(alias="employeeId")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[CertificationResponse]:
    return await _staff_certification_list(
        request=request,
        claims=claims,
        principal=principal,
        employee_id=employee_id,
        limit=limit,
        scope="direct_report",
    )


@certification_router.post(
    "/direct-reports", operation_id="create_direct_report_certification", responses=ERRORS
)
async def create_direct_report_certification(
    request: Request,
    body: CertificationStaffCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    return await _create_staff_certification(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        scope="direct_report",
    )


async def _certification_decision(
    *,
    certification_id: uuid.UUID,
    request: Request,
    body: CertificationDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    verify: bool,
) -> JSONResponse:
    operation_id = "verify_certification" if verify else "reject_certification"

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.decide_certification(
            principal,
            branch_id,
            certification_id,
            body.expected_updated_at,
            verify=verify,
            reason=body.reason,
        )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "certification",
            certification_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id=operation_id,
        method="POST",
        route_parameters={"certificationId": str(certification_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@certification_router.post(
    "/{certification_id}/verify", operation_id="verify_certification", responses=ERRORS
)
async def verify_certification(
    certification_id: uuid.UUID,
    request: Request,
    body: CertificationDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    if body.reason is not None:
        raise api_error("validation_failed")
    return await _certification_decision(
        certification_id=certification_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        verify=True,
    )


@certification_router.post(
    "/{certification_id}/reject", operation_id="reject_certification", responses=ERRORS
)
async def reject_certification(
    certification_id: uuid.UUID,
    request: Request,
    body: CertificationDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _certification_decision(
        certification_id=certification_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        verify=False,
    )


@certification_router.delete(
    "/{certification_id}", operation_id="delete_certification", responses=ERRORS
)
async def delete_certification(
    certification_id: uuid.UUID,
    request: Request,
    body: VersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> JSONResponse:
    branch_id = _staff_branch(principal, selected_branch)
    scope = "admin" if principal.role is AppRole.ADMIN else "staff"

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        await service.delete_certification(
            principal,
            branch_id,
            certification_id,
            body.expected_updated_at,
            scope=scope,
        )
        response = DataResponse(data=DeletedDevelopmentResponse(id=certification_id, deleted=True))
        return IdempotentResponse(
            200,
            response.model_dump(mode="json", by_alias=True),
            None,
            "certification",
            certification_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        operation_id="delete_certification",
        method="DELETE",
        route_parameters={"certificationId": str(certification_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        authorize=False,
    )


@cme_router.get(
    "/requirements/{employee_id}/{year}",
    response_model=DataResponse[CmeRequirementResponse],
    operation_id="read_cme_requirement",
    responses=ERRORS,
)
async def read_cme_requirement(
    employee_id: uuid.UUID,
    year: int,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[CmeRequirementResponse]:
    if year < 1900 or year > 9999:
        raise api_error("validation_failed")
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).get_requirement(
            principal, selected, employee_id, year
        ),
    )
    return DataResponse(data=result)


@cme_router.put(
    "/requirements/{employee_id}/{year}", operation_id="save_cme_requirement", responses=ERRORS
)
async def save_cme_requirement(
    employee_id: uuid.UUID,
    year: int,
    request: Request,
    body: CmeRequirementRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    if year < 1900 or year > 9999:
        raise api_error("validation_failed")

    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        result = await service.save_requirement(principal, selected, employee_id, year, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "cme_requirement",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="save_cme_requirement",
        method="PUT",
        route_parameters={"employeeId": str(employee_id), "year": year},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@cme_router.delete(
    "/requirements/{employee_id}/{year}", operation_id="delete_cme_requirement", responses=ERRORS
)
async def delete_cme_requirement(
    employee_id: uuid.UUID,
    year: int,
    request: Request,
    body: VersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: DevelopmentService) -> IdempotentResponse:
        current = await service.get_requirement(principal, selected, employee_id, year)
        await service.delete_requirement(
            principal, selected, employee_id, year, body.expected_updated_at
        )
        response = DataResponse(data=DeletedDevelopmentResponse(id=current.id, deleted=True))
        return IdempotentResponse(
            200,
            response.model_dump(mode="json", by_alias=True),
            None,
            "cme_requirement",
            current.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="delete_cme_requirement",
        method="DELETE",
        route_parameters={"employeeId": str(employee_id), "year": year},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        authorize=False,
    )


@cme_router.get(
    "/self",
    response_model=DataResponse[CmeSummaryResponse],
    operation_id="read_self_cme",
    responses=ERRORS,
)
async def read_self_cme(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    year: Annotated[int, Query(ge=1900, le=9999)],
) -> DataResponse[CmeSummaryResponse]:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    branch_id = principal.branch_id
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).self_cme(
            principal, branch_id, year
        ),
    )
    return DataResponse(data=result)
