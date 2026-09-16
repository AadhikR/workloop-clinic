from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.advances import AdvanceRepository
from app.schemas.advance import (
    AdminAdvanceCreateRequest,
    AdvanceAdminResponse,
    AdvanceCreateRequest,
    AdvanceDecisionRequest,
    AdvanceRepaymentRequest,
    AdvanceRepaymentResponse,
    AdvanceResponse,
    AdvanceScheduleRequest,
    AdvanceScheduleRow,
    AdvanceVersionRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError

CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class AdvanceListQuery:
    limit: int = 50
    cursor: str | None = None
    status: str | None = None
    employee_id: uuid.UUID | None = None
    start_period: str | None = None


def _money(value: Decimal | str) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def monthly_installment(amount: Decimal | str, count: int) -> Decimal:
    return (_money(amount) / Decimal(count)).quantize(CENT, rounding=ROUND_HALF_UP)


def _period_date(period: str) -> date:
    year, month = (int(part) for part in period.split("-"))
    return date(year, month, 1)


def _period(value: date) -> str:
    return value.strftime("%Y-%m")


def _add_months(value: date, count: int) -> date:
    index = value.year * 12 + value.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def _same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        utc_value = value.astimezone(UTC)
        return utc_value.replace(microsecond=utc_value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


def schedule_values(amount: Decimal, count: int) -> list[Decimal]:
    monthly = monthly_installment(amount, count)
    remaining = amount
    values: list[Decimal] = []
    for index in range(count):
        installment = remaining if index == count - 1 else min(monthly, remaining)
        installment = _money(installment)
        values.append(installment)
        remaining = _money(remaining - installment)
    return values


def build_schedule(
    row: RowMapping,
    repayments: list[RowMapping],
    business_period: str,
) -> list[AdvanceScheduleRow]:
    paid = sum((_money(item["amount"]) for item in repayments), Decimal("0.00"))
    remaining_paid = paid
    result: list[AdvanceScheduleRow] = []
    start = row["repayment_start_month"]
    for index, amount in enumerate(schedule_values(_money(row["amount"]), row["repayment_months"])):
        applied = min(amount, remaining_paid)
        remaining_paid = _money(remaining_paid - applied)
        remaining = _money(amount - applied)
        installment_period = _period(_add_months(start, index))
        if remaining == 0:
            status = "paid"
        elif applied > 0:
            status = "partial"
        elif installment_period <= business_period:
            status = "due"
        else:
            status = "upcoming"
        result.append(
            AdvanceScheduleRow(
                period=installment_period,
                scheduled_amount=f"{amount:.2f}",
                paid_amount=f"{applied:.2f}",
                remaining_amount=f"{remaining:.2f}",
                status=status,
            )
        )
    return result


def _repayment_response(row: RowMapping) -> AdvanceRepaymentResponse:
    kind = row["repayment_kind"]
    if kind not in {"manual", "payroll", "settlement"}:
        kind = "payroll"
    return AdvanceRepaymentResponse(
        id=row["id"],
        amount=f"{row['amount']:.2f}",
        paid_date=row["paid_date"],
        payroll_run_id=row["payroll_run_id"],
        payroll_period=row["payroll_period"],
        repayment_kind=kind,
        created_at=row["created_at"],
    )


def _self_response(row: RowMapping, schedule: list[AdvanceScheduleRow]) -> AdvanceResponse:
    next_period = next(
        (item.period for item in schedule if item.status in {"partial", "due", "upcoming"}),
        None,
    )
    if row["status"] in {"settled", "cancelled"}:
        next_period = None
    return AdvanceResponse(
        id=row["id"],
        amount=f"{row['amount']:.2f}",
        reason=row["reason"],
        status=row["status"],
        repayment_start_period=_period(row["repayment_start_month"]),
        installment_count=row["repayment_months"],
        monthly_installment=f"{row['monthly_deduction']:.2f}",
        outstanding_balance=f"{row['outstanding_balance']:.2f}",
        next_repayment_period=next_period,
        rejection_reason=row["rejection_reason"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _admin_response(
    row: RowMapping,
    schedule: list[AdvanceScheduleRow],
    repayments: list[RowMapping],
    *,
    actor_id: uuid.UUID,
    actor_employee_id: uuid.UUID | None,
) -> AdvanceAdminResponse:
    base = _self_response(row, schedule).model_dump()
    return AdvanceAdminResponse(
        **base,
        employee_id=row["employee_id"],
        employee_name=row["employee_name"],
        creator_name=row["creator_name"],
        decision_actor_name=row["decision_actor_name"],
        disbursed_date=row["disbursed_date"],
        can_decide=(
            row["status"] == "pending"
            and row["creator_app_user_id"] != actor_id
            and row["employee_id"] != actor_employee_id
        ),
        schedule=schedule,
        repayments=[_repayment_response(item) for item in repayments],
    )


class AdvanceService:
    def __init__(self, connection: AsyncConnection, cursor_codec: EmployeeCursorCodec) -> None:
        self.connection = connection
        self.repository = AdvanceRepository(connection)
        self.cursor_codec = cursor_codec

    def _decode(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: AdvanceListQuery,
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
        query: AdvanceListQuery,
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

    async def _schedule_for(
        self, row: RowMapping, *, admin: bool
    ) -> tuple[list[AdvanceScheduleRow], list[RowMapping]]:
        repayments = await self.repository.repayments(row["id"], admin=admin)
        business_period = _period(await self.repository.business_date())
        return build_schedule(row, repayments, business_period), repayments

    async def list_self(
        self, principal: AuthorizationPrincipal, query: AdvanceListQuery
    ) -> tuple[list[AdvanceResponse], str | None]:
        if (
            principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}
            or principal.employee_id is None
            or principal.branch_id is None
            or query.employee_id is not None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        operation_id = "list_self_advances"
        cursor_id = self._decode(principal, principal.branch_id, operation_id, query)
        rows = await self.repository.list_advances(
            company_id=principal.company_id,
            branch_id=principal.branch_id,
            employee_id=principal.employee_id,
            status=query.status,
            start_period=query.start_period,
            cursor_id=cursor_id,
            limit=query.limit + 1,
            admin=False,
        )
        visible = rows[: query.limit]
        responses: list[AdvanceResponse] = []
        for row in visible:
            schedule, _ = await self._schedule_for(row, admin=False)
            responses.append(_self_response(row, schedule))
        next_cursor = (
            self._next(principal, principal.branch_id, operation_id, query, visible)
            if len(rows) > query.limit
            else None
        )
        return responses, next_cursor

    async def list_admin(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: AdvanceListQuery,
    ) -> tuple[list[AdvanceAdminResponse], str | None]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        operation_id = "list_admin_advances"
        cursor_id = self._decode(principal, branch_id, operation_id, query)
        rows = await self.repository.list_advances(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=query.employee_id,
            status=query.status,
            start_period=query.start_period,
            cursor_id=cursor_id,
            limit=query.limit + 1,
            admin=True,
        )
        visible = rows[: query.limit]
        responses: list[AdvanceAdminResponse] = []
        for row in visible:
            schedule, repayments = await self._schedule_for(row, admin=True)
            responses.append(
                _admin_response(
                    row,
                    schedule,
                    repayments,
                    actor_id=principal.app_user_id,
                    actor_employee_id=principal.employee_id,
                )
            )
        next_cursor = (
            self._next(principal, branch_id, operation_id, query, visible)
            if len(rows) > query.limit
            else None
        )
        return responses, next_cursor

    async def _validate_start(self, value: str) -> date:
        start = _period_date(value)
        current = (await self.repository.business_date()).replace(day=1)
        if start < current or start > _add_months(current, 120):
            raise ServiceExecutionError("validation_failed")
        return start

    async def create(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: AdvanceCreateRequest | AdminAdvanceCreateRequest,
        *,
        admin: bool,
    ) -> AdvanceResponse | AdvanceAdminResponse:
        if admin:
            if principal.role is not AppRole.ADMIN or not isinstance(
                request, AdminAdvanceCreateRequest
            ):
                raise ServiceExecutionError("operation_not_permitted")
            employee_id = request.employee_id
        else:
            if (
                principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}
                or principal.employee_id is None
                or principal.branch_id != branch_id
                or isinstance(request, AdminAdvanceCreateRequest)
            ):
                raise ServiceExecutionError("operation_not_permitted")
            employee_id = principal.employee_id
        if not await self.repository.lock_employee(principal.company_id, branch_id, employee_id):
            raise ServiceExecutionError("resource_not_found")
        start = await self._validate_start(request.repayment_start_period)
        amount = _money(request.amount)
        monthly = monthly_installment(amount, request.installment_count)
        advance_id = uuid.uuid4()
        await self.repository.create_advance(
            advance_id=advance_id,
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            amount=f"{amount:.2f}",
            reason=request.reason,
            installment_count=request.installment_count,
            repayment_start_month=start,
            monthly_installment=f"{monthly:.2f}",
        )
        await append_audit_event(
            self.connection,
            action="salary_advance_requested",
            entity_type="salary_advance",
            entity_id=advance_id,
            changed_fields=[
                "amount",
                "reason",
                "repayment_months",
                "repayment_start_month",
                "monthly_deduction",
                "outstanding_balance",
                "status",
            ],
            reason="Salary advance requested",
        )
        row = await self.repository.get_advance(
            principal.company_id, branch_id, advance_id, admin=admin
        )
        if row is None:
            raise RuntimeError("created salary advance is not visible")
        schedule, repayments = await self._schedule_for(row, admin=admin)
        if admin:
            return _admin_response(
                row,
                schedule,
                repayments,
                actor_id=principal.app_user_id,
                actor_employee_id=principal.employee_id,
            )
        return _self_response(row, schedule)

    async def withdraw(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        advance_id: uuid.UUID,
        request: AdvanceVersionRequest,
    ) -> AdvanceResponse:
        if (
            principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}
            or principal.employee_id is None
            or principal.branch_id != branch_id
        ):
            raise ServiceExecutionError("operation_not_permitted")
        row = await self.repository.lock_advance(principal.company_id, branch_id, advance_id)
        if row is None or row["employee_id"] != principal.employee_id:
            raise ServiceExecutionError("resource_not_found")
        self._check_pending_version(row, request.expected_updated_at)
        await self.repository.update_advance(
            advance_id,
            {"status": "cancelled", "rejection_reason": "Withdrawn by employee"},
        )
        await append_audit_event(
            self.connection,
            action="salary_advance_withdrawn",
            entity_type="salary_advance",
            entity_id=advance_id,
            changed_fields=["status", "rejection_reason"],
            reason="Salary advance withdrawn by employee",
        )
        current = await self.repository.get_advance(
            principal.company_id, branch_id, advance_id, admin=False
        )
        if current is None:
            raise RuntimeError("withdrawn salary advance is not visible")
        schedule, _ = await self._schedule_for(current, admin=False)
        return _self_response(current, schedule)

    def _check_pending_version(self, row: RowMapping, expected: datetime) -> None:
        if not _same_version(row["updated_at"], expected):
            raise ServiceExecutionError("stale_financial_state")
        if row["status"] != "pending":
            raise ServiceExecutionError("stale_financial_state")

    def _check_admin(self, principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    async def _locked_admin(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        advance_id: uuid.UUID,
    ) -> RowMapping:
        self._check_admin(principal)
        row = await self.repository.lock_advance(principal.company_id, branch_id, advance_id)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    async def schedule(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        advance_id: uuid.UUID,
        request: AdvanceScheduleRequest,
    ) -> AdvanceAdminResponse:
        row = await self._locked_admin(principal, branch_id, advance_id)
        self._check_pending_version(row, request.expected_updated_at)
        start = await self._validate_start(request.repayment_start_period)
        amount = _money(request.amount)
        monthly = monthly_installment(amount, request.installment_count)
        await self.repository.update_advance(
            advance_id,
            {
                "amount": f"{amount:.2f}",
                "repayment_months": request.installment_count,
                "repayment_start_month": start,
                "monthly_deduction": f"{monthly:.2f}",
                "outstanding_balance": f"{amount:.2f}",
            },
        )
        await append_audit_event(
            self.connection,
            action="salary_advance_schedule_changed",
            entity_type="salary_advance",
            entity_id=advance_id,
            changed_fields=[
                "amount",
                "repayment_months",
                "repayment_start_month",
                "monthly_deduction",
                "outstanding_balance",
            ],
            reason="Salary advance schedule changed",
        )
        return await self._admin_result(principal, branch_id, advance_id)

    async def decide(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        advance_id: uuid.UUID,
        request: AdvanceDecisionRequest,
        *,
        approve: bool,
    ) -> AdvanceAdminResponse:
        row = await self._locked_admin(principal, branch_id, advance_id)
        self._check_pending_version(row, request.expected_updated_at)
        if (
            row["creator_app_user_id"] == principal.app_user_id
            or row["employee_id"] == principal.employee_id
        ):
            raise ServiceExecutionError("resource_not_found")
        if approve:
            if request.reason is not None:
                raise ServiceExecutionError("validation_failed")
            business_date = await self.repository.business_date()
            await self.repository.update_advance(
                advance_id,
                {
                    "status": "active",
                    "disbursed_date": business_date,
                    "monthly_deduction": row["monthly_deduction"],
                    "outstanding_balance": row["amount"],
                    "rejection_reason": None,
                },
            )
            action = "salary_advance_approved"
            changed = ["status", "disbursed_date", "monthly_deduction", "outstanding_balance"]
            reason = "Salary advance approved"
        else:
            if request.reason is None:
                raise ServiceExecutionError("validation_failed")
            await self.repository.update_advance(
                advance_id,
                {"status": "cancelled", "rejection_reason": request.reason},
            )
            action = "salary_advance_rejected"
            changed = ["status", "rejection_reason"]
            reason = request.reason
        await append_audit_event(
            self.connection,
            action=action,
            entity_type="salary_advance",
            entity_id=advance_id,
            changed_fields=changed,
            reason=reason,
        )
        return await self._admin_result(principal, branch_id, advance_id)

    async def repay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        advance_id: uuid.UUID,
        request: AdvanceRepaymentRequest | AdvanceVersionRequest,
        *,
        idempotency_key: uuid.UUID,
        settle: bool,
    ) -> AdvanceAdminResponse:
        row = await self._locked_admin(principal, branch_id, advance_id)
        if not _same_version(row["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("stale_financial_state")
        if row["status"] != "active" or _money(row["outstanding_balance"]) <= 0:
            raise ServiceExecutionError("stale_financial_state")
        balance = _money(row["outstanding_balance"])
        if settle:
            amount = balance
            kind = "settlement"
        else:
            if not isinstance(request, AdvanceRepaymentRequest):
                raise ServiceExecutionError("validation_failed")
            amount = _money(request.amount)
            if amount > balance:
                raise ServiceExecutionError("validation_failed")
            kind = "manual"
        paid_date = await self.repository.business_date()
        result = await self.repository.record_repayment(
            advance_id=advance_id,
            payroll_run_id=None,
            idempotency_key=idempotency_key,
            amount=f"{amount:.2f}",
            paid_date=paid_date,
        )
        payload = result["result"]
        repayment_id = uuid.UUID(str(payload["repaymentId"]))
        new_status = str(payload["newStatus"])
        await append_audit_event(
            self.connection,
            action="salary_advance_repayment_recorded",
            entity_type="salary_advance",
            entity_id=advance_id,
            changed_fields=["outstanding_balance", "status"],
            reason="Salary advance repayment recorded",
            metadata={
                "repayment_id": str(repayment_id),
                "payroll_run_id": None,
                "repayment_kind": kind,
            },
        )
        if new_status == "settled":
            await append_audit_event(
                self.connection,
                action="salary_advance_settled",
                entity_type="salary_advance",
                entity_id=advance_id,
                changed_fields=["status", "outstanding_balance"],
                reason="Salary advance settled",
                metadata={
                    "repayment_id": str(repayment_id),
                    "payroll_run_id": None,
                    "repayment_kind": kind,
                },
            )
        return await self._admin_result(principal, branch_id, advance_id)

    async def _admin_result(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        advance_id: uuid.UUID,
    ) -> AdvanceAdminResponse:
        row = await self.repository.get_advance(
            principal.company_id, branch_id, advance_id, admin=True
        )
        if row is None:
            raise RuntimeError("salary advance is not visible")
        schedule, repayments = await self._schedule_for(row, admin=True)
        return _admin_response(
            row,
            schedule,
            repayments,
            actor_id=principal.app_user_id,
            actor_employee_id=principal.employee_id,
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "salary_advance" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        admin = principal.role is AppRole.ADMIN
        row = await self.repository.get_advance(
            principal.company_id, branch_id, resource_id, admin=admin
        )
        if row is None or (not admin and row["employee_id"] != principal.employee_id):
            raise ServiceExecutionError("resource_not_found")
