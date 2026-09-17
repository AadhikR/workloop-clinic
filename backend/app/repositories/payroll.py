from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


class PayrollRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()

    async def lock_branch(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,default_bank_routing_code,default_salary_day "
                        "FROM public.branches "
                        "WHERE id=:branch_id AND company_id=:company_id FOR UPDATE"
                    ),
                    {"company_id": company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def list_runs(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str | None,
        run_status: str | None,
        approval_status: str | None,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT run.* FROM public.payroll_runs AS run
WHERE run.company_id=:company_id AND run.branch_id=:branch_id
  AND (CAST(:period AS text) IS NULL OR run.period=CAST(:period AS text))
  AND (CAST(:run_status AS text) IS NULL OR run.status=CAST(:run_status AS text))
  AND (CAST(:approval_status AS text) IS NULL
       OR run.approval_status=CAST(:approval_status AS text))
  AND (CAST(:cursor_id AS uuid) IS NULL OR (run.period,run.sequence_no,run.id)<(
    SELECT anchor.period,anchor.sequence_no,anchor.id FROM public.payroll_runs AS anchor
    WHERE anchor.id=CAST(:cursor_id AS uuid) AND anchor.company_id=:company_id
      AND anchor.branch_id=:branch_id))
ORDER BY run.period DESC,run.sequence_no DESC,run.id DESC
LIMIT :limit
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "period": period,
                        "run_status": run_status,
                        "approval_status": approval_status,
                        "cursor_id": cursor_id,
                        "limit": limit,
                    },
                )
            ).mappings()
        )

    async def get_run(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT * FROM public.payroll_runs WHERE id=:id AND company_id=:company_id "
                        "AND branch_id=:branch_id"
                    ),
                    {"id": run_id, "company_id": company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def get_run_for_action(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> RowMapping | None:
        await self.connection.execute(text("SELECT public.lock_payroll_run(:id)"), {"id": run_id})
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT * FROM public.payroll_runs WHERE id=:id AND company_id=:company_id "
                        "AND branch_id=:branch_id"
                    ),
                    {"id": run_id, "company_id": company_id, "branch_id": branch_id},
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
SELECT entry.*,employee.name AS employee_name
FROM public.payroll_entries AS entry
JOIN public.employees AS employee
  ON employee.id=entry.employee_id AND employee.company_id=entry.company_id
 AND employee.branch_id=entry.branch_id
WHERE entry.payroll_run_id=:run_id
ORDER BY employee.name,entry.employee_id
"""
                    ),
                    {"run_id": run_id},
                )
            ).mappings()
        )

    async def approval_history(self, run_id: uuid.UUID) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT history.id,history.action,history.notes,history.created_at,
       'Administrator' AS actor_name
FROM public.payroll_approval_log AS history
WHERE history.payroll_run_id=:run_id
ORDER BY history.created_at,history.id
"""
                    ),
                    {"run_id": run_id},
                )
            ).mappings()
        )

    async def list_self_payslips(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT slip.* FROM public.payslips AS slip
WHERE slip.company_id=:company_id AND slip.branch_id=:branch_id
  AND slip.employee_id=:employee_id
  AND (CAST(:cursor_id AS uuid) IS NULL OR (slip.period,slip.id)<(
    SELECT anchor.period,anchor.id FROM public.payslips AS anchor
    WHERE anchor.id=CAST(:cursor_id AS uuid) AND anchor.company_id=:company_id
      AND anchor.branch_id=:branch_id AND anchor.employee_id=:employee_id))
ORDER BY slip.period DESC,slip.id DESC
LIMIT :limit
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                        "cursor_id": cursor_id,
                        "limit": limit,
                    },
                )
            ).mappings()
        )

    async def get_self_payslip(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        payslip_id: uuid.UUID,
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    text(
                        "SELECT * FROM public.payslips WHERE id=:id AND company_id=:company_id "
                        "AND branch_id=:branch_id AND employee_id=:employee_id"
                    ),
                    {
                        "id": payslip_id,
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "employee_id": employee_id,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )

    async def transition(
        self,
        run_id: uuid.UUID,
        action: str,
        reason: str,
        expected_updated_at: object,
    ) -> None:
        await self.connection.execute(
            text(
                "SELECT public.transition_payroll_run(:run_id,:action,:reason,:expected_updated_at)"
            ),
            {
                "run_id": run_id,
                "action": action,
                "reason": reason,
                "expected_updated_at": expected_updated_at,
            },
        )

    async def insert_payslip(
        self,
        *,
        payslip_id: uuid.UUID,
        run: RowMapping,
        employee_id: uuid.UUID,
        gross_pay: Decimal,
        net_pay: Decimal,
        snapshot: dict[str, object],
    ) -> None:
        await self.connection.execute(
            text(
                """
INSERT INTO public.payslips(
 id,company_id,branch_id,payroll_run_id,employee_id,period,payment_date,
 gross_pay,net_pay,data_snapshot)
VALUES(:id,:company_id,:branch_id,:run_id,:employee_id,:period,:payment_date,
 :gross_pay,:net_pay,CAST(:snapshot AS jsonb))
"""
            ),
            {
                "id": payslip_id,
                "company_id": run["company_id"],
                "branch_id": run["branch_id"],
                "run_id": run["id"],
                "employee_id": employee_id,
                "period": run["period"],
                "payment_date": run["payment_date"],
                "gross_pay": gross_pay,
                "net_pay": net_pay,
                "snapshot": json.dumps(snapshot, sort_keys=True),
            },
        )

    async def pay_expense(self, expense_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        return (
            await self.connection.execute(
                text(
                    "UPDATE public.expense_claims SET status='paid',payroll_run_id=:run_id,"
                    "updated_at=statement_timestamp() WHERE id=:expense_id AND status='approved' "
                    "AND payroll_run_id IS NULL RETURNING id"
                ),
                {"expense_id": expense_id, "run_id": run_id},
            )
        ).scalar_one_or_none() is not None

    async def record_advance_repayment(
        self,
        *,
        advance_id: uuid.UUID,
        run_id: uuid.UUID,
        repayment_key: uuid.UUID,
        amount: Decimal,
        paid_date: date,
    ) -> dict[str, object]:
        result = await self.connection.scalar(
            text(
                "SELECT public.record_advance_repayment("
                ":advance_id,:run_id,:repayment_key,:amount,:paid_date)"
            ),
            {
                "advance_id": advance_id,
                "run_id": run_id,
                "repayment_key": repayment_key,
                "amount": amount,
                "paid_date": paid_date,
            },
        )
        return dict(result)

    async def generate(
        self,
        run_id: uuid.UUID,
        *,
        total: Decimal,
        count: int,
        expected_updated_at: object,
    ) -> None:
        await self.connection.execute(
            text("SELECT public.finalize_payroll_run(:run_id,:total,:count,:expected_updated_at)"),
            {
                "run_id": run_id,
                "total": total,
                "count": count,
                "expected_updated_at": expected_updated_at,
            },
        )

    async def eligible_employees(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT id,name,basic_salary,housing_allowance,transport_allowance,allowance,
       employment_start_date,termination_date,updated_at
FROM public.employees
WHERE company_id=:company_id AND branch_id=:branch_id
  AND (employment_start_date IS NULL OR employment_start_date<=:period_end)
  AND (termination_date IS NULL OR termination_date>=:period_start)
  AND employment_status IN ('Active','Probation','On Leave','Terminated')
ORDER BY name,id
FOR SHARE
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "period_start": period_start,
                        "period_end": period_end,
                    },
                )
            ).mappings()
        )

    async def lock_leave_inputs(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT request.id AS source_id,request.employee_id,request.start_date,request.end_date,
       request.days_requested,request.is_half_day,request.updated_at AS request_updated_at,
       leave_type.code AS leave_type_code,leave_type.updated_at AS leave_type_updated_at
FROM public.leave_requests AS request
JOIN public.leave_types AS leave_type
  ON leave_type.id=request.leave_type_id AND leave_type.company_id=request.company_id
 AND leave_type.branch_id=request.branch_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
  AND request.status='Approved' AND leave_type.affects_payroll
  AND request.start_date<=:period_end AND request.end_date>=:period_start
ORDER BY request.employee_id,request.start_date,request.id
FOR UPDATE OF request
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "period_start": period_start,
                        "period_end": period_end,
                    },
                )
            ).mappings()
        )

    async def attendance_input_projection(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> list[RowMapping] | None:
        del company_id, branch_id, period
        return None

    async def roster_input_projection(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID, period: str
    ) -> list[RowMapping] | None:
        del company_id, branch_id, period
        return None

    async def lock_expense_inputs(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period_start: date,
        period_end: date,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT claim.id AS source_id,claim.employee_id,claim.amount,claim.expense_date,
       claim.updated_at AS source_version
FROM public.expense_claims AS claim
WHERE claim.company_id=:company_id AND claim.branch_id=:branch_id
  AND claim.status='approved' AND claim.payroll_run_id IS NULL
  AND claim.expense_date BETWEEN :period_start AND :period_end
ORDER BY claim.employee_id,claim.expense_date,claim.id
FOR UPDATE OF claim
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "period_start": period_start,
                        "period_end": period_end,
                    },
                )
            ).mappings()
        )

    async def lock_advance_inputs(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period_start: date,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT advance.id AS source_id,advance.employee_id,advance.amount,
       advance.repayment_start_month,advance.repayment_months,
       advance.monthly_deduction,advance.outstanding_balance,
       advance.created_at,advance.updated_at AS source_version
FROM public.salary_advances AS advance
WHERE advance.company_id=:company_id AND advance.branch_id=:branch_id
  AND advance.status='active' AND advance.outstanding_balance>0
  AND advance.repayment_start_month<=:period_start
ORDER BY advance.employee_id,advance.repayment_start_month,advance.created_at,advance.id
FOR UPDATE OF advance
"""
                    ),
                    {
                        "company_id": company_id,
                        "branch_id": branch_id,
                        "period_start": period_start,
                    },
                )
            ).mappings()
        )

    async def create_run(
        self,
        *,
        run_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        period: str,
        payment_date: date,
        sequence: str,
        routing_code: str,
        actor_id: uuid.UUID,
    ) -> None:
        await self.connection.execute(
            text(
                """
INSERT INTO public.payroll_runs(
  id,company_id,branch_id,period,payment_date,sequence_no,scr_bank_routing_code,
  description,status,run_by_app_user_id,approval_status)
VALUES(:id,:company_id,:branch_id,:period,:payment_date,:sequence,:routing_code,
       :description,'draft',:actor_id,'draft')
"""
            ),
            {
                "id": run_id,
                "company_id": company_id,
                "branch_id": branch_id,
                "period": period,
                "payment_date": payment_date,
                "sequence": sequence,
                "routing_code": routing_code,
                "description": f"Salary for {period}",
                "actor_id": actor_id,
            },
        )

    async def replace_entries(self, run_id: uuid.UUID, entries: list[dict[str, object]]) -> None:
        await self.connection.execute(
            text("SELECT public.replace_payroll_entries(:run_id,CAST(:entries AS jsonb))"),
            {"run_id": run_id, "entries": json.dumps(entries, sort_keys=True)},
        )

    async def delete_run(self, run_id: uuid.UUID) -> bool:
        return (
            await self.connection.execute(
                text(
                    "DELETE FROM public.payroll_runs WHERE id=:run_id AND status='draft' "
                    "AND approval_status='draft' RETURNING id"
                ),
                {"run_id": run_id},
            )
        ).scalar_one_or_none() is not None

    async def replay_visible(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> bool:
        if await self.get_run(company_id, branch_id, run_id) is not None:
            return True
        return bool(
            await self.connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM public.audit_events "
                    "WHERE entity_type='payroll_run' "
                    "AND entity_id=:run_id AND company_id=:company_id AND branch_id=:branch_id "
                    "AND action='payroll_draft_deleted')"
                ),
                {"run_id": run_id, "company_id": company_id, "branch_id": branch_id},
            )
        )
