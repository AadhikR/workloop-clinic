from __future__ import annotations

import uuid
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
from app.schemas.employment_contract import (
    ContractCommandRequest,
    ContractNotRenewedRequest,
    EmployeeContractResponse,
)
from app.services.employment_contracts import (
    ContractAction,
    EmploymentContractListQuery,
    EmploymentContractService,
)
from app.services.idempotency import IdempotentResponse

router = APIRouter(prefix="/api/v1/employees", tags=["employment-contracts"])
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


@router.get(
    "/{employee_id}/contracts",
    response_model=CollectionResponse[EmployeeContractResponse],
    operation_id="list_employee_contracts",
    responses={**success_response_documentation(200, "Employment contract history"), **ERRORS},
)
async def list_employee_contracts(
    employee_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> CollectionResponse[EmployeeContractResponse]:
    items, next_cursor = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: EmploymentContractService(connection).list(
            principal,
            selected,
            EmploymentContractListQuery(
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


async def _record(
    *,
    employee_id: uuid.UUID,
    action: ContractAction,
    operation_id: str,
    request: Request,
    body: ContractCommandRequest | ContractNotRenewedRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
) -> JSONResponse:
    async def mutate(connection: AsyncConnection) -> IdempotentResponse:
        result = await EmploymentContractService(connection).record(
            principal, branch_id, employee_id, action, body
        )
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/employees/{employee_id}/contracts/{result.id}",
            "employee_contract",
            result.id,
        )

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=branch_id,
        operation_id=operation_id,
        method="POST",
        route_parameters={"employeeId": str(employee_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=lambda connection, kind, resource_id: EmploymentContractService(
            connection
        ).authorize_replay(principal, branch_id, kind, resource_id),
        mutation=mutate,
    )


@router.post("/{employee_id}/contracts/new", operation_id="record_new_contract", responses=ERRORS)
async def record_new_contract(
    employee_id: uuid.UUID,
    request: Request,
    body: ContractCommandRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _record(
        employee_id=employee_id,
        action="new",
        operation_id="record_new_contract",
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
    )


@router.post(
    "/{employee_id}/contracts/renew", operation_id="renew_employee_contract", responses=ERRORS
)
async def renew_employee_contract(
    employee_id: uuid.UUID,
    request: Request,
    body: ContractCommandRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _record(
        employee_id=employee_id,
        action="renewed",
        operation_id="renew_employee_contract",
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
    )


@router.post(
    "/{employee_id}/contracts/convert",
    operation_id="convert_employee_contract",
    responses=ERRORS,
)
async def convert_employee_contract(
    employee_id: uuid.UUID,
    request: Request,
    body: ContractCommandRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _record(
        employee_id=employee_id,
        action="converted",
        operation_id="convert_employee_contract",
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
    )


@router.post(
    "/{employee_id}/contracts/not-renewed",
    operation_id="record_contract_not_renewed",
    responses=ERRORS,
)
async def record_contract_not_renewed(
    employee_id: uuid.UUID,
    request: Request,
    body: ContractNotRenewedRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _record(
        employee_id=employee_id,
        action="not_renewed",
        operation_id="record_contract_not_renewed",
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
    )
