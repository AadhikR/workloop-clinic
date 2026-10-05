from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.expiry_command import CLINICAL_DOCUMENT_TYPES
from app.http.pagination import uuid_page
from app.models.identity import AppRole
from app.repositories.admin_workspace import ADMIN_WORKSPACE
from app.repositories.clinical_credentials import CLINICAL_CREDENTIALS
from app.repositories.clinical_workforce import CLINICAL_WORKFORCE, WORKFORCE_GROUPS
from app.schemas.portal_projections import (
    AdminWorkspaceResponse,
    ClinicalDepartmentResponse,
    ClinicalWorkforceRowResponse,
    ClinicalWorkforceSummaryResponse,
    EmployeeDirectoryDetailResponse,
    EmployeeExpiryResponse,
    LeaveActionResponse,
    OwnAdvancePaymentResponse,
    OwnAdvanceProgressResponse,
    OwnAdvanceSummaryResponse,
)
from app.services.advances import build_schedule
from app.services.execution import ServiceExecutionError

EXPIRY_SOURCES = """
SELECT 'employee:'||employee.id::text||':'||source.kind id,
 employee.id employee_id,employee.name employee_name,source.kind source_type,source.expiry_date
FROM public.employees employee
CROSS JOIN LATERAL (VALUES
 ('visa',employee.visa_expiry),('passport',employee.passport_expiry),
 ('emirates_id',employee.emirates_id_expiry),('labour_card',employee.labour_card_expiry),
 ('licence',CASE WHEN employee.licence_authority<>'' AND employee.licence_authority<>'None'
 THEN employee.licence_expiry END)) source(kind,expiry_date)
WHERE employee.company_id=:company_id AND employee.branch_id=:branch_id
 AND employee.active AND employee.employment_status<>'Terminated'
 AND source.expiry_date IS NOT NULL
UNION ALL
SELECT 'document:'||document.id::text,employee.id,employee.name,
 document.document_type,document.expiry_date
FROM public.employee_documents document
JOIN public.employees employee ON employee.id=document.employee_id
 AND employee.company_id=document.company_id AND employee.branch_id=document.branch_id
WHERE document.company_id=:company_id AND document.branch_id=:branch_id
 AND employee.active AND employee.employment_status<>'Terminated'
 AND document.expiry_date IS NOT NULL
 AND document.cleanup_requested_at IS NULL
"""


class PortalProjectionService:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def admin_workspace(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> AdminWorkspaceResponse:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        row = (
            (
                await self.connection.execute(
                    text(ADMIN_WORKSPACE),
                    {"company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one()
        )
        fields = {
            key: row[key]
            for key in (
                "business_date",
                "active_employees",
                "payroll_runs",
                "draft_payrolls",
                "sif_generated",
                "insurance_policies",
            )
        }
        return AdminWorkspaceResponse.model_validate(
            {
                **fields,
                "alerts": {
                    {
                        "policy_renewals": "policyRenewals",
                        "payroll_approval": "payrollApproval",
                        "wps_overdue": "wpsOverdue",
                    }.get(key, key): value
                    for key, value in row.items()
                    if key not in fields
                },
            }
        )

    @staticmethod
    def _clinical_parameters(
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        scanner_definition: str,
    ) -> dict[str, object]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        return {
            "company_id": principal.company_id,
            "branch_id": branch_id,
            "scanner_definition": scanner_definition,
            "clinical_types": list(CLINICAL_DOCUMENT_TYPES),
        }

    async def clinical_workforce_summary(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        scanner_definition: str,
    ) -> ClinicalWorkforceSummaryResponse:
        params = self._clinical_parameters(principal, branch_id, scanner_definition)
        row = (
            (
                await self.connection.execute(
                    text(
                        CLINICAL_WORKFORCE
                        + """
SELECT business_date,
 (SELECT jsonb_object_agg(group_code,total) FROM (
 SELECT group_code,count(*)::integer total FROM groups GROUP BY group_code) counts) counts,
 (SELECT count(*)::integer FROM base WHERE compliant AND has_credentials) compliant,
 (SELECT count(*)::integer FROM base WHERE rostered) rostered FROM snapshot
"""
                    ),
                    params,
                )
            )
            .mappings()
            .one()
        )
        department_rows = (
            (
                await self.connection.execute(
                    text(
                        CLINICAL_WORKFORCE
                        + """
SELECT department,count(*)::integer headcount,
 count(*) FILTER(WHERE compliant AND has_credentials)::integer credentialled,
 count(*) FILTER(WHERE rostered)::integer rostered,
 (SELECT coalesce(sum(rule.min_staff),0)::integer FROM public.department_staffing_rules rule
 WHERE rule.company_id=:company_id AND rule.branch_id=:branch_id AND rule.department=base.department
 AND (rule.effective_from IS NULL OR rule.effective_from<=(SELECT business_date FROM snapshot))
 AND (rule.effective_to IS NULL
 OR rule.effective_to>=(SELECT business_date FROM snapshot))) min_staff
 FROM base GROUP BY department
ORDER BY count(*) DESC,department
"""
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        raw_counts = cast(dict[str, int], row["counts"] or {})
        counts = {group: raw_counts.get(group, 0) for group in WORKFORCE_GROUPS}
        departments = [ClinicalDepartmentResponse.model_validate(item) for item in department_rows]
        if sum(item.headcount for item in departments) != counts["activeStaff"]:
            raise ServiceExecutionError("state_conflict")
        return ClinicalWorkforceSummaryResponse(
            business_date=row["business_date"],
            counts=counts,
            compliant=row["compliant"],
            rostered=row["rostered"],
            departments=departments,
        )

    async def clinical_workforce_details(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        scanner_definition: str,
        group: str,
        limit: int,
        cursor: str | None,
    ) -> list[ClinicalWorkforceRowResponse]:
        if group not in WORKFORCE_GROUPS:
            raise ServiceExecutionError("validation_failed")
        params = self._clinical_parameters(principal, branch_id, scanner_definition)
        params.update({"group": group, "limit": limit, "cursor": cursor})
        rows = (
            (
                await self.connection.execute(
                    text(
                        CLINICAL_WORKFORCE
                        + """
SELECT id,employee_id,employee_name,department,job_title,status,source_date,source_time,source_label
FROM groups WHERE group_code=:group AND (CAST(:cursor AS text) IS NULL OR id>:cursor)
ORDER BY id ASC LIMIT :limit
"""
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        return [ClinicalWorkforceRowResponse.model_validate(row) for row in rows]

    async def employee_directory_details(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        limit: int,
        cursor: uuid.UUID | None,
    ) -> list[EmployeeDirectoryDetailResponse]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        rows = (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,mol_id,allowance::text,visa_expiry,emirates_id_expiry "
                        "FROM public.employees WHERE company_id=:company_id "
                        "AND branch_id=:branch_id "
                        "AND (CAST(:cursor AS uuid) IS NULL OR id>:cursor) ORDER BY id LIMIT :limit"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "cursor": cursor,
                        "limit": limit,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [EmployeeDirectoryDetailResponse.model_validate(row) for row in rows]

    async def own_advance_progress(
        self,
        principal: AuthorizationPrincipal,
        record_id: uuid.UUID,
        limit: int,
        cursor: uuid.UUID | None,
    ) -> OwnAdvanceProgressResponse:
        if (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.branch_id is None
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        payload = (
            await self.connection.execute(
                text("SELECT public.read_own_advance_progress(:id,:cursor,:limit)"),
                {"id": record_id, "cursor": cursor, "limit": limit + 1},
            )
        ).scalar_one()
        if payload is None:
            raise ServiceExecutionError("resource_not_found")
        payload = cast(dict[str, Any], payload)
        advance = payload["advance"]
        amount = Decimal(str(advance["amount"]))
        paid = Decimal(str(payload["total_paid"]))
        outstanding = Decimal(str(advance["outstanding_balance"]))
        if paid < 0 or outstanding < 0 or amount != paid + outstanding:
            raise ServiceExecutionError("state_conflict")
        values = cast(
            RowMapping,
            {
                "amount": amount,
                "repayment_start_month": date.fromisoformat(advance["repayment_start_month"]),
                "repayment_months": advance["repayment_months"],
            },
        )
        schedule = build_schedule(
            values, [cast(RowMapping, {"amount": paid})], payload["business_period"]
        )
        payments = [
            OwnAdvancePaymentResponse.model_validate(
                {
                    **item,
                    "amount": f"{Decimal(str(item['amount'])):.2f}",
                }
            )
            for item in payload["payments"]
        ]
        page = uuid_page(payments, limit)
        version = hashlib.sha256(
            json.dumps(
                {
                    "advance": advance,
                    "total_paid": payload["total_paid"],
                    "business_period": payload["business_period"],
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return OwnAdvanceProgressResponse(
            data=page.data,
            page=page.page,
            summary=OwnAdvanceSummaryResponse(
                advance_id=record_id,
                amount=f"{amount:.2f}",
                total_paid=f"{paid:.2f}",
                outstanding_balance=f"{outstanding:.2f}",
                status=advance["status"],
                updated_at=advance["updated_at"],
                source_version=f"sha256:{version}",
                schedule=schedule,
            ),
        )

    async def clinical_credentials(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        status: str,
        scanner_definition: str,
        limit: int,
        cursor: str | None,
    ) -> list[EmployeeExpiryResponse]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        if status not in {"valid", "expiring", "expired"}:
            raise ServiceExecutionError("validation_failed")
        rows = (
            (
                await self.connection.execute(
                    text(f"""
WITH credentials AS ({CLINICAL_CREDENTIALS}), classified AS (
 SELECT credentials.id,employee.id employee_id,employee.name employee_name,
  credentials.source_type,credentials.expiry_date,
  CASE WHEN credentials.expiry_date<public.workloop_business_date() THEN 'expired'
   WHEN credentials.expiry_date<=public.workloop_business_date()+90 THEN 'expiring'
   ELSE 'valid' END status
 FROM credentials JOIN public.employees employee ON employee.id=credentials.employee_id
  AND employee.company_id=:company_id AND employee.branch_id=:branch_id
)
SELECT * FROM classified WHERE status=:status AND (CAST(:cursor AS text) IS NULL OR id>:cursor)
ORDER BY id ASC LIMIT :limit
"""),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "status": status,
                        "scanner_definition": scanner_definition,
                        "clinical_types": sorted(CLINICAL_DOCUMENT_TYPES),
                        "limit": limit,
                        "cursor": cursor,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [EmployeeExpiryResponse.model_validate(row) for row in rows]

    async def employee_expiry(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        limit: int,
        cursor: str | None,
    ) -> list[EmployeeExpiryResponse]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        rows = (
            (
                await self.connection.execute(
                    text(
                        f"""WITH sources AS ({EXPIRY_SOURCES})
SELECT id,employee_id,employee_name,source_type,expiry_date,
 CASE WHEN expiry_date<public.workloop_business_date() THEN 'expired'
 WHEN expiry_date<=public.workloop_business_date()+
 CASE WHEN id LIKE 'document:%' AND source_type=ANY(:clinical_types) THEN 90 ELSE 60 END
 THEN 'expiring' ELSE 'valid' END status
FROM sources WHERE (CAST(:cursor AS text) IS NULL OR id>:cursor)
ORDER BY id ASC LIMIT :limit"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "limit": limit,
                        "cursor": cursor,
                        "clinical_types": sorted(CLINICAL_DOCUMENT_TYPES),
                    },
                )
            )
            .mappings()
            .all()
        )
        return [EmployeeExpiryResponse.model_validate(row) for row in rows]

    async def recent_leave_actions(
        self,
        principal: AuthorizationPrincipal,
        limit: int,
        cursor: uuid.UUID | None,
    ) -> list[LeaveActionResponse]:
        if (
            principal.role is not AppRole.MANAGER
            or principal.branch_id is None
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        rows = (
            (
                await self.connection.execute(
                    text("""
SELECT * FROM public.read_recent_manager_leave_actions(:cursor,:limit)
"""),
                    {
                        "company_id": principal.company_id,
                        "branch_id": principal.branch_id,
                        "employee_id": principal.employee_id,
                        "actor_id": principal.app_user_id,
                        "limit": limit,
                        "cursor": cursor,
                    },
                )
            )
            .mappings()
            .all()
        )
        return [LeaveActionResponse.model_validate(row) for row in rows]
