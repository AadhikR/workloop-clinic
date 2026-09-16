from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection


class ExpenseRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.execute(text("SELECT public.workloop_business_date()"))
        ).scalar_one()

    async def list_claims(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        view: Literal["self", "manager", "admin"],
        employee_id: uuid.UUID | None,
        actor_employee_id: uuid.UUID | None,
        status: str | None,
        from_date: date | None,
        to_date: date | None,
        cursor_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        if view == "self":
            scope = "claim.employee_id=:employee_id"
            order = "claim.expense_date DESC,claim.created_at DESC,claim.id DESC"
            cursor = """
AND (CAST(:cursor_id AS uuid) IS NULL OR (claim.expense_date,claim.created_at,claim.id)<(
  SELECT expense_date,created_at,id FROM public.expense_claims
  WHERE id=:cursor_id AND company_id=:company_id AND branch_id=:branch_id))
"""
        elif view == "manager":
            scope = """
employee.reporting_manager_id=:actor_employee_id
AND employee.id<>:actor_employee_id
AND employee.active AND employee.employment_status IN ('Active','Probation','On Leave')
"""
            order = "claim.created_at ASC,claim.id ASC"
            cursor = """
AND (CAST(:cursor_id AS uuid) IS NULL OR (claim.created_at,claim.id)>(
  SELECT created_at,id FROM public.expense_claims
  WHERE id=:cursor_id AND company_id=:company_id AND branch_id=:branch_id))
"""
        else:
            scope = "true"
            order = "claim.expense_date DESC,claim.id DESC"
            cursor = """
AND (CAST(:cursor_id AS uuid) IS NULL OR (claim.expense_date,claim.id)<(
  SELECT expense_date,id FROM public.expense_claims
  WHERE id=:cursor_id AND company_id=:company_id AND branch_id=:branch_id))
"""
        default_manager_status = (
            "AND claim.status='pending'" if view == "manager" and status is None else ""
        )
        statement = text(
            f"""
SELECT claim.*,employee.name AS employee_name,
       receipt.id IS NOT NULL AS has_receipt,payroll.period AS payroll_period,
       manager_employee.name AS manager_actor_name,
       admin_employee.name AS admin_actor_name
FROM public.expense_claims AS claim
JOIN public.employees AS employee
  ON employee.id=claim.employee_id AND employee.company_id=claim.company_id
 AND employee.branch_id=claim.branch_id
LEFT JOIN public.expense_receipts AS receipt
  ON receipt.expense_claim_id=claim.id AND receipt.status='attached'
LEFT JOIN public.payroll_runs AS payroll ON payroll.id=claim.payroll_run_id
LEFT JOIN public.user_profiles AS manager_profile
  ON manager_profile.app_user_id=claim.manager_approved_by_app_user_id
LEFT JOIN public.employees AS manager_employee ON manager_employee.id=manager_profile.employee_id
LEFT JOIN public.user_profiles AS admin_profile
  ON admin_profile.app_user_id=claim.approved_by_app_user_id
LEFT JOIN public.employees AS admin_employee ON admin_employee.id=admin_profile.employee_id
WHERE claim.company_id=:company_id AND claim.branch_id=:branch_id AND {scope}
  AND (CAST(:employee_id AS uuid) IS NULL OR claim.employee_id=CAST(:employee_id AS uuid))
  AND (CAST(:status AS text) IS NULL OR claim.status=CAST(:status AS text))
  {default_manager_status}
  AND (CAST(:from_date AS date) IS NULL OR claim.expense_date>=CAST(:from_date AS date))
  AND (CAST(:to_date AS date) IS NULL OR claim.expense_date<=CAST(:to_date AS date))
  {cursor}
ORDER BY {order}
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
                        "actor_employee_id": actor_employee_id,
                        "status": status,
                        "from_date": from_date,
                        "to_date": to_date,
                        "cursor_id": cursor_id,
                        "limit": limit,
                    },
                )
            ).mappings()
        )

    async def create_claim(
        self,
        *,
        claim_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        category: str,
        amount: str,
        expense_date: date,
        description: str,
    ) -> None:
        await self.connection.execute(
            text(
                """
INSERT INTO public.expense_claims(
  id,company_id,branch_id,employee_id,category,amount,expense_date,description,receipt_url,status)
VALUES(:id,:company_id,:branch_id,:employee_id,:category,:amount,:expense_date,:description,'','pending')
"""
            ),
            {
                "id": claim_id,
                "company_id": company_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
                "category": category,
                "amount": amount,
                "expense_date": expense_date,
                "description": description,
            },
        )

    async def lock_claim(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, claim_id: uuid.UUID
    ) -> RowMapping | None:
        locked = await self.connection.scalar(
            text("SELECT public.lock_expense_claim(:id)"), {"id": claim_id}
        )
        if locked is not True:
            return None
        return (
            (
                await self.connection.execute(
                    text(
                        """
SELECT claim.*,employee.name AS employee_name,
       receipt.id AS receipt_id,receipt.object_key AS receipt_object_key,
       receipt.created_by_app_user_id AS receipt_creator_id,
       receipt.status AS receipt_status,
       payroll.period AS payroll_period
FROM public.expense_claims AS claim
JOIN public.employees AS employee
  ON employee.id=claim.employee_id AND employee.company_id=claim.company_id
 AND employee.branch_id=claim.branch_id
LEFT JOIN public.expense_receipts AS receipt ON receipt.expense_claim_id=claim.id
LEFT JOIN public.payroll_runs AS payroll ON payroll.id=claim.payroll_run_id
WHERE claim.id=:id AND claim.company_id=:company_id AND claim.branch_id=:branch_id
"""
                    ),
                    {"id": claim_id, "company_id": company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def get_claim(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, claim_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    text(
                        """
SELECT claim.*,employee.name AS employee_name,
       receipt.id IS NOT NULL AS has_receipt,payroll.period AS payroll_period,
       manager_employee.name AS manager_actor_name,
       admin_employee.name AS admin_actor_name
FROM public.expense_claims AS claim
JOIN public.employees AS employee
  ON employee.id=claim.employee_id AND employee.company_id=claim.company_id
 AND employee.branch_id=claim.branch_id
LEFT JOIN public.expense_receipts AS receipt
  ON receipt.expense_claim_id=claim.id AND receipt.status='attached'
LEFT JOIN public.payroll_runs AS payroll ON payroll.id=claim.payroll_run_id
LEFT JOIN public.user_profiles AS manager_profile
  ON manager_profile.app_user_id=claim.manager_approved_by_app_user_id
LEFT JOIN public.employees AS manager_employee ON manager_employee.id=manager_profile.employee_id
LEFT JOIN public.user_profiles AS admin_profile
  ON admin_profile.app_user_id=claim.approved_by_app_user_id
LEFT JOIN public.employees AS admin_employee ON admin_employee.id=admin_profile.employee_id
WHERE claim.id=:id AND claim.company_id=:company_id AND claim.branch_id=:branch_id
"""
                    ),
                    {"id": claim_id, "company_id": company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )

    async def bind_receipt(
        self,
        *,
        receipt_id: uuid.UUID,
        claim_id: uuid.UUID,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> bool:
        result = await self.connection.execute(
            text(
                """
UPDATE public.expense_receipts
SET expense_claim_id=:claim_id,status='attached',expires_at=NULL,
    attached_at=statement_timestamp(),updated_at=statement_timestamp()
WHERE id=:receipt_id AND company_id=:company_id AND branch_id=:branch_id
  AND employee_id=:employee_id AND status='staged' AND expires_at>statement_timestamp()
  AND expense_claim_id IS NULL
"""
            ),
            {
                "receipt_id": receipt_id,
                "claim_id": claim_id,
                "company_id": company_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
            },
        )
        return result.rowcount == 1

    async def update_decision(self, claim_id: uuid.UUID, values: dict[str, object]) -> None:
        assignments = ",".join(f"{name}=:{name}" for name in values)
        await self.connection.execute(
            text(
                "UPDATE public.expense_claims "
                f"SET {assignments},updated_at=statement_timestamp() WHERE id=:id"
            ),
            {"id": claim_id, **values},
        )

    async def is_current_direct_report(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        manager_employee_id: uuid.UUID,
        employee_id: uuid.UUID,
        lock: bool = False,
    ) -> bool:
        if lock:
            return bool(
                await self.connection.scalar(
                    text(
                        "SELECT public.workloop_employee_id()=:manager_id "
                        "AND public.lock_expense_direct_report(:employee_id)"
                    ),
                    {"manager_id": manager_employee_id, "employee_id": employee_id},
                )
            )
        suffix = " FOR UPDATE" if lock else ""
        value = (
            await self.connection.execute(
                text(
                    """
SELECT id FROM public.employees
WHERE id=:employee_id AND company_id=:company_id AND branch_id=:branch_id
  AND reporting_manager_id=:manager_id AND id<>:manager_id
  AND active AND employment_status IN ('Active','Probation','On Leave')
"""
                    + suffix
                ),
                {
                    "employee_id": employee_id,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "manager_id": manager_employee_id,
                },
            )
        ).scalar_one_or_none()
        return value is not None

    async def request_receipt_cleanup(
        self, *, claim: RowMapping, actor_id: uuid.UUID, trigger: str
    ) -> tuple[uuid.UUID, uuid.UUID, str] | None:
        if claim["receipt_id"] is None or claim["receipt_status"] not in {"staged", "attached"}:
            return None
        receipt_id = claim["receipt_id"]
        object_key = claim["receipt_object_key"]
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
                    "company_id": claim["company_id"],
                    "branch_id": claim["branch_id"],
                    "employee_id": claim["employee_id"],
                    "creator": actor_id,
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
        return receipt_id, operation_id, object_key

    async def delete_claim(self, claim_id: uuid.UUID) -> None:
        await self.connection.execute(
            text("DELETE FROM public.expense_claims WHERE id=:id"), {"id": claim_id}
        )
