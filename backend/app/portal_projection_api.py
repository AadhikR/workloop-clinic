from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    VerifiedAccessToken,
)
from app.http.pagination import uuid_page
from app.http.schemas import CollectionResponse, DataResponse
from app.leave_approval_api import ERRORS
from app.phase11c_support import executor
from app.schemas.portal_projections import (
    AdminWorkspaceResponse,
    ClinicalWorkforceRowResponse,
    ClinicalWorkforceSummaryResponse,
    EmployeeDirectoryDetailResponse,
    EmployeeExpiryResponse,
    LeaveActionResponse,
    OwnAdvanceProgressResponse,
)
from app.services.portal_projections import PortalProjectionService

router = APIRouter(prefix="/api/v1", tags=["portal-projections"])


@router.get(
    "/dashboards/admin/workspace-summary",
    operation_id="read_admin_workspace_summary",
    responses=ERRORS,
)
async def admin_workspace_summary(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[AdminWorkspaceResponse]:
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: PortalProjectionService(connection).admin_workspace(
            principal, selected
        ),
    )
    return DataResponse(data=result)


@router.get(
    "/dashboards/clinical/workforce-summary",
    operation_id="read_clinical_workforce_summary",
    responses=ERRORS,
)
async def clinical_workforce_summary(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> DataResponse[ClinicalWorkforceSummaryResponse]:
    data = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: PortalProjectionService(connection).clinical_workforce_summary(
            principal,
            selected,
            request.app.state.settings.malware_scanner_definition,
        ),
    )
    return DataResponse(data=data)


@router.get(
    "/dashboards/clinical/workforce-details",
    operation_id="list_clinical_workforce_details",
    responses=ERRORS,
)
async def clinical_workforce_details(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    group: Annotated[str, Query(max_length=40)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    cursor: Annotated[str | None, Query(max_length=100)] = None,
) -> CollectionResponse[ClinicalWorkforceRowResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: PortalProjectionService(connection).clinical_workforce_details(
            principal,
            selected,
            request.app.state.settings.malware_scanner_definition,
            group,
            limit + 1,
            cursor,
        ),
    )
    return uuid_page(items, limit)


@router.get(
    "/employees/directory-details",
    operation_id="list_employee_directory_details",
    responses=ERRORS,
)
async def employee_directory_details(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[uuid.UUID | None, Query()] = None,
) -> CollectionResponse[EmployeeDirectoryDetailResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: PortalProjectionService(connection).employee_directory_details(
            principal,
            selected,
            limit + 1,
            cursor,
        ),
    )
    return uuid_page(items, limit)


@router.get(
    "/advances/{record_id}/self-progress",
    operation_id="read_own_advance_progress",
    responses=ERRORS,
)
async def own_advance_progress(
    record_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[uuid.UUID | None, Query()] = None,
) -> OwnAdvanceProgressResponse:
    return await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: PortalProjectionService(connection).own_advance_progress(
            principal,
            record_id,
            limit,
            cursor,
        ),
    )


@router.get(
    "/dashboards/clinical/credentials",
    operation_id="list_clinical_credential_employees",
    responses=ERRORS,
)
async def clinical_credential_employees(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    credential_status: Annotated[str, Query(alias="status")] = "expiring",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=100)] = None,
) -> CollectionResponse[EmployeeExpiryResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: PortalProjectionService(connection).clinical_credentials(
            principal,
            selected,
            credential_status,
            request.app.state.settings.malware_scanner_definition,
            limit + 1,
            cursor,
        ),
    )
    return uuid_page(items, limit)


@router.get(
    "/employees/expiry-summary", operation_id="list_employee_expiry_summary", responses=ERRORS
)
async def employee_expiry_summary(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=100)] = None,
) -> CollectionResponse[EmployeeExpiryResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: PortalProjectionService(connection).employee_expiry(
            principal,
            selected,
            limit + 1,
            cursor,
        ),
    )
    return uuid_page(items, limit)


@router.get(
    "/leave/approvals/recent", operation_id="list_recent_manager_leave_actions", responses=ERRORS
)
async def recent_manager_leave_actions(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[uuid.UUID | None, Query()] = None,
) -> CollectionResponse[LeaveActionResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: PortalProjectionService(connection).recent_leave_actions(
            principal,
            limit + 1,
            cursor,
        ),
    )
    return uuid_page(items, limit)
