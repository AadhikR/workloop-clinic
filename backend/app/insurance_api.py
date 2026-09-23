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
from app.schemas.insurance import (
    CoverageReplaceRequest,
    DeletedInsuranceResponse,
    InsuranceDependantCreateRequest,
    InsuranceDependantDeleteRequest,
    InsuranceDependantResponse,
    InsuranceDependantUpdateRequest,
    InsurancePolicyCreateRequest,
    InsurancePolicyDeleteRequest,
    InsurancePolicyResponse,
    InsurancePolicyUpdateRequest,
    SelfInsuranceResponse,
)
from app.services.idempotency import IdempotentResponse
from app.services.insurance import (
    InsuranceDependantListQuery,
    InsurancePolicyListQuery,
    InsuranceService,
)

router = APIRouter(prefix="/api/v1/insurance", tags=["insurance"])
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "validation_failed",
    "invalid_cursor",
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


def _service(connection: AsyncConnection) -> InsuranceService:
    return InsuranceService(connection)


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
    mutate: Callable[[InsuranceService], Awaitable[IdempotentResponse]],
    authorize: bool = True,
) -> JSONResponse:
    async def run(connection: AsyncConnection) -> IdempotentResponse:
        return await mutate(_service(connection))

    async def authorize_replay(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        if authorize:
            await _service(connection).authorize_replay(principal, branch_id, kind, resource_id)

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
    "/policies",
    response_model=CollectionResponse[InsurancePolicyResponse],
    operation_id="list_insurance_policies",
    responses={**success_response_documentation(200, "Insurance policies"), **ERRORS},
)
async def list_insurance_policies(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    renewal_from: Annotated[date | None, Query(alias="renewalFrom")] = None,
    renewal_to: Annotated[date | None, Query(alias="renewalTo")] = None,
    search: Annotated[str | None, Query(max_length=180)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> CollectionResponse[InsurancePolicyResponse]:
    if renewal_from is not None and renewal_to is not None and renewal_to < renewal_from:
        raise api_error("validation_failed")
    normalized_search = search.strip() if search is not None else None
    if normalized_search == "":
        raise api_error("validation_failed")
    items, next_cursor = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(connection).list_policies(
            principal,
            selected,
            InsurancePolicyListQuery(
                renewal_from=renewal_from,
                renewal_to=renewal_to,
                search=normalized_search,
                limit=limit,
                cursor=cursor,
            ),
            request.app.state.employee_cursor_codec,
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.post("/policies", operation_id="create_insurance_policy", responses=ERRORS)
async def create_insurance_policy(
    request: Request,
    body: InsurancePolicyCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: InsuranceService) -> IdempotentResponse:
        result = await service.create_policy(principal, selected, body)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/insurance/policies/{result.id}",
            "insurance_policy",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_insurance_policy",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.patch("/policies/{policy_id}", operation_id="update_insurance_policy", responses=ERRORS)
async def update_insurance_policy(
    policy_id: uuid.UUID,
    request: Request,
    body: InsurancePolicyUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: InsuranceService) -> IdempotentResponse:
        result = await service.update_policy(principal, selected, policy_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "insurance_policy",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="update_insurance_policy",
        method="PATCH",
        route_parameters={"policyId": str(policy_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.delete("/policies/{policy_id}", operation_id="delete_insurance_policy", responses=ERRORS)
async def delete_insurance_policy(
    policy_id: uuid.UUID,
    request: Request,
    body: InsurancePolicyDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: InsuranceService) -> IdempotentResponse:
        await service.delete_policy(principal, selected, policy_id, body.expected_updated_at)
        response = DataResponse(data=DeletedInsuranceResponse(id=policy_id, deleted=True))
        return IdempotentResponse(
            200,
            response.model_dump(mode="json", by_alias=True),
            None,
            "insurance_policy",
            policy_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="delete_insurance_policy",
        method="DELETE",
        route_parameters={"policyId": str(policy_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        authorize=False,
    )


@router.put(
    "/employees/{employee_id}/coverage",
    operation_id="replace_employee_coverage",
    responses=ERRORS,
)
async def replace_employee_coverage(
    employee_id: uuid.UUID,
    request: Request,
    body: CoverageReplaceRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: InsuranceService) -> IdempotentResponse:
        result = await service.replace_coverage(principal, selected, employee_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "employee_insurance",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="replace_employee_coverage",
        method="PUT",
        route_parameters={"employeeId": str(employee_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.get(
    "/self",
    response_model=DataResponse[SelfInsuranceResponse],
    operation_id="read_self_insurance",
    responses={**success_response_documentation(200, "Own insurance coverage"), **ERRORS},
)
async def read_self_insurance(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> DataResponse[SelfInsuranceResponse]:
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(connection).self_coverage(principal),
    )
    return DataResponse(data=result)


@router.get(
    "/employees/{employee_id}/dependants",
    response_model=CollectionResponse[InsuranceDependantResponse],
    operation_id="list_insurance_dependants",
    responses={**success_response_documentation(200, "Insurance dependants"), **ERRORS},
)
async def list_insurance_dependants(
    employee_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> CollectionResponse[InsuranceDependantResponse]:
    items, next_cursor = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(connection).list_dependants(
            principal,
            selected,
            InsuranceDependantListQuery(
                employee_id=employee_id,
                limit=limit,
                cursor=cursor,
            ),
            request.app.state.employee_cursor_codec,
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.post(
    "/employees/{employee_id}/dependants",
    operation_id="create_insurance_dependant",
    responses=ERRORS,
)
async def create_insurance_dependant(
    employee_id: uuid.UUID,
    request: Request,
    body: InsuranceDependantCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: InsuranceService) -> IdempotentResponse:
        result = await service.create_dependant(principal, selected, employee_id, body)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/insurance/dependants/{result.id}",
            "insurance_dependant",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_insurance_dependant",
        method="POST",
        route_parameters={"employeeId": str(employee_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.patch(
    "/dependants/{dependant_id}", operation_id="update_insurance_dependant", responses=ERRORS
)
async def update_insurance_dependant(
    dependant_id: uuid.UUID,
    request: Request,
    body: InsuranceDependantUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: InsuranceService) -> IdempotentResponse:
        result = await service.update_dependant(principal, selected, dependant_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "insurance_dependant",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="update_insurance_dependant",
        method="PATCH",
        route_parameters={"dependantId": str(dependant_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.delete(
    "/dependants/{dependant_id}", operation_id="delete_insurance_dependant", responses=ERRORS
)
async def delete_insurance_dependant(
    dependant_id: uuid.UUID,
    request: Request,
    body: InsuranceDependantDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: InsuranceService) -> IdempotentResponse:
        await service.delete_dependant(principal, selected, dependant_id, body.expected_updated_at)
        response = DataResponse(data=DeletedInsuranceResponse(id=dependant_id, deleted=True))
        return IdempotentResponse(
            200,
            response.model_dump(mode="json", by_alias=True),
            None,
            "insurance_dependant",
            dependant_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="delete_insurance_dependant",
        method="DELETE",
        route_parameters={"dependantId": str(dependant_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        authorize=False,
    )
