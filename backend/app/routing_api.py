import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
    resource_not_found_error,
)
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import DataResponse
from app.http.validation import validate_query_parameters
from app.organization_api import CANONICAL_UUID_PATTERN, ORGANIZATION_ERRORS
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.routing import (
    RoutingChangeRequest,
    RoutingChangeResponse,
    RoutingDraft,
    RoutingSnapshot,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.organization import OrganizationService

router = APIRouter(prefix="/api/v1/branches", tags=["organization"])


def service(request: Request, connection: AsyncConnection) -> OrganizationService:
    return OrganizationService(connection, request.app.state.organization_cursor_codec)


@router.get(
    "/{branch_id}/payroll-routing",
    operation_id="read_branch_payroll_routing",
    response_model=DataResponse[RoutingSnapshot],
    responses=ORGANIZATION_ERRORS,
)
async def read_routing(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected_branch_id: AdminSelectedBranch,
    branch_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> DataResponse[RoutingSnapshot]:
    validate_query_parameters(request, allowed=set())
    if uuid.UUID(branch_id) != selected_branch_id:
        raise resource_not_found_error()
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> RoutingSnapshot:
        branch = await service(request, connection).get_branch(principal, selected_branch_id)
        rows = (
            (
                await connection.execute(
                    text(
                        "SELECT id,updated_at AS expected_updated_at,"
                        "source_snapshot_digest AS source_digest "
                        "FROM public.payroll_runs WHERE company_id=:company AND branch_id=:branch "
                        "AND status='draft' ORDER BY id"
                    ),
                    {"company": principal.company_id, "branch": selected_branch_id},
                )
            )
            .mappings()
            .all()
        )
        return RoutingSnapshot(
            branch=branch, drafts=[RoutingDraft.model_validate(row) for row in rows]
        )

    return DataResponse(
        data=await executor.execute(
            claims=claims,
            principal=principal,
            operation=operation,
            selected_admin_branch_id=selected_branch_id,
        )
    )


@router.post(
    "/{branch_id}/payroll-routing",
    operation_id="change_branch_payroll_routing",
    response_model=DataResponse[RoutingChangeResponse],
    responses=ORGANIZATION_ERRORS,
)
async def change_routing(
    request: Request,
    body: RoutingChangeRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch_id: AdminSelectedBranch,
    branch_id: Annotated[str, Path(pattern=CANONICAL_UUID_PATTERN)],
) -> JSONResponse:
    validate_query_parameters(request, allowed=set())
    if uuid.UUID(branch_id) != selected_branch_id:
        raise resource_not_found_error()
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    values = body.model_dump(mode="json", by_alias=True)
    routes: dict[str, object] = {"branch_id": branch_id}
    command = IdempotencyCommand(
        key=key,
        operation_id="change_branch_payroll_routing",
        method="POST",
        route_parameters=routes,
        branch_id=selected_branch_id,
        fingerprint=request_fingerprint(
            operation_id="change_branch_payroll_routing",
            method="POST",
            route_parameters=routes,
            effective_query_parameters={},
            body=values,
        ),
    )
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        organization = service(request, connection)

        async def authorize(kind: str, resource_id: uuid.UUID | None) -> None:
            if kind != "branch" or resource_id != selected_branch_id:
                raise ServiceExecutionError("resource_not_found")
            await organization.get_branch(principal, selected_branch_id)

        async def mutate() -> IdempotentResponse:
            try:
                changed = await connection.scalar(
                    text(
                        "SELECT public.change_branch_payroll_routing(:branch,:expected,:code,"
                        "CAST(:drafts AS jsonb))"
                    ),
                    {
                        "branch": selected_branch_id,
                        "expected": body.expected_updated_at,
                        "code": body.routing_code,
                        "drafts": json.dumps(values["drafts"]),
                    },
                )
            except DBAPIError as error:
                if getattr(error.orig, "sqlstate", None) == "40001":
                    raise ServiceExecutionError("state_conflict") from None
                raise
            branch = await organization.get_branch(principal, selected_branch_id)
            response = RoutingChangeResponse(branch=branch, changed_runs=changed)
            return IdempotentResponse(
                status=200,
                body=DataResponse(data=response).model_dump(mode="json", by_alias=True),
                location=None,
                resource_kind="branch",
                resource_id=selected_branch_id,
            )

        return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
            principal=principal,
            command=command,
            authorize_replay=authorize,
            mutation=mutate,
        )

    result = await executor.execute(
        claims=claims,
        principal=principal,
        operation=operation,
        selected_admin_branch_id=selected_branch_id,
    )
    headers = {"Cache-Control": "no-store"}
    if result.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=result.status, content=result.body, headers=headers)
