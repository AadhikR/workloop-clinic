from __future__ import annotations

import calendar
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.wps import WpsRepository
from app.schemas.wps import (
    ComplianceOverrideRequest,
    ComplianceOverrideResponse,
    NafisEmployeeResponse,
    NafisReplaceRequest,
    NafisSnapshotResponse,
    SifEntryResponse,
    SifHeaderResponse,
    SifInputResponse,
    WpsEntryRejectRequest,
    WpsEntryResponse,
    WpsEntryVersionRequest,
    WpsReasonRequest,
    WpsRunResponse,
    WpsSubmitRequest,
    WpsVersionRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError
from app.services.payroll import calculate_entry, money

WHOLE_AED = Decimal("1")
PERCENT = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass(frozen=True, slots=True)
class NafisListQuery:
    limit: int = 50
    cursor: str | None = None
    period: str | None = None


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _same_timestamp(actual: datetime, expected: datetime) -> bool:
    return actual.replace(microsecond=(actual.microsecond // 1000) * 1000) == expected.replace(
        microsecond=(expected.microsecond // 1000) * 1000
    )


def period_dates(period: str) -> tuple[date, date]:
    year, month = (int(part) for part in period.split("-"))
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def integer_aed(value: Decimal) -> int:
    return int(value.quantize(WHOLE_AED, rounding=ROUND_HALF_UP))


def entry_values(row: RowMapping) -> tuple[int, int, int]:
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
        additional_allowances=list(row["additional_allowances"]),
        deductions=list(row["deductions"]),
    )
    basic = integer_aed(values.wps_basic_pay)
    variable = integer_aed(values.wps_variable_pay)
    return basic, variable, basic + variable


def _wps_entry(row: RowMapping) -> WpsEntryResponse:
    return WpsEntryResponse(
        id=row["id"],
        employee_id=row["employee_id"],
        employee_name=row["employee_name"],
        payment_status=row["wps_payment_status"],
        rejection_reason=row["wps_rejection_reason"] or None,
        updated_at=row["updated_at"],
    )


def _wps_response(run: RowMapping, entries: list[RowMapping]) -> WpsRunResponse:
    return WpsRunResponse(
        run_id=run["id"],
        period=run["period"],
        payment_date=run["payment_date"],
        status=run["wps_status"],
        submitted_at=run["wps_submitted_at"],
        confirmed_at=run["wps_confirmed_at"],
        reference_number=run["wps_reference_no"] or None,
        updated_at=run["updated_at"],
        entries=[_wps_entry(item) for item in entries],
    )


def _nafis_response(row: RowMapping) -> NafisSnapshotResponse:
    snapshot = dict(row["snapshot"] or {})
    employees = [
        NafisEmployeeResponse(
            employee_id=item["employeeId"],
            employee_name=item["employeeName"],
            nafis_registration_number=item.get("nafisRegistrationNumber") or None,
            qualifying_basic_wage=item["qualifyingBasicWage"],
        )
        for item in snapshot.get("employees", [])
    ]
    return NafisSnapshotResponse(
        id=row["id"],
        period=row["period"],
        total_headcount=row["total_headcount"],
        emirati_count=row["emirati_count"],
        ratio_percent=f"{Decimal(row['ratio_percent']):.2f}",
        required_percent=f"{Decimal(row['required_percent']):.2f}",
        compliant=row["compliant"],
        source_version=str(snapshot.get("sourceVersion", "")),
        qualifying_wage_total=str(snapshot.get("qualifyingWageTotal", "0.00")),
        employees=employees,
        generated_at=row["generated_at"],
    )


class WpsService:
    def __init__(self, connection: AsyncConnection, cursor_codec: EmployeeCursorCodec) -> None:
        self.connection = connection
        self.repository = WpsRepository(connection)
        self.cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN or principal.employee_id is not None:
            raise ServiceExecutionError("operation_not_permitted")

    async def _run(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> tuple[RowMapping, list[RowMapping]]:
        self._admin(principal)
        run = await self.repository.get_run(principal.company_id, branch_id, run_id)
        if run is None or run["status"] != "generated" or run["approval_status"] != "approved":
            raise ServiceExecutionError("resource_not_found")
        return run, await self.repository.entries(run_id)

    async def get_wps(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, run_id: uuid.UUID
    ) -> WpsRunResponse:
        run, entries = await self._run(principal, branch_id, run_id)
        return _wps_response(run, entries)

    async def sif_input(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        correction: Literal["rejected"] | None = None,
    ) -> SifInputResponse:
        run, entries = await self._run(principal, branch_id, run_id)
        if correction == "rejected":
            if run["wps_status"] != "partial_rejection":
                raise ServiceExecutionError("stale_financial_state")
            entries = [item for item in entries if item["wps_payment_status"] == "rejected"]
        if not entries:
            raise ServiceExecutionError("validation_failed")
        if not run["mol_employer_id"] or not run["scr_bank_routing_code"]:
            raise ServiceExecutionError("validation_failed")
        period_start, period_end = period_dates(run["period"])
        rows: list[SifEntryResponse] = []
        for item in entries:
            if not item["mol_id"] or not item["bank_routing_code"] or not item["iban"]:
                raise ServiceExecutionError("validation_failed")
            basic, variable, total = entry_values(item)
            snapshot = dict(item["source_snapshot"])
            paid_days = int(snapshot.get("eligibleDays", period_end.day))
            if paid_days < 0 or paid_days > period_end.day:
                raise ServiceExecutionError("validation_failed")
            rows.append(
                SifEntryResponse(
                    payroll_entry_id=item["id"],
                    employee_mol_id=item["mol_id"],
                    bank_routing_code=item["bank_routing_code"],
                    iban=item["iban"],
                    period_start=period_start,
                    period_end=period_end,
                    paid_days=paid_days,
                    basic_pay=basic,
                    variable_pay=variable,
                    total_pay=total,
                )
            )
        rows.sort(key=lambda item: (item.employee_mol_id, str(item.payroll_entry_id)))
        header = SifHeaderResponse(
            employer_mol_id=run["mol_employer_id"],
            branch_routing_code=run["scr_bank_routing_code"],
            period_start=period_start,
            period_end=period_end,
            payment_date=run["payment_date"],
            employee_count=len(rows),
            total_integer_pay=sum(item.total_pay for item in rows),
        )
        mode: Literal["full", "rejected"] = "rejected" if correction else "full"
        material = {
            "mode": mode,
            "header": header.model_dump(mode="json", by_alias=True),
            "entries": [item.model_dump(mode="json", by_alias=True) for item in rows],
        }
        return SifInputResponse(mode=mode, digest=_digest(material), header=header, entries=rows)

    async def record_sif_projection(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: WpsVersionRequest,
    ) -> WpsRunResponse:
        run, _ = await self._run(principal, branch_id, run_id)
        if not _same_timestamp(run["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("stale_financial_state")
        correction: Literal["rejected"] | None = (
            "rejected" if run["wps_status"] == "partial_rejection" else None
        )
        if run["wps_status"] not in {"draft", "partial_rejection"}:
            raise ServiceExecutionError("stale_financial_state")
        projection = await self.sif_input(principal, branch_id, run_id, correction)
        await self._transition_run(
            run_id=run_id,
            action="sif_generated",
            expected_updated_at=request.expected_updated_at,
            projection_digest=projection.digest,
            projection_mode=projection.mode,
        )
        await append_audit_event(
            self.connection,
            action="sif_projection_recorded",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=["wps_status", "updated_at"],
            reason="SIF input projection recorded",
            metadata={
                "mode": projection.mode,
                "row_count": projection.header.employee_count,
                "integer_total": projection.header.total_integer_pay,
                "digest": projection.digest,
            },
        )
        return await self.get_wps(principal, branch_id, run_id)

    async def _transition_run(
        self,
        *,
        run_id: uuid.UUID,
        action: str,
        expected_updated_at: datetime,
        reference_number: str = "",
        reason: str = "",
        projection_digest: str = "",
        projection_mode: str = "",
    ) -> None:
        try:
            await self.repository.transition_run(
                run_id=run_id,
                action=action,
                reference_number=reference_number,
                reason=reason,
                expected_updated_at=expected_updated_at,
                projection_digest=projection_digest,
                projection_mode=projection_mode,
            )
        except DBAPIError:
            raise ServiceExecutionError("stale_financial_state") from None

    async def submit(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: WpsSubmitRequest,
    ) -> WpsRunResponse:
        run, _ = await self._run(principal, branch_id, run_id)
        if run["wps_status"] != "sif_generated" or not _same_timestamp(
            run["updated_at"], request.expected_updated_at
        ):
            raise ServiceExecutionError("stale_financial_state")
        await self._transition_run(
            run_id=run_id,
            action="submit",
            expected_updated_at=request.expected_updated_at,
            reference_number=request.reference_number.strip(),
        )
        await self._audit_wps(run_id, "WPS submission recorded")
        return await self.get_wps(principal, branch_id, run_id)

    async def confirm(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: WpsVersionRequest,
    ) -> WpsRunResponse:
        run, entries = await self._run(principal, branch_id, run_id)
        if run["wps_status"] not in {"submitted", "partial_rejection"} or any(
            item["wps_payment_status"] != "paid" for item in entries
        ):
            raise ServiceExecutionError("stale_financial_state")
        await self._transition_run(
            run_id=run_id, action="confirm", expected_updated_at=request.expected_updated_at
        )
        await self._audit_wps(run_id, "WPS payment confirmed")
        return await self.get_wps(principal, branch_id, run_id)

    async def fail(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: WpsReasonRequest,
    ) -> WpsRunResponse:
        run, _ = await self._run(principal, branch_id, run_id)
        if run["wps_status"] == "confirmed":
            raise ServiceExecutionError("stale_financial_state")
        await self._transition_run(
            run_id=run_id,
            action="fail",
            expected_updated_at=request.expected_updated_at,
            reason=request.reason.strip(),
        )
        await self._audit_wps(run_id, request.reason.strip())
        return await self.get_wps(principal, branch_id, run_id)

    async def _audit_wps(self, run_id: uuid.UUID, reason: str) -> None:
        await append_audit_event(
            self.connection,
            action="payroll_wps_changed",
            entity_type="payroll_run",
            entity_id=run_id,
            changed_fields=[
                "wps_status",
                "wps_submitted_at",
                "wps_confirmed_at",
                "wps_reference_no",
            ],
            reason=reason,
        )

    async def mark_entry_paid(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        entry_id: uuid.UUID,
        request: WpsEntryVersionRequest,
    ) -> WpsRunResponse:
        return await self._transition_entry(
            principal, branch_id, run_id, entry_id, "paid", "", request.expected_updated_at
        )

    async def reject_entry(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        entry_id: uuid.UUID,
        request: WpsEntryRejectRequest,
    ) -> WpsRunResponse:
        return await self._transition_entry(
            principal,
            branch_id,
            run_id,
            entry_id,
            "reject",
            request.reason.strip(),
            request.expected_updated_at,
        )

    async def _transition_entry(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        entry_id: uuid.UUID,
        action: str,
        reason: str,
        expected_updated_at: datetime,
    ) -> WpsRunResponse:
        _, entries = await self._run(principal, branch_id, run_id)
        entry = next((item for item in entries if item["id"] == entry_id), None)
        if entry is None:
            raise ServiceExecutionError("resource_not_found")
        if entry["wps_payment_status"] != "pending" or not _same_timestamp(
            entry["updated_at"], expected_updated_at
        ):
            raise ServiceExecutionError("stale_financial_state")
        try:
            await self.repository.transition_entry(
                run_id=run_id,
                entry_id=entry_id,
                action=action,
                reason=reason,
                expected_updated_at=expected_updated_at,
            )
        except DBAPIError:
            raise ServiceExecutionError("stale_financial_state") from None
        await append_audit_event(
            self.connection,
            action="wps_entry_paid" if action == "paid" else "wps_entry_rejected",
            entity_type="payroll_entry",
            entity_id=entry_id,
            changed_fields=["wps_payment_status", "wps_rejection_reason"],
            reason="WPS entry marked paid" if action == "paid" else reason,
        )
        if action == "reject":
            await self._audit_wps(run_id, reason)
        return await self.get_wps(principal, branch_id, run_id)

    async def create_compliance_override(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        run_id: uuid.UUID,
        request: ComplianceOverrideRequest,
    ) -> ComplianceOverrideResponse:
        _, entries = await self._run(principal, branch_id, run_id)
        if request.payroll_entry_id is not None and all(
            item["id"] != request.payroll_entry_id for item in entries
        ):
            raise ServiceExecutionError("resource_not_found")
        override_id = uuid.uuid4()
        try:
            await self.repository.create_override(
                override_id=override_id,
                run_id=run_id,
                entry_id=request.payroll_entry_id,
                rule_code=request.rule_code,
                reason=request.reason.strip(),
            )
        except DBAPIError:
            raise ServiceExecutionError("validation_failed") from None
        await append_audit_event(
            self.connection,
            action="compliance_override_created",
            entity_type="compliance_override",
            entity_id=override_id,
            changed_fields=["rule_code", "reason"],
            reason=request.reason.strip(),
        )
        row = await self.repository.get_override(override_id)
        if row is None:
            raise RuntimeError("created compliance override is not visible")
        return ComplianceOverrideResponse(**dict(row))

    async def list_nafis(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: NafisListQuery,
    ) -> tuple[list[NafisSnapshotResponse], str | None]:
        self._admin(principal)
        try:
            cursor_id = self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_nafis_snapshots",
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self.repository.list_nafis(
            company_id=principal.company_id,
            branch_id=branch_id,
            period=query.period,
            cursor_id=cursor_id,
            limit=query.limit + 1,
        )
        visible = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit and visible:
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_nafis_snapshots",
                query=query,
                last_id=visible[-1]["id"],
            )
        return [_nafis_response(row) for row in visible], next_cursor

    async def replace_nafis_snapshot(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        period: str,
        request: NafisReplaceRequest,
    ) -> NafisSnapshotResponse:
        self._admin(principal)
        _, period_end = period_dates(period)
        company, employees = await self.repository.nafis_sources(
            principal.company_id, branch_id, period_end
        )
        if company is None:
            raise ServiceExecutionError("resource_not_found")
        emirati = [item for item in employees if item["nationality"] == "United Arab Emirates"]
        total = len(employees)
        count = len(emirati)
        ratio = (
            (Decimal(count) * Decimal(100) / Decimal(total)).quantize(PERCENT, ROUND_HALF_UP)
            if total
            else ZERO
        )
        required = money(company["nafis_quota_percent"])
        wage_total = money(sum((Decimal(item["basic_salary"]) for item in emirati), ZERO))
        source_material = {
            "branchUpdatedAt": company["branch_updated_at"].isoformat(),
            "companyUpdatedAt": company["updated_at"].isoformat(),
            "employees": [
                {
                    "basicSalary": f"{money(item['basic_salary']):.2f}",
                    "employeeId": str(item["id"]),
                    "employeeName": item["name"],
                    "employmentStartDate": str(item["employment_start_date"])
                    if item["employment_start_date"]
                    else None,
                    "nationality": item["nationality"],
                    "nafisRegistrationNumber": item["nafis_registration_no"],
                    "terminationDate": str(item["termination_date"])
                    if item["termination_date"]
                    else None,
                    "updatedAt": item["updated_at"].isoformat(),
                }
                for item in employees
            ],
            "period": period,
        }
        source_version = _digest(source_material)
        snapshot: dict[str, object] = {
            "employees": [
                {
                    "employeeId": str(item["id"]),
                    "employeeName": item["name"],
                    "nafisRegistrationNumber": item["nafis_registration_no"],
                    "qualifyingBasicWage": f"{money(item['basic_salary']):.2f}",
                }
                for item in emirati
            ],
            "qualifyingWageTotal": f"{wage_total:.2f}",
            "sourceVersion": source_version,
        }
        snapshot_id = uuid.uuid4()
        try:
            stored_id = await self.repository.replace_nafis(
                snapshot_id=snapshot_id,
                period=period,
                total_headcount=total,
                emirati_count=count,
                ratio_percent=ratio,
                required_percent=required,
                compliant=ratio >= required,
                snapshot=snapshot,
                expected_generated_at=request.expected_generated_at,
            )
        except DBAPIError:
            raise ServiceExecutionError("stale_financial_state") from None
        row = await self.repository.get_nafis(stored_id)
        if row is None:
            raise RuntimeError("replaced Nafis snapshot is not visible")
        await append_audit_event(
            self.connection,
            action="nafis_snapshot_replaced",
            entity_type="nafis_report",
            entity_id=stored_id,
            changed_fields=[
                "total_headcount",
                "emirati_count",
                "ratio_percent",
                "required_percent",
                "compliant",
                "snapshot",
                "generated_at",
            ],
            reason="Trusted Nafis snapshot replaced",
            metadata={"period": period, "source_digest": source_version},
        )
        return _nafis_response(row)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if resource_id is None or not await self.repository.replay_visible(
            principal.company_id, branch_id, kind, resource_id
        ):
            raise ServiceExecutionError("resource_not_found")
