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
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.assets import (
    AssetAssignmentResponse,
    AssetAssignRequest,
    AssetCreateRequest,
    AssetDeleteRequest,
    AssetResponse,
    AssetReturnRequest,
    AssetStatusRequest,
    AssetUpdateRequest,
    DeletedAssetResponse,
)
from app.services.assets import AssetListQuery, AssetService
from app.services.idempotency import IdempotentResponse

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])
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
    mutate: Callable[[AssetService], Awaitable[IdempotentResponse]],
    authorize: bool = True,
) -> JSONResponse:
    async def run(connection: AsyncConnection) -> IdempotentResponse:
        return await mutate(AssetService(connection))

    async def authorize_replay(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        if authorize:
            await AssetService(connection).authorize_replay(principal, branch_id, kind, resource_id)

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
    response_model=CollectionResponse[AssetResponse],
    operation_id="list_assets",
    responses={**success_response_documentation(200, "Assets"), **ERRORS},
)
async def list_assets(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    asset_status: Annotated[str | None, Query(alias="status")] = None,
    category: Annotated[str | None, Query(max_length=120)] = None,
    search: Annotated[str | None, Query(max_length=180)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[AssetResponse]:
    if asset_status not in {None, "available", "assigned", "under_repair", "retired", "lost"}:
        raise api_error("validation_failed")
    normalized_category = category.strip() if category is not None else None
    normalized_search = search.strip() if search is not None else None
    if normalized_category == "" or normalized_search == "":
        raise api_error("validation_failed")
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: AssetService(connection).list(
            principal,
            selected,
            AssetListQuery(asset_status, normalized_category, normalized_search, limit),
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.get(
    "/self",
    response_model=CollectionResponse[AssetAssignmentResponse],
    operation_id="list_self_assets",
    responses={**success_response_documentation(200, "Own asset history"), **ERRORS},
)
async def list_self_assets(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> CollectionResponse[AssetAssignmentResponse]:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    branch_id = principal.branch_id
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: AssetService(connection).list_self(
            principal, branch_id, limit
        ),
    )
    return CollectionResponse(data=items, page=Page(limit=limit, next_cursor=None, has_more=False))


@router.post("", operation_id="create_asset", responses=ERRORS)
async def create_asset(
    request: Request,
    body: AssetCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AssetService) -> IdempotentResponse:
        result = await service.create(principal, selected, body)
        return IdempotentResponse(
            201,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            f"/api/v1/assets/{result.id}",
            "asset",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="create_asset",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.patch("/{asset_id}", operation_id="update_asset", responses=ERRORS)
async def update_asset(
    asset_id: uuid.UUID,
    request: Request,
    body: AssetUpdateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AssetService) -> IdempotentResponse:
        result = await service.update(principal, selected, asset_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "asset",
            asset_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="update_asset",
        method="PATCH",
        route_parameters={"assetId": str(asset_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post("/{asset_id}/status", operation_id="change_asset_status", responses=ERRORS)
async def change_asset_status(
    asset_id: uuid.UUID,
    request: Request,
    body: AssetStatusRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AssetService) -> IdempotentResponse:
        result = await service.transition(
            principal, selected, asset_id, body.status, body.expected_updated_at
        )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "asset",
            asset_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="change_asset_status",
        method="POST",
        route_parameters={"assetId": str(asset_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post("/{asset_id}/assign", operation_id="assign_asset", responses=ERRORS)
async def assign_asset(
    asset_id: uuid.UUID,
    request: Request,
    body: AssetAssignRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AssetService) -> IdempotentResponse:
        result = await service.assign(principal, selected, asset_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "asset_assignment",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="assign_asset",
        method="POST",
        route_parameters={"assetId": str(asset_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post("/{asset_id}/return", operation_id="return_asset", responses=ERRORS)
async def return_asset(
    asset_id: uuid.UUID,
    request: Request,
    body: AssetReturnRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AssetService) -> IdempotentResponse:
        result = await service.return_asset(principal, selected, asset_id, body)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "asset_assignment",
            result.id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="return_asset",
        method="POST",
        route_parameters={"assetId": str(asset_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.delete("/{asset_id}", operation_id="delete_asset", responses=ERRORS)
async def delete_asset(
    asset_id: uuid.UUID,
    request: Request,
    body: AssetDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutate(service: AssetService) -> IdempotentResponse:
        await service.delete(principal, selected, asset_id, body.expected_updated_at)
        response = DataResponse(data=DeletedAssetResponse(id=asset_id, deleted=True))
        return IdempotentResponse(
            200,
            response.model_dump(mode="json", by_alias=True),
            None,
            "asset",
            asset_id,
        )

    return await _mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        operation_id="delete_asset",
        method="DELETE",
        route_parameters={"assetId": str(asset_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        authorize=False,
    )
