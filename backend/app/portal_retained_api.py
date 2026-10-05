from __future__ import annotations

import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.http.pagination import uuid_page
from app.http.schemas import CollectionResponse, DataResponse
from app.http.versions import same_instant
from app.incident_api import ERRORS
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.appraisals import (
    AppraisalAdminReviewRequest,
    AppraisalReviewRequest,
    AppraisalSectionRatingRequest,
)
from app.schemas.development import VersionRequest
from app.schemas.portal_projections import RetainedRecordResponse
from app.services.appraisals import AppraisalService
from app.services.execution import ServiceExecutionError
from app.services.idempotency import IdempotentResponse
from app.services.retained_records import RetainedRecordService

router = APIRouter(prefix="/api/v1", tags=["retained-records"])


@router.post(
    "/appraisals/{record_id}/admin-review",
    operation_id="save_admin_appraisal_review",
    responses=ERRORS,
)
async def save_admin_appraisal_review(
    record_id: uuid.UUID,
    body: AppraisalAdminReviewRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutation(connection: AsyncConnection) -> IdempotentResponse:
        service = AppraisalService(connection)
        current = await service.get_appraisal(principal, selected, record_id)
        if not same_instant(current.updated_at, body.expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        if {section.id for section in current.sections} != {
            section.id for section in body.sections
        }:
            raise ServiceExecutionError("state_conflict")
        for section in sorted(body.sections, key=lambda item: item.id):
            await RetainedRecordService(connection).rate_admin_section(
                principal,
                selected,
                record_id,
                section.id,
                AppraisalSectionRatingRequest.model_validate(
                    {
                        "expectedUpdatedAt": current.updated_at,
                        "rating": section.rating,
                        "comments": section.comments,
                    }
                ),
            )
            current = await service.get_appraisal(principal, selected, record_id)
        result = await service.review(
            principal,
            selected,
            record_id,
            AppraisalReviewRequest.model_validate(
                {
                    "expectedUpdatedAt": current.updated_at,
                    "reviewerComments": body.reviewer_comments,
                    "developmentPlan": body.development_plan,
                }
            ),
        )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "appraisal",
            record_id,
        )

    async def authorize(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        await AppraisalService(connection).authorize_replay(principal, selected, kind, resource_id)

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected_admin_branch_id=selected,
        operation_id="save_admin_appraisal_review",
        method="POST",
        route_parameters={"recordId": str(record_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=authorize,
        mutation=mutation,
    )


@router.get("/retained-records", operation_id="list_retained_portal_records", responses=ERRORS)
async def list_retained_portal_records(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    kind: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[uuid.UUID | None, Query()] = None,
) -> CollectionResponse[RetainedRecordResponse]:
    items = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: RetainedRecordService(connection).list(
            principal,
            selected,
            kind,
            limit + 1,
            cursor,
        ),
    )
    return uuid_page(items, limit)


async def _archival(
    record_id: uuid.UUID,
    kind: str,
    body: VersionRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: uuid.UUID,
    archived: bool,
) -> JSONResponse:
    async def mutation(connection: AsyncConnection) -> IdempotentResponse:
        result = await RetainedRecordService(connection).archive(
            principal,
            selected,
            kind,
            record_id,
            body.expected_updated_at,
            archived,
        )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            kind,
            record_id,
        )

    async def authorize(
        connection: AsyncConnection, resource_kind: str, resource_id: uuid.UUID | None
    ) -> None:
        if resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        await RetainedRecordService(connection).read(
            principal, selected, resource_kind, resource_id
        )

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected_admin_branch_id=selected,
        operation_id="archive_portal_record" if archived else "restore_portal_record",
        method="POST",
        route_parameters={"kind": kind, "recordId": str(record_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=authorize,
        mutation=mutation,
    )


@router.post(
    "/retained-records/{kind}/{record_id}/archive",
    operation_id="archive_portal_record",
    responses=ERRORS,
)
async def archive_portal_record(
    kind: str,
    record_id: uuid.UUID,
    body: VersionRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _archival(record_id, kind, body, request, claims, principal, selected, True)


@router.post(
    "/retained-records/{kind}/{record_id}/restore",
    operation_id="restore_portal_record",
    responses=ERRORS,
)
async def restore_portal_record(
    kind: str,
    record_id: uuid.UUID,
    body: VersionRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _archival(record_id, kind, body, request, claims, principal, selected, False)


@router.put(
    "/appraisals/{record_id}/sections/{section_id}/admin-rating",
    operation_id="rate_admin_appraisal_section",
    responses=ERRORS,
)
async def rate_admin_appraisal_section(
    record_id: uuid.UUID,
    section_id: uuid.UUID,
    body: AppraisalSectionRatingRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutation(connection: AsyncConnection) -> IdempotentResponse:
        await RetainedRecordService(connection).rate_admin_section(
            principal,
            selected,
            record_id,
            section_id,
            body,
        )
        result = await AppraisalService(connection).get_appraisal(principal, selected, record_id)
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "appraisal",
            record_id,
        )

    async def authorize(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        await AppraisalService(connection).authorize_replay(principal, selected, kind, resource_id)

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected_admin_branch_id=selected,
        operation_id="rate_admin_appraisal_section",
        method="PUT",
        route_parameters={"recordId": str(record_id), "sectionId": str(section_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=authorize,
        mutation=mutation,
    )


@router.post(
    "/advances/{record_id}/admin-cancel",
    operation_id="cancel_pending_admin_advance",
    responses=ERRORS,
)
async def cancel_pending_admin_advance(
    record_id: uuid.UUID,
    body: VersionRequest,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    async def mutation(connection: AsyncConnection) -> IdempotentResponse:
        result = await RetainedRecordService(connection).cancel_advance(
            principal,
            selected,
            record_id,
            body.expected_updated_at,
        )
        return IdempotentResponse(
            200,
            DataResponse(data=result).model_dump(mode="json", by_alias=True),
            None,
            "salary_advance",
            record_id,
        )

    async def authorize(
        connection: AsyncConnection, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        if resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        await RetainedRecordService(connection).read(principal, selected, kind, resource_id)

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=selected,
        selected_admin_branch_id=selected,
        operation_id="cancel_pending_admin_advance",
        method="POST",
        route_parameters={"recordId": str(record_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=authorize,
        mutation=mutation,
    )
