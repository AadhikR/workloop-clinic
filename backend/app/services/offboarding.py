from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, cast

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.schemas.employees import EmployeeArchiveRequest
from app.schemas.offboarding import (
    FinalSettlementResponse,
    OffboardingChecklistResponse,
    OffboardingLetterSource,
    OffboardingTaskCreateRequest,
    OffboardingTaskResponse,
    OffboardingTaskUpdateRequest,
    OffboardingVisaRequest,
    SettlementCompleteRequest,
    SettlementInputs,
    SettlementPreviewResponse,
)
from app.services.employees import EmployeeCursorCodec, EmployeeService
from app.services.execution import ServiceExecutionError

CENT = Decimal("0.01")
DAY_PRECISION = Decimal("0.0001")
POLICY_ID = uuid.UUID("c3e5a7b9-d1f6-4b18-9b4e-11a700000001")
POLICY_KEY = "uae-mainland-private-sector-foreign-full-time"
VISA_TRANSITIONS = {
    "not_started": "initiated",
    "initiated": "submitted_gdrfa",
    "submitted_gdrfa": "cancelled",
}


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_gratuity(basic_salary: Decimal, service_days: Decimal) -> tuple[Decimal, Decimal]:
    if service_days < Decimal("365"):
        return Decimal("0.00"), Decimal("0.0000")
    first_days = min(service_days, Decimal("1825"))
    excess_days = max(service_days - Decimal("1825"), Decimal("0"))
    gratuity_days = first_days * Decimal("21") / Decimal("365") + excess_days * Decimal(
        "30"
    ) / Decimal("365")
    daily_rate = basic_salary / Decimal("30")
    calculated = money(daily_rate * gratuity_days)
    cap = money(basic_salary * Decimal("24"))
    return min(calculated, cap), gratuity_days.quantize(DAY_PRECISION, rounding=ROUND_HALF_UP)


def _same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        normalized = value.astimezone(UTC)
        return normalized.replace(microsecond=normalized.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_json_value(item) for item in cast(list[object], value)]
    if isinstance(value, dict):
        return {
            str(key): _json_value(item) for key, item in cast(dict[object, object], value).items()
        }
    return value


def _digest(snapshot: dict[str, object]) -> str:
    encoded = json.dumps(_json_value(snapshot), sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class OffboardingService:
    def __init__(self, connection: AsyncConnection, cursor_codec: EmployeeCursorCodec) -> None:
        self.connection = connection
        self.cursor_codec = cursor_codec

    @staticmethod
    def _require_admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    async def _tasks(self, checklist_id: uuid.UUID, *, lock: bool = False) -> list[Any]:
        suffix = " FOR UPDATE" if lock else ""
        return list(
            (
                await self.connection.execute(
                    text(
                        "SELECT id,task_name,completed,completed_at,notes,sort_order,source,"
                        "template_id,updated_at FROM public.offboarding_tasks "
                        "WHERE checklist_id=:id ORDER BY sort_order,id" + suffix
                    ),
                    {"id": checklist_id},
                )
            ).mappings()
        )

    async def _response(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, checklist_id: uuid.UUID
    ) -> OffboardingChecklistResponse:
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT checklist.id,checklist.employee_id,employee.name employee_name,
 employee.employment_status,checklist.status,checklist.visa_cancellation_status,
 checklist.visa_cancellation_date,checklist.final_settlement_id,checklist.created_at,
 checklist.updated_at,checklist.completed_at
FROM public.offboarding_checklists checklist
JOIN public.employees employee ON employee.id=checklist.employee_id
 AND employee.company_id=checklist.company_id AND employee.branch_id=checklist.branch_id
WHERE checklist.id=:id AND checklist.company_id=:company_id AND checklist.branch_id=:branch_id
"""
                    ),
                    {
                        "id": checklist_id,
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
        tasks = [
            OffboardingTaskResponse.model_validate(item) for item in await self._tasks(checklist_id)
        ]
        return OffboardingChecklistResponse.model_validate({**row, "tasks": tasks})

    async def list(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, limit: int
    ) -> list[OffboardingChecklistResponse]:
        self._require_admin(principal)
        ids = (
            await self.connection.execute(
                text(
                    "SELECT id FROM public.offboarding_checklists WHERE company_id=:company_id "
                    "AND branch_id=:branch_id ORDER BY created_at DESC,id DESC LIMIT :limit"
                ),
                {"company_id": principal.company_id, "branch_id": branch_id, "limit": limit},
            )
        ).scalars()
        return [await self._response(principal, branch_id, item) for item in ids]

    async def get(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, checklist_id: uuid.UUID
    ) -> OffboardingChecklistResponse:
        self._require_admin(principal)
        return await self._response(principal, branch_id, checklist_id)

    async def initialize(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> OffboardingChecklistResponse:
        self._require_admin(principal)
        employee = (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,active,employment_status FROM public.employees WHERE id=:id "
                        "AND company_id=:company_id AND branch_id=:branch_id FOR UPDATE"
                    ),
                    {"id": employee_id, "company_id": principal.company_id, "branch_id": branch_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if employee is None:
            raise ServiceExecutionError("resource_not_found")
        if not employee["active"] or employee["employment_status"] not in {"Active", "On Leave"}:
            raise ServiceExecutionError("employment_transition_conflict")
        existing = (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,initialized_by_app_user_id FROM public.offboarding_checklists "
                        "WHERE employee_id=:employee_id FOR UPDATE"
                    ),
                    {"employee_id": employee_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if existing["initialized_by_app_user_id"] is None:
                await self.connection.execute(
                    text(
                        "UPDATE public.offboarding_checklists "
                        "SET initialized_by_app_user_id=:actor,"
                        "updated_at=statement_timestamp() WHERE id=:id"
                    ),
                    {"actor": principal.app_user_id, "id": existing["id"]},
                )
            return await self._response(principal, branch_id, existing["id"])
        checklist_id = uuid.uuid4()
        await self.connection.execute(
            text(
                "INSERT INTO public.offboarding_checklists(id,company_id,branch_id,employee_id,"
                "initialized_by_app_user_id) VALUES(:id,:company_id,:branch_id,:employee_id,:actor)"
            ),
            {
                "id": checklist_id,
                "company_id": principal.company_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
                "actor": principal.app_user_id,
            },
        )
        await self.connection.execute(
            text(
                """
INSERT INTO public.offboarding_tasks(
 id,company_id,branch_id,checklist_id,task_name,sort_order,source,template_id)
SELECT gen_random_uuid(),company_id,branch_id,:checklist_id,task_name,default_order,'template',id
FROM public.offboarding_task_templates
WHERE company_id=:company_id AND branch_id=:branch_id ORDER BY default_order,id
"""
            ),
            {
                "checklist_id": checklist_id,
                "company_id": principal.company_id,
                "branch_id": branch_id,
            },
        )
        await append_audit_event(
            self.connection,
            action="offboarding_initialized",
            entity_type="offboarding_checklist",
            entity_id=checklist_id,
            changed_fields=["initialized_by_app_user_id", "status"],
            reason="Offboarding checklist initialized",
        )
        return await self._response(principal, branch_id, checklist_id)

    async def _lock_checklist(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        expected: datetime | None = None,
    ) -> Any:
        self._require_admin(principal)
        row = (
            (
                await self.connection.execute(
                    text(
                        "SELECT * FROM public.offboarding_checklists WHERE id=:id "
                        "AND company_id=:company_id AND branch_id=:branch_id FOR UPDATE"
                    ),
                    {
                        "id": checklist_id,
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
        if row["status"] != "in_progress" or (
            expected is not None and not _same_version(row["updated_at"], expected)
        ):
            raise ServiceExecutionError("state_conflict")
        return row

    async def add_task(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        request: OffboardingTaskCreateRequest,
    ) -> OffboardingChecklistResponse:
        await self._lock_checklist(
            principal, branch_id, checklist_id, request.expected_checklist_updated_at
        )
        task_id = uuid.uuid4()
        await self.connection.execute(
            text(
                "INSERT INTO public.offboarding_tasks("
                "id,company_id,branch_id,checklist_id,task_name,"
                "sort_order,source) SELECT :id,:company_id,:branch_id,:checklist_id,:name,"
                "coalesce(max(sort_order),-1)+1,'custom' FROM public.offboarding_tasks "
                "WHERE checklist_id=:checklist_id"
            ),
            {
                "id": task_id,
                "company_id": principal.company_id,
                "branch_id": branch_id,
                "checklist_id": checklist_id,
                "name": request.task_name,
            },
        )
        await self._touch_and_audit(checklist_id, "offboarding_task_added", ["tasks"])
        return await self._response(principal, branch_id, checklist_id)

    async def update_task(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        task_id: uuid.UUID,
        request: OffboardingTaskUpdateRequest,
        *,
        complete: bool,
    ) -> OffboardingChecklistResponse:
        await self._lock_checklist(
            principal, branch_id, checklist_id, request.expected_checklist_updated_at
        )
        task = (
            (
                await self.connection.execute(
                    text(
                        "SELECT * FROM public.offboarding_tasks "
                        "WHERE id=:id AND checklist_id=:checklist_id FOR UPDATE"
                    ),
                    {"id": task_id, "checklist_id": checklist_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if task is None:
            raise ServiceExecutionError("resource_not_found")
        if (
            not _same_version(task["updated_at"], request.expected_task_updated_at)
            or task["completed"] is complete
        ):
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text(
                "UPDATE public.offboarding_tasks SET completed=:completed,notes=:notes,"
                "completed_at=CASE WHEN :completed THEN statement_timestamp() ELSE NULL END,"
                "completed_by_app_user_id=CASE WHEN :completed THEN :actor ELSE NULL END "
                "WHERE id=:id"
            ),
            {
                "completed": complete,
                "notes": request.notes,
                "actor": principal.app_user_id,
                "id": task_id,
            },
        )
        action = "offboarding_task_completed" if complete else "offboarding_task_reopened"
        await self._touch_and_audit(checklist_id, action, ["tasks"])
        return await self._response(principal, branch_id, checklist_id)

    async def delete_task(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        task_id: uuid.UUID,
        request: OffboardingTaskUpdateRequest,
    ) -> OffboardingChecklistResponse:
        await self._lock_checklist(
            principal, branch_id, checklist_id, request.expected_checklist_updated_at
        )
        task = (
            (
                await self.connection.execute(
                    text(
                        "SELECT source,completed,updated_at FROM public.offboarding_tasks "
                        "WHERE id=:id AND checklist_id=:checklist_id FOR UPDATE"
                    ),
                    {"id": task_id, "checklist_id": checklist_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if task is None:
            raise ServiceExecutionError("resource_not_found")
        if (
            task["source"] != "custom"
            or task["completed"]
            or not _same_version(task["updated_at"], request.expected_task_updated_at)
        ):
            raise ServiceExecutionError("state_conflict")
        await self.connection.execute(
            text("DELETE FROM public.offboarding_tasks WHERE id=:id"), {"id": task_id}
        )
        await self._touch_and_audit(checklist_id, "offboarding_task_deleted", ["tasks"])
        return await self._response(principal, branch_id, checklist_id)

    async def _touch_and_audit(
        self, checklist_id: uuid.UUID, action: str, fields: list[str]
    ) -> None:
        await self.connection.execute(
            text(
                "UPDATE public.offboarding_checklists SET updated_at=statement_timestamp() "
                "WHERE id=:id"
            ),
            {"id": checklist_id},
        )
        await append_audit_event(
            self.connection,
            action=action,
            entity_type="offboarding_checklist",
            entity_id=checklist_id,
            changed_fields=fields,
            reason="Offboarding checklist updated",
        )

    async def update_visa(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        request: OffboardingVisaRequest,
    ) -> OffboardingChecklistResponse:
        checklist = await self._lock_checklist(
            principal, branch_id, checklist_id, request.expected_checklist_updated_at
        )
        if VISA_TRANSITIONS.get(checklist["visa_cancellation_status"]) != request.status:
            raise ServiceExecutionError("state_conflict")
        business_date = await self.connection.scalar(text("SELECT public.workloop_business_date()"))
        await self.connection.execute(
            text(
                "UPDATE public.offboarding_checklists SET visa_cancellation_status=:status,"
                "visa_cancellation_date=CASE WHEN :status='cancelled' "
                "THEN :business_date ELSE NULL END,"
                "updated_at=statement_timestamp() WHERE id=:id"
            ),
            {"status": request.status, "business_date": business_date, "id": checklist_id},
        )
        await append_audit_event(
            self.connection,
            action="offboarding_visa_changed",
            entity_type="offboarding_checklist",
            entity_id=checklist_id,
            changed_fields=["visa_cancellation_status", "visa_cancellation_date"],
            reason="Visa cancellation state advanced",
        )
        return await self._response(principal, branch_id, checklist_id)

    async def _calculate(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        request: SettlementInputs,
        *,
        completing: bool,
    ) -> tuple[SettlementPreviewResponse, dict[str, object], Any, list[Any]]:
        checklist = await self._lock_checklist(
            principal, branch_id, checklist_id, request.expected_checklist_updated_at
        )
        employee = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT employee.*,branch.name branch_name
FROM public.employees employee
JOIN public.branches branch ON branch.id=employee.branch_id
 AND branch.company_id=employee.company_id
WHERE employee.id=:employee_id AND employee.company_id=:company_id AND employee.branch_id=:branch_id
FOR UPDATE OF employee
"""
                    ),
                    {
                        "employee_id": checklist["employee_id"],
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        business_date: date = await self.connection.scalar(
            text("SELECT public.workloop_business_date()")
        )
        if (
            employee["work_location_type"] != "Mainland"
            or employee["nationality"] in {"", "United Arab Emirates"}
            or employee["employment_start_date"] is None
            or employee["employment_start_date"] > business_date
            or not employee["active"]
            or employee["employment_status"] not in {"Active", "On Leave"}
        ):
            raise ServiceExecutionError("settlement_policy_unavailable")
        tasks = await self._tasks(checklist_id, lock=True)
        if completing and (not tasks or any(not item["completed"] for item in tasks)):
            raise ServiceExecutionError("offboarding_blocked")
        if (
            completing
            and employee["visa_type"] == "Employment Visa"
            and checklist["visa_cancellation_status"] != "cancelled"
        ):
            raise ServiceExecutionError("offboarding_blocked")
        open_assets = list(
            (
                await self.connection.execute(
                    text(
                        "SELECT assignment.id,assignment.asset_id "
                        "FROM public.asset_assignments assignment "
                        "WHERE assignment.company_id=:company_id "
                        "AND assignment.branch_id=:branch_id "
                        "AND assignment.employee_id=:employee_id "
                        "AND assignment.return_date IS NULL "
                        "ORDER BY assignment.id FOR UPDATE"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee["id"],
                    },
                )
            ).mappings()
        )
        if open_assets:
            raise ServiceExecutionError("offboarding_blocked")
        unpaid = list(
            (
                await self.connection.execute(
                    text(
                        """
SELECT request.id,request.days_requested,request.updated_at
FROM public.leave_requests request
JOIN public.leave_types type ON type.id=request.leave_type_id
 AND type.company_id=request.company_id AND type.branch_id=request.branch_id
WHERE request.company_id=:company_id AND request.branch_id=:branch_id
 AND request.employee_id=:employee_id AND request.status='Approved' AND NOT type.is_paid
 AND request.start_date>=:start_date AND request.end_date<=:end_date
ORDER BY request.id FOR UPDATE OF request
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee["id"],
                        "start_date": employee["employment_start_date"],
                        "end_date": business_date,
                    },
                )
            ).mappings()
        )
        unpaid_days = sum((Decimal(item["days_requested"]) for item in unpaid), Decimal("0"))
        service_days = (
            Decimal((business_date - employee["employment_start_date"]).days + 1) - unpaid_days
        )
        if service_days < 0:
            raise ServiceExecutionError("settlement_policy_unavailable")
        leave = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT balance.id,balance.remaining_days,balance.updated_at,type.id leave_type_id
FROM public.leave_balances balance
JOIN public.leave_types type ON type.id=balance.leave_type_id
 AND type.company_id=balance.company_id AND type.branch_id=balance.branch_id
WHERE balance.company_id=:company_id AND balance.branch_id=:branch_id
 AND balance.employee_id=:employee_id AND balance.leave_year=:year AND type.code='ANNUAL'
FOR UPDATE OF balance
"""
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee["id"],
                        "year": business_date.year,
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        payroll = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT * FROM public.read_offboarding_payroll_source(:employee_id,:period)
"""
                    ),
                    {
                        "period": business_date.strftime("%Y-%m"),
                        "employee_id": employee["id"],
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if payroll is None:
            raise ServiceExecutionError("offboarding_blocked")
        advances = list(
            (
                await self.connection.execute(
                    text(
                        "SELECT id,outstanding_balance,updated_at FROM public.salary_advances "
                        "WHERE company_id=:company_id AND branch_id=:branch_id "
                        "AND employee_id=:employee_id "
                        "AND status='active' AND outstanding_balance>0 ORDER BY id FOR UPDATE"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee["id"],
                    },
                )
            ).mappings()
        )
        policy = (
            (
                await self.connection.execute(
                    text("SELECT * FROM public.settlement_policy_versions WHERE id=:id"),
                    {"id": POLICY_ID},
                )
            )
            .mappings()
            .one_or_none()
        )
        if policy is None:
            raise ServiceExecutionError("settlement_policy_unavailable")
        contract = (
            (
                await self.connection.execute(
                    text(
                        "SELECT id,action,contract_type,start_date,end_date,created_at "
                        "FROM public.employee_contracts "
                        "WHERE company_id=:company_id AND branch_id=:branch_id "
                        "AND employee_id=:employee_id "
                        "ORDER BY created_at DESC,id DESC LIMIT 1"
                    ),
                    {
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "employee_id": employee["id"],
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        basic = money(employee["basic_salary"])
        leave_days = Decimal(leave["remaining_days"]) if leave is not None else Decimal("0")
        gratuity, gratuity_days = calculate_gratuity(basic, service_days)
        leave_encashment = money(basic / Decimal("30") * leave_days)
        was_paid = (
            payroll["payslip_payment_date"] is not None or payroll["run_payment_date"] is not None
        )
        final_salary = Decimal("0.00") if was_paid else money(payroll["net_pay"])
        advance_deduction = money(
            sum((Decimal(item["outstanding_balance"]) for item in advances), Decimal("0"))
        )
        notice_pay = money(request.notice_pay)
        other_earnings = money(request.other_earnings)
        notice_deduction = money(request.notice_deduction)
        other_deductions = money(request.other_deductions)
        gross = money(final_salary + leave_encashment + gratuity + notice_pay + other_earnings)
        deductions = money(advance_deduction + notice_deduction + other_deductions)
        net = money(gross - deductions)
        if net < 0:
            raise ServiceExecutionError("offboarding_blocked")
        snapshot: dict[str, object] = {
            "businessDate": business_date,
            "checklist": {"id": checklist_id, "updatedAt": checklist["updated_at"]},
            "employee": {
                "id": employee["id"],
                "updatedAt": employee["updated_at"],
                "employmentStartDate": employee["employment_start_date"],
                "basicSalary": f"{basic:.2f}",
                "nationality": employee["nationality"],
                "workLocationType": employee["work_location_type"],
            },
            "tasks": [
                {
                    "id": item["id"],
                    "updatedAt": item["updated_at"],
                    "completed": item["completed"],
                    "source": item["source"],
                }
                for item in tasks
            ],
            "unpaidLeave": [
                {"id": item["id"], "days": item["days_requested"], "updatedAt": item["updated_at"]}
                for item in unpaid
            ],
            "annualLeave": None
            if leave is None
            else {
                "id": leave["id"],
                "typeId": leave["leave_type_id"],
                "remainingDays": leave_days,
                "updatedAt": leave["updated_at"],
            },
            "payroll": {
                "runId": payroll["payroll_run_id"],
                "runUpdatedAt": payroll["payroll_updated_at"],
                "payslipId": payroll["payslip_id"],
                "issuedAt": payroll["issued_at"],
                "netPay": payroll["net_pay"],
                "paid": was_paid,
            },
            "advances": [
                {
                    "id": item["id"],
                    "outstandingBalance": item["outstanding_balance"],
                    "updatedAt": item["updated_at"],
                }
                for item in advances
            ],
            "contract": None if contract is None else dict(contract),
            "manualAdjustments": {
                "noticePay": notice_pay,
                "noticeDeduction": notice_deduction,
                "otherEarnings": other_earnings,
                "otherDeductions": other_deductions,
                "reason": request.adjustment_reason,
            },
            "policy": {
                "id": policy["id"],
                "version": policy["semantic_version"],
                "digest": policy["digest"],
            },
        }
        source_digest = _digest(snapshot)
        captured_at: datetime = await self.connection.scalar(text("SELECT statement_timestamp()"))
        preview = SettlementPreviewResponse(
            policy_version=policy["semantic_version"],
            policy_digest=policy["digest"],
            source_digest=source_digest,
            source_captured_at=captured_at,
            service_days=service_days,
            gratuity_days=gratuity_days,
            leave_days=leave_days,
            final_salary=final_salary,
            leave_encashment=leave_encashment,
            gratuity=gratuity,
            notice_pay=notice_pay,
            other_earnings=other_earnings,
            advance_deduction=advance_deduction,
            asset_deduction=Decimal("0.00"),
            notice_deduction=notice_deduction,
            other_deductions=other_deductions,
            gross_amount=gross,
            total_deductions=deductions,
            net_amount=net,
        )
        return preview, snapshot, employee, advances

    async def preview(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        request: SettlementInputs,
    ) -> SettlementPreviewResponse:
        preview, _, _, _ = await self._calculate(
            principal, branch_id, checklist_id, request, completing=False
        )
        return preview

    async def complete(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        checklist_id: uuid.UUID,
        request: SettlementCompleteRequest,
    ) -> FinalSettlementResponse:
        preview, snapshot, employee, advances = await self._calculate(
            principal, branch_id, checklist_id, request, completing=True
        )
        if preview.source_digest != request.expected_source_digest:
            raise ServiceExecutionError("state_conflict")
        checklist = (
            (
                await self.connection.execute(
                    text(
                        "SELECT initialized_by_app_user_id "
                        "FROM public.offboarding_checklists WHERE id=:id"
                    ),
                    {"id": checklist_id},
                )
            )
            .mappings()
            .one()
        )
        if (
            checklist["initialized_by_app_user_id"] is None
            or checklist["initialized_by_app_user_id"] == principal.app_user_id
        ):
            raise ServiceExecutionError("offboarding_blocked")
        settlement_id = uuid.uuid4()
        breakdown = {
            "serviceDays": format(preview.service_days, "f"),
            "gratuityDays": format(preview.gratuity_days, "f"),
            "dailyBasicRate": format(Decimal(employee["basic_salary"]) / Decimal("30"), ".8f"),
            "leaveDays": format(preview.leave_days, "f"),
            "rounding": "ROUND_HALF_UP component then total to 0.01 AED",
        }
        values = preview.model_dump(by_alias=False)
        await self.connection.execute(
            text(
                """
INSERT INTO public.final_settlements(
 id,company_id,branch_id,employee_id,checklist_id,policy_version_id,
 source_snapshot,source_digest,source_captured_at,final_salary,leave_encashment,
 gratuity,notice_pay,other_earnings,advance_deduction,asset_deduction,
 notice_deduction,other_deductions,gross_amount,total_deductions,net_amount,
 calculation_breakdown,completed_by_app_user_id,reviewed_by_app_user_id)
VALUES(:id,:company_id,:branch_id,:employee_id,:checklist_id,:policy_id,
 :snapshot,:source_digest,:captured_at,:final_salary,:leave_encashment,:gratuity,
 :notice_pay,:other_earnings,:advance_deduction,:asset_deduction,:notice_deduction,
 :other_deductions,:gross_amount,:total_deductions,:net_amount,:breakdown,:actor,:actor)
"""
            ).bindparams(
                bindparam("snapshot", type_=JSONB()), bindparam("breakdown", type_=JSONB())
            ),
            {
                "id": settlement_id,
                "company_id": principal.company_id,
                "branch_id": branch_id,
                "employee_id": employee["id"],
                "checklist_id": checklist_id,
                "policy_id": POLICY_ID,
                "snapshot": _json_value(snapshot),
                "source_digest": preview.source_digest,
                "captured_at": preview.source_captured_at,
                "breakdown": breakdown,
                "actor": principal.app_user_id,
                **{
                    name: values[name]
                    for name in (
                        "final_salary",
                        "leave_encashment",
                        "gratuity",
                        "notice_pay",
                        "other_earnings",
                        "advance_deduction",
                        "asset_deduction",
                        "notice_deduction",
                        "other_deductions",
                        "gross_amount",
                        "total_deductions",
                        "net_amount",
                    )
                },
            },
        )
        business_date: date = await self.connection.scalar(
            text("SELECT public.workloop_business_date()")
        )
        for advance in advances:
            repayment_key = uuid.uuid5(settlement_id, str(advance["id"]))
            result = (
                (
                    await self.connection.execute(
                        text(
                            "SELECT public.record_advance_repayment("
                            ":advance_id,NULL,:key,:amount,:paid_date) result"
                        ),
                        {
                            "advance_id": advance["id"],
                            "key": repayment_key,
                            "amount": advance["outstanding_balance"],
                            "paid_date": business_date,
                        },
                    )
                )
                .mappings()
                .one()["result"]
            )
            repayment_id = uuid.UUID(str(result["repaymentId"]))
            metadata = {
                "repayment_id": str(repayment_id),
                "payroll_run_id": None,
                "repayment_kind": "settlement",
            }
            await append_audit_event(
                self.connection,
                action="salary_advance_repayment_recorded",
                entity_type="salary_advance",
                entity_id=advance["id"],
                changed_fields=["outstanding_balance", "status"],
                reason="Salary advance deducted from final settlement",
                metadata=metadata,
            )
            await append_audit_event(
                self.connection,
                action="salary_advance_settled",
                entity_type="salary_advance",
                entity_id=advance["id"],
                changed_fields=["status", "outstanding_balance"],
                reason="Salary advance settled through offboarding",
                metadata=metadata,
            )
        archive = EmployeeArchiveRequest(
            expected_updated_at=employee["updated_at"],
            reason=request.termination_reason,
            report_reassignments=[],
        )
        await EmployeeService(self.connection, self.cursor_codec).archive_employee(
            principal, branch_id, employee["id"], archive
        )
        await self.connection.execute(
            text(
                "UPDATE public.offboarding_checklists SET status='completed',"
                "final_settlement_id=:settlement_id,completed_at=statement_timestamp(),"
                "completed_by_app_user_id=:actor,updated_at=statement_timestamp() "
                "WHERE id=:id"
            ),
            {"settlement_id": settlement_id, "actor": principal.app_user_id, "id": checklist_id},
        )
        await append_audit_event(
            self.connection,
            action="final_settlement_completed",
            entity_type="final_settlement",
            entity_id=settlement_id,
            changed_fields=[
                "source_snapshot",
                "calculation_breakdown",
                "net_amount",
                "completed_by_app_user_id",
            ],
            reason="Final settlement reviewed and completed",
            metadata={"source_digest": preview.source_digest},
        )
        await append_audit_event(
            self.connection,
            action="offboarding_completed",
            entity_type="offboarding_checklist",
            entity_id=checklist_id,
            changed_fields=["status", "completed_at", "completed_by_app_user_id"],
            reason="Offboarding and final settlement completed",
        )
        completed_at: datetime = await self.connection.scalar(
            text("SELECT completed_at FROM public.final_settlements WHERE id=:id"),
            {"id": settlement_id},
        )
        return FinalSettlementResponse(
            **preview.model_dump(by_alias=False),
            id=settlement_id,
            checklist_id=checklist_id,
            employee_id=employee["id"],
            completed_at=completed_at,
        )

    async def letter_source(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, checklist_id: uuid.UUID
    ) -> OffboardingLetterSource:
        self._require_admin(principal)
        row = (
            (
                await self.connection.execute(
                    text(
                        """
SELECT checklist.id checklist_id,settlement.id settlement_id,employee.name employee_name,
 employee.job_title,employee.department,employee.employment_start_date,employee.termination_date,
 branch.name branch_name,checklist.completed_at
FROM public.offboarding_checklists checklist
JOIN public.final_settlements settlement ON settlement.id=checklist.final_settlement_id
JOIN public.employees employee ON employee.id=checklist.employee_id
 AND employee.company_id=checklist.company_id AND employee.branch_id=checklist.branch_id
JOIN public.branches branch ON branch.id=checklist.branch_id
 AND branch.company_id=checklist.company_id
WHERE checklist.id=:id AND checklist.company_id=:company_id AND checklist.branch_id=:branch_id
 AND checklist.status='completed'
"""
                    ),
                    {
                        "id": checklist_id,
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
        return OffboardingLetterSource.model_validate(row)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "offboarding_checklist" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        exists = await self.connection.scalar(
            text(
                "SELECT 1 FROM public.offboarding_checklists "
                "WHERE id=:id AND company_id=:company_id AND branch_id=:branch_id"
            ),
            {"id": resource_id, "company_id": principal.company_id, "branch_id": branch_id},
        )
        if exists is None:
            raise ServiceExecutionError("resource_not_found")
