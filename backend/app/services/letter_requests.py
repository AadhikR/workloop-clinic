from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.schemas.letter_requests import (
    SALARY_LETTER_TYPES,
    LetterRequestCreateRequest,
    LetterRequestPrintSource,
    LetterRequestResponse,
)
from app.services.execution import ServiceExecutionError

SAFE_COLUMNS = """
request.id,request.employee_id,request.employee_name_snapshot employee_name,
request.job_title_snapshot job_title,request.department_snapshot department,
request.employment_start_date_snapshot employment_start_date,
request.branch_name_snapshot branch_name,request.request_kind,request.letter_type,
request.purpose,request.status,request.notes,request.rejection_reason,
request.requested_at,request.completed_at,request.actioned_at,request.updated_at
"""


@dataclass(frozen=True, slots=True)
class LetterRequestListQuery:
    status: str | None
    kind: str | None
    employee_id: uuid.UUID | None
    limit: int


class LetterRequestService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def list_self(
        self,
        principal: AuthorizationPrincipal,
        *,
        status: str | None,
        kind: str | None,
        limit: int,
    ) -> list[LetterRequestResponse]:
        employee_id, branch_id = self._staff_identity(principal)
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {SAFE_COLUMNS}
FROM public.letter_requests request
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.employee_id=:employee_id
  AND (CAST(:status AS text) IS NULL OR request.status=:status)
  AND (CAST(:kind AS text) IS NULL OR request.request_kind=:kind)
ORDER BY request.requested_at DESC,request.id DESC
LIMIT :limit
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "status": status,
                        "kind": kind,
                        "limit": limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [LetterRequestResponse.model_validate(row) for row in rows]

    async def list_admin(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: LetterRequestListQuery,
    ) -> list[LetterRequestResponse]:
        self._require_admin(principal)
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {SAFE_COLUMNS}
FROM public.letter_requests request
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND (CAST(:status AS text) IS NULL OR request.status=:status)
  AND (CAST(:kind AS text) IS NULL OR request.request_kind=:kind)
  AND (CAST(:employee_id AS uuid) IS NULL OR request.employee_id=:employee_id)
ORDER BY request.requested_at DESC,request.id DESC
LIMIT :limit
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "status": query.status,
                        "kind": query.kind,
                        "employee_id": query.employee_id,
                        "limit": query.limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [LetterRequestResponse.model_validate(row) for row in rows]

    async def get(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> LetterRequestResponse:
        row = await self._get_row(principal, branch_id, request_id, include_salary=False)
        return LetterRequestResponse.model_validate(row)

    async def submit(
        self,
        principal: AuthorizationPrincipal,
        request: LetterRequestCreateRequest,
    ) -> LetterRequestResponse:
        employee_id, branch_id = self._staff_identity(principal)
        snapshot = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT employee.name,employee.job_title,employee.department,
 employee.employment_start_date,employee.basic_salary,employee.allowance,
 branch.name branch_name
FROM public.employees employee
JOIN public.branches branch ON branch.id=employee.branch_id
 AND branch.company_id=employee.company_id
WHERE employee.id=:employee_id AND employee.company_id=:company_id
 AND employee.branch_id=:branch_id
FOR SHARE OF employee
"""
                    ),
                    {
                        "employee_id": employee_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if snapshot is None:
            raise ServiceExecutionError("resource_not_found")
        include_salary = request.letter_type in SALARY_LETTER_TYPES
        request_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.letter_requests(
 company_id,branch_id,employee_id,request_kind,letter_type,purpose,status,
 employee_name_snapshot,job_title_snapshot,department_snapshot,
 employment_start_date_snapshot,branch_name_snapshot,basic_salary_snapshot,
 allowance_snapshot)
VALUES(:company_id,:branch_id,:employee_id,:request_kind,:letter_type,:purpose,'pending',
 :employee_name,:job_title,:department,:employment_start_date,:branch_name,
 :basic_salary,:allowance) RETURNING id
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "request_kind": request.request_kind,
                    "letter_type": request.stored_letter_type(),
                    "purpose": request.stored_purpose(),
                    "employee_name": snapshot["name"],
                    "job_title": snapshot["job_title"],
                    "department": snapshot["department"],
                    "employment_start_date": snapshot["employment_start_date"],
                    "branch_name": snapshot["branch_name"],
                    "basic_salary": snapshot["basic_salary"] if include_salary else None,
                    "allowance": snapshot["allowance"] if include_salary else None,
                },
            )
        ).scalar_one()
        await append_audit_event(
            self.connection,
            action="letter_submitted",
            entity_type="letter_request",
            entity_id=request_id,
            changed_fields=[
                "request_kind",
                "letter_type",
                "purpose",
                "status",
                "employee_name_snapshot",
                "job_title_snapshot",
                "department_snapshot",
                "employment_start_date_snapshot",
                "branch_name_snapshot",
                "basic_salary_snapshot",
                "allowance_snapshot",
            ],
            reason="Letter or custom request submitted",
            metadata={
                "request_kind": request.request_kind,
                "letter_type": request.stored_letter_type()
                if request.request_kind == "letter"
                else None,
            },
        )
        return await self.get(principal, branch_id, request_id)

    async def complete(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        expected_requested_at: datetime,
    ) -> LetterRequestResponse:
        current = await self._lock_pending(principal, branch_id, request_id, expected_requested_at)
        await self.connection.execute(
            text(
                """
UPDATE public.letter_requests SET status='completed',completed_at=statement_timestamp(),
 actioned_at=statement_timestamp(),actioned_by_app_user_id=:actor,rejection_reason=''
WHERE id=:id
"""
            ),
            {"id": request_id, "actor": principal.app_user_id},
        )
        await self._audit_decision("letter_completed", request_id, current, "pending_to_completed")
        return await self.get(principal, branch_id, request_id)

    async def reject(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        expected_requested_at: datetime,
        reason: str,
    ) -> LetterRequestResponse:
        current = await self._lock_pending(principal, branch_id, request_id, expected_requested_at)
        await self.connection.execute(
            text(
                """
UPDATE public.letter_requests SET status='rejected',rejection_reason=:reason,
 completed_at=NULL,actioned_at=statement_timestamp(),actioned_by_app_user_id=:actor
WHERE id=:id
"""
            ),
            {"id": request_id, "reason": reason, "actor": principal.app_user_id},
        )
        await self._audit_decision("letter_rejected", request_id, current, "pending_to_rejected")
        return await self.get(principal, branch_id, request_id)

    async def print_source(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> LetterRequestPrintSource:
        row = await self._get_row(principal, branch_id, request_id, include_salary=True)
        if row["status"] != "completed" or row["completed_at"] is None:
            raise ServiceExecutionError("state_conflict")
        return LetterRequestPrintSource.model_validate(
            {
                "request_id": row["id"],
                "request_kind": row["request_kind"],
                "letter_type": row["letter_type"],
                "purpose": row["purpose"],
                "employee_name": row["employee_name"],
                "job_title": row["job_title"],
                "department": row["department"],
                "employment_start_date": row["employment_start_date"],
                "branch_name": row["branch_name"],
                "basic_salary": row["basic_salary_snapshot"],
                "allowance": row["allowance_snapshot"],
                "requested_at": row["requested_at"],
                "completed_at": row["completed_at"],
            }
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "letter_request" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        conditions = "id=:id AND company_id=:company_id AND branch_id=:branch_id"
        parameters: dict[str, object] = {
            "id": resource_id,
            "company_id": principal.company_id,
            "branch_id": branch_id,
        }
        if principal.role is not AppRole.ADMIN:
            employee_id, _ = self._staff_identity(principal)
            conditions += " AND employee_id=:employee_id"
            parameters["employee_id"] = employee_id
        exists = (
            await self.connection.execute(
                text(f"SELECT 1 FROM public.letter_requests WHERE {conditions}"), parameters
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ServiceExecutionError("resource_not_found")

    async def _get_row(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        *,
        include_salary: bool,
    ) -> Any:
        conditions = (
            "request.id=:id AND request.company_id=:company_id AND request.branch_id=:branch_id"
        )
        parameters: dict[str, object] = {
            "id": request_id,
            "company_id": principal.company_id,
            "branch_id": branch_id,
        }
        if principal.role is not AppRole.ADMIN:
            employee_id, own_branch = self._staff_identity(principal)
            if own_branch != branch_id:
                raise ServiceExecutionError("resource_not_found")
            conditions += " AND request.employee_id=:employee_id"
            parameters["employee_id"] = employee_id
        salary_columns = (
            ",request.basic_salary_snapshot,request.allowance_snapshot" if include_salary else ""
        )
        row = (
            (
                await self.connection.execute(
                    text(
                        f"SELECT {SAFE_COLUMNS}{salary_columns} "
                        f"FROM public.letter_requests request WHERE {conditions}"
                    ),
                    parameters,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def _lock_pending(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        expected_requested_at: datetime,
    ) -> Any:
        self._require_admin(principal)
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT id,status,request_kind,letter_type,requested_at
FROM public.letter_requests
WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id
FOR UPDATE
"""
                    ),
                    {
                        "id": request_id,
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
        persisted_requested_at = row["requested_at"].replace(
            microsecond=row["requested_at"].microsecond // 1000 * 1000
        )
        public_requested_at = expected_requested_at.replace(
            microsecond=expected_requested_at.microsecond // 1000 * 1000
        )
        if row["status"] != "pending" or persisted_requested_at != public_requested_at:
            raise ServiceExecutionError("state_conflict")
        return row

    async def _audit_decision(
        self, action: str, request_id: uuid.UUID, current: Any, transition: str
    ) -> None:
        changed_fields = ["status", "actioned_at", "actioned_by_app_user_id"]
        if action == "letter_completed":
            changed_fields.append("completed_at")
        else:
            changed_fields.append("rejection_reason")
        await append_audit_event(
            self.connection,
            action=action,
            entity_type="letter_request",
            entity_id=request_id,
            changed_fields=changed_fields,
            reason="Letter or custom request decided",
            metadata={
                "transition": transition,
                "request_kind": current["request_kind"],
                "letter_type": current["letter_type"]
                if current["request_kind"] == "letter"
                else None,
            },
        )

    @staticmethod
    def _staff_identity(principal: AuthorizationPrincipal) -> tuple[uuid.UUID, uuid.UUID]:
        if (
            principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}
            or principal.employee_id is None
            or principal.branch_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        return principal.employee_id, principal.branch_id

    @staticmethod
    def _require_admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
