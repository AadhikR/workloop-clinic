from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from typing import Annotated, cast

from fastapi import APIRouter, Header, Query, Request, Response, status
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
from app.schemas.employee_document import (
    DOCUMENT_TYPES,
    EmployeeDocumentDecisionRequest,
    EmployeeDocumentDeleteRequest,
    EmployeeDocumentDownloadResponse,
    EmployeeDocumentResponse,
    EmployeeDocumentSubmissionRequest,
    EmployeeDocumentSubmissionResponse,
)
from app.services.employee_documents import (
    ClaimedDocumentCleanup,
    EmployeeDocumentListQuery,
    EmployeeDocumentService,
)
from app.services.idempotency import IdempotentResponse
from app.services.leave_attachment import parse_upload
from app.storage.base import StorageError, StorageNotFoundError

router = APIRouter(prefix="/api/v1/employee-documents", tags=["employee-documents"])
logger = logging.getLogger(__name__)
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "request_too_large",
    "unsupported_media_type",
    "validation_failed",
    "invalid_cursor",
    "invalid_branch",
    "branch_required",
    "state_conflict",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_in_progress",
    "attachment_submission_unavailable",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _service(request: Request, connection: AsyncConnection) -> EmployeeDocumentService:
    return EmployeeDocumentService(
        connection,
        object_key_hmac_key=request.app.state.settings.decoded_attachment_object_key_hmac_key(),
        scanner_definition=request.app.state.settings.malware_scanner_definition,
        cursor_codec=request.app.state.employee_cursor_codec,
    )


def _branch(principal: AuthorizationPrincipal, raw_branch: str | None) -> uuid.UUID:
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


@router.get(
    "",
    response_model=CollectionResponse[EmployeeDocumentResponse],
    operation_id="list_employee_documents",
    responses={**success_response_documentation(200, "Employee documents"), **ERRORS},
)
async def list_employee_documents(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    employee_id: Annotated[uuid.UUID, Query(alias="employeeId")],
    document_status: Annotated[str | None, Query(alias="status")] = None,
    document_type: Annotated[str | None, Query(alias="documentType")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> CollectionResponse[EmployeeDocumentResponse]:
    if document_status not in {None, "pending_verification", "verified", "rejected"} or (
        document_type is not None and document_type not in DOCUMENT_TYPES
    ):
        raise api_error("validation_failed")
    items, next_cursor = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list(
            principal,
            selected,
            EmployeeDocumentListQuery(
                employee_id=employee_id,
                status=document_status,
                document_type=document_type,
                limit=limit,
                cursor=cursor,
            ),
            operation_id="list_employee_documents",
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/self",
    response_model=CollectionResponse[EmployeeDocumentResponse],
    operation_id="list_self_employee_documents",
    responses={**success_response_documentation(200, "Own employee documents"), **ERRORS},
)
async def list_self_employee_documents(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> CollectionResponse[EmployeeDocumentResponse]:
    employee_id = principal.employee_id
    branch_id = principal.branch_id
    if employee_id is None or branch_id is None:
        raise api_error("operation_not_permitted")
    items, next_cursor = await executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list(
            principal,
            branch_id,
            EmployeeDocumentListQuery(
                employee_id=employee_id,
                status=None,
                document_type=None,
                limit=limit,
                cursor=cursor,
            ),
            operation_id="list_self_employee_documents",
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.post(
    "/submissions",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[EmployeeDocumentSubmissionResponse],
    operation_id="create_employee_document_submission",
    responses={**success_response_documentation(201, "Employee document upload intent"), **ERRORS},
)
async def create_employee_document_submission(
    request: Request,
    body: EmployeeDocumentSubmissionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> JSONResponse:
    branch_id = _branch(principal, selected_branch)

    async def mutate(connection: AsyncConnection) -> IdempotentResponse:
        result = await _service(request, connection).create_submission(principal, branch_id, body)
        return IdempotentResponse(
            status=201,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=f"/api/v1/employee-documents/submissions/{result.id}",
            resource_kind="employee_document",
            resource_id=result.id,
        )

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation_id="create_employee_document_submission",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=lambda connection, kind, resource_id: _service(
            request, connection
        ).authorize_replay(principal, branch_id, kind, resource_id),
        mutation=mutate,
    )


@router.post(
    "/submissions/{submission_id}/file",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[EmployeeDocumentResponse],
    operation_id="upload_employee_document",
    responses={**success_response_documentation(201, "Employee document uploaded"), **ERRORS},
)
async def upload_employee_document(
    submission_id: uuid.UUID,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[EmployeeDocumentResponse]:
    branch_id = _branch(principal, selected_branch)
    content_type = request.headers.get("content-type")
    if content_type is None:
        raise api_error("unsupported_media_type")
    upload = parse_upload(content_type, await request.body())
    selected = branch_id if principal.role is AppRole.ADMIN else None
    claimed = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).claim_upload(
            principal, branch_id, submission_id, upload
        ),
    )
    storage = request.app.state.object_storage
    try:
        async with asyncio.timeout(45):
            await storage.put_object(
                key=claimed.object_key,
                body=upload.body,
                content_type=upload.content_type,
                sha256=upload.sha256,
                if_absent=True,
            )
            metadata = await storage.head_object(key=claimed.object_key)
            if (
                metadata.size_bytes != len(upload.body)
                or metadata.content_type != upload.content_type
                or metadata.sha256 != upload.sha256
            ):
                raise StorageError
    except (StorageError, TimeoutError):
        await executor(request).execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=selected,
            operation=lambda connection: _service(request, connection).fail_upload(claimed),
        )
        raise api_error("service_unavailable") from None
    result = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).complete_upload(
            principal, claimed, upload
        ),
    )
    response.headers["Location"] = f"/api/v1/employee-documents/{result.id}"
    return DataResponse(data=result)


async def _decision(
    *,
    document_id: uuid.UUID,
    request: Request,
    body: EmployeeDocumentDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    verify: bool,
) -> JSONResponse:
    operation_id = "verify_employee_document" if verify else "reject_employee_document"

    async def mutate(connection: AsyncConnection) -> IdempotentResponse:
        result = await _service(request, connection).decide(
            principal,
            branch_id,
            document_id,
            body.expected_updated_at,
            verify=verify,
            reason=body.reason,
        )
        return IdempotentResponse(
            status=200,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=None,
            resource_kind="employee_document",
            resource_id=document_id,
        )

    return await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=branch_id,
        operation_id=operation_id,
        method="POST",
        route_parameters={"documentId": str(document_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=lambda connection, kind, resource_id: _service(
            request, connection
        ).authorize_replay(principal, branch_id, kind, resource_id),
        mutation=mutate,
    )


@router.post("/{document_id}/verify", operation_id="verify_employee_document", responses=ERRORS)
async def verify_employee_document(
    document_id: uuid.UUID,
    request: Request,
    body: EmployeeDocumentDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    if body.reason is not None:
        raise api_error("validation_failed")
    return await _decision(
        document_id=document_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        verify=True,
    )


@router.post("/{document_id}/reject", operation_id="reject_employee_document", responses=ERRORS)
async def reject_employee_document(
    document_id: uuid.UUID,
    request: Request,
    body: EmployeeDocumentDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decision(
        document_id=document_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=selected,
        verify=False,
    )


@router.post(
    "/{document_id}/download",
    response_model=DataResponse[EmployeeDocumentDownloadResponse],
    operation_id="download_employee_document",
    responses={**success_response_documentation(200, "Employee document download"), **ERRORS},
)
async def download_employee_document(
    document_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[EmployeeDocumentDownloadResponse]:
    if await request.body():
        raise api_error("invalid_request")
    branch_id = _branch(principal, selected_branch)
    selected = branch_id if principal.role is AppRole.ADMIN else None
    metadata = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).load_for_download(
            principal, branch_id, document_id
        ),
    )
    storage = request.app.state.object_storage
    try:
        async with asyncio.timeout(45):
            actual = await storage.head_object(key=cast(str, metadata["storage_path"]))
            if (
                actual.size_bytes != metadata["file_size"]
                or actual.content_type != metadata["content_type"]
                or actual.sha256 != metadata["sha256"]
            ):
                raise StorageError
            signed = await storage.create_download_url(
                key=cast(str, metadata["storage_path"]),
                expires_in_seconds=300,
                download_name=cast(str, metadata["file_name"]),
                content_type=cast(str, metadata["content_type"]),
            )
    except (StorageError, TimeoutError):
        raise api_error("service_unavailable") from None
    return DataResponse(
        data=EmployeeDocumentDownloadResponse(url=signed.url, expires_at=signed.expires_at)
    )


@router.delete("/{document_id}", operation_id="delete_employee_document", responses=ERRORS)
async def delete_employee_document(
    document_id: uuid.UUID,
    request: Request,
    body: EmployeeDocumentDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> JSONResponse:
    branch_id = _branch(principal, selected_branch)
    selected = branch_id if principal.role is AppRole.ADMIN else None
    claimed: ClaimedDocumentCleanup | None = None

    async def mutate(connection: AsyncConnection) -> IdempotentResponse:
        nonlocal claimed
        claimed = await _service(request, connection).claim_cleanup(
            principal, branch_id, document_id, body.expected_updated_at
        )
        return IdempotentResponse(
            status=202,
            body={"data": {"id": str(document_id), "cleanupPending": True}},
            location=None,
            resource_kind="employee_document",
            resource_id=document_id,
        )

    response = await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=selected,
        operation_id="delete_employee_document",
        method="DELETE",
        route_parameters={"documentId": str(document_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=lambda _connection, _kind, _resource_id: _noop(),
        mutation=mutate,
    )
    if claimed is not None:
        active_claim = claimed
        try:
            async with asyncio.timeout(45):
                with suppress(StorageNotFoundError):
                    await request.app.state.object_storage.delete_object(
                        key=active_claim.object_key
                    )
            await executor(request).execute(
                claims=claims,
                principal=principal,
                selected_admin_branch_id=selected,
                operation=lambda connection: _service(request, connection).complete_cleanup(
                    active_claim
                ),
            )
        except Exception:
            await executor(request).execute(
                claims=claims,
                principal=principal,
                selected_admin_branch_id=selected,
                operation=lambda connection: _service(request, connection).fail_cleanup(
                    active_claim
                ),
            )
            logger.error(
                "employee_document_cleanup_deferred",
                extra={
                    "operation_id": str(active_claim.operation_id),
                    "error_code": "provider_error",
                },
            )
    return response


async def _noop() -> None:
    return None
