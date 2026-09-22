from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import AuthenticatedWritePrincipal, VerifiedAccessToken
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import DataResponse
from app.models.identity import AppRole
from app.schemas.leave_attachment import (
    AttachmentDownloadResponse,
    AttachmentSubmissionRequest,
    AttachmentSubmissionResponse,
    LeaveAttachmentResponse,
)
from app.services.execution import AuthorizedServiceExecutor
from app.services.leave_attachment import LeaveAttachmentService, parse_upload
from app.storage.base import StorageError, StorageNotFoundError

router = APIRouter(prefix="/api/v1/leave", tags=["leave-attachments"])
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
    "invalid_branch",
    "branch_required",
    "attachment_submission_unavailable",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
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
    if raw_branch is not None:
        raise api_error("operation_not_permitted")
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    return principal.branch_id


def _service(request: Request, connection: AsyncConnection) -> LeaveAttachmentService:
    return LeaveAttachmentService(
        connection,
        object_key_hmac_key=(request.app.state.settings.decoded_attachment_object_key_hmac_key()),
        scanner_definition=request.app.state.settings.malware_scanner_definition,
    )


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


@router.post(
    "/attachment-submissions",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[AttachmentSubmissionResponse],
    operation_id="create_leave_attachment_submission",
    responses={
        **success_response_documentation(
            201, "Leave attachment upload intent", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def create_attachment_submission(
    request: Request,
    response: Response,
    body: AttachmentSubmissionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[AttachmentSubmissionResponse]:
    branch_id = _branch(principal, selected_branch)
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation=lambda connection: _service(request, connection).create_submission(
            principal, branch_id, body
        ),
    )
    response.headers["Location"] = f"/api/v1/leave/attachment-submissions/{data.id}"
    return DataResponse(data=data)


@router.post(
    "/attachment-submissions/{submission_id}/file",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[LeaveAttachmentResponse],
    operation_id="upload_leave_attachment",
    responses={
        **success_response_documentation(
            201, "Leave attachment uploaded", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def upload_attachment(
    submission_id: uuid.UUID,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[LeaveAttachmentResponse]:
    branch_id = _branch(principal, selected_branch)
    content_type = request.headers.get("content-type")
    if content_type is None:
        raise api_error("unsupported_media_type")
    upload = parse_upload(content_type, await request.body())
    executor = _executor(request)
    selected = branch_id if principal.role is AppRole.ADMIN else None
    claimed = await executor.execute(
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
        await executor.execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=selected,
            operation=lambda connection: _service(request, connection).fail_upload(claimed),
        )
        raise api_error("service_unavailable") from None
    data = await executor.execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).complete_upload(
            principal, claimed, upload
        ),
    )
    response.headers["Location"] = f"/api/v1/leave/attachments/{data.id}"
    return DataResponse(data=data)


@router.post(
    "/attachments/{attachment_id}/download",
    response_model=DataResponse[AttachmentDownloadResponse],
    operation_id="create_leave_attachment_download",
    responses={
        **success_response_documentation(
            200, "Authorized leave attachment download", cache_control="no-store"
        ),
        **ERRORS,
    },
)
async def create_attachment_download(
    attachment_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[AttachmentDownloadResponse]:
    if await request.body():
        raise api_error("invalid_request")
    branch_id = _branch(principal, selected_branch)
    selected = branch_id if principal.role is AppRole.ADMIN else None
    metadata = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).load_for_download(
            principal, branch_id, attachment_id
        ),
    )
    storage = request.app.state.object_storage
    object_key = cast(str, metadata["object_key"])
    file_name = cast(str, metadata["file_name"])
    content_type = cast(str, metadata["content_type"])
    try:
        async with asyncio.timeout(45):
            if metadata["status"] == "staged" and cast(
                datetime, metadata["expires_at"]
            ) <= datetime.now(UTC):
                raise StorageError
            actual = await storage.head_object(key=object_key)
            if (
                actual.size_bytes != metadata["size_bytes"]
                or actual.content_type != metadata["content_type"]
                or actual.sha256 != metadata["sha256"]
            ):
                raise StorageError
            signed = await storage.create_download_url(
                key=object_key,
                expires_in_seconds=300,
                download_name=file_name,
                content_type=content_type,
            )
    except (StorageError, TimeoutError):
        can_cleanup = principal.role is AppRole.ADMIN or (
            principal.employee_id == metadata["employee_id"]
            and principal.app_user_id == metadata["created_by_app_user_id"]
        )
        if can_cleanup:
            try:
                claimed = await _executor(request).execute(
                    claims=claims,
                    principal=principal,
                    selected_admin_branch_id=selected,
                    operation=lambda connection: _service(request, connection).request_cleanup(
                        principal,
                        branch_id,
                        attachment_id,
                        "staged_expired"
                        if metadata["status"] == "staged"
                        and cast(datetime, metadata["expires_at"]) <= datetime.now(UTC)
                        else "missing_object",
                    ),
                )
                async with asyncio.timeout(45):
                    with suppress(StorageNotFoundError):
                        await storage.delete_object(key=claimed.object_key)
                await _executor(request).execute(
                    claims=claims,
                    principal=principal,
                    selected_admin_branch_id=selected,
                    operation=lambda connection: _service(request, connection).complete_cleanup(
                        claimed
                    ),
                )
                logger.error(
                    "leave_attachment_object_unavailable",
                    extra={
                        "operation_id": str(claimed.operation_id),
                        "error_code": "missing_object",
                    },
                )
            except Exception:
                logger.error(
                    "leave_attachment_cleanup_failed",
                    extra={"error_code": "cleanup_failed"},
                )
        raise api_error("service_unavailable") from None
    return DataResponse(
        data=AttachmentDownloadResponse(url=signed.url, expires_at=signed.expires_at)
    )
