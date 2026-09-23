from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.schemas.employee_document import (
    EmployeeDocumentResponse,
    EmployeeDocumentSubmissionRequest,
    EmployeeDocumentSubmissionResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError
from app.services.leave_attachment import ValidatedUpload


@dataclass(frozen=True, slots=True)
class ClaimedDocumentUpload:
    document_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


@dataclass(frozen=True, slots=True)
class ClaimedDocumentCleanup:
    document_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


@dataclass(frozen=True, slots=True)
class EmployeeDocumentListQuery:
    employee_id: uuid.UUID
    status: str | None
    document_type: str | None
    limit: int
    cursor: str | None


class EmployeeDocumentService:
    def __init__(
        self,
        connection: AsyncConnection,
        *,
        object_key_hmac_key: bytes,
        scanner_definition: str,
        cursor_codec: EmployeeCursorCodec | None = None,
    ) -> None:
        self.connection = connection
        self.key = object_key_hmac_key
        self.scanner_definition = scanner_definition
        self.cursor_codec = cursor_codec

    def _submission_token(self, document_id: uuid.UUID, expires: int) -> str:
        material = f"wled1.{document_id}.{expires}".encode("ascii")
        signature = base64.urlsafe_b64encode(hmac.new(self.key, material, hashlib.sha256).digest())
        return f"{material.decode()}.{signature.decode().rstrip('=')}"

    def _validate_token(self, document_id: uuid.UUID, token: str) -> None:
        parts = token.split(".")
        if len(parts) != 4 or parts[:2] != ["wled1", str(document_id)]:
            raise ServiceExecutionError("attachment_submission_unavailable")
        try:
            expires = int(parts[2])
        except ValueError:
            raise ServiceExecutionError("attachment_submission_unavailable") from None
        if expires <= int(time.time()) or not hmac.compare_digest(
            token, self._submission_token(document_id, expires)
        ):
            raise ServiceExecutionError("attachment_submission_unavailable")

    def _object_key(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> str:
        scope = b"\0".join(
            str(value).encode("ascii") for value in (company_id, branch_id, employee_id)
        )
        digest = base64.urlsafe_b64encode(
            hmac.new(self.key, scope, hashlib.sha256).digest()
        ).rstrip(b"=")[:22]
        return f"employee-documents/v1/{digest.decode()}/{item_id.hex}"

    async def create_submission(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: EmployeeDocumentSubmissionRequest,
    ) -> EmployeeDocumentSubmissionResponse:
        if principal.role is AppRole.ADMIN:
            if request.employee_id is None:
                raise ServiceExecutionError("validation_failed")
            employee_id = request.employee_id
        else:
            if request.employee_id is not None or principal.employee_id is None:
                raise ServiceExecutionError("operation_not_permitted")
            employee_id = principal.employee_id
        business_date = (
            await self.connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()
        if request.expiry_date is not None and request.expiry_date < business_date:
            raise ServiceExecutionError("validation_failed")
        employee_exists = (
            await self.connection.execute(
                text(
                    "SELECT 1 FROM public.employees WHERE id=:employee_id "
                    "AND company_id=:company_id AND branch_id=:branch_id AND active FOR SHARE"
                ),
                {
                    "employee_id": employee_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                },
            )
        ).scalar_one_or_none()
        if employee_exists is None:
            raise ServiceExecutionError("resource_not_found")
        document_id = uuid.uuid4()
        admin = principal.role is AppRole.ADMIN
        await self.connection.execute(
            text(
                """
INSERT INTO public.employee_documents(
 id,company_id,branch_id,employee_id,document_type,document_number,
 file_name,file_size,storage_path,expiry_date,notes,status,rejection_reason,
 submitted_by,reviewed_by_app_user_id,reviewed_at,created_by_app_user_id)
VALUES(:id,:company_id,:branch_id,:employee_id,:document_type,:document_number,
 NULL,NULL,NULL,:expiry_date,:notes,:status,'',:submitted_by,:reviewer,
 CASE WHEN :admin THEN statement_timestamp() ELSE NULL END,:creator)
"""
            ),
            {
                "id": document_id,
                "company_id": principal.company_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
                "document_type": request.document_type,
                "document_number": request.document_number,
                "expiry_date": request.expiry_date,
                "notes": request.notes,
                "status": "verified" if admin else "pending_verification",
                "submitted_by": "hr" if admin else "employee",
                "reviewer": principal.app_user_id if admin else None,
                "admin": admin,
                "creator": principal.app_user_id,
            },
        )
        expires = int(time.time()) + 900
        return EmployeeDocumentSubmissionResponse(
            id=document_id,
            submission_token=self._submission_token(document_id, expires),
            expires_at=time_to_datetime(expires),
        )

    async def claim_upload(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        document_id: uuid.UUID,
        upload: ValidatedUpload,
    ) -> ClaimedDocumentUpload:
        self._validate_token(document_id, upload.submission_token)
        row = (
            await self.connection.execute(
                text(
                    """
SELECT document.id,document.company_id,document.branch_id,document.employee_id
FROM public.employee_documents document
WHERE document.id=:id AND document.company_id=:company_id AND document.branch_id=:branch_id
  AND document.created_by_app_user_id=:creator AND document.file_security_scan_id IS NULL
  AND document.cleanup_requested_at IS NULL AND document.upload_claimed_at IS NULL
FOR UPDATE
"""
                ),
                {
                    "id": document_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "creator": principal.app_user_id,
                },
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("attachment_submission_unavailable")
        object_key = self._object_key(row.company_id, row.branch_id, row.employee_id, row.id)
        await self.connection.execute(
            text(
                "UPDATE public.employee_documents SET upload_claimed_at=statement_timestamp() "
                "WHERE id=:id"
            ),
            {"id": row.id},
        )
        operation_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.storage_operations(
 company_id,branch_id,employee_id,created_by_app_user_id,
 entity_type,entity_id,operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,'employee_document',:entity_id,
 'upload',:object_key)
RETURNING id
"""
                ),
                {
                    "company_id": row.company_id,
                    "branch_id": row.branch_id,
                    "employee_id": row.employee_id,
                    "creator": principal.app_user_id,
                    "entity_id": row.id,
                    "object_key": object_key,
                },
            )
        ).scalar_one()
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='claimed',attempt_count=1,claimed_at=statement_timestamp(),
 lease_expires_at=statement_timestamp()+interval '15 minutes',updated_at=statement_timestamp()
WHERE id=:id AND status='pending'
"""
            ),
            {"id": operation_id},
        )
        return ClaimedDocumentUpload(row.id, operation_id, object_key)

    async def complete_upload(
        self,
        principal: AuthorizationPrincipal,
        claimed: ClaimedDocumentUpload,
        upload: ValidatedUpload,
    ) -> EmployeeDocumentResponse:
        row = (
            await self.connection.execute(
                text(
                    """
SELECT id,company_id,branch_id,employee_id,created_by_app_user_id
FROM public.employee_documents
WHERE id=:id AND company_id=:company_id AND created_by_app_user_id=:creator
  AND file_security_scan_id IS NULL AND cleanup_requested_at IS NULL FOR UPDATE
"""
                ),
                {
                    "id": claimed.document_id,
                    "company_id": principal.company_id,
                    "creator": principal.app_user_id,
                },
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("attachment_submission_unavailable")
        scan_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.file_security_scans(
 company_id,branch_id,employee_id,created_by_app_user_id,entity_type,entity_id,
 object_key,content_type,size_bytes,sha256,scanner_definition)
VALUES(:company_id,:branch_id,:employee_id,:creator,'employee_document',:entity_id,
 :object_key,:content_type,:size_bytes,:sha256,:scanner_definition)
RETURNING id
"""
                ),
                {
                    "company_id": row.company_id,
                    "branch_id": row.branch_id,
                    "employee_id": row.employee_id,
                    "creator": row.created_by_app_user_id,
                    "entity_id": row.id,
                    "object_key": claimed.object_key,
                    "content_type": upload.content_type,
                    "size_bytes": len(upload.body),
                    "sha256": upload.sha256,
                    "scanner_definition": self.scanner_definition,
                },
            )
        ).scalar_one()
        await self.connection.execute(
            text(
                """
UPDATE public.employee_documents
SET file_name=:file_name,file_size=:file_size,storage_path=:object_key,
 content_type=:content_type,sha256=:sha256,file_security_scan_id=:scan_id,
 uploaded_at=statement_timestamp()
WHERE id=:id
"""
            ),
            {
                "id": row.id,
                "file_name": upload.file_name,
                "file_size": len(upload.body),
                "object_key": claimed.object_key,
                "content_type": upload.content_type,
                "sha256": upload.sha256,
                "scan_id": scan_id,
            },
        )
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations SET status='succeeded',claimed_at=NULL,
 lease_expires_at=NULL,completed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )
        await append_audit_event(
            self.connection,
            action="employee_document_uploaded",
            entity_type="employee_document",
            entity_id=row.id,
            changed_fields=["file_name", "file_size", "content_type", "status"],
            reason="Employee document uploaded",
            metadata={"operation_id": str(claimed.operation_id)},
        )
        return await self.get(principal, row.branch_id, row.id)

    async def fail_upload(self, claimed: ClaimedDocumentUpload) -> None:
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations SET status='failed',last_error_code='provider_error',
 next_attempt_at=statement_timestamp()+interval '1 minute',claimed_at=NULL,
 lease_expires_at=NULL,updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: EmployeeDocumentListQuery,
        *,
        operation_id: str,
    ) -> tuple[list[EmployeeDocumentResponse], str | None]:
        employee_id = query.employee_id
        if principal.role is not AppRole.ADMIN and principal.employee_id != employee_id:
            raise ServiceExecutionError("operation_not_permitted")
        if self.cursor_codec is None:
            raise RuntimeError("document list cursor codec is required")
        try:
            cursor_id = self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        cursor_clause = ""
        parameters: dict[str, object] = {
            "company_id": principal.company_id,
            "branch_id": branch_id,
            "employee_id": employee_id,
            "status": query.status,
            "document_type": query.document_type,
            "limit": query.limit + 1,
        }
        if cursor_id is not None:
            anchor = (
                await self.connection.execute(
                    text(
                        "SELECT uploaded_at FROM public.employee_documents "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id "
                        "AND employee_id=:employee_id AND content_type IS NOT NULL "
                        "AND cleanup_requested_at IS NULL "
                        "AND (CAST(:status AS text) IS NULL OR status=:status) "
                        "AND (CAST(:document_type AS text) IS NULL OR document_type=:document_type)"
                    ),
                    {**parameters, "id": cursor_id},
                )
            ).scalar_one_or_none()
            if anchor is None:
                raise ServiceExecutionError("invalid_cursor")
            parameters.update({"cursor_uploaded_at": anchor, "cursor_id": cursor_id})
            cursor_clause = (
                " AND (document.uploaded_at,document.id) < (:cursor_uploaded_at,:cursor_id)"
            )
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT document.id,document.employee_id,document.document_type,document.status,
 NULLIF(document.rejection_reason,'') rejection_reason,document.file_name,
 document.file_size size_bytes,document.content_type,document.expiry_date,document.notes,
 CASE WHEN document.reviewed_by_app_user_id IS NULL THEN NULL
      WHEN reviewer.employee_id IS NULL THEN 'Administrator' ELSE employee.name END reviewer_name,
 document.uploaded_at,document.reviewed_at,document.updated_at
FROM public.employee_documents document
LEFT JOIN public.user_profiles reviewer
  ON reviewer.app_user_id=document.reviewed_by_app_user_id
LEFT JOIN public.employees employee ON employee.id=reviewer.employee_id
WHERE document.company_id=:company_id AND document.branch_id=:branch_id
  AND document.employee_id=:employee_id AND document.content_type IS NOT NULL
  AND document.cleanup_requested_at IS NULL
  AND (CAST(:status AS text) IS NULL OR document.status=:status)
  AND (CAST(:document_type AS text) IS NULL OR document.document_type=:document_type)
{cursor_clause}
ORDER BY document.uploaded_at DESC,document.id DESC LIMIT :limit
"""
                    ),
                    parameters,
                )
            )
            .mappings()
            .all()
        )
        visible = rows[: query.limit]
        items = [EmployeeDocumentResponse.model_validate(row) for row in visible]
        next_cursor = (
            self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                last_id=visible[-1]["id"],
            )
            if len(rows) > query.limit
            else None
        )
        return items, next_cursor

    async def get(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, document_id: uuid.UUID
    ) -> EmployeeDocumentResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT document.id,document.employee_id,document.document_type,document.status,
 NULLIF(document.rejection_reason,'') rejection_reason,document.file_name,
 document.file_size size_bytes,document.content_type,document.expiry_date,document.notes,
 CASE WHEN document.reviewed_by_app_user_id IS NULL THEN NULL
      WHEN reviewer.employee_id IS NULL THEN 'Administrator' ELSE employee.name END reviewer_name,
 document.uploaded_at,document.reviewed_at,document.updated_at
FROM public.employee_documents document
LEFT JOIN public.user_profiles reviewer ON reviewer.app_user_id=document.reviewed_by_app_user_id
LEFT JOIN public.employees employee ON employee.id=reviewer.employee_id
WHERE document.id=:id AND document.company_id=:company_id AND document.branch_id=:branch_id
  AND document.content_type IS NOT NULL AND document.cleanup_requested_at IS NULL
"""
                    ),
                    {
                        "id": document_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None or (
            principal.role is not AppRole.ADMIN and row["employee_id"] != principal.employee_id
        ):
            raise ServiceExecutionError("resource_not_found")
        return EmployeeDocumentResponse.model_validate(row)

    async def decide(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        document_id: uuid.UUID,
        expected_updated_at: object,
        *,
        verify: bool,
        reason: str | None,
    ) -> EmployeeDocumentResponse:
        row = (
            await self.connection.execute(
                text(
                    """
SELECT id,status,updated_at FROM public.employee_documents
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND content_type IS NOT NULL AND cleanup_requested_at IS NULL FOR UPDATE
"""
                ),
                {"id": document_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        if row.updated_at != expected_updated_at or row.status != "pending_verification":
            raise ServiceExecutionError("state_conflict")
        if not verify and not reason:
            raise ServiceExecutionError("validation_failed")
        status = "verified" if verify else "rejected"
        await self.connection.execute(
            text(
                """
UPDATE public.employee_documents SET status=:status,rejection_reason=:reason,
 reviewed_by_app_user_id=:actor,reviewed_at=statement_timestamp() WHERE id=:id
"""
            ),
            {
                "id": document_id,
                "status": status,
                "reason": "" if verify else reason,
                "actor": principal.app_user_id,
            },
        )
        await append_audit_event(
            self.connection,
            action="employee_document_verified" if verify else "employee_document_rejected",
            entity_type="employee_document",
            entity_id=document_id,
            changed_fields=(
                ["status", "reviewed_by_app_user_id", "reviewed_at"]
                if verify
                else ["status", "rejection_reason"]
            ),
            reason="Employee document verified" if verify else "Employee document rejected",
            metadata={"transition": f"pending_verification_to_{status}"},
        )
        return await self.get(principal, branch_id, document_id)

    async def load_for_download(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, document_id: uuid.UUID
    ) -> dict[str, object]:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT document.id,document.employee_id,document.file_name,document.file_size,
 document.storage_path,document.content_type,document.sha256,
 public.file_security_scan_allows_download(
   document.file_security_scan_id,'employee_document',document.id,document.storage_path,
   document.content_type,document.file_size,document.sha256,:scanner_definition) scan_released
FROM public.employee_documents document
WHERE document.id=:id AND document.company_id=:company_id AND document.branch_id=:branch_id
  AND document.content_type IS NOT NULL AND document.cleanup_requested_at IS NULL
"""
                    ),
                    {
                        "id": document_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "scanner_definition": self.scanner_definition,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None or (
            principal.role is not AppRole.ADMIN and row["employee_id"] != principal.employee_id
        ):
            raise ServiceExecutionError("resource_not_found")
        if not row["scan_released"]:
            raise ServiceExecutionError("service_unavailable")
        return dict(row)

    async def claim_cleanup(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        document_id: uuid.UUID,
        expected_updated_at: object,
    ) -> ClaimedDocumentCleanup:
        row = (
            await self.connection.execute(
                text(
                    """
SELECT id,company_id,branch_id,employee_id,status,storage_path,updated_at
FROM public.employee_documents
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND content_type IS NOT NULL AND cleanup_requested_at IS NULL FOR UPDATE
"""
                ),
                {"id": document_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None or (
            principal.role is not AppRole.ADMIN and row.employee_id != principal.employee_id
        ):
            raise ServiceExecutionError("resource_not_found")
        if row.status not in {"pending_verification", "rejected"}:
            raise ServiceExecutionError("operation_not_permitted")
        if row.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        operation_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.storage_operations(
 company_id,branch_id,employee_id,created_by_app_user_id,entity_type,entity_id,
 operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,'employee_document',:entity_id,
 'delete',:object_key)
RETURNING id
"""
                ),
                {
                    "company_id": row.company_id,
                    "branch_id": row.branch_id,
                    "employee_id": row.employee_id,
                    "creator": principal.app_user_id,
                    "entity_id": row.id,
                    "object_key": row.storage_path,
                },
            )
        ).scalar_one()
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='claimed',attempt_count=1,claimed_at=statement_timestamp(),
 lease_expires_at=statement_timestamp()+interval '15 minutes',updated_at=statement_timestamp()
WHERE id=:id AND status='pending'
"""
            ),
            {"id": operation_id},
        )
        await self.connection.execute(
            text(
                "UPDATE public.employee_documents SET cleanup_requested_at=statement_timestamp() "
                "WHERE id=:id"
            ),
            {"id": document_id},
        )
        await append_audit_event(
            self.connection,
            action="employee_document_cleanup_requested",
            entity_type="employee_document",
            entity_id=document_id,
            changed_fields=["cleanup_requested_at"],
            reason="Employee document cleanup requested",
            metadata={"operation_id": str(operation_id)},
        )
        return ClaimedDocumentCleanup(document_id, operation_id, row.storage_path)

    async def complete_cleanup(self, claimed: ClaimedDocumentCleanup) -> None:
        await self.connection.execute(
            text(
                "DELETE FROM public.employee_documents WHERE id=:id "
                "AND cleanup_requested_at IS NOT NULL"
            ),
            {"id": claimed.document_id},
        )
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations SET status='succeeded',claimed_at=NULL,
 lease_expires_at=NULL,completed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )

    async def fail_cleanup(self, claimed: ClaimedDocumentCleanup) -> None:
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations SET status='failed',last_error_code='provider_error',
 next_attempt_at=statement_timestamp()+interval '1 minute',claimed_at=NULL,
 lease_expires_at=NULL,updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "employee_document" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        exists = (
            await self.connection.execute(
                text(
                    "SELECT employee_id FROM public.employee_documents WHERE id=:id "
                    "AND company_id=:company_id AND branch_id=:branch_id"
                ),
                {"id": resource_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if exists is None and principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("resource_not_found")
        if (
            exists is not None
            and principal.role is not AppRole.ADMIN
            and exists != principal.employee_id
        ):
            raise ServiceExecutionError("resource_not_found")


def time_to_datetime(value: int):
    from datetime import UTC, datetime

    return datetime.fromtimestamp(value, UTC)
