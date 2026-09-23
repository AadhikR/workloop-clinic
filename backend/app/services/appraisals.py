from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.schemas.appraisals import (
    AppraisalCalibrationRequest,
    AppraisalCycleCreateRequest,
    AppraisalCycleResponse,
    AppraisalCycleUpdateRequest,
    AppraisalGenerationResponse,
    AppraisalResponse,
    AppraisalReviewRequest,
    AppraisalSectionRatingRequest,
    AppraisalSectionResponse,
)
from app.services.execution import ServiceExecutionError

CYCLE_COLUMNS = """
id,name,review_from,review_to,status,closed_by_app_user_id,closed_at,created_at,updated_at
"""
APPRAISAL_COLUMNS = """
a.id,a.cycle_id,c.name cycle_name,c.review_from,c.review_to,a.employee_id,
e.name employee_name,a.template_version,a.overall_rating,a.status,
COALESCE(a.reviewer_comments,'') reviewer_comments,
COALESCE(a.development_plan,'') development_plan,a.reviewed_at,
a.reviewed_by_app_user_id,a.created_at,a.updated_at
"""
SECTION_COLUMNS = """
id,section_name,weight,rating,COALESCE(comments,'') comments,sort_order,updated_at
"""
FIXED_SECTIONS = (
    ("Clinical Competency", Decimal("2.00"), 10),
    ("Patient Care Quality", Decimal("2.00"), 20),
    ("Communication and Teamwork", Decimal("1.50"), 30),
    ("Punctuality and Attendance", Decimal("1.00"), 40),
    ("Professional Development", Decimal("1.00"), 50),
)


def calculate_weighted_rating(sections: list[tuple[Decimal, Decimal]]) -> Decimal:
    numerator = sum((rating * weight for rating, weight in sections), Decimal("0"))
    denominator = sum((weight for _, weight in sections), Decimal("0"))
    if denominator != Decimal("7.50") or len(sections) != len(FIXED_SECTIONS):
        raise ServiceExecutionError("state_conflict")
    return (numerator / denominator).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class AppraisalCycleListQuery:
    limit: int


class AppraisalService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def list_cycles(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: AppraisalCycleListQuery,
    ) -> list[AppraisalCycleResponse]:
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {CYCLE_COLUMNS} FROM public.appraisal_cycles "
                        "WHERE company_id=:company_id AND branch_id=:branch_id "
                        "ORDER BY review_from DESC,id DESC LIMIT :limit"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "limit": query.limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [await self._cycle_response(principal, branch_id, row) for row in rows]

    async def create_cycle(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: AppraisalCycleCreateRequest,
    ) -> AppraisalCycleResponse:
        try:
            cycle_id = (
                await self.connection.execute(
                    text(
                        "INSERT INTO public.appraisal_cycles("
                        "company_id,branch_id,name,review_from,review_to,status) "
                        "VALUES(:company_id,:branch_id,:name,:review_from,:review_to,'draft') "
                        "RETURNING id"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        **request.model_dump(by_alias=False),
                    },
                )
            ).scalar_one()
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        await self._audit(
            "appraisal_cycle_created",
            "appraisal_cycle",
            cycle_id,
            ["name", "review_from", "review_to", "status"],
            "Appraisal cycle created",
        )
        return await self.get_cycle(principal, branch_id, cycle_id)

    async def get_cycle(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, cycle_id: uuid.UUID
    ) -> AppraisalCycleResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {CYCLE_COLUMNS} FROM public.appraisal_cycles "
                        "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id"
                    ),
                    {"id": cycle_id, "company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return await self._cycle_response(principal, branch_id, row)

    async def update_cycle(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        cycle_id: uuid.UUID,
        request: AppraisalCycleUpdateRequest,
    ) -> AppraisalCycleResponse:
        current = await self._lock_cycle(principal, branch_id, cycle_id)
        if current.status != "draft" or current.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        try:
            await self.connection.execute(
                text(
                    "UPDATE public.appraisal_cycles SET name=:name,review_from=:review_from,"
                    "review_to=:review_to WHERE id=:id"
                ),
                {
                    "id": cycle_id,
                    **request.model_dump(exclude={"expected_updated_at"}, by_alias=False),
                },
            )
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        await self._audit(
            "appraisal_cycle_updated",
            "appraisal_cycle",
            cycle_id,
            ["name", "review_from", "review_to"],
            "Appraisal cycle updated",
        )
        return await self.get_cycle(principal, branch_id, cycle_id)

    async def activate_cycle(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        cycle_id: uuid.UUID,
        expected_updated_at: object,
    ) -> AppraisalCycleResponse:
        current = await self._lock_cycle(principal, branch_id, cycle_id)
        if current.status != "draft" or current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text("UPDATE public.appraisal_cycles SET status='active' WHERE id=:id"),
            {"id": cycle_id},
        )
        await self._audit(
            "appraisal_cycle_activated",
            "appraisal_cycle",
            cycle_id,
            ["status"],
            "Appraisal cycle activated",
            {"transition": "draft_to_active"},
        )
        return await self.get_cycle(principal, branch_id, cycle_id)

    async def generate(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        cycle_id: uuid.UUID,
        expected_updated_at: object,
    ) -> AppraisalGenerationResponse:
        current = await self._lock_cycle(principal, branch_id, cycle_id)
        if current.status != "active" or current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        before = (
            await self.connection.execute(
                text("SELECT count(*) FROM public.appraisals WHERE cycle_id=:cycle_id"),
                {"cycle_id": cycle_id},
            )
        ).scalar_one()
        await self.connection.execute(
            text(
                """
INSERT INTO public.appraisals(company_id,branch_id,cycle_id,employee_id,template_version)
SELECT :company_id,:branch_id,:cycle_id,employee.id,'clinic-v1'
FROM public.employees employee
WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
  AND employee.active AND employee.employment_status IN ('Active','Probation','On Leave')
ON CONFLICT (cycle_id,employee_id) DO NOTHING
"""
            ),
            {"company_id": principal.company_id, "branch_id": branch_id, "cycle_id": cycle_id},
        )
        for name, weight, order in FIXED_SECTIONS:
            await self.connection.execute(
                text(
                    """
INSERT INTO public.appraisal_sections(
 company_id,branch_id,appraisal_id,section_name,weight,sort_order)
SELECT appraisal.company_id,appraisal.branch_id,appraisal.id,:name,:weight,:sort_order
FROM public.appraisals appraisal WHERE appraisal.cycle_id=:cycle_id
ON CONFLICT (appraisal_id,section_name) DO NOTHING
"""
                ),
                {"cycle_id": cycle_id, "name": name, "weight": weight, "sort_order": order},
            )
        counts = (
            await self.connection.execute(
                text(
                    "SELECT count(DISTINCT appraisal.id) appraisal_count,"
                    "count(section.id) section_count "
                    "FROM public.appraisals appraisal LEFT JOIN public.appraisal_sections section "
                    "ON section.appraisal_id=appraisal.id WHERE appraisal.cycle_id=:cycle_id"
                ),
                {"cycle_id": cycle_id},
            )
        ).one()
        await self._audit(
            "appraisal_cycle_generated",
            "appraisal_cycle",
            cycle_id,
            ["appraisals", "appraisal_sections"],
            "Appraisals generated",
            {"created_count": counts.appraisal_count - before},
        )
        return AppraisalGenerationResponse(
            cycle_id=cycle_id,
            created_count=counts.appraisal_count - before,
            appraisal_count=counts.appraisal_count,
            section_count=counts.section_count,
        )

    async def close_cycle(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        cycle_id: uuid.UUID,
        expected_updated_at: object,
    ) -> AppraisalCycleResponse:
        current = await self._lock_cycle(principal, branch_id, cycle_id)
        if current.status != "active" or current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        counts = (
            await self.connection.execute(
                text(
                    "SELECT count(*) total,count(*) FILTER "
                    "(WHERE status IN ('reviewed','calibrated')) done "
                    "FROM public.appraisals WHERE cycle_id=:cycle_id"
                ),
                {"cycle_id": cycle_id},
            )
        ).one()
        if counts.total == 0 or counts.done != counts.total:
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text(
                "UPDATE public.appraisal_cycles SET status='closed',"
                "closed_by_app_user_id=:actor,closed_at=statement_timestamp() WHERE id=:id"
            ),
            {"id": cycle_id, "actor": principal.app_user_id},
        )
        await self._audit(
            "appraisal_cycle_closed",
            "appraisal_cycle",
            cycle_id,
            ["status", "closed_by_app_user_id", "closed_at"],
            "Appraisal cycle closed",
            {"transition": "active_to_closed"},
        )
        return await self.get_cycle(principal, branch_id, cycle_id)

    async def delete_cycle(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        cycle_id: uuid.UUID,
        expected_updated_at: object,
    ) -> None:
        current = await self._lock_cycle(principal, branch_id, cycle_id)
        if current.status != "draft" or current.updated_at != expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        used = (
            await self.connection.execute(
                text("SELECT 1 FROM public.appraisals WHERE cycle_id=:id LIMIT 1"), {"id": cycle_id}
            )
        ).scalar_one_or_none()
        if used is not None:
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            "appraisal_cycle_deleted",
            "appraisal_cycle",
            cycle_id,
            ["id"],
            "Appraisal cycle deleted",
        )
        await self.connection.execute(
            text("DELETE FROM public.appraisal_cycles WHERE id=:id"), {"id": cycle_id}
        )

    async def list_appraisals(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        *,
        scope: str,
        limit: int,
    ) -> list[AppraisalResponse]:
        if principal.employee_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        if scope == "self":
            predicate = "a.employee_id=:employee_id"
        elif scope == "direct_report" and principal.role is AppRole.MANAGER:
            predicate = "e.reporting_manager_id=:employee_id AND a.employee_id<>:employee_id"
        else:
            raise ServiceExecutionError("operation_not_permitted")
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {APPRAISAL_COLUMNS} FROM public.appraisals a "
                        "JOIN public.appraisal_cycles c ON c.id=a.cycle_id "
                        "JOIN public.employees e ON e.id=a.employee_id "
                        "WHERE a.company_id=:company_id AND a.branch_id=:branch_id AND "
                        f"{predicate} "
                        "ORDER BY c.review_from DESC,a.id DESC LIMIT :limit"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": principal.employee_id,
                        "limit": limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [await self._response(row) for row in rows]

    async def rate_section(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        appraisal_id: uuid.UUID,
        section_id: uuid.UUID,
        request: AppraisalSectionRatingRequest,
    ) -> AppraisalResponse:
        if principal.role is not AppRole.MANAGER or principal.employee_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        appraisal = await self._lock_appraisal(principal, branch_id, appraisal_id)
        if appraisal.status != "pending" or appraisal.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        allowed = (
            await self.connection.execute(
                text("SELECT public.lock_development_direct_report(:employee_id)"),
                {"employee_id": appraisal.employee_id},
            )
        ).scalar_one()
        if not allowed:
            raise ServiceExecutionError("resource_not_found")
        section = (
            await self.connection.execute(
                text(
                    "SELECT id FROM public.appraisal_sections WHERE id=:id "
                    "AND appraisal_id=:appraisal_id AND company_id=:company_id "
                    "AND branch_id=:branch_id FOR UPDATE"
                ),
                {
                    "id": section_id,
                    "appraisal_id": appraisal_id,
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                },
            )
        ).scalar_one_or_none()
        if section is None:
            raise ServiceExecutionError("resource_not_found")
        await self.connection.execute(
            text(
                "UPDATE public.appraisal_sections SET rating=:rating,comments=:comments "
                "WHERE id=:id"
            ),
            {"id": section_id, "rating": request.rating, "comments": request.comments},
        )
        await self.connection.execute(
            text("UPDATE public.appraisals SET updated_at=statement_timestamp() WHERE id=:id"),
            {"id": appraisal_id},
        )
        await self._audit(
            "appraisal_section_rated",
            "appraisal",
            appraisal_id,
            ["section.rating", "section.comments", "updated_at"],
            "Appraisal section rated",
            {"section_id": str(section_id)},
        )
        return await self.get_appraisal(principal, branch_id, appraisal_id)

    async def review(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        appraisal_id: uuid.UUID,
        request: AppraisalReviewRequest,
    ) -> AppraisalResponse:
        appraisal = await self._lock_appraisal(principal, branch_id, appraisal_id)
        if appraisal.status != "pending" or appraisal.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        sections = (
            (
                await self.connection.execute(
                    text(
                        "SELECT section_name,weight,rating FROM public.appraisal_sections "
                        "WHERE appraisal_id=:id ORDER BY sort_order,id FOR UPDATE"
                    ),
                    {"id": appraisal_id},
                )
            )
            .mappings()
            .all()
        )
        expected = {(name, weight) for name, weight, _ in FIXED_SECTIONS}
        actual = {(row["section_name"], row["weight"]) for row in sections}
        if (
            len(sections) != len(FIXED_SECTIONS)
            or actual != expected
            or any(row["rating"] is None for row in sections)
        ):
            raise ServiceExecutionError("state_conflict")
        rating = calculate_weighted_rating([(row["rating"], row["weight"]) for row in sections])
        await self.connection.execute(
            text(
                "UPDATE public.appraisals SET status='reviewed',overall_rating=:rating,"
                "reviewer_comments=:comments,development_plan=:plan,"
                "reviewed_by_app_user_id=:actor,reviewed_at=statement_timestamp() WHERE id=:id"
            ),
            {
                "id": appraisal_id,
                "rating": rating,
                "comments": request.reviewer_comments,
                "plan": request.development_plan,
                "actor": principal.app_user_id,
            },
        )
        await self._audit(
            "appraisal_reviewed",
            "appraisal",
            appraisal_id,
            [
                "status",
                "overall_rating",
                "reviewer_comments",
                "development_plan",
                "reviewed_by_app_user_id",
                "reviewed_at",
            ],
            "Appraisal reviewed",
            {"transition": "pending_to_reviewed"},
        )
        return await self.get_appraisal(principal, branch_id, appraisal_id)

    async def calibrate(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        appraisal_id: uuid.UUID,
        request: AppraisalCalibrationRequest,
    ) -> AppraisalResponse:
        appraisal = await self._lock_appraisal(principal, branch_id, appraisal_id)
        if appraisal.status != "reviewed" or appraisal.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text(
                "UPDATE public.appraisals SET status='calibrated',overall_rating=:rating,"
                "reviewed_by_app_user_id=:actor,reviewed_at=statement_timestamp() WHERE id=:id"
            ),
            {
                "id": appraisal_id,
                "rating": request.final_rating,
                "actor": principal.app_user_id,
            },
        )
        await self._audit(
            "appraisal_calibrated",
            "appraisal",
            appraisal_id,
            ["status", "overall_rating", "reviewed_by_app_user_id", "reviewed_at"],
            "Appraisal calibrated",
            {"transition": "reviewed_to_calibrated"},
        )
        return await self.get_appraisal(principal, branch_id, appraisal_id)

    async def get_appraisal(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, appraisal_id: uuid.UUID
    ) -> AppraisalResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {APPRAISAL_COLUMNS} FROM public.appraisals a "
                        "JOIN public.appraisal_cycles c ON c.id=a.cycle_id "
                        "JOIN public.employees e ON e.id=a.employee_id "
                        "WHERE a.id=:id AND a.company_id=:company_id AND a.branch_id=:branch_id"
                    ),
                    {
                        "id": appraisal_id,
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
        return await self._response(row)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        table = {"appraisal_cycle": "appraisal_cycles", "appraisal": "appraisals"}.get(kind)
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

    async def _response(self, row: Any) -> AppraisalResponse:
        sections = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {SECTION_COLUMNS} FROM public.appraisal_sections "
                        "WHERE appraisal_id=:id ORDER BY sort_order,id"
                    ),
                    {"id": row["id"]},
                )
            )
            .mappings()
            .all()
        )
        values = dict(row)
        values["sections"] = [AppraisalSectionResponse.model_validate(item) for item in sections]
        return AppraisalResponse.model_validate(values)

    async def _cycle_response(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        row: Any,
    ) -> AppraisalCycleResponse:
        appraisals = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {APPRAISAL_COLUMNS} FROM public.appraisals a "
                        "JOIN public.appraisal_cycles c ON c.id=a.cycle_id "
                        "JOIN public.employees e ON e.id=a.employee_id "
                        "WHERE a.cycle_id=:cycle_id AND a.company_id=:company_id "
                        "AND a.branch_id=:branch_id ORDER BY e.name,a.id"
                    ),
                    {
                        "cycle_id": row["id"],
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                    },
                )
            )
            .mappings()
            .all()
        )
        values = dict(row)
        values["appraisals"] = [await self._response(item) for item in appraisals]
        return AppraisalCycleResponse.model_validate(values)

    async def _lock_cycle(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, cycle_id: uuid.UUID
    ) -> Any:
        row = (
            await self.connection.execute(
                text(
                    "SELECT id,status,updated_at FROM public.appraisal_cycles WHERE id=:id "
                    "AND company_id=:company_id AND branch_id=:branch_id FOR UPDATE"
                ),
                {"id": cycle_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def _lock_appraisal(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, appraisal_id: uuid.UUID
    ) -> Any:
        row = (
            await self.connection.execute(
                text(
                    "SELECT id,employee_id,status,updated_at FROM public.appraisals WHERE id=:id "
                    "AND company_id=:company_id AND branch_id=:branch_id FOR UPDATE"
                ),
                {"id": appraisal_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

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
