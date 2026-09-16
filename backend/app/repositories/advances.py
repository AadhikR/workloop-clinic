from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

_BASE_SELECT = """
SELECT advance.*,employee.name AS employee_name,
       creator.actor_app_user_id AS creator_app_user_id,
       CASE WHEN creator_profile.employee_id IS NULL THEN 'Administrator'
            ELSE creator_employee.name END AS creator_name,
       decision.actor_app_user_id AS decision_actor_app_user_id,
       CASE WHEN decision.id IS NULL THEN NULL
            WHEN decision_profile.employee_id IS NULL THEN 'Administrator'
            ELSE decision_employee.name END AS decision_actor_name
FROM public.salary_advances AS advance
JOIN public.employees AS employee
  ON employee.id=advance.employee_id AND employee.company_id=advance.company_id
 AND employee.branch_id=advance.branch_id
LEFT JOIN LATERAL (
  SELECT event.id,event.actor_app_user_id
  FROM public.audit_events AS event
  WHERE event.entity_type='salary_advance' AND event.entity_id=advance.id
    AND event.action='salary_advance_requested'
  ORDER BY event.occurred_at,event.id LIMIT 1
) AS creator ON true
LEFT JOIN public.user_profiles AS creator_profile
  ON creator_profile.app_user_id=creator.actor_app_user_id
LEFT JOIN public.employees AS creator_employee ON creator_employee.id=creator_profile.employee_id
LEFT JOIN LATERAL (
  SELECT event.id,event.actor_app_user_id
  FROM public.audit_events AS event
  WHERE event.entity_type='salary_advance' AND event.entity_id=advance.id
    AND event.action IN ('salary_advance_approved','salary_advance_rejected')
  ORDER BY event.occurred_at DESC,event.id DESC LIMIT 1
) AS decision ON true
LEFT JOIN public.user_profiles AS decision_profile
  ON decision_profile.app_user_id=decision.actor_app_user_id
LEFT JOIN public.employees AS decision_employee ON decision_employee.id=decision_profile.employee_id
"""


class AdvanceRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()

    async def list_advances(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID | None,
        status: str | None,
        start_period: str | None,
        cursor_id: uuid.UUID | None,
        limit: int,
        admin: bool,
    ) -> list[RowMapping]:
        projection = (
            _BASE_SELECT
            if admin
            else (
                "SELECT advance.*,employee.name AS employee_name "
                "FROM public.salary_advances AS advance "
                "JOIN public.employees AS employee ON employee.id=advance.employee_id "
                "AND employee.company_id=advance.company_id "
                "AND employee.branch_id=advance.branch_id "
            )
        )
        employee_scope = "" if admin else "AND advance.employee_id=:employee_id"
        statement = text(
            projection
            + f"""
WHERE advance.company_id=:company_id AND advance.branch_id=:branch_id
  {employee_scope}
  AND (CAST(:employee_filter AS uuid) IS NULL
       OR advance.employee_id=CAST(:employee_filter AS uuid))
  AND (CAST(:status AS text) IS NULL OR advance.status=CAST(:status AS text))
  AND (CAST(:start_period AS text) IS NULL
       OR to_char(advance.repayment_start_month,'YYYY-MM')=CAST(:start_period AS text))
  AND (CAST(:cursor_id AS uuid) IS NULL OR (advance.created_at,advance.id)<(
    SELECT anchor.created_at,anchor.id FROM public.salary_advances AS anchor
    WHERE anchor.id=CAST(:cursor_id AS uuid) AND anchor.company_id=:company_id
      AND anchor.branch_id=:branch_id {employee_scope.replace("advance.", "anchor.")}))
ORDER BY advance.created_at DESC,advance.id DESC
LIMIT :limit
"""
        )
        return list(
            (
                await self.connection.execute(
                    statement,
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "employee_filter": employee_id if admin else None,
                        "status": status,
                        "start_period": start_period,
                        "cursor_id": cursor_id,
                        "limit": limit,
                    },
                )
            ).mappings()
        )

    async def get_advance(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        advance_id: uuid.UUID,
        *,
        admin: bool,
    ) -> RowMapping | None:
        projection = (
            _BASE_SELECT
            if admin
            else (
                "SELECT advance.*,employee.name AS employee_name "
                "FROM public.salary_advances AS advance "
                "JOIN public.employees AS employee ON employee.id=advance.employee_id "
                "AND employee.company_id=advance.company_id "
                "AND employee.branch_id=advance.branch_id "
            )
        )
        return (
            (
                await self.connection.execute(
                    text(
                        projection + " WHERE advance.id=:id AND advance.company_id=:company_id "
                        "AND advance.branch_id=:branch_id"
                    ),
                    {"id": advance_id, "company_id": company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_advance(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, advance_id: uuid.UUID
    ) -> RowMapping | None:
        locked = await self.connection.scalar(
            text("SELECT public.lock_salary_advance(:id)"), {"id": advance_id}
        )
        if locked is not True:
            return None
        return await self.get_advance(company_id, branch_id, advance_id, admin=True)

    async def lock_employee(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> bool:
        value = await self.connection.scalar(
            text(
                "SELECT id FROM public.employees WHERE id=:employee_id "
                "AND company_id=:company_id AND branch_id=:branch_id AND active "
                "AND employment_status IN ('Active','Probation','On Leave') FOR SHARE"
            ),
            {
                "employee_id": employee_id,
                "company_id": company_id,
                "branch_id": branch_id,
            },
        )
        return value is not None

    async def create_advance(
        self,
        *,
        advance_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        amount: str,
        reason: str,
        installment_count: int,
        repayment_start_month: date,
        monthly_installment: str,
    ) -> None:
        await self.connection.execute(
            text(
                """
INSERT INTO public.salary_advances(
  id,company_id,branch_id,employee_id,amount,repayment_start_month,reason,
  repayment_months,monthly_deduction,outstanding_balance,status)
VALUES(:id,:company_id,:branch_id,:employee_id,:amount,:start_month,:reason,
       :months,:monthly,:amount,'pending')
"""
            ),
            {
                "id": advance_id,
                "company_id": company_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
                "amount": amount,
                "start_month": repayment_start_month,
                "reason": reason,
                "months": installment_count,
                "monthly": monthly_installment,
            },
        )

    async def update_advance(self, advance_id: uuid.UUID, values: dict[str, object]) -> None:
        assignments = ",".join(f"{name}=:{name}" for name in values)
        await self.connection.execute(
            text(
                f"UPDATE public.salary_advances SET {assignments},"
                "updated_at=statement_timestamp() WHERE id=:id"
            ),
            {"id": advance_id, **values},
        )

    async def repayments(self, advance_id: uuid.UUID, *, admin: bool) -> list[RowMapping]:
        audit = (
            """
LEFT JOIN LATERAL (
  SELECT event.metadata->>'repayment_kind' AS repayment_kind
  FROM public.audit_events AS event
  WHERE event.entity_type='salary_advance' AND event.entity_id=repayment.advance_id
    AND event.action='salary_advance_repayment_recorded'
    AND event.metadata->>'repayment_id'=repayment.id::text
  ORDER BY event.occurred_at DESC,event.id DESC LIMIT 1
) AS repayment_audit ON true
"""
            if admin
            else ""
        )
        kind = "coalesce(repayment_audit.repayment_kind,'payroll')" if admin else "'payroll'"
        return list(
            (
                await self.connection.execute(
                    text(
                        f"""
SELECT repayment.*,payroll.period AS payroll_period,{kind} AS repayment_kind
FROM public.advance_repayments AS repayment
LEFT JOIN public.payroll_runs AS payroll ON payroll.id=repayment.payroll_run_id
{audit}
WHERE repayment.advance_id=:advance_id
ORDER BY repayment.paid_date,repayment.created_at,repayment.id
"""
                    ),
                    {"advance_id": advance_id},
                )
            ).mappings()
        )

    async def record_repayment(
        self,
        *,
        advance_id: uuid.UUID,
        payroll_run_id: uuid.UUID | None,
        idempotency_key: uuid.UUID,
        amount: str,
        paid_date: date,
    ) -> RowMapping:
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT public.record_advance_repayment("
                        ":advance_id,:payroll_run_id,:idempotency_key,:amount,:paid_date) AS result"
                    ),
                    {
                        "advance_id": advance_id,
                        "payroll_run_id": payroll_run_id,
                        "idempotency_key": idempotency_key,
                        "amount": amount,
                        "paid_date": paid_date,
                    },
                )
            )
            .mappings()
            .one()
        )
