from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.schemas.incidents import (
    IncidentCorrectiveActionRequest,
    IncidentCreateRequest,
    IncidentInvestigationRequest,
    IncidentResponse,
    IncidentUpdateRequest,
)
from app.services.execution import ServiceExecutionError

INCIDENT_COLUMNS = """
report.id,report.incident_date,report.incident_time,report.location,report.department,
report.incident_type,report.severity,report.description,report.reported_by_id,
reporter.name reported_by_name,report.involved_emp_id,involved.name involved_employee_name,
report.immediate_action,report.root_cause,report.corrective_action,report.status,
report.closed_date,report.closed_by_app_user_id,report.notes,report.created_at,report.updated_at
"""


@dataclass(frozen=True, slots=True)
class IncidentListQuery:
    date_from: date | None
    date_to: date | None
    incident_type: str | None
    severity: str | None
    status: str | None
    limit: int


class IncidentService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: IncidentListQuery,
    ) -> list[IncidentResponse]:
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {INCIDENT_COLUMNS}
FROM public.incident_reports report
LEFT JOIN public.employees reporter ON reporter.id=report.reported_by_id
LEFT JOIN public.employees involved ON involved.id=report.involved_emp_id
WHERE report.company_id=:company_id AND report.branch_id=:branch_id
  AND (CAST(:date_from AS date) IS NULL OR report.incident_date>=:date_from)
  AND (CAST(:date_to AS date) IS NULL OR report.incident_date<=:date_to)
  AND (CAST(:incident_type AS text) IS NULL OR report.incident_type=:incident_type)
  AND (CAST(:severity AS text) IS NULL OR report.severity=:severity)
  AND (CAST(:status AS text) IS NULL OR report.status=:status)
ORDER BY report.incident_date DESC,report.incident_time DESC NULLS LAST,report.id DESC
LIMIT :limit
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "date_from": query.date_from,
                        "date_to": query.date_to,
                        "incident_type": query.incident_type,
                        "severity": query.severity,
                        "status": query.status,
                        "limit": query.limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [IncidentResponse.model_validate(row) for row in rows]

    async def get(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, incident_id: uuid.UUID
    ) -> IncidentResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT {INCIDENT_COLUMNS}
FROM public.incident_reports report
LEFT JOIN public.employees reporter ON reporter.id=report.reported_by_id
LEFT JOIN public.employees involved ON involved.id=report.involved_emp_id
WHERE report.id=:id AND report.company_id=:company_id AND report.branch_id=:branch_id
"""
                    ),
                    {
                        "id": incident_id,
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
        return IncidentResponse.model_validate(row)

    async def create(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: IncidentCreateRequest,
    ) -> IncidentResponse:
        await self._validate_people(
            principal, branch_id, request.reported_by_id, request.involved_emp_id
        )
        incident_id = (
            await self.connection.execute(
                text(
                    """
INSERT INTO public.incident_reports(
 company_id,branch_id,incident_date,incident_time,location,department,incident_type,
 severity,description,reported_by_id,involved_emp_id,immediate_action,notes,status)
VALUES(:company_id,:branch_id,:incident_date,:incident_time,:location,:department,
 :incident_type,:severity,:description,:reported_by_id,:involved_emp_id,
 :immediate_action,:notes,'open') RETURNING id
"""
                ),
                {
                    "company_id": principal.company_id,
                    "branch_id": branch_id,
                    **request.model_dump(by_alias=False),
                },
            )
        ).scalar_one()
        await self._audit(
            "incident_created",
            incident_id,
            [
                "incident_date",
                "incident_time",
                "location",
                "department",
                "incident_type",
                "severity",
                "description",
                "reported_by_id",
                "involved_emp_id",
                "immediate_action",
                "notes",
                "status",
            ],
            "Clinical incident created",
            request.incident_type,
            request.severity,
        )
        return await self.get(principal, branch_id, incident_id)

    async def update(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        incident_id: uuid.UUID,
        request: IncidentUpdateRequest,
    ) -> IncidentResponse:
        current = await self._lock(principal, branch_id, incident_id)
        if current.status != "open" or current.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        await self._validate_people(
            principal, branch_id, request.reported_by_id, request.involved_emp_id
        )
        await self.connection.execute(
            text(
                """
UPDATE public.incident_reports SET incident_date=:incident_date,incident_time=:incident_time,
 location=:location,department=:department,incident_type=:incident_type,severity=:severity,
 description=:description,reported_by_id=:reported_by_id,involved_emp_id=:involved_emp_id,
 immediate_action=:immediate_action,notes=:notes WHERE id=:id
"""
            ),
            {
                "id": incident_id,
                **request.model_dump(exclude={"expected_updated_at"}, by_alias=False),
            },
        )
        await self._audit(
            "incident_updated",
            incident_id,
            [
                "incident_date",
                "incident_time",
                "location",
                "department",
                "incident_type",
                "severity",
                "description",
                "reported_by_id",
                "involved_emp_id",
                "immediate_action",
                "notes",
            ],
            "Clinical incident updated",
            request.incident_type,
            request.severity,
        )
        return await self.get(principal, branch_id, incident_id)

    async def investigate(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        incident_id: uuid.UUID,
        request: IncidentInvestigationRequest,
    ) -> IncidentResponse:
        current = await self._lock(principal, branch_id, incident_id)
        if current.status != "open" or current.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text(
                "UPDATE public.incident_reports SET status='investigating',root_cause=:root_cause "
                "WHERE id=:id"
            ),
            {"id": incident_id, "root_cause": request.root_cause},
        )
        await self._audit(
            "incident_investigated",
            incident_id,
            ["status", "root_cause"],
            "Clinical incident investigation started",
            current.incident_type,
            current.severity,
            from_status="open",
            to_status="investigating",
        )
        return await self.get(principal, branch_id, incident_id)

    async def corrective_action(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        incident_id: uuid.UUID,
        request: IncidentCorrectiveActionRequest,
    ) -> IncidentResponse:
        current = await self._lock(principal, branch_id, incident_id)
        if current.status != "investigating" or current.updated_at != request.expected_updated_at:
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text(
                "UPDATE public.incident_reports SET corrective_action=:corrective_action "
                "WHERE id=:id"
            ),
            {"id": incident_id, "corrective_action": request.corrective_action},
        )
        await self._audit(
            "incident_corrective_action_recorded",
            incident_id,
            ["corrective_action"],
            "Clinical incident corrective action recorded",
            current.incident_type,
            current.severity,
            from_status="investigating",
            to_status="investigating",
        )
        return await self.get(principal, branch_id, incident_id)

    async def close(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        incident_id: uuid.UUID,
        expected_updated_at: object,
    ) -> IncidentResponse:
        current = await self._lock(principal, branch_id, incident_id)
        if (
            current.status != "investigating"
            or current.updated_at != expected_updated_at
            or not current.root_cause.strip()
            or not current.corrective_action.strip()
        ):
            raise ServiceExecutionError("state_conflict")
        business_date = (
            await self.connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()
        await self.connection.execute(
            text(
                "UPDATE public.incident_reports SET status='closed',closed_date=:closed_date,"
                "closed_by_app_user_id=:actor WHERE id=:id"
            ),
            {"id": incident_id, "closed_date": business_date, "actor": principal.app_user_id},
        )
        await self._audit(
            "incident_closed",
            incident_id,
            ["status", "closed_date", "closed_by_app_user_id"],
            "Clinical incident closed",
            current.incident_type,
            current.severity,
            from_status="investigating",
            to_status="closed",
        )
        return await self.get(principal, branch_id, incident_id)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "incident_report" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        exists = (
            await self.connection.execute(
                text(
                    "SELECT 1 FROM public.incident_reports WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id"
                ),
                {"id": resource_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one_or_none()
        if exists is None:
            raise ServiceExecutionError("resource_not_found")

    async def _validate_people(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        reported_by_id: uuid.UUID | None,
        involved_emp_id: uuid.UUID | None,
    ) -> None:
        ids = {item for item in (reported_by_id, involved_emp_id) if item is not None}
        if not ids:
            return
        count = (
            await self.connection.execute(
                text(
                    "SELECT count(*) FROM public.employees WHERE id=ANY(:ids) "
                    "AND company_id=:company_id AND branch_id=:branch_id"
                ),
                {"ids": list(ids), "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).scalar_one()
        if count != len(ids):
            raise ServiceExecutionError("resource_not_found")

    async def _lock(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, incident_id: uuid.UUID
    ) -> Any:
        row = (
            await self.connection.execute(
                text(
                    "SELECT id,status,incident_type,severity,root_cause,corrective_action,"
                    "updated_at "
                    "FROM public.incident_reports WHERE id=:id AND company_id=:company_id "
                    "AND branch_id=:branch_id FOR UPDATE"
                ),
                {"id": incident_id, "company_id": principal.company_id, "branch_id": branch_id},
            )
        ).one_or_none()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def _audit(
        self,
        action: str,
        incident_id: uuid.UUID,
        fields: list[str],
        reason: str,
        incident_type: str,
        severity: str,
        *,
        from_status: str | None = None,
        to_status: str | None = None,
    ) -> None:
        metadata: dict[str, object] = {"incident_type": incident_type, "severity": severity}
        if from_status is not None:
            metadata["from_status"] = from_status
        if to_status is not None:
            metadata["to_status"] = to_status
        await append_audit_event(
            self.connection,
            action=action,
            entity_type="incident_report",
            entity_id=incident_id,
            changed_fields=fields,
            reason=reason,
            metadata=metadata,
        )
