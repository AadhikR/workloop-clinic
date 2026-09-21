from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, TypedDict, cast

from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.payroll import PayrollRepository
from app.schemas.payroll import (
    PayrollAdjustmentRequest,
    PayrollAdjustmentResponse,
    PayrollApprovalHistoryResponse,
    PayrollCreateRequest,
    PayrollEntriesRequest,
    PayrollEntryPreview,
    PayrollEntryResponse,
    PayrollReasonRequest,
    PayrollRepeatRequest,
    PayrollRunDetailResponse,
    PayrollRunResponse,
    PayrollVersionRequest,
    PayslipLineResponse,
    PayslipResponse,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
AUTOMATIC_PREFIXES = ("AUTO_", "LEAVE_", "ATTENDANCE_", "ROSTER_", "EXPENSE_", "ADVANCE_")
SOURCE_TYPES = ("leave", "attendance", "roster", "expense", "advance")
AUTOMATIC_NAMESPACE = uuid.UUID("9e000000-0000-4000-8000-000000000001")
PAYSLIP_NAMESPACE = uuid.UUID("9f000000-0000-4000-8000-000000000001")
REPAYMENT_NAMESPACE = uuid.UUID("9f000000-0000-4000-8000-000000000002")


@dataclass(frozen=True, slots=True)
class PayrollListQuery:
    limit: int = 50
    cursor: str | None = None
    period: str | None = None
    run_status: str | None = None
    approval_status: str | None = None


@dataclass(frozen=True, slots=True)
class PayslipListQuery:
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class EntryValues:
    basic_salary: Decimal
    housing_allowance: Decimal
    transport_allowance: Decimal
    fixed_allowance: Decimal
    increment: Decimal
    bonus: Decimal
    other_pay: Decimal
    variable_allowance: Decimal
    leave_deduction: Decimal
    fixed_pay: Decimal
    gross_pay: Decimal
    total_deductions: Decimal
    net_pay: Decimal
    wps_basic_pay: Decimal
    wps_variable_pay: Decimal


class ManualValues(TypedDict):
    increment: Decimal | str
    bonus: Decimal | str
    other_pay: Decimal | str
    variable_allowance: Decimal | str
    additional_allowances: list[dict[str, object]]
    deductions: list[dict[str, object]]
    excluded: bool


def money(value: Decimal | str | int) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _sum_adjustments(values: list[PayrollAdjustmentRequest] | list[dict[str, object]]) -> Decimal:
    total = ZERO
    for item in values:
        amount = item.amount if isinstance(item, PayrollAdjustmentRequest) else item["amount"]
        total += Decimal(str(amount))
    return money(total)


def calculate_entry(
    *,
    basic_salary: Decimal | str,
    housing_allowance: Decimal | str,
    transport_allowance: Decimal | str,
    fixed_allowance: Decimal | str,
    increment: Decimal | str = ZERO,
    bonus: Decimal | str = ZERO,
    other_pay: Decimal | str = ZERO,
    variable_allowance: Decimal | str = ZERO,
    leave_deduction: Decimal | str = ZERO,
    additional_allowances: list[PayrollAdjustmentRequest] | list[dict[str, object]] | None = None,
    deductions: list[PayrollAdjustmentRequest] | list[dict[str, object]] | None = None,
) -> EntryValues:
    basic = money(basic_salary)
    housing = money(housing_allowance)
    transport = money(transport_allowance)
    fixed_allow = money(fixed_allowance)
    increment_value = money(increment)
    bonus_value = money(bonus)
    other = money(other_pay)
    variable = money(variable_allowance)
    leave = money(leave_deduction)
    additions = _sum_adjustments(additional_allowances or [])
    deductions_value = _sum_adjustments(deductions or [])
    fixed_pay = money(basic + housing + transport + fixed_allow)
    gross = money(fixed_pay + increment_value + bonus_value + other + variable + additions)
    total_deductions = money(leave + deductions_value)
    net = money(gross - total_deductions)
    return EntryValues(
        basic_salary=basic,
        housing_allowance=housing,
        transport_allowance=transport,
        fixed_allowance=fixed_allow,
        increment=increment_value,
        bonus=bonus_value,
        other_pay=other,
        variable_allowance=variable,
        leave_deduction=leave,
        fixed_pay=fixed_pay,
        gross_pay=gross,
        total_deductions=total_deductions,
        net_pay=net,
        wps_basic_pay=basic,
        wps_variable_pay=money(net - basic),
    )


def _period_dates(period: str) -> tuple[date, date]:
    year, month = (int(part) for part in period.split("-"))
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def prorate(value: Decimal | str, eligible_days: int, period_days: int) -> Decimal:
    return (Decimal(value) * Decimal(eligible_days) / Decimal(period_days)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _canonical(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _stamp_digest(entries: list[dict[str, object]]) -> list[dict[str, object]]:
    snapshots = [
        item["source_snapshot"]
        for item in sorted(entries, key=lambda value: str(value["employee_id"]))
    ]
    digest = _digest(snapshots)
    return [{**item, "source_snapshot_digest": digest} for item in entries]


def is_automatic_adjustment(item: dict[str, object]) -> bool:
    code = str(item.get("code", ""))
    return item.get("source") == "automatic" or code.startswith(AUTOMATIC_PREFIXES)


def manual_adjustments(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [item for item in items if not is_automatic_adjustment(item)]


def automatic_adjustment(
    source_type: str,
    source_id: uuid.UUID,
    label: str,
    amount: Decimal,
) -> dict[str, object]:
    return {
        "id": str(uuid.uuid5(AUTOMATIC_NAMESPACE, f"{source_type}:{source_id}")),
        "code": f"{source_type.upper()}_{source_id.hex.upper()}",
        "label": label,
        "amount": f"{money(amount):.2f}",
        "recurrence": "one_time",
        "note": None,
    }


def _automatic_source(
    *,
    source_type: str,
    source_id: uuid.UUID,
    source_version: datetime | str,
    period: str,
    direction: Literal["addition", "deduction"],
    amount: Decimal,
    calculation_inputs: dict[str, object],
) -> dict[str, object]:
    return {
        "calculatedAmount": f"{money(amount):.2f}",
        "calculationInputs": calculation_inputs,
        "direction": direction,
        "period": period,
        "sourceId": str(source_id),
        "sourceType": source_type,
        "sourceVersion": source_version
        if isinstance(source_version, str)
        else _iso(source_version),
    }


def _add_months(value: date, count: int) -> date:
    index = value.year * 12 + value.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def _installments(amount: Decimal, count: int) -> list[Decimal]:
    monthly = (amount / Decimal(count)).quantize(CENT, rounding=ROUND_HALF_UP)
    remaining = amount
    values: list[Decimal] = []
    for index in range(count):
        installment = remaining if index == count - 1 else min(monthly, remaining)
        installment = money(installment)
        values.append(installment)
        remaining = money(remaining - installment)
    return values


def advance_due(row: RowMapping, period_start: date) -> tuple[date, Decimal]:
    amount = money(row["amount"])
    paid = money(amount - money(row["outstanding_balance"]))
    due = ZERO
    due_period = row["repayment_start_month"]
    for index, scheduled in enumerate(_installments(amount, row["repayment_months"])):
        installment_period = _add_months(row["repayment_start_month"], index)
        applied = min(scheduled, paid)
        paid = money(paid - applied)
        remaining = money(scheduled - applied)
        if remaining > ZERO and installment_period <= period_start:
            if due == ZERO:
                due_period = installment_period
            due = money(due + remaining)
    return due_period, min(due, money(row["outstanding_balance"]))


def _source_audit_metadata(entries: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = {name: [] for name in SOURCE_TYPES}
    for entry in entries:
        snapshot = cast(dict[str, object], entry["source_snapshot"])
        inputs = cast(list[dict[str, object]], snapshot.get("automaticInputs", []))
        for item in inputs:
            source_type = str(item["sourceType"])
            if source_type in grouped:
                grouped[source_type].append(item)
    return {
        "counts": {name: len(grouped[name]) for name in SOURCE_TYPES},
        "digests": {
            name: _digest(
                sorted(
                    grouped[name],
                    key=lambda item: (str(item["sourceId"]), str(item["sourceVersion"])),
                )
            )
            for name in SOURCE_TYPES
        },
    }


def _adjustment_dict(item: PayrollAdjustmentRequest | dict[str, object]) -> dict[str, object]:
    if isinstance(item, PayrollAdjustmentRequest):
        return item.model_dump(mode="json", by_alias=True)
    return {
        "id": str(item["id"]),
        "code": str(item["code"]),
        "label": str(item["label"]),
        "amount": f"{money(str(item['amount'])):.2f}",
        "recurrence": str(item["recurrence"]),
        "note": item.get("note"),
    }


def _same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        utc_value = value.astimezone(UTC)
        return utc_value.replace(microsecond=utc_value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


def _preview(values: EntryValues) -> PayrollEntryPreview:
    return PayrollEntryPreview(
        basic_salary=f"{values.basic_salary:.2f}",
        housing_allowance=f"{values.housing_allowance:.2f}",
        transport_allowance=f"{values.transport_allowance:.2f}",
        fixed_allowance=f"{values.fixed_allowance:.2f}",
        fixed_pay=f"{values.fixed_pay:.2f}",
        gross_pay=f"{values.gross_pay:.2f}",
        total_deductions=f"{values.total_deductions:.2f}",
        net_pay=f"{values.net_pay:.2f}",
        wps_basic_pay=f"{values.wps_basic_pay:.2f}",
        wps_variable_pay=f"{values.wps_variable_pay:.2f}",
    )


def _adjustment_response(item: dict[str, object]) -> PayrollAdjustmentResponse:
    return PayrollAdjustmentResponse.model_validate(_adjustment_dict(item))


def _entry_response(row: RowMapping) -> PayrollEntryResponse:
    additions = cast(list[dict[str, object]], row["additional_allowances"] or [])
    deductions = cast(list[dict[str, object]], row["deductions"] or [])
    values = calculate_entry(
        basic_salary=row["basic_salary"],
        housing_allowance=row["housing_allowance"],
        transport_allowance=row["transport_allowance"],
        fixed_allowance=row["allowance"],
        increment=row["increment"],
        bonus=row["bonus"],
        other_pay=row["other_pay"],
        variable_allowance=row["variable_allowance"],
        leave_deduction=row["leave_deduction"],
        additional_allowances=additions,
        deductions=deductions,
    )
    snapshot = dict(row["source_snapshot"] or {})
    return PayrollEntryResponse(
        id=row["id"],
        employee_id=row["employee_id"],
        employee_name=row["employee_name"],
        basic_salary=f"{values.basic_salary:.2f}",
        housing_allowance=f"{values.housing_allowance:.2f}",
        transport_allowance=f"{values.transport_allowance:.2f}",
        fixed_allowance=f"{values.fixed_allowance:.2f}",
        increment=f"{values.increment:.2f}",
        bonus=f"{values.bonus:.2f}",
        other_pay=f"{values.other_pay:.2f}",
        variable_allowance=f"{values.variable_allowance:.2f}",
        leave_deduction=f"{values.leave_deduction:.2f}",
        fixed_pay=f"{values.fixed_pay:.2f}",
        gross_pay=f"{values.gross_pay:.2f}",
        total_deductions=f"{values.total_deductions:.2f}",
        net_pay=f"{values.net_pay:.2f}",
        wps_basic_pay=f"{values.wps_basic_pay:.2f}",
        wps_variable_pay=f"{values.wps_variable_pay:.2f}",
        excluded=row["excluded"],
        additional_allowances=[_adjustment_response(item) for item in additions],
        deductions=[_adjustment_response(item) for item in deductions],
        source_explanations=list(snapshot.get("sourceExplanations", [])),
        source_fingerprint=_digest(snapshot),
    )


def _source_warnings(rows: list[RowMapping]) -> list[str]:
    values: set[str] = set()
    for row in rows:
        snapshot = dict(row["source_snapshot"] or {})
        values.update(str(item) for item in snapshot.get("sourceWarnings", []))
    return sorted(values)


def _validation(
    entries: list[PayrollEntryResponse], source_warnings: list[str]
) -> tuple[Literal["valid", "blocking"], list[str]]:
    errors = [
        f"negative_net_pay:{item.employee_id}"
        for item in entries
        if not item.excluded and Decimal(item.net_pay) < ZERO
    ]
    errors.extend(
        f"payroll_input_not_ready:{item.removesuffix('_input_not_ready')}"
        for item in source_warnings
    )
    return ("blocking" if errors else "valid"), errors


def _run_response(
    row: RowMapping, entries: list[PayrollEntryResponse], source_warnings: list[str]
) -> PayrollRunResponse:
    validation_status, errors = _validation(entries, source_warnings)
    return PayrollRunResponse(
        id=row["id"],
        period=row["period"],
        payment_date=row["payment_date"],
        sequence=row["sequence_no"],
        run_status=row["status"],
        approval_status=row["approval_status"],
        employee_count=row["employee_count"],
        total_amount=f"{money(row['total_disbursed']):.2f}",
        validation_status=validation_status,
        blocking_errors=errors,
        source_warnings=source_warnings,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _payslip_response(row: RowMapping) -> PayslipResponse:
    snapshot = dict(row["data_snapshot"])
    return PayslipResponse(
        id=row["id"],
        period=row["period"],
        payment_date=row["payment_date"],
        employee_name=str(snapshot["employeeName"]),
        earnings=[PayslipLineResponse.model_validate(item) for item in snapshot["earnings"]],
        deductions=[PayslipLineResponse.model_validate(item) for item in snapshot["deductions"]],
        gross_pay=f"{money(row['gross_pay']):.2f}",
        total_deductions=str(snapshot["totalDeductions"]),
        net_pay=f"{money(row['net_pay']):.2f}",
        wps_basic_pay=str(snapshot["wpsBasicPay"]),
        wps_variable_pay=str(snapshot["wpsVariablePay"]),
        issued_at=row["issued_at"],
    )


class PayrollService:
    def __init__(self, connection: AsyncConnection, cursor_codec: EmployeeCursorCodec) -> None:
        self.connection = connection
        self.repository = PayrollRepository(connection)
        self.cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN or principal.employee_id is not None:
            raise ServiceExecutionError("operation_not_permitted")

    def _decode(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: PayrollListQuery,
    ) -> uuid.UUID | None:
        try:
            return self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_payroll_runs",
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None

    async def list_runs(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: PayrollListQuery,
    ) -> tuple[list[PayrollRunResponse], str | None]:
        self._admin(principal)
        cursor_id = self._decode(principal, branch_id, query)
        rows = await self.repository.list_runs(
            company_id=principal.company_id,
            branch_id=branch_id,
            period=query.period,
            run_status=query.run_status,
            approval_status=query.approval_status,
            cursor_id=cursor_id,
            limit=query.limit + 1,
        )
        visible = rows[: query.limit]
        responses: list[PayrollRunResponse] = []
        for row in visible:
            entry_rows = await self.repository.entries(row["id"])
            entries = [_entry_response(item) for item in entry_rows]
            responses.append(_run_response(row, entries, _source_warnings(entry_rows)))
        next_cursor = None
        if len(rows) > query.limit and visible:
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_payroll_runs",
                query=query,
                last_id=visible[-1]["id"],
            )
        return responses, next_cursor

    async def detail(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> PayrollRunDetailResponse:
        self._admin(principal)
        row = await self.repository.get_run(principal.company_id, branch_id, run_id)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        entry_rows = await self.repository.entries(run_id)
        entries = [_entry_response(item) for item in entry_rows]
        base = _run_response(row, entries, _source_warnings(entry_rows)).model_dump()
        return PayrollRunDetailResponse(**base, entries=entries)

    async def approval_history(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> list[PayrollApprovalHistoryResponse]:
        self._admin(principal)
        if await self.repository.get_run(principal.company_id, branch_id, run_id) is None:
            raise ServiceExecutionError("resource_not_found")
        return [
            PayrollApprovalHistoryResponse(
                id=row["id"],
                action=row["action"],
                actor_name=row["actor_name"],
                reason=row["notes"] or None,
                created_at=row["created_at"],
            )
            for row in await self.repository.approval_history(run_id)
        ]

    async def list_self_payslips(
        self, principal: AuthorizationPrincipal, query: PayslipListQuery
    ) -> tuple[list[PayslipResponse], str | None]:
        if (
            principal.role is not AppRole.EMPLOYEE
            or principal.employee_id is None
            or principal.branch_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        try:
            cursor_id = self.cursor_codec.decode(
                principal=principal,
                branch_id=principal.branch_id,
                operation_id="list_self_payslips",
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self.repository.list_self_payslips(
            company_id=principal.company_id,
            branch_id=principal.branch_id,
            employee_id=principal.employee_id,
            cursor_id=cursor_id,
            limit=query.limit + 1,
        )
        visible = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit and visible:
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=principal.branch_id,
                operation_id="list_self_payslips",
                query=query,
                last_id=visible[-1]["id"],
            )
        return [_payslip_response(row) for row in visible], next_cursor

    async def get_self_payslip(
        self, principal: AuthorizationPrincipal, payslip_id: uuid.UUID
    ) -> PayslipResponse:
        if (
            principal.role is not AppRole.EMPLOYEE
            or principal.employee_id is None
            or principal.branch_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        row = await self.repository.get_self_payslip(
            company_id=principal.company_id,
            branch_id=principal.branch_id,
            employee_id=principal.employee_id,
            payslip_id=payslip_id,
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return _payslip_response(row)

    async def _validate_period_and_payment(self, period: str, payment_date: date) -> None:
        business_date = await self.repository.business_date()
        period_start, period_end = _period_dates(period)
        if period_start > business_date.replace(day=1):
            raise ServiceExecutionError("validation_failed")
        if payment_date < period_start or payment_date > period_end + timedelta(days=31):
            raise ServiceExecutionError("validation_failed")

    async def _locked(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> RowMapping:
        self._admin(principal)
        row = await self.repository.get_run_for_action(principal.company_id, branch_id, run_id)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        return row

    @staticmethod
    def _draft_version(row: RowMapping, expected: datetime) -> None:
        if (
            not _same_version(row["updated_at"], expected)
            or row["status"] != "draft"
            or row["approval_status"] != "draft"
        ):
            raise ServiceExecutionError("stale_financial_state")

    async def _employee_entries(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        preserved: dict[uuid.UUID, ManualValues],
    ) -> list[dict[str, object]]:
        start, end = _period_dates(period)
        leave_inputs = await self.repository.lock_leave_inputs(
            company_id=principal.company_id,
            branch_id=branch_id,
            period_start=start,
            period_end=end,
        )
        attendance_inputs = await self.repository.attendance_input_projection(
            company_id=principal.company_id,
            branch_id=branch_id,
            period=period,
        )
        roster_inputs = await self.repository.roster_input_projection(
            company_id=principal.company_id,
            branch_id=branch_id,
            period=period,
        )
        expense_inputs = await self.repository.lock_expense_inputs(
            company_id=principal.company_id,
            branch_id=branch_id,
            period_start=start,
            period_end=end,
        )
        advance_inputs = await self.repository.lock_advance_inputs(
            company_id=principal.company_id,
            branch_id=branch_id,
            period_start=start,
        )
        employees = await self.repository.eligible_employees(
            company_id=principal.company_id,
            branch_id=branch_id,
            period_start=start,
            period_end=end,
        )
        leave_by_employee: defaultdict[uuid.UUID, list[RowMapping]] = defaultdict(list)
        attendance_by_employee: dict[uuid.UUID, RowMapping] = {}
        expense_by_employee: defaultdict[uuid.UUID, list[RowMapping]] = defaultdict(list)
        advance_by_employee: defaultdict[uuid.UUID, list[RowMapping]] = defaultdict(list)
        for item in leave_inputs:
            leave_by_employee[item["employee_id"]].append(item)
        for item in attendance_inputs or []:
            attendance_by_employee[item["employee_id"]] = item
        for item in expense_inputs:
            expense_by_employee[item["employee_id"]].append(item)
        for item in advance_inputs:
            advance_by_employee[item["employee_id"]].append(item)
        source_warnings: list[str] = []
        if attendance_inputs is None:
            source_warnings.append("attendance_input_not_ready")
        if roster_inputs is None:
            source_warnings.append("roster_input_not_ready")
        result: list[dict[str, object]] = []
        for employee in employees:
            eligible_start = max(start, employee["employment_start_date"] or start)
            eligible_end = min(end, employee["termination_date"] or end)
            days = (eligible_end - eligible_start).days + 1
            period_days = end.day
            manual = preserved.get(employee["id"])
            additions = list(manual["additional_allowances"]) if manual else []
            deductions = list(manual["deductions"]) if manual else []
            automatic_inputs: list[dict[str, object]] = []
            explanations: list[str] = []
            leave_deduction = ZERO

            for leave in leave_by_employee[employee["id"]]:
                overlap_start = max(start, leave["start_date"])
                overlap_end = min(end, leave["end_date"])
                overlap_days = Decimal((overlap_end - overlap_start).days + 1)
                if leave["is_half_day"]:
                    overlap_days = Decimal("0.5")
                amount = money(Decimal(employee["basic_salary"]) / Decimal(30) * overlap_days)
                leave_deduction = money(leave_deduction + amount)
                source_version = max(leave["request_updated_at"], leave["leave_type_updated_at"])
                automatic_inputs.append(
                    _automatic_source(
                        source_type="leave",
                        source_id=leave["source_id"],
                        source_version=source_version,
                        period=period,
                        direction="deduction",
                        amount=amount,
                        calculation_inputs={
                            "basicSalary": f"{money(employee['basic_salary']):.2f}",
                            "days": f"{overlap_days:.2f}",
                            "leaveTypeCode": leave["leave_type_code"],
                        },
                    )
                )
                explanations.append(
                    f"Approved {leave['leave_type_code']} leave deducted AED {amount:.2f}."
                )

            attendance = attendance_by_employee.get(employee["id"])
            if attendance is not None:
                source_rows = [str(value) for value in attendance["source_row_ids"]]
                deduction_amount = money(
                    Decimal(attendance["absence_amount"]) + Decimal(attendance["late_amount"])
                )
                overtime_amount = money(
                    Decimal(attendance["standard_overtime_amount"])
                    + Decimal(attendance["rest_day_overtime_amount"])
                )
                if deduction_amount > ZERO:
                    source_id = uuid.uuid5(
                        AUTOMATIC_NAMESPACE,
                        f"attendance:{attendance['period_version_id']}:{employee['id']}:deduction",
                    )
                    deductions.append(
                        automatic_adjustment(
                            "attendance", source_id, "Attendance deductions", deduction_amount
                        )
                    )
                    automatic_inputs.append(
                        _automatic_source(
                            source_type="attendance",
                            source_id=source_id,
                            source_version=attendance["source_version"],
                            period=period,
                            direction="deduction",
                            amount=deduction_amount,
                            calculation_inputs={
                                "absenceAmount": f"{Decimal(attendance['absence_amount']):.2f}",
                                "absenceDays": f"{Decimal(attendance['absence_days']):.2f}",
                                "closedAt": _iso(attendance["closed_at"]),
                                "lateAmount": f"{Decimal(attendance['late_amount']):.2f}",
                                "lateMinutes": int(attendance["late_minutes"]),
                                "sourceRowIds": source_rows,
                            },
                        )
                    )
                    explanations.append(f"Attendance deducted AED {deduction_amount:.2f}.")
                if overtime_amount > ZERO:
                    rest_amount = f"{Decimal(attendance['rest_day_overtime_amount']):.2f}"
                    rest_hours = f"{Decimal(attendance['rest_day_overtime_hours']):.2f}"
                    standard_amount = f"{Decimal(attendance['standard_overtime_amount']):.2f}"
                    standard_hours = f"{Decimal(attendance['standard_overtime_hours']):.2f}"
                    source_id = uuid.uuid5(
                        AUTOMATIC_NAMESPACE,
                        f"attendance:{attendance['period_version_id']}:{employee['id']}:overtime",
                    )
                    additions.append(
                        automatic_adjustment(
                            "attendance", source_id, "Attendance overtime", overtime_amount
                        )
                    )
                    automatic_inputs.append(
                        _automatic_source(
                            source_type="attendance",
                            source_id=source_id,
                            source_version=attendance["source_version"],
                            period=period,
                            direction="addition",
                            amount=overtime_amount,
                            calculation_inputs={
                                "closedAt": _iso(attendance["closed_at"]),
                                "restDayOvertimeAmount": rest_amount,
                                "restDayOvertimeHours": rest_hours,
                                "sourceRowIds": source_rows,
                                "standardOvertimeAmount": standard_amount,
                                "standardOvertimeHours": standard_hours,
                            },
                        )
                    )
                    explanations.append(f"Attendance overtime added AED {overtime_amount:.2f}.")

            for expense in expense_by_employee[employee["id"]]:
                amount = money(expense["amount"])
                additions.append(
                    automatic_adjustment(
                        "expense", expense["source_id"], "Expense reimbursement", amount
                    )
                )
                automatic_inputs.append(
                    _automatic_source(
                        source_type="expense",
                        source_id=expense["source_id"],
                        source_version=expense["source_version"],
                        period=period,
                        direction="addition",
                        amount=amount,
                        calculation_inputs={"expenseDate": str(expense["expense_date"])},
                    )
                )
                explanations.append(f"Approved expense reimbursed AED {amount:.2f}.")

            before_advances = calculate_entry(
                basic_salary=prorate(employee["basic_salary"], days, period_days),
                housing_allowance=prorate(employee["housing_allowance"], days, period_days),
                transport_allowance=prorate(employee["transport_allowance"], days, period_days),
                fixed_allowance=prorate(employee["allowance"], days, period_days),
                increment=manual["increment"] if manual else ZERO,
                bonus=manual["bonus"] if manual else ZERO,
                other_pay=manual["other_pay"] if manual else ZERO,
                variable_allowance=manual["variable_allowance"] if manual else ZERO,
                leave_deduction=leave_deduction,
                additional_allowances=additions,
                deductions=deductions,
            )
            available = max(before_advances.net_pay, ZERO)
            due_advances = [
                (*advance_due(advance, start), advance)
                for advance in advance_by_employee[employee["id"]]
            ]
            due_advances.sort(
                key=lambda item: (item[0], item[2]["created_at"], item[2]["source_id"])
            )
            for due_period, due, advance in due_advances:
                if due <= ZERO:
                    continue
                amount = min(due, available)
                available = money(available - amount)
                deductions.append(
                    automatic_adjustment(
                        "advance", advance["source_id"], "Advance repayment", amount
                    )
                )
                automatic_inputs.append(
                    _automatic_source(
                        source_type="advance",
                        source_id=advance["source_id"],
                        source_version=advance["source_version"],
                        period=period,
                        direction="deduction",
                        amount=amount,
                        calculation_inputs={
                            "availablePayCapacity": f"{money(available + amount):.2f}",
                            "dueAmount": f"{due:.2f}",
                            "duePeriod": due_period.strftime("%Y-%m"),
                            "outstandingBalance": f"{money(advance['outstanding_balance']):.2f}",
                        },
                    )
                )
                explanations.append(f"Advance repayment deducted AED {amount:.2f}.")

            values = calculate_entry(
                basic_salary=prorate(employee["basic_salary"], days, period_days),
                housing_allowance=prorate(employee["housing_allowance"], days, period_days),
                transport_allowance=prorate(employee["transport_allowance"], days, period_days),
                fixed_allowance=prorate(employee["allowance"], days, period_days),
                increment=manual["increment"] if manual else ZERO,
                bonus=manual["bonus"] if manual else ZERO,
                other_pay=manual["other_pay"] if manual else ZERO,
                variable_allowance=manual["variable_allowance"] if manual else ZERO,
                leave_deduction=leave_deduction,
                additional_allowances=additions,
                deductions=deductions,
            )
            snapshot: dict[str, object] = {
                "automaticInputs": automatic_inputs,
                "effectiveDate": _iso(employee["updated_at"]),
                "eligibleDays": days,
                "employmentStartDate": str(employee["employment_start_date"])
                if employee["employment_start_date"]
                else None,
                "employeeSourceVersion": _iso(employee["updated_at"]),
                "manualAdjustments": {
                    "allowances": manual_adjustments(additions),
                    "deductions": manual_adjustments(deductions),
                },
                "periodDays": period_days,
                "salary": {
                    "allowance": f"{money(employee['allowance']):.2f}",
                    "basicSalary": f"{money(employee['basic_salary']):.2f}",
                    "housingAllowance": f"{money(employee['housing_allowance']):.2f}",
                    "transportAllowance": f"{money(employee['transport_allowance']):.2f}",
                },
                "sourceExplanations": explanations,
                "sourceWarnings": source_warnings,
                "terminationDate": str(employee["termination_date"])
                if employee["termination_date"]
                else None,
            }
            result.append(
                self._stored(
                    employee["id"],
                    values,
                    additions,
                    deductions,
                    manual["excluded"] if manual else False,
                    snapshot,
                )
            )
        return _stamp_digest(result)

    @staticmethod
    def _stored(
        employee_id: uuid.UUID,
        values: EntryValues,
        additions: list[dict[str, object]],
        deductions: list[dict[str, object]],
        excluded: bool,
        snapshot: dict[str, object],
    ) -> dict[str, object]:
        return {
            "employee_id": str(employee_id),
            "basic_salary": f"{values.basic_salary:.2f}",
            "housing_allowance": f"{values.housing_allowance:.2f}",
            "transport_allowance": f"{values.transport_allowance:.2f}",
            "allowance": f"{values.fixed_allowance:.2f}",
            "increment": f"{values.increment:.2f}",
            "bonus": f"{values.bonus:.2f}",
            "other_pay": f"{values.other_pay:.2f}",
            "leave_deduction": f"{values.leave_deduction:.2f}",
            "variable_allowance": f"{values.variable_allowance:.2f}",
            "additional_allowances": additions,
            "deductions": deductions,
            "excluded": excluded,
            "source_snapshot": snapshot,
            "calculated_net_pay": f"{values.net_pay:.2f}",
        }

    async def create(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: PayrollCreateRequest,
        *,
        recurring: dict[uuid.UUID, ManualValues] | None = None,
    ) -> PayrollRunDetailResponse:
        self._admin(principal)
        await self._validate_period_and_payment(request.period, request.payment_date)
        branch = await self.repository.lock_branch(principal.company_id, branch_id)
        if branch is None:
            raise ServiceExecutionError("resource_not_found")
        existing = await self.repository.list_runs(
            company_id=principal.company_id,
            branch_id=branch_id,
            period=request.period,
            run_status=None,
            approval_status=None,
            cursor_id=None,
            limit=1,
        )
        if existing:
            raise ServiceExecutionError("stale_financial_state")
        run_id = uuid.uuid4()
        await self.repository.create_run(
            run_id=run_id,
            company_id=principal.company_id,
            branch_id=branch_id,
            period=request.period,
            payment_date=request.payment_date,
            sequence="0001",
            routing_code=branch["default_bank_routing_code"],
            actor_id=principal.app_user_id,
        )
        await append_audit_event(
            self.connection,
            action="payroll_draft_created",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "period",
                "payment_date",
                "sequence_no",
                "scr_bank_routing_code",
                "status",
                "approval_status",
            ],
            reason="Payroll draft created",
        )
        entries = await self._employee_entries(
            principal, branch_id, request.period, recurring or {}
        )
        if not entries:
            raise ServiceExecutionError("validation_failed")
        await self.repository.replace_entries(run_id, entries)
        await append_audit_event(
            self.connection,
            action="payroll_inputs_refreshed",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "source_snapshot_digest",
                "employee_count",
                "total_disbursed",
                "updated_at",
            ],
            reason="Payroll inputs refreshed",
            metadata=_source_audit_metadata(entries),
        )
        return await self.detail(principal, branch_id, run_id)

    async def repeat(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollRepeatRequest,
    ) -> PayrollRunDetailResponse:
        source = await self._locked(principal, branch_id, run_id)
        self._draft_version(source, request.expected_updated_at)
        recurring: dict[uuid.UUID, ManualValues] = {}
        for row in await self.repository.entries(run_id):
            recurring[row["employee_id"]] = {
                "increment": ZERO,
                "bonus": ZERO,
                "other_pay": ZERO,
                "variable_allowance": ZERO,
                "additional_allowances": [
                    item
                    for item in row["additional_allowances"]
                    if item.get("recurrence") == "recurring" and not is_automatic_adjustment(item)
                ],
                "deductions": [
                    item
                    for item in row["deductions"]
                    if item.get("recurrence") == "recurring" and not is_automatic_adjustment(item)
                ],
                "excluded": False,
            }
        return await self.create(principal, branch_id, request, recurring=recurring)

    async def refresh(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollVersionRequest,
    ) -> PayrollRunDetailResponse:
        row = await self._locked(principal, branch_id, run_id)
        self._draft_version(row, request.expected_updated_at)
        preserved: dict[uuid.UUID, ManualValues] = {}
        for entry in await self.repository.entries(run_id):
            preserved[entry["employee_id"]] = {
                "increment": entry["increment"],
                "bonus": entry["bonus"],
                "other_pay": entry["other_pay"],
                "variable_allowance": entry["variable_allowance"],
                "additional_allowances": manual_adjustments(list(entry["additional_allowances"])),
                "deductions": manual_adjustments(list(entry["deductions"])),
                "excluded": entry["excluded"],
            }
        entries = await self._employee_entries(principal, branch_id, row["period"], preserved)
        if not entries:
            raise ServiceExecutionError("validation_failed")
        await self.repository.replace_entries(run_id, entries)
        await append_audit_event(
            self.connection,
            action="payroll_inputs_refreshed",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "source_snapshot_digest",
                "employee_count",
                "total_disbursed",
                "updated_at",
            ],
            reason="Payroll inputs refreshed",
            metadata=_source_audit_metadata(entries),
        )
        return await self.detail(principal, branch_id, run_id)

    async def save_entries(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollEntriesRequest,
    ) -> PayrollRunDetailResponse:
        row = await self._locked(principal, branch_id, run_id)
        self._draft_version(row, request.expected_updated_at)
        start, end = _period_dates(row["period"])
        existing_rows = await self.repository.entries(run_id)
        existing_by_employee = {item["employee_id"]: item for item in existing_rows}
        employees = await self.repository.eligible_employees(
            company_id=principal.company_id,
            branch_id=branch_id,
            period_start=start,
            period_end=end,
        )
        employee_by_id = {item["id"]: item for item in employees}
        request_employee_ids = {item.employee_id for item in request.entries}
        if (
            set(employee_by_id) != request_employee_ids
            or set(existing_by_employee) != request_employee_ids
        ):
            raise ServiceExecutionError("validation_failed")
        stored: list[dict[str, object]] = []
        for item in request.entries:
            employee = employee_by_id[item.employee_id]
            existing = existing_by_employee[item.employee_id]
            eligible_start = max(start, employee["employment_start_date"] or start)
            eligible_end = min(end, employee["termination_date"] or end)
            days = (eligible_end - eligible_start).days + 1
            manual_additions = [_adjustment_dict(value) for value in item.additional_allowances]
            manual_deductions = [_adjustment_dict(value) for value in item.deductions]
            automatic_additions = [
                dict(value)
                for value in existing["additional_allowances"]
                if is_automatic_adjustment(value)
            ]
            automatic_deductions = [
                dict(value) for value in existing["deductions"] if is_automatic_adjustment(value)
            ]
            additions = manual_additions + automatic_additions
            deductions = manual_deductions + automatic_deductions
            values = calculate_entry(
                basic_salary=prorate(employee["basic_salary"], days, end.day),
                housing_allowance=prorate(employee["housing_allowance"], days, end.day),
                transport_allowance=prorate(employee["transport_allowance"], days, end.day),
                fixed_allowance=prorate(employee["allowance"], days, end.day),
                increment=item.increment,
                bonus=item.bonus,
                other_pay=item.other_pay,
                variable_allowance=item.variable_allowance,
                leave_deduction=existing["leave_deduction"],
                additional_allowances=additions,
                deductions=deductions,
            )
            if item.preview != _preview(values):
                raise ServiceExecutionError("validation_failed")
            snapshot = dict(existing["source_snapshot"] or {})
            snapshot.update(
                {
                    "effectiveDate": _iso(employee["updated_at"]),
                    "eligibleDays": days,
                    "employmentStartDate": str(employee["employment_start_date"])
                    if employee["employment_start_date"]
                    else None,
                    "employeeSourceVersion": _iso(employee["updated_at"]),
                    "manualAdjustments": {
                        "allowances": manual_additions,
                        "deductions": manual_deductions,
                    },
                    "periodDays": end.day,
                    "salary": {
                        "allowance": f"{money(employee['allowance']):.2f}",
                        "basicSalary": f"{money(employee['basic_salary']):.2f}",
                        "housingAllowance": f"{money(employee['housing_allowance']):.2f}",
                        "transportAllowance": f"{money(employee['transport_allowance']):.2f}",
                    },
                    "terminationDate": str(employee["termination_date"])
                    if employee["termination_date"]
                    else None,
                }
            )
            stored.append(
                {
                    **self._stored(
                        item.employee_id,
                        values,
                        additions,
                        deductions,
                        item.excluded,
                        snapshot,
                    ),
                    "leave_deduction": f"{money(existing['leave_deduction']):.2f}",
                }
            )
        await self.repository.replace_entries(run_id, _stamp_digest(stored))
        await append_audit_event(
            self.connection,
            action="payroll_entries_replaced",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "source_snapshot_digest",
                "employee_count",
                "total_disbursed",
                "updated_at",
            ],
            reason="Payroll entries replaced",
        )
        return await self.detail(principal, branch_id, run_id)

    @staticmethod
    def _preserved(rows: list[RowMapping]) -> dict[uuid.UUID, ManualValues]:
        return {
            row["employee_id"]: ManualValues(
                increment=row["increment"],
                bonus=row["bonus"],
                other_pay=row["other_pay"],
                variable_allowance=row["variable_allowance"],
                additional_allowances=manual_adjustments(
                    [dict(item) for item in row["additional_allowances"]]
                ),
                deductions=manual_adjustments([dict(item) for item in row["deductions"]]),
                excluded=row["excluded"],
            )
            for row in rows
        }

    @staticmethod
    def _stored_row(row: RowMapping) -> dict[str, object]:
        additions = [dict(item) for item in row["additional_allowances"]]
        deductions = [dict(item) for item in row["deductions"]]
        values = calculate_entry(
            basic_salary=row["basic_salary"],
            housing_allowance=row["housing_allowance"],
            transport_allowance=row["transport_allowance"],
            fixed_allowance=row["allowance"],
            increment=row["increment"],
            bonus=row["bonus"],
            other_pay=row["other_pay"],
            variable_allowance=row["variable_allowance"],
            leave_deduction=row["leave_deduction"],
            additional_allowances=additions,
            deductions=deductions,
        )
        return {
            "employee_id": str(row["employee_id"]),
            "basic_salary": f"{money(row['basic_salary']):.2f}",
            "housing_allowance": f"{money(row['housing_allowance']):.2f}",
            "transport_allowance": f"{money(row['transport_allowance']):.2f}",
            "allowance": f"{money(row['allowance']):.2f}",
            "increment": f"{money(row['increment']):.2f}",
            "bonus": f"{money(row['bonus']):.2f}",
            "other_pay": f"{money(row['other_pay']):.2f}",
            "leave_deduction": f"{money(row['leave_deduction']):.2f}",
            "variable_allowance": f"{money(row['variable_allowance']):.2f}",
            "additional_allowances": additions,
            "deductions": deductions,
            "excluded": row["excluded"],
            "source_snapshot": dict(row["source_snapshot"]),
            "calculated_net_pay": f"{values.net_pay:.2f}",
        }

    async def _approval_recheck(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        row: RowMapping,
        *,
        require_current_sources: bool,
    ) -> list[RowMapping]:
        entry_rows = await self.repository.entries(row["id"])
        if not entry_rows:
            raise ServiceExecutionError("validation_failed")
        rebuilt = await self._employee_entries(
            principal,
            branch_id,
            row["period"],
            self._preserved(entry_rows),
        )
        rebuilt_digest = rebuilt[0]["source_snapshot_digest"] if rebuilt else _digest([])
        stored = [self._stored_row(item) for item in entry_rows]
        stored.sort(key=lambda item: str(item["employee_id"]))
        rebuilt_without_digest = [
            {key: value for key, value in item.items() if key != "source_snapshot_digest"}
            for item in rebuilt
        ]
        rebuilt_without_digest.sort(key=lambda item: str(item["employee_id"]))
        responses = [_entry_response(item) for item in entry_rows]
        warnings = _source_warnings(entry_rows)
        validation_status, _ = _validation(responses, warnings)
        total = money(
            sum(
                (Decimal(item.net_pay) for item in responses if not item.excluded),
                ZERO,
            )
        )
        count = sum(not item.excluded for item in responses)
        consistent = (
            _canonical(stored) == _canonical(rebuilt_without_digest)
            and rebuilt_digest == row["source_snapshot_digest"]
            and total == money(row["total_disbursed"])
            and count == row["employee_count"]
        )
        if require_current_sources and (not consistent or validation_status != "valid"):
            raise ServiceExecutionError("stale_financial_state")
        return entry_rows

    @staticmethod
    def _transition_version(row: RowMapping, request: PayrollVersionRequest) -> None:
        if not _same_version(row["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("stale_financial_state")

    async def submit(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollVersionRequest,
    ) -> PayrollRunDetailResponse:
        row = await self._locked(principal, branch_id, run_id)
        self._transition_version(row, request)
        if row["status"] != "draft" or row["approval_status"] != "draft":
            raise ServiceExecutionError("stale_financial_state")
        await self._approval_recheck(principal, branch_id, row, require_current_sources=True)
        await self.repository.transition(run_id, "submit", "", request.expected_updated_at)
        await append_audit_event(
            self.connection,
            action="payroll_submitted",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "approval_status",
                "submitted_by_app_user_id",
                "submitted_for_approval_at",
            ],
            reason="Payroll submitted for approval",
        )
        return await self.detail(principal, branch_id, run_id)

    async def recall(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollReasonRequest,
    ) -> PayrollRunDetailResponse:
        row = await self._locked(principal, branch_id, run_id)
        self._transition_version(row, request)
        if row["status"] != "draft" or row["approval_status"] != "pending_approval":
            raise ServiceExecutionError("stale_financial_state")
        await self._approval_recheck(principal, branch_id, row, require_current_sources=False)
        await self.repository.transition(
            run_id, "recall", request.reason, request.expected_updated_at
        )
        await append_audit_event(
            self.connection,
            action="payroll_recalled",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "approval_status",
                "submitted_by_app_user_id",
                "submitted_for_approval_at",
            ],
            reason=request.reason,
        )
        return await self.detail(principal, branch_id, run_id)

    async def approve(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollVersionRequest,
    ) -> PayrollRunDetailResponse:
        row = await self._locked(principal, branch_id, run_id)
        self._transition_version(row, request)
        if row["status"] != "draft" or row["approval_status"] != "pending_approval":
            raise ServiceExecutionError("stale_financial_state")
        if principal.app_user_id in {
            row["run_by_app_user_id"],
            row["submitted_by_app_user_id"],
        }:
            raise ServiceExecutionError("operation_not_permitted")
        await self._approval_recheck(principal, branch_id, row, require_current_sources=True)
        await self.repository.transition(run_id, "approve", "", request.expected_updated_at)
        await append_audit_event(
            self.connection,
            action="payroll_approved",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=["approval_status", "approved_by_app_user_id", "approved_at"],
            reason="Payroll approved",
        )
        return await self.detail(principal, branch_id, run_id)

    async def reject(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollReasonRequest,
    ) -> PayrollRunDetailResponse:
        row = await self._locked(principal, branch_id, run_id)
        self._transition_version(row, request)
        if row["status"] != "draft" or row["approval_status"] != "pending_approval":
            raise ServiceExecutionError("stale_financial_state")
        if principal.app_user_id == row["submitted_by_app_user_id"]:
            raise ServiceExecutionError("operation_not_permitted")
        await self._approval_recheck(principal, branch_id, row, require_current_sources=False)
        await self.repository.transition(
            run_id, "reject", request.reason, request.expected_updated_at
        )
        await append_audit_event(
            self.connection,
            action="payroll_rejected",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "approval_status",
                "rejection_reason",
                "rejected_by_app_user_id",
                "rejected_at",
            ],
            reason=request.reason,
        )
        return await self.detail(principal, branch_id, run_id)

    @staticmethod
    def _payslip_snapshot(entry: PayrollEntryResponse) -> dict[str, object]:
        earnings: list[dict[str, object]] = [
            PayslipLineResponse(label=label, amount=amount).model_dump(mode="json", by_alias=True)
            for label, amount in (
                ("Basic salary", entry.basic_salary),
                ("Housing allowance", entry.housing_allowance),
                ("Transport allowance", entry.transport_allowance),
                ("Fixed allowance", entry.fixed_allowance),
                ("Increment", entry.increment),
                ("Bonus", entry.bonus),
                ("Other pay", entry.other_pay),
                ("Variable allowance", entry.variable_allowance),
            )
            if Decimal(amount) != ZERO
        ]
        earnings.extend(
            PayslipLineResponse(label=item.label, amount=item.amount).model_dump(
                mode="json", by_alias=True
            )
            for item in entry.additional_allowances
        )
        deductions: list[dict[str, object]] = []
        if Decimal(entry.leave_deduction) != ZERO:
            deductions.append(
                PayslipLineResponse(
                    label="Leave deduction", amount=entry.leave_deduction
                ).model_dump(mode="json", by_alias=True)
            )
        deductions.extend(
            PayslipLineResponse(label=item.label, amount=item.amount).model_dump(
                mode="json", by_alias=True
            )
            for item in entry.deductions
        )
        return {
            "deductions": deductions,
            "earnings": earnings,
            "employeeName": entry.employee_name,
            "totalDeductions": entry.total_deductions,
            "wpsBasicPay": entry.wps_basic_pay,
            "wpsVariablePay": entry.wps_variable_pay,
        }

    async def generate(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollVersionRequest,
    ) -> PayrollRunDetailResponse:
        row = await self._locked(principal, branch_id, run_id)
        self._transition_version(row, request)
        if row["status"] != "draft" or row["approval_status"] != "approved":
            raise ServiceExecutionError("stale_financial_state")
        entry_rows = await self._approval_recheck(
            principal, branch_id, row, require_current_sources=True
        )
        business_date = await self.repository.business_date()
        payslip_snapshots: list[dict[str, object]] = []
        paid_expenses: set[uuid.UUID] = set()
        repaid_advances: set[uuid.UUID] = set()
        total = ZERO
        count = 0
        for entry_row in entry_rows:
            entry = _entry_response(entry_row)
            if entry.excluded:
                continue
            if Decimal(entry.net_pay) < ZERO:
                raise ServiceExecutionError("validation_failed")
            snapshot = self._payslip_snapshot(entry)
            payslip_snapshots.append(snapshot)
            await self.repository.insert_payslip(
                payslip_id=uuid.uuid5(PAYSLIP_NAMESPACE, f"{run_id}:{entry.employee_id}"),
                run=row,
                employee_id=entry.employee_id,
                gross_pay=Decimal(entry.gross_pay),
                net_pay=Decimal(entry.net_pay),
                snapshot=snapshot,
            )
            total = money(total + Decimal(entry.net_pay))
            count += 1
            source_snapshot = dict(entry_row["source_snapshot"])
            for source in source_snapshot.get("automaticInputs", []):
                source_type = source["sourceType"]
                source_id = uuid.UUID(source["sourceId"])
                amount = Decimal(source["calculatedAmount"])
                if source_type == "expense":
                    if source_id in paid_expenses or not await self.repository.pay_expense(
                        source_id, run_id
                    ):
                        raise ServiceExecutionError("stale_financial_state")
                    paid_expenses.add(source_id)
                    await append_audit_event(
                        self.connection,
                        action="expense_paid",
                        entity_type="expense_claim",
                        entity_id=source_id,
                        changed_fields=["status", "payroll_run_id"],
                        reason="Expense paid through generated payroll",
                    )
                elif source_type == "advance":
                    if source_id in repaid_advances:
                        raise ServiceExecutionError("validation_failed")
                    repaid_advances.add(source_id)
                    repayment = await self.repository.record_advance_repayment(
                        advance_id=source_id,
                        run_id=run_id,
                        repayment_key=uuid.uuid5(REPAYMENT_NAMESPACE, f"{run_id}:{source_id}"),
                        amount=amount,
                        paid_date=business_date,
                    )
                    metadata = {
                        "repayment_id": str(repayment["repaymentId"]),
                        "payroll_run_id": str(run_id),
                        "repayment_kind": "payroll",
                    }
                    await append_audit_event(
                        self.connection,
                        action="salary_advance_repayment_recorded",
                        entity_type="salary_advance",
                        entity_id=source_id,
                        changed_fields=["outstanding_balance", "status"],
                        reason="Advance repayment applied through generated payroll",
                        metadata=metadata,
                    )
                    if repayment["newStatus"] == "settled":
                        await append_audit_event(
                            self.connection,
                            action="salary_advance_settled",
                            entity_type="salary_advance",
                            entity_id=source_id,
                            changed_fields=["status", "outstanding_balance"],
                            reason="Advance settled through generated payroll",
                            metadata=metadata,
                        )
        if total != money(row["total_disbursed"]) or count != row["employee_count"]:
            raise ServiceExecutionError("stale_financial_state")
        await self.repository.generate(
            run_id,
            total=total,
            count=count,
            expected_updated_at=request.expected_updated_at,
        )
        await append_audit_event(
            self.connection,
            action="payroll_generated",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=["status", "total_disbursed", "employee_count"],
            reason="Payroll generated",
        )
        await append_audit_event(
            self.connection,
            action="payslips_issued",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=["status", "total_disbursed", "employee_count"],
            reason="Immutable payslips issued",
            metadata={
                "payslip_count": count,
                "snapshot_digest": _digest(payslip_snapshots),
            },
        )
        return await self.detail(principal, branch_id, run_id)

    async def delete(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: PayrollVersionRequest,
    ) -> None:
        row = await self._locked(principal, branch_id, run_id)
        self._draft_version(row, request.expected_updated_at)
        entries = await self.repository.entries(run_id)
        summary = _digest(
            {
                "entryIds": [str(item["id"]) for item in entries],
                "period": row["period"],
                "runId": str(run_id),
                "sourceSnapshotDigest": row["source_snapshot_digest"],
            }
        )
        await append_audit_event(
            self.connection,
            action="payroll_draft_deleted",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=["status"],
            reason="Payroll draft deleted",
            metadata={"summary_digest": summary},
        )
        await self.repository.replace_entries(run_id, [])
        if not await self.repository.delete_run(run_id):
            raise ServiceExecutionError("stale_financial_state")

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if kind != "payroll_run" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        if not await self.repository.replay_visible(principal.company_id, branch_id, resource_id):
            raise ServiceExecutionError("resource_not_found")
