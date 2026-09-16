from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from dataclasses import dataclass
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.schemas.expense_receipt import (
    ExpenseReceiptResponse,
    ReceiptSubmissionRequest,
    ReceiptSubmissionResponse,
)
from app.services.execution import ServiceExecutionError
from app.services.leave_attachment import ValidatedUpload


@dataclass(frozen=True, slots=True)
class ClaimedReceiptUpload:
    receipt_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


@dataclass(frozen=True, slots=True)
class ClaimedReceiptCleanup:
    receipt_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


class ExpenseReceiptService:
    def __init__(self, connection: AsyncConnection, *, object_key_hmac_key: bytes) -> None:
        self.connection = connection
        self.object_key_hmac_key = object_key_hmac_key

    async def create_submission(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: ReceiptSubmissionRequest,
    ) -> ReceiptSubmissionResponse:
        if principal.role is AppRole.ADMIN:
            if principal.employee_id is not None:
                raise ServiceExecutionError("operation_not_permitted")
            if request.claim_id is None and request.employee_id is None:
                raise ServiceExecutionError("validation_failed")
        elif (
            principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}
            or principal.employee_id is None
            or principal.branch_id != branch_id
            or request.employee_id is not None
        ):
            raise ServiceExecutionError("operation_not_permitted")

        employee_id = request.employee_id or principal.employee_id
        if request.claim_id is not None:
            claim = (
                await self.connection.execute(
                    text(
                        """
SELECT employee_id FROM public.expense_claims AS claim
WHERE claim.id=:claim_id AND claim.company_id=:company_id AND claim.branch_id=:branch_id
  AND claim.status IN ('pending','manager_rejected','rejected')
  AND claim.payroll_run_id IS NULL
  AND (:employee_id IS NULL OR claim.employee_id=:employee_id)
  AND NOT EXISTS (
    SELECT 1 FROM public.expense_receipts AS receipt
    WHERE receipt.expense_claim_id=claim.id)
"""
                    ),
                    {
                        "claim_id": request.claim_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": principal.employee_id,
                    },
                )
            ).one_or_none()
            if claim is None:
                raise ServiceExecutionError("resource_not_found")
            employee_id = cast(uuid.UUID, claim.employee_id)
        if employee_id is None:
            raise ServiceExecutionError("validation_failed")
        eligible = (
            await self.connection.execute(
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
        receipt_id = uuid.uuid4()
        secret = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        token = f"wler1.{receipt_id}.{secret}"
        digest = hashlib.sha256(token.encode("ascii")).digest()
        row = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.expense_receipts(
  id,company_id,branch_id,employee_id,expense_claim_id,created_by_app_user_id,
  submission_token_digest,expires_at)
VALUES(:id,:company_id,:branch_id,:employee_id,:claim_id,:creator,:digest,
       statement_timestamp()+interval '15 minutes')
RETURNING id,expires_at
"""
                ),
                {
                    "id": receipt_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "claim_id": request.claim_id,
                    "creator": principal.app_user_id,
                    "digest": digest,
                },
            )
        ).one()
        return ReceiptSubmissionResponse(
            id=row.id, submission_token=token, expires_at=row.expires_at
        )

    def _object_key(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        receipt_id: uuid.UUID,
    ) -> str:
        message = b"\0".join(
            value.bytes for value in (company_id, branch_id, employee_id, receipt_id)
        )
        digest = base64.urlsafe_b64encode(
            hmac.digest(self.object_key_hmac_key, message, "sha256")
        ).rstrip(b"=")[:22]
        return f"expense-receipts/v1/{digest.decode()}/{receipt_id.hex}"

    async def claim_upload(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        receipt_id: uuid.UUID,
        upload: ValidatedUpload,
    ) -> ClaimedReceiptUpload:
        row = (
            await self.connection.execute(
                text(
                    """
SELECT id,company_id,branch_id,employee_id,submission_token_digest
FROM public.expense_receipts
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND created_by_app_user_id=:creator AND status='pending'
  AND expires_at>statement_timestamp()
FOR UPDATE
"""
                ),
                {
                    "id": receipt_id,
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
            or not upload.submission_token.startswith(f"wler1.{receipt_id}.")
        ):
            raise ServiceExecutionError("attachment_submission_unavailable")
        object_key = self._object_key(row.company_id, row.branch_id, row.employee_id, row.id)
        await self.connection.execute(
            text(
                """
UPDATE public.expense_receipts
SET status='uploading',token_consumed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:id
"""
            ),
            {"id": receipt_id},
        )
        operation_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.storage_operations(
  company_id,branch_id,employee_id,created_by_app_user_id,
  entity_type,entity_id,operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,
       'expense_receipt',:receipt_id,'upload',:object_key)
RETURNING id
"""
                ),
                {
                    "company_id": row.company_id,
                    "branch_id": row.branch_id,
                    "employee_id": row.employee_id,
                    "creator": principal.app_user_id,
                    "receipt_id": receipt_id,
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
        return ClaimedReceiptUpload(receipt_id, operation_id, object_key)

    async def complete_upload(
        self,
        principal: AuthorizationPrincipal,
        claimed: ClaimedReceiptUpload,
        upload: ValidatedUpload,
    ) -> ExpenseReceiptResponse:
        row = (
            await self.connection.execute(
                text(
                    """
SELECT expense_claim_id FROM public.expense_receipts
WHERE id=:id AND company_id=:company_id AND created_by_app_user_id=:creator
  AND status='uploading'
FOR UPDATE
"""
                ),
                {
                    "id": claimed.receipt_id,
                    "company_id": principal.company_id,
                    "creator": principal.app_user_id,
                },
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("attachment_submission_unavailable")
        attached = row.expense_claim_id is not None
        result = (
            (
                await self.connection.execute(
                    text(
                        """
UPDATE public.expense_receipts
SET file_name=:file_name,content_type=:content_type,size_bytes=:size_bytes,
    sha256=:sha256,object_key=:object_key,status=:status,
    uploaded_at=statement_timestamp(),
    attached_at=CASE WHEN :attached THEN statement_timestamp() ELSE NULL END,
    expires_at=CASE WHEN :attached THEN NULL ELSE statement_timestamp()+interval '24 hours' END,
    updated_at=statement_timestamp()
WHERE id=:id
RETURNING id,file_name,content_type,size_bytes,sha256,uploaded_at,expires_at
"""
                    ),
                    {
                        "id": claimed.receipt_id,
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
        await self.connection.execute(
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
            self.connection,
            action="expense_receipt_uploaded",
            entity_type="expense_receipt",
            entity_id=claimed.receipt_id,
            changed_fields=["file_name", "content_type", "size_bytes", "sha256", "status"],
            reason="Expense receipt uploaded",
            metadata={"storage_operation_id": str(claimed.operation_id)},
        )
        return ExpenseReceiptResponse.model_validate(result)

    async def fail_upload(self, claimed: ClaimedReceiptUpload) -> None:
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='failed',last_error_code='provider_error',
    next_attempt_at=statement_timestamp()+interval '1 minute',
    claimed_at=NULL,lease_expires_at=NULL,updated_at=statement_timestamp()
WHERE id=:id AND status='claimed'
"""
            ),
            {"id": claimed.operation_id},
        )

    async def load_for_download(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, receipt_id: uuid.UUID
    ) -> dict[str, object]:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT receipt.id,receipt.file_name,receipt.content_type,receipt.size_bytes,
       receipt.sha256,receipt.object_key,receipt.status,receipt.expires_at,
       receipt.employee_id,receipt.created_by_app_user_id,receipt.expense_claim_id,
       employee.reporting_manager_id
FROM public.expense_receipts AS receipt
JOIN public.employees AS employee
  ON employee.id=receipt.employee_id AND employee.company_id=receipt.company_id
 AND employee.branch_id=receipt.branch_id
WHERE receipt.id=:id AND receipt.company_id=:company_id AND receipt.branch_id=:branch_id
  AND receipt.status IN ('staged','attached')
"""
                    ),
                    {
                        "id": receipt_id,
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
        authorized = principal.role is AppRole.ADMIN or row["employee_id"] == principal.employee_id
        if principal.role is AppRole.MANAGER:
            authorized = (
                row["expense_claim_id"] is not None
                and row["reporting_manager_id"] == principal.employee_id
                and row["employee_id"] != principal.employee_id
            ) or row["employee_id"] == principal.employee_id
        if not authorized:
            raise ServiceExecutionError("resource_not_found")
        return dict(row)

    async def request_cleanup(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        receipt_id: uuid.UUID,
        trigger: str,
    ) -> ClaimedReceiptCleanup:
        if trigger not in {
            "failed_submission",
            "claim_deleted",
            "staged_expired",
            "missing_object",
        }:
            raise ValueError("unsupported cleanup trigger")
        row = (
            await self.connection.execute(
                text(
                    """
SELECT id,company_id,branch_id,employee_id,object_key
FROM public.expense_receipts
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
  AND status IN ('staged','attached')
FOR UPDATE
"""
                ),
                {"id": receipt_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None or row.object_key is None:
            raise ServiceExecutionError("resource_not_found")
        await self.connection.execute(
            text(
                """
UPDATE public.expense_receipts
SET expense_claim_id=NULL,status='cleanup_pending',expires_at=NULL,
    cleanup_requested_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:id
"""
            ),
            {"id": receipt_id},
        )
        operation_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.storage_operations(
  company_id,branch_id,employee_id,created_by_app_user_id,
  entity_type,entity_id,operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,
       'expense_receipt',:receipt_id,'delete',:object_key)
RETURNING id
"""
                ),
                {
                    "company_id": row.company_id,
                    "branch_id": row.branch_id,
                    "employee_id": row.employee_id,
                    "creator": principal.app_user_id,
                    "receipt_id": receipt_id,
                    "object_key": row.object_key,
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
        await append_audit_event(
            self.connection,
            action="expense_receipt_cleanup_requested",
            entity_type="expense_receipt",
            entity_id=receipt_id,
            changed_fields=["status"],
            reason="Expense receipt cleanup requested",
            metadata={"storage_operation_id": str(operation_id), "trigger": trigger},
        )
        return ClaimedReceiptCleanup(receipt_id, operation_id, row.object_key)

    async def complete_cleanup(self, claimed: ClaimedReceiptCleanup) -> None:
        await self.connection.execute(
            text(
                """
UPDATE public.expense_receipts
SET status='removed',removed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:receipt_id AND status='cleanup_pending'
"""
            ),
            {"receipt_id": claimed.receipt_id},
        )
        await self.connection.execute(
            text(
                """
UPDATE public.storage_operations
SET status='succeeded',claimed_at=NULL,lease_expires_at=NULL,
    completed_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:operation_id AND status='claimed'
"""
            ),
            {"operation_id": claimed.operation_id},
        )
