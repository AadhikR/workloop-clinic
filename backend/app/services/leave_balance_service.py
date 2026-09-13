from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.leave_balance import LeaveBalanceRepository, LockedBalanceState
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.leave_balance import LeaveBalanceResponse, LeaveRequestResponse
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError
from app.services.leave_balance import (
    ZERO,
    BalanceInputs,
    accrued_days,
    decimal_days,
    leave_days,
    recompute_balance,
    sick_tiers,
)

LeaveStatus = Literal[
    "Pending",
    "ManagerApproved",
    "ManagerRejected",
    "Approved",
    "Rejected",
    "Cancelled",
]


@dataclass(frozen=True, slots=True)
class BalanceListQuery:
    limit: int
    leave_year: int
    employee_id: uuid.UUID | None
    leave_type_id: uuid.UUID | None
    cursor: str | None


@dataclass(frozen=True, slots=True)
class RequestCalendarQuery:
    limit: int
    leave_year: int
    employee_id: uuid.UUID | None
    leave_type_id: uuid.UUID | None
    status: LeaveStatus | None
    cursor: str | None


class LeaveBalanceService:
    def __init__(
        self,
        connection: AsyncConnection,
        cursor_codec: EmployeeCursorCodec,
        repository: LeaveBalanceRepository | None = None,
    ) -> None:
        self._repository = repository or LeaveBalanceRepository(connection)
        self._cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")

    @staticmethod
    def _staff_identity(principal: AuthorizationPrincipal) -> tuple[uuid.UUID, uuid.UUID]:
        if (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.branch_id is None
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        return principal.branch_id, principal.employee_id

    async def list_self_balances(
        self, principal: AuthorizationPrincipal, query: BalanceListQuery
    ) -> tuple[list[LeaveBalanceResponse], str | None]:
        branch_id, employee_id = self._staff_identity(principal)
        scoped = BalanceListQuery(
            limit=query.limit,
            leave_year=query.leave_year,
            employee_id=employee_id,
            leave_type_id=query.leave_type_id,
            cursor=query.cursor,
        )
        return await self._list_balances(
            principal, branch_id, scoped, operation_id="get_employee_leave_balances"
        )

    async def list_admin_balances(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: BalanceListQuery,
    ) -> tuple[list[LeaveBalanceResponse], str | None]:
        self._admin(principal)
        return await self._list_balances(
            principal, branch_id, query, operation_id="get_admin_leave_balances"
        )

    async def list_approver_balances(
        self, principal: AuthorizationPrincipal, query: BalanceListQuery
    ) -> tuple[list[LeaveBalanceResponse], str | None]:
        branch_id, actor_employee_id = self._staff_identity(principal)
        if query.employee_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        if not await self._repository.approver_can_read_employee(
            principal.company_id,
            branch_id,
            actor_employee_id,
            query.employee_id,
        ):
            raise ServiceExecutionError("resource_not_found")
        return await self._list_balances(
            principal,
            branch_id,
            query,
            operation_id="get_approver_leave_balances",
        )

    async def _list_balances(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: BalanceListQuery,
        *,
        operation_id: str,
    ) -> tuple[list[LeaveBalanceResponse], str | None]:
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                cursor=query.cursor,
            )
            if after_id is not None and not await self._repository.balance_cursor_exists(
                principal.company_id,
                branch_id,
                query.leave_year,
                after_id,
                employee_id=query.employee_id,
                leave_type_id=query.leave_type_id,
            ):
                raise ValueError("invalid cursor")
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.list_balances(
            principal.company_id,
            branch_id,
            query.leave_year,
            employee_id=query.employee_id,
            leave_type_id=query.leave_type_id,
            after_id=after_id,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        next_cursor = None
        if has_more:
            next_cursor = self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                last_id=visible[-1]["id"],
            )
        return [
            LeaveBalanceResponse.model_validate(
                {key: value for key, value in row.items() if key != "id"}
            )
            for row in visible
        ], next_cursor

    async def list_self_requests(
        self, principal: AuthorizationPrincipal, query: RequestCalendarQuery
    ) -> tuple[list[LeaveRequestResponse], str | None]:
        branch_id, employee_id = self._staff_identity(principal)
        scoped = RequestCalendarQuery(
            limit=query.limit,
            leave_year=query.leave_year,
            employee_id=employee_id,
            leave_type_id=query.leave_type_id,
            status=query.status,
            cursor=query.cursor,
        )
        return await self._list_requests(
            principal,
            branch_id,
            scoped,
            operation_id="get_employee_leave_request_calendar",
        )

    async def list_admin_requests(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: RequestCalendarQuery,
    ) -> tuple[list[LeaveRequestResponse], str | None]:
        self._admin(principal)
        return await self._list_requests(
            principal,
            branch_id,
            query,
            operation_id="get_admin_leave_request_calendar",
        )

    async def _list_requests(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: RequestCalendarQuery,
        *,
        operation_id: str,
    ) -> tuple[list[LeaveRequestResponse], str | None]:
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                cursor=query.cursor,
            )
            if after_id is not None and not await self._repository.request_cursor_exists(
                principal.company_id,
                branch_id,
                query.leave_year,
                after_id,
                employee_id=query.employee_id,
                leave_type_id=query.leave_type_id,
                status=query.status,
            ):
                raise ValueError("invalid cursor")
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.list_requests(
            principal.company_id,
            branch_id,
            query.leave_year,
            employee_id=query.employee_id,
            leave_type_id=query.leave_type_id,
            status=query.status,
            after_id=after_id,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        next_cursor = None
        if has_more:
            next_cursor = self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                last_id=visible[-1]["id"],
            )
        years = {
            candidate
            for row in visible
            for candidate in range(row["start_date"].year, row["end_date"].year + 1)
        }
        holidays = await self._repository.holidays(
            principal.company_id, branch_id, years or {query.leave_year}
        )
        settings = await self._settings_for_reads(principal.company_id, branch_id)
        responses: list[LeaveRequestResponse] = []
        for row in visible:
            values = dict(row)
            values["days_requested"] = leave_days(
                row["start_date"],
                row["end_date"],
                day_count_type=row["day_count_type"],
                weekend_definition=settings["weekend_definition"],
                holidays=holidays,
                half_day=row["is_half_day"],
            )
            values["attachment"] = None
            values.pop("day_count_type")
            responses.append(LeaveRequestResponse.model_validate(values))
        return responses, next_cursor

    async def _settings_for_reads(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> dict[str, Any]:
        try:
            settings = await self._repository.settings(company_id, branch_id)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        return dict(settings)

    async def initialize(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, year: int
    ) -> list[LeaveBalanceResponse]:
        return await self._write_balances(principal, branch_id, year, replace_existing=False)

    async def recalculate(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, year: int
    ) -> list[LeaveBalanceResponse]:
        return await self._write_balances(principal, branch_id, year, replace_existing=True)

    async def _write_balances(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        year: int,
        *,
        replace_existing: bool,
    ) -> list[LeaveBalanceResponse]:
        self._admin(principal)
        try:
            state = await self._repository.lock_recalculation_state(
                principal.company_id, branch_id, year
            )
            values = self.balance_rows(state, year, await self._repository.business_date())
            await self._repository.write_balances(
                principal.company_id,
                branch_id,
                year,
                values,
                replace_existing=replace_existing,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None
        rows = await self._repository.list_balances(
            principal.company_id,
            branch_id,
            year,
            employee_id=None,
            leave_type_id=None,
            after_id=None,
            limit=max(1, len(values)),
        )
        return [
            LeaveBalanceResponse.model_validate(
                {key: value for key, value in row.items() if key != "id"}
            )
            for row in rows[: len(values)]
        ]

    @staticmethod
    def _request_days(
        request: dict[str, Any],
        leave_type: dict[str, Any],
        settings: dict[str, Any],
        holidays: list[date],
        year: int,
    ) -> Decimal:
        start = max(request["start_date"], date(year, 1, 1))
        end = min(request["end_date"], date(year, 12, 31))
        if end < start:
            return ZERO
        half_day = bool(request["is_half_day"]) and request["start_date"].year == year
        return leave_days(
            start,
            end,
            day_count_type=leave_type["day_count_type"],
            weekend_definition=settings["weekend_definition"],
            holidays=holidays,
            half_day=half_day,
        )

    @classmethod
    def _request_totals(
        cls,
        related: list[dict[str, Any]],
        leave_type: dict[str, Any],
        settings: dict[str, Any],
        holidays: list[date],
        year: int,
    ) -> tuple[Decimal, Decimal]:
        used = ZERO
        pending = ZERO
        for request in related:
            days = cls._request_days(request, leave_type, settings, holidays, year)
            if request["status"] == "Approved":
                used += days
            elif request["status"] in {"Pending", "ManagerApproved"}:
                pending += days
        return decimal_days(used), decimal_days(pending)

    @classmethod
    def balance_rows(
        cls, state: LockedBalanceState, year: int, business_date: date
    ) -> list[dict[str, object]]:
        settings = dict(state.settings)
        requests = [dict(row) for row in state.requests]
        existing = [dict(row) for row in state.balances]
        rows: list[dict[str, object]] = []
        for employee_row in state.employees:
            employee = dict(employee_row)
            for type_row in state.leave_types:
                leave_type = dict(type_row)
                related = [
                    request
                    for request in requests
                    if request["employee_id"] == employee["id"]
                    and request["leave_type_id"] == leave_type["id"]
                ]

                used, pending = cls._request_totals(
                    related, leave_type, settings, state.holidays, year
                )
                previous_used, previous_pending = cls._request_totals(
                    related, leave_type, settings, state.holidays, year - 1
                )
                eligible = not (
                    employee["employment_status"] == "Probation"
                    and not leave_type["probation_eligible"]
                ) and (
                    leave_type["gender_restriction"] is None
                    or leave_type["gender_restriction"] == employee["gender"]
                )
                previous_carried = next(
                    (
                        balance["carried_forward"]
                        for balance in existing
                        if balance["employee_id"] == employee["id"]
                        and balance["leave_type_id"] == leave_type["id"]
                        and balance["leave_year"] == year - 1
                    ),
                    ZERO,
                )
                previous_accrued = accrued_days(
                    leave_type["annual_entitlement_days"],
                    accrual_type=leave_type["accrual_type"],
                    leave_year=year - 1,
                    business_date=business_date,
                    employment_start_date=employee["employment_start_date"],
                    min_service_months=leave_type["min_service_months"],
                    eligible=eligible,
                )
                previous_remaining = decimal_days(
                    max(
                        ZERO,
                        previous_accrued
                        + decimal_days(previous_carried)
                        - previous_used
                        - previous_pending,
                    )
                )
                hajj_taken = leave_type["once_per_career"] and any(
                    request["status"] == "Approved" for request in related
                )
                full, half, unpaid = (
                    sick_tiers(
                        used,
                        probation=employee["employment_status"] == "Probation",
                    )
                    if leave_type["code"] == "SICK"
                    else (ZERO, ZERO, ZERO)
                )
                calculated = recompute_balance(
                    BalanceInputs(
                        entitlement=leave_type["annual_entitlement_days"],
                        accrual_type=leave_type["accrual_type"],
                        leave_year=year,
                        business_date=business_date,
                        employment_start_date=employee["employment_start_date"],
                        min_service_months=leave_type["min_service_months"],
                        eligible=eligible,
                        previous_remaining=previous_remaining,
                        carry_forward_enabled=settings["carry_forward_enabled"],
                        carry_forward_allowed=leave_type["carry_forward_allowed"],
                        settings_carry_forward_cap=settings["carry_forward_max_days"],
                        type_carry_forward_cap=leave_type["carry_forward_max_days"],
                        used_days=used,
                        pending_days=pending,
                        sick_full_pay_used=full,
                        sick_half_pay_used=half,
                        sick_unpaid_used=unpaid,
                        hajj_taken=hajj_taken,
                        once_per_career=leave_type["once_per_career"],
                        unlimited=leave_type["is_unlimited"],
                    )
                )
                rows.append(
                    {
                        "employee_id": employee["id"],
                        "leave_type_id": leave_type["id"],
                        **calculated,
                    }
                )
        return rows
