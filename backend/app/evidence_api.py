from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from typing import cast

from fastapi import APIRouter, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.schemas import DataResponse
from app.models.identity import AppRole
from app.phase11c_support import executor, idempotent_mutation
from app.schemas.development import (
    CertificationResponse,
    EvidenceDownloadResponse,
    TrainingResponse,
    VersionRequest,
)
from app.services.development import (
    ClaimedEvidenceCleanup,
    DevelopmentService,
)
from app.services.idempotency import IdempotentResponse
from app.services.leave_attachment import parse_direct_upload
from app.storage.base import StorageError, StorageNotFoundError

training_file_router = APIRouter(prefix="/api/v1/training-files", tags=["training-files"])
certification_file_router = APIRouter(
    prefix="/api/v1/certification-files", tags=["certification-files"]
)
logger = logging.getLogger(__name__)
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "request_too_large",
    "unsupported_media_type",
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


def _scope(principal: AuthorizationPrincipal) -> str:
    return "admin" if principal.role is AppRole.ADMIN else "staff"


async def _upload(
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
) -> TrainingResponse | CertificationResponse:
    content_type = request.headers.get("content-type")
    if content_type is None:
        raise api_error("unsupported_media_type")
    upload = parse_direct_upload(content_type, await request.body())
    selected = branch_id if principal.role is AppRole.ADMIN else None
    claimed = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).claim_evidence_upload(
            principal,
            branch_id,
            entity_type,
            entity_id,
            upload,
            scope=_scope(principal),
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
            operation=lambda connection: _service(request, connection).fail_evidence_upload(
                claimed
            ),
        )
        raise api_error("service_unavailable") from None
    await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).complete_evidence_upload(
            principal, claimed, upload
        ),
    )
    response.headers["Location"] = (
        f"/api/v1/training-files/{entity_id}"
        if entity_type == "training_evidence"
        else f"/api/v1/certification-files/{entity_id}"
    )
    if entity_type == "training_evidence":
        return await executor(request).execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=selected,
            operation=lambda connection: _service(request, connection).get_training(
                principal, branch_id, entity_id, scope=_scope(principal)
            ),
        )
    return await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).get_certification(
            principal, branch_id, entity_id, scope=_scope(principal)
        ),
    )


@training_file_router.post(
    "/{record_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[TrainingResponse],
    operation_id="upload_training_evidence",
    responses={**success_response_documentation(201, "Training evidence uploaded"), **ERRORS},
)
async def upload_training_evidence(
    record_id: uuid.UUID,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[TrainingResponse]:
    result = await _upload(
        entity_type="training_evidence",
        entity_id=record_id,
        request=request,
        response=response,
        claims=claims,
        principal=principal,
        branch_id=_branch(principal, selected_branch),
    )
    return DataResponse(data=cast(TrainingResponse, result))


@certification_file_router.post(
    "/{certification_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[CertificationResponse],
    operation_id="upload_certification_evidence",
    responses={**success_response_documentation(201, "Certification evidence uploaded"), **ERRORS},
)
async def upload_certification_evidence(
    certification_id: uuid.UUID,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[CertificationResponse]:
    result = await _upload(
        entity_type="certification_evidence",
        entity_id=certification_id,
        request=request,
        response=response,
        claims=claims,
        principal=principal,
        branch_id=_branch(principal, selected_branch),
    )
    return DataResponse(data=cast(CertificationResponse, result))


async def _download(
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
) -> DataResponse[EvidenceDownloadResponse]:
    if await request.body():
        raise api_error("invalid_request")
    selected = branch_id if principal.role is AppRole.ADMIN else None
    metadata = await executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).load_evidence_download(
            principal,
            branch_id,
            entity_type,
            entity_id,
            scope=_scope(principal),
        ),
    )
    storage = request.app.state.object_storage
    try:
        async with asyncio.timeout(45):
            actual = await storage.head_object(key=cast(str, metadata["storage_path"]))
            if (
                actual.size_bytes != metadata["size_bytes"]
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
    return DataResponse(data=EvidenceDownloadResponse(url=signed.url, expires_at=signed.expires_at))


@training_file_router.post(
    "/{record_id}/download", operation_id="download_training_evidence", responses=ERRORS
)
async def download_training_evidence(
    record_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[EvidenceDownloadResponse]:
    return await _download(
        entity_type="training_evidence",
        entity_id=record_id,
        request=request,
        claims=claims,
        principal=principal,
        branch_id=_branch(principal, selected_branch),
    )


@certification_file_router.post(
    "/{certification_id}/download",
    operation_id="download_certification_evidence",
    responses=ERRORS,
)
async def download_certification_evidence(
    certification_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[EvidenceDownloadResponse]:
    return await _download(
        entity_type="certification_evidence",
        entity_id=certification_id,
        request=request,
        claims=claims,
        principal=principal,
        branch_id=_branch(principal, selected_branch),
    )


async def _cleanup(
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    request: Request,
    body: VersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
) -> Response:
    selected = branch_id if principal.role is AppRole.ADMIN else None
    claimed: ClaimedEvidenceCleanup | None = None

    async def mutate(connection: AsyncConnection) -> IdempotentResponse:
        nonlocal claimed
        claimed = await _service(request, connection).claim_evidence_cleanup(
            principal,
            branch_id,
            entity_type,
            entity_id,
            body.expected_updated_at,
            scope=_scope(principal),
        )
        return IdempotentResponse(
            202,
            {"data": {"id": str(entity_id), "cleanupPending": True}},
            None,
            "training_record" if entity_type == "training_evidence" else "certification",
            entity_id,
        )

    result = await idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected_admin_branch_id=selected,
        operation_id=(
            "delete_training_evidence"
            if entity_type == "training_evidence"
            else "delete_certification_evidence"
        ),
        method="DELETE",
        route_parameters={"entityId": str(entity_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        resource_authorizer=lambda _connection, _kind, _resource_id: _noop(),
        mutation=mutate,
    )
    if claimed is not None:
        active = claimed
        try:
            async with asyncio.timeout(45):
                with suppress(StorageNotFoundError):
                    await request.app.state.object_storage.delete_object(key=active.object_key)
            await executor(request).execute(
                claims=claims,
                principal=principal,
                selected_admin_branch_id=selected,
                operation=lambda connection: _service(
                    request, connection
                ).complete_evidence_cleanup(active),
            )
        except Exception:
            await executor(request).execute(
                claims=claims,
                principal=principal,
                selected_admin_branch_id=selected,
                operation=lambda connection: _service(request, connection).fail_evidence_cleanup(
                    active
                ),
            )
            logger.error(
                "phase11d_evidence_cleanup_deferred",
                extra={"operation_id": str(active.operation_id), "error_code": "provider_error"},
            )
    return result


@training_file_router.delete(
    "/{record_id}", operation_id="delete_training_evidence", responses=ERRORS
)
async def delete_training_evidence(
    record_id: uuid.UUID,
    request: Request,
    body: VersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> Response:
    return await _cleanup(
        entity_type="training_evidence",
        entity_id=record_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=_branch(principal, selected_branch),
    )


@certification_file_router.delete(
    "/{certification_id}", operation_id="delete_certification_evidence", responses=ERRORS
)
async def delete_certification_evidence(
    certification_id: uuid.UUID,
    request: Request,
    body: VersionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected_branch: str | None = Header(default=None, alias="X-Workloop-Branch-ID"),
) -> Response:
    return await _cleanup(
        entity_type="certification_evidence",
        entity_id=certification_id,
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        branch_id=_branch(principal, selected_branch),
    )


async def _noop() -> None:
    return None
