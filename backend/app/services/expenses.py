from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.expenses import ExpenseRepository
from app.schemas.expense import (
    ExpenseCreateRequest,
    ExpenseDecisionRequest,
    ExpenseQueueResponse,
    ExpenseResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class ExpenseListQuery:
    limit: int = 50
    cursor: str | None = None
    status: str | None = None
    employee_id: uuid.UUID | None = None
    from_date: date | None = None
    to_date: date | None = None


@dataclass(frozen=True, slots=True)
class ExpenseCleanup:
    receipt_id: uuid.UUID
    operation_id: uuid.UUID
    object_key: str


def _same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        utc_value = value.astimezone(UTC)
        return utc_value.replace(microsecond=utc_value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


def _rejection_reason(row: RowMapping) -> str | None:
    if row["status"] == "manager_rejected":
        return row["manager_rejection_reason"] or None
    if row["status"] == "rejected":
        return row["rejection_reason"] or None
    return None


def _self_response(row: RowMapping) -> ExpenseResponse:
    return ExpenseResponse(
        id=row["id"],
        category=row["category"],
        amount=f"{row['amount']:.2f}",
        expense_date=row["expense_date"],
        description=row["description"],
        status=row["status"],
        rejection_reason=_rejection_reason(row),
        has_receipt=bool(row["has_receipt"]),
        payroll_period=row["payroll_period"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _queue_response(row: RowMapping, *, can_decide: bool, admin: bool) -> ExpenseQueueResponse:
    base = _self_response(row).model_dump()
    return ExpenseQueueResponse(
        **base,
        employee_id=row["employee_id"],
        employee_name=row["employee_name"],
        manager_decision_at=row["manager_approved_at"],
        admin_decision_at=row["approved_at"],
        can_decide=can_decide,
        manager_actor_name=row.get("manager_actor_name") if admin else None,
        admin_actor_name=row.get("admin_actor_name") if admin else None,
    )


class ExpenseService:
    def __init__(
        self,
        connection: AsyncConnection,
        cursor_codec: EmployeeCursorCodec,
    ) -> None:
        self.connection = connection
        self.repository = ExpenseRepository(connection)
        self.cursor_codec = cursor_codec

    def _decode(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: ExpenseListQuery,
    ) -> uuid.UUID | None:
        try:
            return self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None

    def _next(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: ExpenseListQuery,
        rows: list[RowMapping],
    ) -> str | None:
        if not rows:
            return None
        return self.cursor_codec.encode(
            principal=principal,
            branch_id=branch_id,
            operation_id=operation_id,
            query=query,
            last_id=rows[-1]["id"],
        )

    async def list_self(
        self, principal: AuthorizationPrincipal, query: ExpenseListQuery
    ) -> tuple[list[ExpenseResponse], str | None]:
        if principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}:
            raise ServiceExecutionError("operation_not_permitted")
        if (
            principal.branch_id is None
            or principal.employee_id is None
            or query.employee_id is not None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        cursor_id = self._decode(principal, principal.branch_id, "list_self_expenses", query)
        rows = await self.repository.list_claims(
            company_id=principal.company_id,
            branch_id=principal.branch_id,
            view="self",
            employee_id=principal.employee_id,
            actor_employee_id=principal.employee_id,
            status=query.status,
            from_date=query.from_date,
            to_date=query.to_date,
            cursor_id=cursor_id,
            limit=query.limit + 1,
        )
        visible = rows[: query.limit]
        next_cursor = (
            self._next(principal, principal.branch_id, "list_self_expenses", query, visible)
            if len(rows) > query.limit
            else None
        )
        return [_self_response(row) for row in visible], next_cursor

    async def list_queue(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: ExpenseListQuery,
        *,
        admin: bool,
    ) -> tuple[list[ExpenseQueueResponse], str | None]:
        required = AppRole.ADMIN if admin else AppRole.MANAGER
        if principal.role is not required or (not admin and principal.employee_id is None):
            raise ServiceExecutionError("operation_not_permitted")
        operation_id = "list_admin_expenses" if admin else "list_manager_expenses"
        cursor_id = self._decode(principal, branch_id, operation_id, query)
        rows = await self.repository.list_claims(
            company_id=principal.company_id,
            branch_id=branch_id,
            view="admin" if admin else "manager",
            employee_id=query.employee_id,
            actor_employee_id=principal.employee_id,
            status=query.status,
            from_date=query.from_date,
            to_date=query.to_date,
            cursor_id=cursor_id,
            limit=query.limit + 1,
        )
        visible = rows[: query.limit]
        responses: list[ExpenseQueueResponse] = []
        for row in visible:
            if admin:
                can_decide = (
                    row["status"]
                    in {
                        "pending",
                        "manager_approved",
                        "manager_rejected",
                        "rejected",
                    }
                    and row["employee_id"] != principal.employee_id
                )
                if row["manager_approved_by_app_user_id"] == principal.app_user_id:
                    can_decide = False
            else:
                can_decide = (
                    row["status"] == "pending" and row["employee_id"] != principal.employee_id
                )
            responses.append(_queue_response(row, can_decide=can_decide, admin=admin))
        next_cursor = (
            self._next(principal, branch_id, operation_id, query, visible)
            if len(rows) > query.limit
            else None
        )
        return responses, next_cursor

    async def create(
        self, principal: AuthorizationPrincipal, request: ExpenseCreateRequest
    ) -> ExpenseResponse:
        if (
            principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}
            or principal.employee_id is None
            or principal.branch_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        if request.expense_date > await self.repository.business_date():
            raise ServiceExecutionError("validation_failed")
        claim_id = uuid.uuid4()
        await self.repository.create_claim(
            claim_id=claim_id,
            company_id=principal.company_id,
            branch_id=principal.branch_id,
            employee_id=principal.employee_id,
            category=request.category,
            amount=request.amount,
            expense_date=request.expense_date,
            description=request.description,
        )
        if request.receipt_id is not None and not await self.repository.bind_receipt(
            receipt_id=request.receipt_id,
            claim_id=claim_id,
            company_id=principal.company_id,
            branch_id=principal.branch_id,
            employee_id=principal.employee_id,
        ):
            raise ServiceExecutionError("resource_not_found")
        row = await self.repository.get_claim(principal.company_id, principal.branch_id, claim_id)
        if row is None:
            raise RuntimeError("created expense claim is not visible")
        return _self_response(row)

    async def decide(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        claim_id: uuid.UUID,
        request: ExpenseDecisionRequest,
        *,
        stage: Literal["manager", "admin"],
        approve: bool,
    ) -> ExpenseQueueResponse:
        if stage == "manager":
            if principal.role is not AppRole.MANAGER or principal.employee_id is None:
                raise ServiceExecutionError("operation_not_permitted")
        elif principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        row = await self.repository.lock_claim(principal.company_id, branch_id, claim_id)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        if not _same_version(row["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("stale_financial_state")
        if row["employee_id"] == principal.employee_id:
            raise ServiceExecutionError("resource_not_found")

        old_status = row["status"]
        if stage == "manager":
            assert principal.employee_id is not None
            if (
                not await self.repository.is_current_direct_report(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    manager_employee_id=principal.employee_id,
                    employee_id=row["employee_id"],
                    lock=True,
                )
                or old_status != "pending"
            ):
                raise ServiceExecutionError("resource_not_found")
            if approve and request.reason is not None:
                raise ServiceExecutionError("validation_failed")
            if not approve and request.reason is None:
                raise ServiceExecutionError("validation_failed")
            new_status = "manager_approved" if approve else "manager_rejected"
            values: dict[str, object] = {
                "status": new_status,
                "manager_approved_by_app_user_id": principal.app_user_id,
                "manager_approved_at": datetime.now(UTC),
                "manager_rejection_reason": "" if approve else request.reason or "",
            }
        else:
            if row["manager_approved_by_app_user_id"] == principal.app_user_id:
                raise ServiceExecutionError("resource_not_found")
            if approve:
                if old_status not in {
                    "pending",
                    "manager_approved",
                    "manager_rejected",
                    "rejected",
                }:
                    raise ServiceExecutionError("stale_financial_state")
                if old_status == "manager_rejected" and request.reason is None:
                    raise ServiceExecutionError("validation_failed")
                new_status = "approved"
                values = {
                    "status": new_status,
                    "approved_by_app_user_id": principal.app_user_id,
                    "approved_at": datetime.now(UTC),
                    "rejection_reason": "",
                }
            else:
                if old_status not in {"pending", "manager_approved"}:
                    raise ServiceExecutionError("stale_financial_state")
                if request.reason is None:
                    raise ServiceExecutionError("validation_failed")
                new_status = "rejected"
                values = {
                    "status": new_status,
                    "approved_by_app_user_id": principal.app_user_id,
                    "approved_at": datetime.now(UTC),
                    "rejection_reason": request.reason,
                }
        await self.repository.update_decision(claim_id, values)
        action = "expense_approved" if approve else "expense_rejected"
        changed = ["status"]
        if stage == "admin" and approve:
            changed += ["approved_by_app_user_id", "approved_at"]
        if stage == "admin" and not approve:
            changed += ["rejection_reason"]
        metadata: dict[str, str] = {"transition": f"{old_status}_to_{new_status}"}
        if stage == "admin" and old_status == "manager_rejected":
            metadata["override_reason"] = request.reason or ""
        await append_audit_event(
            self.connection,
            action=action,
            entity_type="expense_claim",
            entity_id=claim_id,
            changed_fields=changed,
            reason=request.reason
            or ("Expense approved by manager" if stage == "manager" else "Expense approved"),
            metadata=metadata,
        )
        current = await self.repository.get_claim(principal.company_id, branch_id, claim_id)
        if current is None:
            raise RuntimeError("decided expense claim is not visible")
        return _queue_response(current, can_decide=False, admin=stage == "admin")

    async def delete(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        claim_id: uuid.UUID,
        expected_updated_at: datetime,
        *,
        admin: bool,
    ) -> ExpenseCleanup | None:
        if admin:
            if principal.role is not AppRole.ADMIN:
                raise ServiceExecutionError("operation_not_permitted")
        elif principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}:
            raise ServiceExecutionError("operation_not_permitted")
        row = await self.repository.lock_claim(principal.company_id, branch_id, claim_id)
        if row is None or (not admin and row["employee_id"] != principal.employee_id):
            raise ServiceExecutionError("resource_not_found")
        if not _same_version(row["updated_at"], expected_updated_at):
            raise ServiceExecutionError("stale_financial_state")
        if (
            row["status"] not in {"pending", "manager_rejected", "rejected"}
            or row["payroll_run_id"] is not None
        ):
            raise ServiceExecutionError("stale_financial_state")
        claimed = await self.repository.request_receipt_cleanup(
            claim=row, actor_id=principal.app_user_id, trigger="claim_deleted"
        )
        cleanup = None
        if claimed is not None:
            receipt_id, operation_id, object_key = claimed
            await append_audit_event(
                self.connection,
                action="expense_receipt_cleanup_requested",
                entity_type="expense_receipt",
                entity_id=receipt_id,
                changed_fields=["status"],
                reason="Expense receipt cleanup requested",
                metadata={"storage_operation_id": str(operation_id), "trigger": "claim_deleted"},
            )
            cleanup = ExpenseCleanup(receipt_id, operation_id, object_key)
        await self.repository.delete_claim(claim_id)
        return cleanup

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "expense_claim" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        row = await self.repository.get_claim(principal.company_id, branch_id, resource_id)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        if principal.role is not AppRole.ADMIN and row["employee_id"] != principal.employee_id:
            if principal.role is not AppRole.MANAGER or principal.employee_id is None:
                raise ServiceExecutionError("resource_not_found")
            if not await self.repository.is_current_direct_report(
                company_id=principal.company_id,
                branch_id=branch_id,
                manager_employee_id=principal.employee_id,
                employee_id=row["employee_id"],
            ):
                raise ServiceExecutionError("resource_not_found")
