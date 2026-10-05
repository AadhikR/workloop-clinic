from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.schemas.appraisals import AppraisalSectionRatingRequest
from app.schemas.portal_projections import RetainedRecordResponse
from app.services.execution import ServiceExecutionError

TABLES = {
    "appraisal": ("appraisals", "'Appraisal review · ' || e.name"),
    "incident_report": (
        "incident_reports",
        "'Incident · ' || r.incident_date::text || ' · ' || replace(r.incident_type,'_',' ')",
    ),
    "expense_claim": (
        "expense_claims",
        "e.name || ' · ' || r.expense_date::text || ' · AED ' || r.amount::text",
    ),
    "salary_advance": ("salary_advances", "e.name || ' · AED ' || r.amount::text"),
}


def source_join(kind: str) -> str:
    if kind == "incident_report":
        return ""
    return (
        " JOIN public.employees e ON e.id=r.employee_id "
        "AND e.company_id=r.company_id AND e.branch_id=r.branch_id "
    )


class RetainedRecordService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def read(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        record_id: uuid.UUID,
    ) -> RetainedRecordResponse:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        if kind not in TABLES:
            raise ServiceExecutionError("validation_failed")
        table, label = TABLES[kind]
        archival = "false" if kind == "salary_advance" else "r.archived_at IS NOT NULL"
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT r.id,'{kind}' entity_type,{label} label,r.status,"
                        f"{archival} archived,r.updated_at FROM public.{table} r "
                        + source_join(kind)
                        + "WHERE r.id=:id AND r.company_id=:company_id AND r.branch_id=:branch_id"
                    ),
                    {"id": record_id, "company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return RetainedRecordResponse.model_validate(row)

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        limit: int,
        cursor: uuid.UUID | None,
    ) -> list[RetainedRecordResponse]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        if kind not in {"appraisal", "incident_report", "expense_claim"}:
            raise ServiceExecutionError("validation_failed")
        table, label = TABLES[kind]
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT r.id,'{kind}' entity_type,{label} label,r.status,"
                        f"true archived,r.updated_at FROM public.{table} r "
                        + source_join(kind)
                        + "WHERE r.company_id=:company_id AND r.branch_id=:branch_id "
                        "AND r.archived_at IS NOT NULL "
                        "AND (CAST(:cursor AS uuid) IS NULL OR r.id>:cursor) "
                        "ORDER BY r.id ASC LIMIT :limit"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "limit": limit,
                        "cursor": cursor,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [RetainedRecordResponse.model_validate(row) for row in rows]

    async def archive(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        record_id: uuid.UUID,
        expected: datetime,
        archived: bool,
    ) -> RetainedRecordResponse:
        await self.read(principal, branch_id, kind, record_id)
        result = (
            await self.connection.execute(
                text("SELECT public.set_portal_record_archival(:kind,:id,:expected,:archived)"),
                {"kind": kind, "id": record_id, "expected": expected, "archived": archived},
            )
        ).scalar_one()
        self._confirmed(result)
        return await self.read(principal, branch_id, kind, record_id)

    async def cancel_advance(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        expected: datetime,
    ) -> RetainedRecordResponse:
        await self.read(principal, branch_id, "salary_advance", record_id)
        result = (
            await self.connection.execute(
                text("SELECT public.cancel_pending_advance(:id,:expected)"),
                {"id": record_id, "expected": expected},
            )
        ).scalar_one()
        self._confirmed(result)
        return await self.read(principal, branch_id, "salary_advance", record_id)

    async def rate_admin_section(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        section_id: uuid.UUID,
        request: AppraisalSectionRatingRequest,
    ) -> None:
        await self.read(principal, branch_id, "appraisal", record_id)
        result = (
            await self.connection.execute(
                text(
                    "SELECT public.set_admin_appraisal_section_rating"
                    "(:id,:section,:expected,:rating,:comments)"
                ),
                {
                    "id": record_id,
                    "section": section_id,
                    "expected": request.expected_updated_at,
                    "rating": request.rating,
                    "comments": request.comments,
                },
            )
        ).scalar_one()
        self._confirmed(result)

    @staticmethod
    def _confirmed(result: object) -> None:
        if result != "ok":
            raise ServiceExecutionError(str(result))
