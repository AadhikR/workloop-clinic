from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.http.middleware import UPLOAD_FILE_LIMIT_BYTES, UPLOAD_METADATA_LIMIT_BYTES
from app.models.identity import AppRole
from app.schemas.leave_attachment import (
    AttachmentSubmissionRequest,
    AttachmentSubmissionResponse,
    LeaveAttachmentResponse,
)
from app.services.execution import ServiceExecutionError

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
TOKEN_PATTERN = re.compile(
    r"wlat1\.([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\."
    r"([A-Za-z0-9_-]{43})"
)
BIDI_CONTROLS = frozenset(
    chr(value) for value in (*range(0x202A, 0x202F), *range(0x2066, 0x206A), 0x200E, 0x200F)
)


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    body: bytes
    file_name: str
    content_type: str
    sha256: str
    submission_token: str


@dataclass(frozen=True, slots=True)
class ClaimedUpload:
    attachment_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


@dataclass(frozen=True, slots=True)
class ClaimedCleanup:
    attachment_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


def _normalize_file_name(value: str) -> tuple[str, str]:
    candidate = unicodedata.normalize("NFC", value).strip()
    if (
        not candidate
        or candidate.startswith(".")
        or candidate.endswith(".")
        or any(
            character in {"/", "\\"}
            or character in BIDI_CONTROLS
            or unicodedata.category(character).startswith("C")
            for character in candidate
        )
    ):
        raise ServiceExecutionError("validation_failed")
    candidate = " ".join(candidate.split())
    stem, dot, extension = candidate.rpartition(".")
    if not dot or extension.lower() not in {"pdf", "png", "jpg", "jpeg"}:
        raise ServiceExecutionError("validation_failed")
    canonical_extension = "jpg" if extension.lower() == "jpeg" else extension.lower()
    cleaned = "".join(
        character
        if character.isalpha() or character.isdigit() or character in {" ", ".", "_", "-"}
        else "_"
        for character in stem
    )
    cleaned = re.sub(r"_+", "_", cleaned).strip()
    if not cleaned:
        cleaned = "attachment"
    suffix = f".{canonical_extension}"
    while len((cleaned + suffix).encode()) > 180:
        cleaned = cleaned[:-1]
    return cleaned + suffix, canonical_extension


def _validate_signature(body: bytes, extension: str) -> str:
    if extension == "pdf":
        trimmed = body.rstrip(b" \t\r\n\f\0")
        valid = body.startswith((b"%PDF-1.", b"%PDF-2.")) and trimmed.endswith(b"%%EOF")
        content_type = "application/pdf"
    elif extension == "png":
        valid = (
            len(body) >= 45
            and body.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
            and body[-12:-8] == b"\x00\x00\x00\x00"
            and body[-8:-4] == b"IEND"
        )
        content_type = "image/png"
    else:
        valid = (
            len(body) >= 6
            and body[:3] == b"\xff\xd8\xff"
            and body[3] not in {0x00, 0xFF}
            and body.endswith(b"\xff\xd9")
        )
        content_type = "image/jpeg"
    if not valid:
        raise ServiceExecutionError("validation_failed")
    return content_type


def parse_upload(content_type_header: str, body: bytes) -> ValidatedUpload:
    message = BytesParser(policy=policy.default).parsebytes(
        b"MIME-Version: 1.0\r\nContent-Type: "
        + content_type_header.encode("ascii")
        + b"\r\n\r\n"
        + body
    )
    if not message.is_multipart():
        raise ServiceExecutionError("invalid_request")
    parts: dict[str, object] = {}
    metadata_size = 0
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            raise ServiceExecutionError("invalid_request")
        name = part.get_param("name", header="content-disposition")
        if name not in {"file", "submissionToken", "sha256"} or name in parts:
            raise ServiceExecutionError("invalid_request")
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            raise ServiceExecutionError("invalid_request")
        if name == "file":
            filename = part.get_filename()
            if not isinstance(filename, str) or not filename:
                raise ServiceExecutionError("validation_failed")
            parts[name] = (payload, filename, part.get_content_type())
        else:
            if part.get_filename() is not None:
                raise ServiceExecutionError("invalid_request")
            metadata_size += len(payload)
            try:
                parts[name] = payload.decode("ascii")
            except UnicodeDecodeError:
                raise ServiceExecutionError("validation_failed") from None
    if set(parts) != {"file", "submissionToken", "sha256"}:
        raise ServiceExecutionError("invalid_request")
    if metadata_size > UPLOAD_METADATA_LIMIT_BYTES:
        raise ServiceExecutionError("request_too_large")
    file_body, raw_name, declared_type = cast(tuple[bytes, str, str], parts["file"])
    if not 1 <= len(file_body) <= UPLOAD_FILE_LIMIT_BYTES:
        raise ServiceExecutionError("request_too_large")
    normalized_name, extension = _normalize_file_name(raw_name)
    canonical_type = _validate_signature(file_body, extension)
    if declared_type != canonical_type:
        raise ServiceExecutionError("unsupported_media_type")
    supplied_digest = cast(str, parts["sha256"])
    digest = hashlib.sha256(file_body).hexdigest()
    if not SHA256_PATTERN.fullmatch(supplied_digest) or not hmac.compare_digest(
        supplied_digest, digest
    ):
        raise ServiceExecutionError("validation_failed")
    token = cast(str, parts["submissionToken"])
    if not TOKEN_PATTERN.fullmatch(token):
        raise ServiceExecutionError("attachment_submission_unavailable")
    return ValidatedUpload(
        body=file_body,
        file_name=normalized_name,
        content_type=canonical_type,
        sha256=digest,
        submission_token=token,
    )


class LeaveAttachmentService:
    def __init__(self, connection: AsyncConnection, *, object_key_hmac_key: bytes) -> None:
        self._connection = connection
        self._object_key_hmac_key = object_key_hmac_key

    async def create_submission(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: AttachmentSubmissionRequest,
    ) -> AttachmentSubmissionResponse:
        if principal.role is AppRole.ADMIN:
            if principal.employee_id is not None:
                raise ServiceExecutionError("operation_not_permitted")
            if request.request_id is None and request.employee_id is None:
                raise ServiceExecutionError("validation_failed")
        else:
            if principal.employee_id is None or principal.branch_id != branch_id:
                raise ServiceExecutionError("operation_not_permitted")
            if request.employee_id is not None:
                raise ServiceExecutionError("operation_not_permitted")

        employee_id = principal.employee_id if request.request_id is None else None
        if request.employee_id is not None:
            employee_id = request.employee_id
        if request.request_id is not None:
            row = (
                await self._connection.execute(
                    text(
                        """
SELECT employee_id FROM public.leave_requests AS request
WHERE request.id=:request_id AND request.company_id=:company_id
  AND request.branch_id=:branch_id AND request.status='Pending'
  AND (:employee_id IS NULL OR request.employee_id=:employee_id)
  AND NOT EXISTS (
    SELECT 1 FROM public.leave_attachments AS attachment
    WHERE attachment.leave_request_id=request.id)
"""
                    ),
                    {
                        "request_id": request.request_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": principal.employee_id,
                    },
                )
            ).one_or_none()
            if row is None:
                raise ServiceExecutionError("resource_not_found")
            employee_id = cast(uuid.UUID, row.employee_id)
        assert employee_id is not None
        eligible = (
            await self._connection.execute(
                text(
                    """
SELECT id FROM public.employees
WHERE id=:employee_id AND company_id=:company_id AND branch_id=:branch_id
  AND active AND employment_status IN ('Active','Probation','On Leave')
"""
                ),
                {
                    "employee_id": employee_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                },
            )
        ).scalar_one_or_none()
        if eligible is None:
            raise ServiceExecutionError("resource_not_found")
        attachment_id = uuid.uuid4()
        secret = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        token = f"wlat1.{attachment_id}.{secret}"
        digest = hashlib.sha256(token.encode("ascii")).digest()
        row = (
            await self._connection.execute(
                text(
                    """
INSERT INTO public.leave_attachments(
  id,company_id,branch_id,employee_id,leave_request_id,created_by_app_user_id,
  submission_token_digest,expires_at)
VALUES(:id,:company_id,:branch_id,:employee_id,:request_id,:creator,:digest,
       statement_timestamp()+interval '15 minutes')
RETURNING id,expires_at
"""
                ),
                {
                    "id": attachment_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "request_id": request.request_id,
                    "creator": principal.app_user_id,
                    "digest": digest,
                },
            )
        ).one()
        return AttachmentSubmissionResponse(
            id=row.id, submission_token=token, expires_at=row.expires_at
        )

    def _object_key(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> str:
        message = b"\0".join(value.bytes for value in (company_id, branch_id, employee_id, item_id))
        digest = base64.urlsafe_b64encode(
            hmac.digest(self._object_key_hmac_key, message, "sha256")
        ).rstrip(b"=")[:22]
        return f"leave-attachments/v1/{digest.decode()}/{item_id.hex}"

    async def claim_upload(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        attachment_id: uuid.UUID,
        upload: ValidatedUpload,
    ) -> ClaimedUpload:
        row = (
            await self._connection.execute(
                text(
                    """
SELECT id,company_id,branch_id,employee_id,submission_token_digest
FROM public.leave_attachments
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND created_by_app_user_id=:creator AND status='pending'
  AND expires_at>statement_timestamp()
FOR UPDATE
"""
                ),
                {
                    "id": attachment_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "creator": principal.app_user_id,
                },
            )
        ).one_or_none()
        token_digest = hashlib.sha256(upload.submission_token.encode("ascii")).digest()
        if (
            row is None
            or not hmac.compare_digest(bytes(row.submission_token_digest), token_digest)
            or not upload.submission_token.startswith(f"wlat1.{attachment_id}.")
        ):
            raise ServiceExecutionError("attachment_submission_unavailable")
        object_key = self._object_key(row.company_id, row.branch_id, row.employee_id, row.id)
        await self._connection.execute(
            text(
                """
UPDATE public.leave_attachments
SET status='uploading',token_consumed_at=statement_timestamp(),
    updated_at=statement_timestamp()
WHERE id=:id
"""
            ),
            {"id": attachment_id},
        )
        operation_id = (
            await self._connection.execute(
                text(
                    """
INSERT INTO public.storage_operations(
  company_id,branch_id,employee_id,created_by_app_user_id,
  entity_type,entity_id,operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,
       'leave_attachment',:attachment_id,'upload',:object_key)
RETURNING id
"""
                ),
                {
                    "company_id": row.company_id,
                    "branch_id": row.branch_id,
                    "employee_id": row.employee_id,
                    "creator": principal.app_user_id,
                    "attachment_id": attachment_id,
                    "object_key": object_key,
                },
            )
        ).scalar_one()
        await self._connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='claimed',attempt_count=1,claimed_at=statement_timestamp(),
    lease_expires_at=statement_timestamp()+interval '15 minutes',
    updated_at=statement_timestamp()
WHERE id=:operation_id AND status='pending'
"""
            ),
            {"operation_id": operation_id},
        )
        return ClaimedUpload(attachment_id, operation_id, object_key)

    async def complete_upload(
        self,
        principal: AuthorizationPrincipal,
        claimed: ClaimedUpload,
        upload: ValidatedUpload,
    ) -> LeaveAttachmentResponse:
        row = (
            await self._connection.execute(
                text(
                    """
SELECT leave_request_id FROM public.leave_attachments
WHERE id=:id AND company_id=:company_id AND created_by_app_user_id=:creator
  AND status='uploading'
FOR UPDATE
"""
                ),
                {
                    "id": claimed.attachment_id,
                    "company_id": principal.company_id,
                    "creator": principal.app_user_id,
                },
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("attachment_submission_unavailable")
        attached = row.leave_request_id is not None
        result = (
            (
                await self._connection.execute(
                    text(
                        """
UPDATE public.leave_attachments
SET file_name=:file_name,content_type=:content_type,size_bytes=:size_bytes,
    sha256=:sha256,object_key=:object_key,status=:status,
    uploaded_at=statement_timestamp(),
    attached_at=CASE WHEN :attached THEN statement_timestamp() ELSE NULL END,
    expires_at=CASE WHEN :attached THEN NULL
                    ELSE statement_timestamp()+interval '24 hours' END,
    updated_at=statement_timestamp()
WHERE id=:id
RETURNING id,file_name,content_type,size_bytes,sha256,uploaded_at,expires_at
"""
                    ),
                    {
                        "id": claimed.attachment_id,
                        "file_name": upload.file_name,
                        "content_type": upload.content_type,
                        "size_bytes": len(upload.body),
                        "sha256": upload.sha256,
                        "object_key": claimed.object_key,
                        "status": "attached" if attached else "staged",
                        "attached": attached,
                    },
                )
            )
            .mappings()
            .one()
        )
        await self._connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='succeeded',claimed_at=NULL,lease_expires_at=NULL,
    completed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )
        await append_audit_event(
            self._connection,
            action="leave_attachment_uploaded",
            entity_type="leave_attachment",
            entity_id=claimed.attachment_id,
            changed_fields=["file_name", "content_type", "size_bytes", "sha256", "status"],
            reason="Leave attachment uploaded",
            metadata={"storage_operation_id": str(claimed.operation_id)},
        )
        return LeaveAttachmentResponse.model_validate(result)

    async def fail_upload(self, claimed: ClaimedUpload) -> None:
        await self._connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='failed',last_error_code='provider_error',next_attempt_at=statement_timestamp()
    +interval '1 minute',claimed_at=NULL,lease_expires_at=NULL,updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )

    async def load_for_download(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, attachment_id: uuid.UUID
    ) -> dict[str, object]:
        row = (
            (
                await self._connection.execute(
                    text(
                        """
SELECT id,file_name,content_type,size_bytes,sha256,object_key,status,expires_at,
       employee_id,created_by_app_user_id
FROM public.leave_attachments
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND status IN ('staged','attached')
"""
                    ),
                    {
                        "id": attachment_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return dict(row)

    async def request_cleanup(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        attachment_id: uuid.UUID,
        trigger: str,
    ) -> ClaimedCleanup:
        if trigger not in {
            "failed_submission",
            "request_cancelled",
            "staged_expired",
            "missing_object",
        }:
            raise ValueError("unsupported cleanup trigger")
        row = (
            await self._connection.execute(
                text(
                    """
SELECT id,company_id,branch_id,employee_id,object_key,created_by_app_user_id
FROM public.leave_attachments
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND status IN ('staged','attached')
FOR UPDATE
"""
                ),
                {"id": attachment_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None or (
            principal.role is not AppRole.ADMIN
            and (
                principal.employee_id != row.employee_id
                or principal.app_user_id != row.created_by_app_user_id
            )
        ):
            raise ServiceExecutionError("resource_not_found")
        operation_id = (
            await self._connection.execute(
                text(
                    """
INSERT INTO public.storage_operations(
  company_id,branch_id,employee_id,created_by_app_user_id,
  entity_type,entity_id,operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,
       'leave_attachment',:attachment_id,'delete',:object_key)
RETURNING id
"""
                ),
                {
                    "company_id": row.company_id,
                    "branch_id": row.branch_id,
                    "employee_id": row.employee_id,
                    "creator": principal.app_user_id,
                    "attachment_id": attachment_id,
                    "object_key": row.object_key,
                },
            )
        ).scalar_one()
        await self._connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='claimed',attempt_count=1,claimed_at=statement_timestamp(),
    lease_expires_at=statement_timestamp()+interval '15 minutes',
    updated_at=statement_timestamp()
WHERE id=:id AND status='pending'
"""
            ),
            {"id": operation_id},
        )
        await self._connection.execute(
            text(
                """
UPDATE public.leave_attachments
SET status='cleanup_pending',cleanup_requested_at=statement_timestamp(),
    expires_at=NULL,updated_at=statement_timestamp()
WHERE id=:id
"""
            ),
            {"id": attachment_id},
        )
        await append_audit_event(
            self._connection,
            action="leave_attachment_cleanup_requested",
            entity_type="leave_attachment",
            entity_id=attachment_id,
            changed_fields=["status"],
            reason="Leave attachment cleanup requested",
            metadata={"storage_operation_id": str(operation_id), "trigger": trigger},
        )
        return ClaimedCleanup(attachment_id, operation_id, row.object_key)

    async def complete_cleanup(self, claimed: ClaimedCleanup) -> None:
        await self._connection.execute(
            text(
                """
UPDATE public.leave_attachments
SET status='removed',removed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:id AND status='cleanup_pending'
"""
            ),
            {"id": claimed.attachment_id},
        )
        await self._connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='succeeded',claimed_at=NULL,lease_expires_at=NULL,
    completed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )
