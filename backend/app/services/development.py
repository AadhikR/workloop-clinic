from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.schemas.development import (
    CertificationAdminCreateRequest,
    CertificationResponse,
    CertificationStaffCreateRequest,
    CmeRequirementRequest,
    CmeRequirementResponse,
    CmeSummaryResponse,
    TrainingAdminCreateRequest,
    TrainingCompleteRequest,
    TrainingResponse,
    TrainingStaffCreateRequest,
    TrainingUpdateRequest,
)
from app.services.execution import ServiceExecutionError
from app.services.leave_attachment import ValidatedUpload

TRAINING_COLUMNS = """
id,employee_id,training_title,training_type,provider,start_date,end_date,duration_hours,
cost,status,score,passed,notes,is_cme,(content_type IS NOT NULL) has_evidence,
NULLIF(file_name,'') file_name,content_type,created_at,updated_at
"""
CERTIFICATION_COLUMNS = """
id,employee_id,certification_name,issuing_body,certificate_no,issued_date,expiry_date,
notes,status,(content_type IS NOT NULL) has_evidence,NULLIF(file_name,'') file_name,
content_type,reviewed_at,created_at,updated_at
"""


@dataclass(frozen=True, slots=True)
class TrainingListQuery:
    employee_id: uuid.UUID | None
    year: int | None
    status: str | None
    training_type: str | None
    is_cme: bool | None
    limit: int


@dataclass(frozen=True, slots=True)
class CertificationListQuery:
    employee_id: uuid.UUID | None
    status: str | None
    limit: int


@dataclass(frozen=True, slots=True)
class ClaimedEvidenceUpload:
    entity_type: str
    entity_id: uuid.UUID
    branch_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


@dataclass(frozen=True, slots=True)
class ClaimedEvidenceCleanup:
    entity_type: str
    entity_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


class DevelopmentService:
    def __init__(
        self,
        connection: AsyncConnection,
        *,
        scanner_definition: str,
        object_key_hmac_key: bytes = b"",
    ) -> None:
        self.connection = connection
        self.scanner_definition = scanner_definition
        self.object_key_hmac_key = object_key_hmac_key

    async def list_training(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: TrainingListQuery,
        *,
        scope: str,
    ) -> list[TrainingResponse]:
        employee_id = await self._scope_employee(
            principal, branch_id, query.employee_id, scope=scope, optional=scope == "admin"
        )
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {TRAINING_COLUMNS} FROM public.training_records
WHERE company_id=:company_id AND branch_id=:branch_id
  AND (CAST(:employee_id AS uuid) IS NULL OR employee_id=:employee_id)
  AND (CAST(:year AS integer) IS NULL OR EXTRACT(year FROM start_date)=:year)
  AND (CAST(:status AS text) IS NULL OR status=:status)
  AND (CAST(:training_type AS text) IS NULL OR training_type=:training_type)
  AND (CAST(:is_cme AS boolean) IS NULL OR is_cme=:is_cme)
ORDER BY start_date DESC NULLS LAST,id DESC LIMIT :limit
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "year": query.year,
                        "status": query.status,
                        "training_type": query.training_type,
                        "is_cme": query.is_cme,
                        "limit": query.limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [TrainingResponse.model_validate(row) for row in rows]

    async def create_training(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: TrainingAdminCreateRequest | TrainingStaffCreateRequest,
        *,
        scope: str,
    ) -> TrainingResponse:
        employee_id = await self._scope_employee(
            principal, branch_id, request.employee_id, scope=scope, optional=False
        )
        assert employee_id is not None
        admin = isinstance(request, TrainingAdminCreateRequest)
        values = request.model_dump(exclude={"employee_id"}, by_alias=False)
        values["cost"] = request.cost if admin else Decimal("0.00")
        values["is_cme"] = request.is_cme if admin else False
        record_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.training_records(
 company_id,branch_id,employee_id,training_title,training_type,provider,start_date,
 end_date,duration_hours,cost,status,score,passed,notes,is_cme,created_by_app_user_id)
VALUES(:company_id,:branch_id,:employee_id,:training_title,:training_type,:provider,
 :start_date,:end_date,:duration_hours,:cost,'planned','',NULL,:notes,:is_cme,:creator)
RETURNING id
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "creator": principal.app_user_id,
                    **values,
                },
            )
        ).scalar_one()
        await self._audit(
            "training_enrolled",
            "training_record",
            record_id,
            ["employee_id", "training_title", "status"],
            "Training enrolment created",
        )
        return await self.get_training(principal, branch_id, record_id, scope=scope)

    async def get_training(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        *,
        scope: str,
    ) -> TrainingResponse:
        row = await self._training_row(principal, branch_id, record_id, lock=False)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal, branch_id, employee_id, scope=effective_scope, optional=False
        )
        return TrainingResponse.model_validate(row)

    async def update_training(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        request: TrainingUpdateRequest,
        *,
        scope: str,
    ) -> TrainingResponse:
        row = await self._training_row(principal, branch_id, record_id, lock=True)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal, branch_id, employee_id, scope=effective_scope, optional=False
        )
        if row["updated_at"] != request.expected_updated_at or row["status"] != "planned":
            raise ServiceExecutionError("state_conflict")
        if scope != "admin" and (request.cost != row["cost"] or request.is_cme != row["is_cme"]):
            raise ServiceExecutionError("operation_not_permitted")
        values = request.model_dump(exclude={"expected_updated_at"}, by_alias=False)
        await self.connection.execute(
            text(
                """
UPDATE public.training_records SET training_title=:training_title,
 training_type=:training_type,provider=:provider,start_date=:start_date,end_date=:end_date,
 duration_hours=:duration_hours,cost=:cost,notes=:notes,is_cme=:is_cme WHERE id=:id
"""
            ),
            {"id": record_id, **values},
        )
        await self._audit(
            "training_updated",
            "training_record",
            record_id,
            [
                "training_title",
                "training_type",
                "provider",
                "start_date",
                "end_date",
                "duration_hours",
                "cost",
                "notes",
                "is_cme",
            ],
            "Training record updated",
        )
        return await self.get_training(principal, branch_id, record_id, scope=effective_scope)

    async def complete_training(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        request: TrainingCompleteRequest,
        *,
        scope: str,
    ) -> TrainingResponse:
        if scope not in {"admin", "direct_report"}:
            raise ServiceExecutionError("operation_not_permitted")
        row = await self._training_row(principal, branch_id, record_id, lock=True)
        employee_id = self._row_employee_id(row)
        await self._scope_employee(principal, branch_id, employee_id, scope=scope, optional=False)
        if row["updated_at"] != request.expected_updated_at or row["status"] not in {
            "planned",
            "in_progress",
        }:
            raise ServiceExecutionError("state_conflict")
        start_date = cast(date | None, row["start_date"])
        if start_date is not None and request.end_date < start_date:
            raise ServiceExecutionError("validation_failed")
        await self.connection.execute(
            text(
                """
UPDATE public.training_records SET status='completed',end_date=:end_date,
 duration_hours=:duration_hours,score=:score,passed=:passed,is_cme=:is_cme WHERE id=:id
"""
            ),
            {
                "id": record_id,
                **request.model_dump(exclude={"expected_updated_at"}, by_alias=False),
            },
        )
        await self._audit(
            "training_completed",
            "training_record",
            record_id,
            ["status", "end_date", "duration_hours", "score", "passed", "is_cme"],
            "Training completed",
            {"transition": f"{row['status']}_to_completed"},
        )
        return await self.get_training(principal, branch_id, record_id, scope=scope)

    async def delete_training(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        expected_updated_at: object,
        *,
        scope: str,
    ) -> None:
        row = await self._training_row(principal, branch_id, record_id, lock=True)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal, branch_id, employee_id, scope=effective_scope, optional=False
        )
        if (
            row["updated_at"] != expected_updated_at
            or row["status"] != "planned"
            or row["has_evidence"]
        ):
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            "training_deleted", "training_record", record_id, ["id"], "Training record deleted"
        )
        await self.connection.execute(
            text("DELETE FROM public.training_records WHERE id=:id"), {"id": record_id}
        )

    async def list_certifications(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: CertificationListQuery,
        *,
        scope: str,
    ) -> list[CertificationResponse]:
        employee_id = await self._scope_employee(
            principal, branch_id, query.employee_id, scope=scope, optional=scope == "admin"
        )
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {CERTIFICATION_COLUMNS} FROM public.certifications
WHERE company_id=:company_id AND branch_id=:branch_id
  AND (CAST(:employee_id AS uuid) IS NULL OR employee_id=:employee_id)
  AND (CAST(:status AS text) IS NULL OR status=:status)
ORDER BY expiry_date ASC NULLS LAST,certification_name ASC,id ASC LIMIT :limit
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "status": query.status,
                        "limit": query.limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [CertificationResponse.model_validate(row) for row in rows]

    async def create_certification(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: CertificationAdminCreateRequest | CertificationStaffCreateRequest,
        *,
        scope: str,
    ) -> CertificationResponse:
        employee_id = await self._scope_employee(
            principal, branch_id, request.employee_id, scope=scope, optional=False
        )
        assert employee_id is not None
        admin = isinstance(request, CertificationAdminCreateRequest)
        certification_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.certifications(
 company_id,branch_id,employee_id,certification_name,issuing_body,certificate_no,
 issued_date,expiry_date,notes,status,reviewed_by_app_user_id,reviewed_at,
 created_by_app_user_id)
VALUES(:company_id,:branch_id,:employee_id,:certification_name,:issuing_body,
 :certificate_no,:issued_date,:expiry_date,:notes,:status,:reviewer,
 CASE WHEN :admin THEN statement_timestamp() ELSE NULL END,:creator) RETURNING id
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "status": "verified" if admin else "pending_review",
                    "reviewer": principal.app_user_id if admin else None,
                    "admin": admin,
                    "creator": principal.app_user_id,
                    **request.model_dump(exclude={"employee_id"}, by_alias=False),
                },
            )
        ).scalar_one()
        await self._audit(
            "certification_submitted",
            "certification",
            certification_id,
            ["employee_id", "certification_name", "status"],
            "Certification submitted",
        )
        return await self.get_certification(principal, branch_id, certification_id, scope=scope)

    async def get_certification(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        certification_id: uuid.UUID,
        *,
        scope: str,
    ) -> CertificationResponse:
        row = await self._certification_row(principal, branch_id, certification_id, lock=False)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal, branch_id, employee_id, scope=effective_scope, optional=False
        )
        return CertificationResponse.model_validate(row)

    async def decide_certification(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        certification_id: uuid.UUID,
        expected_updated_at: object,
        *,
        verify: bool,
        reason: str | None,
    ) -> CertificationResponse:
        row = await self._certification_row(principal, branch_id, certification_id, lock=True)
        if row["updated_at"] != expected_updated_at or row["status"] != "pending_review":
            raise ServiceExecutionError("state_conflict")
        if verify and not row["has_evidence"]:
            raise ServiceExecutionError("state_conflict")
        if not verify and not reason:
            raise ServiceExecutionError("validation_failed")
        status = "verified" if verify else "rejected"
        await self.connection.execute(
            text(
                "UPDATE public.certifications SET status=:status,notes=CASE WHEN :verify "
                "THEN notes ELSE :reason END,reviewed_by_app_user_id=:actor,"
                "reviewed_at=statement_timestamp() WHERE id=:id"
            ),
            {
                "id": certification_id,
                "status": status,
                "verify": verify,
                "reason": reason,
                "actor": principal.app_user_id,
            },
        )
        await self._audit(
            "certification_verified" if verify else "certification_rejected",
            "certification",
            certification_id,
            ["status", "reviewed_by_app_user_id", "reviewed_at"],
            "Certification verified" if verify else "Certification rejected",
            {"transition": f"pending_review_to_{status}"},
        )
        return await self.get_certification(principal, branch_id, certification_id, scope="admin")

    async def delete_certification(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        certification_id: uuid.UUID,
        expected_updated_at: object,
        *,
        scope: str,
    ) -> None:
        row = await self._certification_row(principal, branch_id, certification_id, lock=True)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal, branch_id, employee_id, scope=effective_scope, optional=False
        )
        if (
            row["updated_at"] != expected_updated_at
            or row["status"] not in {"pending_review", "rejected"}
            or row["has_evidence"]
        ):
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            "certification_deleted",
            "certification",
            certification_id,
            ["id"],
            "Certification deleted",
        )
        await self.connection.execute(
            text("DELETE FROM public.certifications WHERE id=:id"), {"id": certification_id}
        )

    async def get_requirement(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        year: int,
    ) -> CmeRequirementResponse:
        await self._scope_employee(principal, branch_id, employee_id, scope="admin", optional=False)
        row = (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,employee_id,year,required_hours,notes,created_at,updated_at "
                        "FROM public.cme_requirements WHERE company_id=:company_id "
                        "AND branch_id=:branch_id AND employee_id=:employee_id AND year=:year"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "year": year,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return CmeRequirementResponse.model_validate(row)

    async def save_requirement(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        year: int,
        request: CmeRequirementRequest,
    ) -> CmeRequirementResponse:
        await self._scope_employee(principal, branch_id, employee_id, scope="admin", optional=False)
        current = (
            await self.connection.execute(
                text(
                    "SELECT id,updated_at FROM public.cme_requirements "
                    "WHERE employee_id=:employee_id AND company_id=:company_id "
                    "AND branch_id=:branch_id AND year=:year FOR UPDATE"
                ),
                {
                    "employee_id": employee_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "year": year,
                },
            )
        ).one_or_none()
        if current is None:
            if request.expected_updated_at is not None:
                raise ServiceExecutionError("state_conflict")
            requirement_id = (
                await self.connection.execute(
                    text(
                        "INSERT INTO public.cme_requirements(company_id,branch_id,employee_id,year,"
                        "required_hours,notes) VALUES(:company_id,:branch_id,:employee_id,:year,"
                        ":required_hours,:notes) RETURNING id"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "year": year,
                        "required_hours": request.required_hours,
                        "notes": request.notes,
                    },
                )
            ).scalar_one()
        else:
            if current.updated_at != request.expected_updated_at:
                raise ServiceExecutionError("state_conflict")
            requirement_id = current.id
            await self.connection.execute(
                text(
                    "UPDATE public.cme_requirements SET "
                    "required_hours=:required_hours,notes=:notes WHERE id=:id"
                ),
                {
                    "id": requirement_id,
                    "required_hours": request.required_hours,
                    "notes": request.notes,
                },
            )
        await self._audit(
            "cme_requirement_saved",
            "cme_requirement",
            requirement_id,
            ["required_hours", "notes"],
            "CME requirement saved",
        )
        return await self.get_requirement(principal, branch_id, employee_id, year)

    async def delete_requirement(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        year: int,
        expected_updated_at: object,
    ) -> None:
        current = await self.get_requirement(principal, branch_id, employee_id, year)
        if current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            "cme_requirement_deleted",
            "cme_requirement",
            current.id,
            ["id"],
            "CME requirement deleted",
        )
        await self.connection.execute(
            text("DELETE FROM public.cme_requirements WHERE id=:id"), {"id": current.id}
        )

    async def self_cme(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, year: int
    ) -> CmeSummaryResponse:
        if principal.employee_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        row = (
            await self.connection.execute(
                text(
                    """
SELECT COALESCE((SELECT required_hours FROM public.cme_requirements
 WHERE company_id=:company_id AND branch_id=:branch_id AND employee_id=:employee_id
   AND year=:year),0) target,
COALESCE((SELECT sum(duration_hours) FROM public.training_records record
 WHERE record.company_id=:company_id AND record.branch_id=:branch_id
   AND record.employee_id=:employee_id AND record.status='completed' AND record.passed
   AND record.is_cme AND EXTRACT(year FROM record.start_date)=:year
   AND (record.content_type IS NULL OR public.file_security_scan_allows_download(
     record.file_security_scan_id,'training_evidence',record.id,record.storage_path,
     record.content_type,record.size_bytes,record.sha256,:scanner_definition))),0) achieved
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": principal.employee_id,
                    "year": year,
                    "scanner_definition": self.scanner_definition,
                },
            )
        ).one()
        target = Decimal(row.target).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        achieved = Decimal(row.achieved).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        gap = max(Decimal("0.0"), target - achieved)
        return CmeSummaryResponse(
            year=year, target_hours=target, achieved_hours=achieved, gap_hours=gap
        )

    async def claim_evidence_upload(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        upload: ValidatedUpload,
        *,
        scope: str,
    ) -> ClaimedEvidenceUpload:
        self._evidence_table(entity_type)
        row = await self._evidence_source(principal, branch_id, entity_type, entity_id, lock=True)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal,
            branch_id,
            employee_id,
            scope=effective_scope,
            optional=False,
        )
        if row["content_type"] is not None:
            raise ServiceExecutionError("state_conflict")
        if entity_type == "training_evidence" and row["status"] not in {
            "planned",
            "in_progress",
            "completed",
        }:
            raise ServiceExecutionError("state_conflict")
        if entity_type == "certification_evidence" and row["status"] not in {
            "pending_review",
            "verified",
        }:
            raise ServiceExecutionError("state_conflict")
        object_key = self._evidence_object_key(
            principal.company_id,
            branch_id,
            employee_id,
            entity_type,
            entity_id,
        )
        try:
            operation_id = (
                await self.connection.execute(
                    text(
                        """
INSERT INTO public.storage_operations(
 company_id,branch_id,employee_id,created_by_app_user_id,entity_type,entity_id,
 operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,:entity_type,:entity_id,
 'upload',:object_key) RETURNING id
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": row["employee_id"],
                        "creator": principal.app_user_id,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "object_key": object_key,
                    },
                )
            ).scalar_one()
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        await self._claim_storage_operation(operation_id)
        return ClaimedEvidenceUpload(entity_type, entity_id, branch_id, operation_id, object_key)

    async def complete_evidence_upload(
        self,
        principal: AuthorizationPrincipal,
        claimed: ClaimedEvidenceUpload,
        upload: ValidatedUpload,
    ) -> None:
        table = self._evidence_table(claimed.entity_type)
        row = await self._evidence_source(
            principal,
            claimed.branch_id,
            claimed.entity_type,
            claimed.entity_id,
            lock=True,
        )
        allowed = (
            row["status"] in {"planned", "in_progress", "completed"}
            if claimed.entity_type == "training_evidence"
            else row["status"] in {"pending_review", "verified"}
        )
        if row["content_type"] is not None or not allowed:
            raise ServiceExecutionError("state_conflict")
        scan_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.file_security_scans(
 company_id,branch_id,employee_id,created_by_app_user_id,entity_type,entity_id,
 object_key,content_type,size_bytes,sha256,scanner_definition)
VALUES(:company_id,:branch_id,:employee_id,:creator,:entity_type,:entity_id,
 :object_key,:content_type,:size_bytes,:sha256,:scanner_definition) RETURNING id
"""
                ),
                {
                    "company_id": row["company_id"],
                    "branch_id": row["branch_id"],
                    "employee_id": row["employee_id"],
                    "creator": principal.app_user_id,
                    "entity_type": claimed.entity_type,
                    "entity_id": claimed.entity_id,
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
                f"UPDATE public.{table} SET file_name=:file_name,storage_path=:object_key,"
                "content_type=:content_type,size_bytes=:size_bytes,sha256=:sha256,"
                "file_security_scan_id=:scan_id,created_by_app_user_id=:creator WHERE id=:id"
            ),
            {
                "id": claimed.entity_id,
                "file_name": upload.file_name,
                "object_key": claimed.object_key,
                "content_type": upload.content_type,
                "size_bytes": len(upload.body),
                "sha256": upload.sha256,
                "scan_id": scan_id,
                "creator": principal.app_user_id,
            },
        )
        await self._finish_storage_operation(claimed.operation_id)
        prefix = "training" if claimed.entity_type == "training_evidence" else "certification"
        await self._audit(
            f"{prefix}_evidence_uploaded",
            "training_record" if prefix == "training" else "certification",
            claimed.entity_id,
            ["file_name", "content_type", "size_bytes"],
            f"{prefix.capitalize()} evidence uploaded",
            {"operation_id": str(claimed.operation_id)},
        )

    async def fail_evidence_upload(self, claimed: ClaimedEvidenceUpload) -> None:
        await self._fail_storage_operation(claimed.operation_id)

    async def load_evidence_download(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        *,
        scope: str,
    ) -> dict[str, object]:
        row = await self._evidence_source(principal, branch_id, entity_type, entity_id, lock=False)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal,
            branch_id,
            employee_id,
            scope=effective_scope,
            optional=False,
        )
        if entity_type == "certification_evidence" and row["status"] != "verified":
            raise ServiceExecutionError("service_unavailable")
        released = (
            await self.connection.execute(
                text(
                    "SELECT public.file_security_scan_allows_download("
                    ":scan_id,:entity_type,:entity_id,:object_key,:content_type,"
                    ":size_bytes,:sha256,:scanner_definition)"
                ),
                {
                    "scan_id": row["file_security_scan_id"],
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "object_key": row["storage_path"],
                    "content_type": row["content_type"],
                    "size_bytes": row["size_bytes"],
                    "sha256": row["sha256"],
                    "scanner_definition": self.scanner_definition,
                },
            )
        ).scalar_one()
        if not released:
            raise ServiceExecutionError("service_unavailable")
        return row

    async def claim_evidence_cleanup(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        expected_updated_at: object,
        *,
        scope: str,
    ) -> ClaimedEvidenceCleanup:
        row = await self._evidence_source(principal, branch_id, entity_type, entity_id, lock=True)
        employee_id = self._row_employee_id(row)
        effective_scope = self._effective_scope(principal, employee_id, scope)
        await self._scope_employee(
            principal,
            branch_id,
            employee_id,
            scope=effective_scope,
            optional=False,
        )
        allowed = (
            row["status"] == "planned"
            if entity_type == "training_evidence"
            else row["status"] in {"pending_review", "rejected"}
        )
        if not allowed or row["updated_at"] != expected_updated_at or row["content_type"] is None:
            raise ServiceExecutionError("state_conflict")
        try:
            operation_id = (
                await self.connection.execute(
                    text(
                        """
INSERT INTO public.storage_operations(
 company_id,branch_id,employee_id,created_by_app_user_id,entity_type,entity_id,
 operation,object_key)
VALUES(:company_id,:branch_id,:employee_id,:creator,:entity_type,:entity_id,
 'delete',:object_key) RETURNING id
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": row["employee_id"],
                        "creator": principal.app_user_id,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "object_key": row["storage_path"],
                    },
                )
            ).scalar_one()
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        await self._claim_storage_operation(operation_id)
        prefix = "training" if entity_type == "training_evidence" else "certification"
        await self._audit(
            f"{prefix}_cleanup_requested",
            "training_record" if prefix == "training" else "certification",
            entity_id,
            ["storage_path"],
            f"{prefix.capitalize()} evidence cleanup requested",
            {"operation_id": str(operation_id)},
        )
        return ClaimedEvidenceCleanup(
            entity_type, entity_id, operation_id, str(row["storage_path"])
        )

    async def complete_evidence_cleanup(self, claimed: ClaimedEvidenceCleanup) -> None:
        table = self._evidence_table(claimed.entity_type)
        await self.connection.execute(
            text(
                f"UPDATE public.{table} SET file_name='',storage_path='',content_type=NULL,"
                "size_bytes=NULL,sha256=NULL,file_security_scan_id=NULL WHERE id=:id"
            ),
            {"id": claimed.entity_id},
        )
        await self._finish_storage_operation(claimed.operation_id)

    async def fail_evidence_cleanup(self, claimed: ClaimedEvidenceCleanup) -> None:
        await self._fail_storage_operation(claimed.operation_id)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        table = {
            "training_record": "training_records",
            "certification": "certifications",
            "cme_requirement": "cme_requirements",
        }.get(kind)
        if table is None or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        exists = (
            await self.connection.execute(
                text(
                    f"SELECT 1 FROM public.{table} WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id"
                ),
                {"id": resource_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ServiceExecutionError("resource_not_found")

    @staticmethod
    def _evidence_table(entity_type: str) -> str:
        table = {
            "training_evidence": "training_records",
            "certification_evidence": "certifications",
        }.get(entity_type)
        if table is None:
            raise ServiceExecutionError("resource_not_found")
        return table

    async def _evidence_source(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        *,
        lock: bool,
    ) -> dict[str, object]:
        table = self._evidence_table(entity_type)
        parameters: dict[str, object] = {
            "id": entity_id,
            "company_id": principal.company_id,
        }
        branch_clause = " AND branch_id=:branch_id"
        parameters["branch_id"] = branch_id
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT id,company_id,branch_id,employee_id,status,file_name,storage_path,"
                        "content_type,size_bytes,sha256,file_security_scan_id,updated_at "
                        f"FROM public.{table} WHERE id=:id AND company_id=:company_id"
                        f"{branch_clause}" + (" FOR UPDATE" if lock else "")
                    ),
                    parameters,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return dict(row)

    def _evidence_object_key(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: object,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> str:
        if not self.object_key_hmac_key:
            raise RuntimeError("evidence object-key key is required")
        material = b"\0".join(
            str(value).encode("ascii")
            for value in (company_id, branch_id, employee_id, entity_type)
        )
        digest = base64.urlsafe_b64encode(
            hmac.new(self.object_key_hmac_key, material, hashlib.sha256).digest()
        ).rstrip(b"=")[:22]
        prefix = (
            "training-evidence" if entity_type == "training_evidence" else "certification-evidence"
        )
        return f"{prefix}/v1/{digest.decode()}/{entity_id.hex}"

    async def _finish_storage_operation(self, operation_id: uuid.UUID) -> None:
        await self.connection.execute(
            text(
                "UPDATE public.storage_operations SET status='succeeded',claimed_at=NULL,"
                "lease_expires_at=NULL,completed_at=statement_timestamp(),"
                "updated_at=statement_timestamp() WHERE id=:id AND status='claimed'"
            ),
            {"id": operation_id},
        )

    async def _claim_storage_operation(self, operation_id: uuid.UUID) -> None:
        await self.connection.execute(
            text(
                "UPDATE public.storage_operations SET status='claimed',attempt_count=1,"
                "claimed_at=statement_timestamp(),lease_expires_at=statement_timestamp()+"
                "interval '15 minutes',updated_at=statement_timestamp() "
                "WHERE id=:id AND status='pending'"
            ),
            {"id": operation_id},
        )

    async def _fail_storage_operation(self, operation_id: uuid.UUID) -> None:
        await self.connection.execute(
            text(
                "UPDATE public.storage_operations SET status='failed',"
                "last_error_code='provider_error',next_attempt_at=statement_timestamp()+"
                "interval '1 minute',claimed_at=NULL,lease_expires_at=NULL,"
                "updated_at=statement_timestamp() WHERE id=:id AND status='claimed'"
            ),
            {"id": operation_id},
        )

    async def _scope_employee(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        *,
        scope: str,
        optional: bool,
    ) -> uuid.UUID | None:
        if scope == "self":
            if principal.employee_id is None or employee_id not in {None, principal.employee_id}:
                raise ServiceExecutionError("operation_not_permitted")
            return principal.employee_id
        if scope == "direct_report":
            if (
                principal.role is not AppRole.MANAGER
                or principal.employee_id is None
                or employee_id is None
            ):
                raise ServiceExecutionError("operation_not_permitted")
            report = (
                await self.connection.execute(
                    text("SELECT public.lock_development_direct_report(:id)"),
                    {"id": employee_id},
                )
            ).scalar_one()
            if not report:
                raise ServiceExecutionError("resource_not_found")
            return employee_id
        if scope != "admin" or principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        if employee_id is None:
            if optional:
                return None
            raise ServiceExecutionError("validation_failed")
        employee = (
            await self.connection.execute(
                text(
                    "SELECT id FROM public.employees WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id AND active FOR SHARE"
                ),
                {"id": employee_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if employee is None:
            raise ServiceExecutionError("resource_not_found")
        return employee

    @staticmethod
    def _effective_scope(
        principal: AuthorizationPrincipal, employee_id: uuid.UUID, scope: str
    ) -> str:
        if scope != "staff":
            return scope
        return "self" if employee_id == principal.employee_id else "direct_report"

    @staticmethod
    def _row_employee_id(row: dict[str, object]) -> uuid.UUID:
        return cast(uuid.UUID, row["employee_id"])

    async def _training_row(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        *,
        lock: bool,
    ) -> dict[str, object]:
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {TRAINING_COLUMNS} FROM public.training_records "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id"
                        + (" FOR UPDATE" if lock else "")
                    ),
                    {"id": record_id, "company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return dict(row)

    async def _certification_row(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        certification_id: uuid.UUID,
        *,
        lock: bool,
    ) -> dict[str, object]:
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {CERTIFICATION_COLUMNS} FROM public.certifications "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id"
                        + (" FOR UPDATE" if lock else "")
                    ),
                    {
                        "id": certification_id,
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

    async def _audit(
        self,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        fields: list[str],
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        await append_audit_event(
            self.connection,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changed_fields=fields,
            reason=reason,
            metadata=metadata or {},
        )
