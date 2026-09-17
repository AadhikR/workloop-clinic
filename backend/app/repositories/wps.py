from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


class WpsRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def get_run(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT run.*,branch.mol_employer_id,branch.default_bank_routing_code "
                        "FROM public.payroll_runs AS run JOIN public.branches AS branch "
                        "ON branch.id=run.branch_id AND branch.company_id=run.company_id "
                        "WHERE run.id=:run_id AND run.company_id=:company_id "
                        "AND run.branch_id=:branch_id"
                    ),
                    {"run_id": run_id, "company_id": company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def entries(self, run_id: uuid.UUID) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT entry.*,employee.name AS employee_name,employee.mol_id,
       employee.bank_routing_code,employee.iban
FROM public.payroll_entries AS entry
JOIN public.employees AS employee ON employee.id=entry.employee_id
 AND employee.company_id=entry.company_id AND employee.branch_id=entry.branch_id
WHERE entry.payroll_run_id=:run_id AND NOT entry.excluded
ORDER BY employee.mol_id,entry.id
"""
                    ),
                    {"run_id": run_id},
                )
            ).mappings()
        )

    async def transition_run(
        self,
        *,
        run_id: uuid.UUID,
        action: str,
        reference_number: str,
        reason: str,
        expected_updated_at: datetime,
        projection_digest: str,
        projection_mode: str,
    ) -> None:
        await self.connection.execute(
            text(
                "SELECT public.transition_payroll_wps(:run_id,:action,:reference_number,:reason,"
                ":expected_updated_at,:projection_digest,:projection_mode)"
            ),
            {
                "run_id": run_id,
                "action": action,
                "reference_number": reference_number,
                "reason": reason,
                "expected_updated_at": expected_updated_at,
                "projection_digest": projection_digest,
                "projection_mode": projection_mode,
            },
        )

    async def transition_entry(
        self,
        *,
        run_id: uuid.UUID,
        entry_id: uuid.UUID,
        action: str,
        reason: str,
        expected_updated_at: datetime,
    ) -> None:
        await self.connection.execute(
            text(
                "SELECT public.transition_wps_entry(:run_id,:entry_id,:action,:reason,"
                ":expected_updated_at)"
            ),
            {
                "run_id": run_id,
                "entry_id": entry_id,
                "action": action,
                "reason": reason,
                "expected_updated_at": expected_updated_at,
            },
        )

    async def create_override(
        self,
        *,
        override_id: uuid.UUID,
        run_id: uuid.UUID,
        entry_id: uuid.UUID | None,
        rule_code: str,
        reason: str,
    ) -> None:
        await self.connection.execute(
            text(
                "SELECT public.create_wps_compliance_override(:override_id,:run_id,:entry_id,"
                ":rule_code,:reason)"
            ),
            {
                "override_id": override_id,
                "run_id": run_id,
                "entry_id": entry_id,
                "rule_code": rule_code,
                "reason": reason,
            },
        )

    async def get_override(self, override_id: uuid.UUID) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,payroll_run_id,payroll_entry_id,rule_code,reason,created_at "
                        "FROM public.compliance_overrides WHERE id=:id"
                    ),
                    {"id": override_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def nafis_sources(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, period_end: date
    ) -> tuple[RowMapping | None, list[RowMapping]]:
        await self.connection.execute(
            text("SELECT public.lock_nafis_sources(:period_end)"), {"period_end": period_end}
        )
        company = (
            (
                await self.connection.execute(
                    text(
                        "SELECT company.id,company.nafis_quota_percent,company.updated_at,"
                        "branch.updated_at AS branch_updated_at "
                        "FROM public.companies AS company JOIN public.branches AS branch "
                        "ON branch.company_id=company.id WHERE company.id=:company_id "
                        "AND branch.id=:branch_id"
                    ),
                    {"company_id": company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        employees = list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT id,name,nationality,nafis_registration_no,basic_salary,
       employment_start_date,termination_date,updated_at
FROM public.employees
WHERE company_id=:company_id AND branch_id=:branch_id
  AND (employment_start_date IS NULL OR employment_start_date<=:period_end)
  AND (termination_date IS NULL OR termination_date>=:period_end)
  AND employment_status IN ('Active','Probation','On Leave','Terminated')
ORDER BY id
"""
                    ),
                    {"company_id": company_id, "branch_id": branch_id, "period_end": period_end},
                )
            ).mappings()
        )
        return company, employees

    async def list_nafis(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str | None,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT report.* FROM public.nafis_reports AS report
WHERE report.company_id=:company_id AND report.branch_id=:branch_id
  AND (CAST(:period AS text) IS NULL OR report.period=CAST(:period AS text))
  AND (CAST(:cursor_id AS uuid) IS NULL OR (report.period,report.id)<(
    SELECT anchor.period,anchor.id FROM public.nafis_reports AS anchor
    WHERE anchor.id=CAST(:cursor_id AS uuid) AND anchor.company_id=:company_id
      AND anchor.branch_id=:branch_id))
ORDER BY report.period DESC,report.id DESC
LIMIT :limit
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "period": period,
                        "cursor_id": cursor_id,
                        "limit": limit,
                    },
                )
            ).mappings()
        )

    async def replace_nafis(
        self,
        *,
        snapshot_id: uuid.UUID,
        period: str,
        total_headcount: int,
        emirati_count: int,
        ratio_percent: Decimal,
        required_percent: Decimal,
        compliant: bool,
        snapshot: dict[str, object],
        expected_generated_at: datetime | None,
    ) -> uuid.UUID:
        result = await self.connection.scalar(
            text(
                "SELECT public.replace_nafis_snapshot(:snapshot_id,:period,:total_headcount,"
                ":emirati_count,:ratio_percent,:required_percent,:compliant,"
                "CAST(:snapshot AS jsonb),:expected_generated_at)"
            ),
            {
                "snapshot_id": snapshot_id,
                "period": period,
                "total_headcount": total_headcount,
                "emirati_count": emirati_count,
                "ratio_percent": ratio_percent,
                "required_percent": required_percent,
                "compliant": compliant,
                "snapshot": json.dumps(snapshot, sort_keys=True, separators=(",", ":")),
                "expected_generated_at": expected_generated_at,
            },
        )
        return uuid.UUID(str(result))

    async def get_nafis(self, snapshot_id: uuid.UUID) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    text("SELECT * FROM public.nafis_reports WHERE id=:id"),
                    {"id": snapshot_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def replay_visible(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, kind: str, resource_id: uuid.UUID
    ) -> bool:
        table = {
            "payroll_run": "payroll_runs",
            "compliance_override": "compliance_overrides",
            "nafis_snapshot": "nafis_reports",
        }.get(kind)
        if table is None:
            return False
        return bool(
            await self.connection.scalar(
                text(
                    f"SELECT EXISTS(SELECT 1 FROM public.{table} WHERE id=:id "
                    "AND company_id=:company_id AND branch_id=:branch_id)"
                ),
                {"id": resource_id, "company_id": company_id, "branch_id": branch_id},
            )
        )
