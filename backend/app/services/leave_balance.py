from __future__ import annotations

import calendar
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

DAY = Decimal("0.01")
ZERO = Decimal("0.00")
SICK_FULL_PAY_LIMIT = Decimal("15.00")
SICK_HALF_PAY_LIMIT = Decimal("30.00")


def decimal_days(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(DAY, rounding=ROUND_HALF_UP)


def calendar_days(start: date, end: date, *, half_day: bool = False) -> Decimal:
    if end < start:
        raise ValueError("end date precedes start date")
    if half_day and start != end:
        raise ValueError("half-day ranges must contain one date")
    if half_day:
        return Decimal("0.50")
    return decimal_days((end - start).days + 1)


def working_days(
    start: date,
    end: date,
    *,
    weekend_definition: Literal["fri-sat", "sat-sun"],
    holidays: Iterable[date] = (),
    half_day: bool = False,
) -> Decimal:
    if end < start:
        raise ValueError("end date precedes start date")
    if half_day and start != end:
        raise ValueError("half-day ranges must contain one date")
    if weekend_definition not in {"fri-sat", "sat-sun"}:
        raise ValueError("unsupported weekend definition")
    if half_day:
        return Decimal("0.50")
    weekend = {4, 5} if weekend_definition == "fri-sat" else {5, 6}
    holiday_set = set(holidays)
    count = sum(
        1
        for offset in range((end - start).days + 1)
        if (current := start + timedelta(days=offset)).weekday() not in weekend
        and current not in holiday_set
    )
    return decimal_days(count)


def leave_days(
    start: date,
    end: date,
    *,
    day_count_type: Literal["calendar", "working"],
    weekend_definition: Literal["fri-sat", "sat-sun"],
    holidays: Iterable[date] = (),
    half_day: bool = False,
) -> Decimal:
    if day_count_type == "calendar":
        return calendar_days(start, end, half_day=half_day)
    if day_count_type == "working":
        return working_days(
            start,
            end,
            weekend_definition=weekend_definition,
            holidays=holidays,
            half_day=half_day,
        )
    raise ValueError("unsupported day count type")


def completed_service_months(start: date | None, as_of: date) -> int:
    if start is None or start > as_of:
        return 0
    months = (as_of.year - start.year) * 12 + as_of.month - start.month
    if as_of.day < start.day:
        months -= 1
    return max(0, months)


def _months_elapsed(start: date, as_of: date) -> Decimal:
    if as_of < start:
        return Decimal("0")
    whole = (as_of.year - start.year) * 12 + as_of.month - start.month
    anchor_day = min(start.day, calendar.monthrange(as_of.year, as_of.month)[1])
    if as_of.day < anchor_day:
        whole -= 1
        previous_month_end = as_of.replace(day=1) - timedelta(days=1)
        anchor_day = min(start.day, previous_month_end.day)
        anchor = previous_month_end.replace(day=anchor_day)
    else:
        anchor = as_of.replace(day=anchor_day)
    month_days = Decimal(calendar.monthrange(anchor.year, anchor.month)[1])
    fraction = Decimal((as_of - anchor).days + 1) / month_days
    return max(Decimal("0"), Decimal(whole) + fraction)


def accrued_days(
    entitlement: Decimal,
    *,
    accrual_type: str,
    leave_year: int,
    business_date: date,
    employment_start_date: date | None,
    min_service_months: int = 0,
    eligible: bool = True,
) -> Decimal:
    entitlement = decimal_days(entitlement)
    if not eligible or leave_year > business_date.year:
        return ZERO
    as_of = date(leave_year, 12, 31) if leave_year < business_date.year else business_date
    if completed_service_months(employment_start_date, as_of) < min_service_months:
        return ZERO
    if accrual_type in {"fixed", "none", "once_per_career"}:
        return entitlement
    if accrual_type != "monthly":
        raise ValueError("unsupported accrual type")
    if employment_start_date is None or employment_start_date > as_of:
        return ZERO

    service_months = completed_service_months(employment_start_date, as_of)
    if service_months < 6:
        return ZERO
    year_start = date(leave_year, 1, 1)
    effective_start = max(year_start, employment_start_date)
    elapsed = _months_elapsed(effective_start, as_of)
    if service_months < 12:
        return decimal_days(min(Decimal("24.00"), Decimal(service_months) * Decimal("2.00")))
    return decimal_days(min(entitlement, elapsed * entitlement / Decimal("12")))


def carry_forward(
    previous_remaining: Decimal,
    *,
    enabled: bool,
    type_allowed: bool,
    settings_cap: int,
    type_cap: int,
) -> Decimal:
    if not enabled or not type_allowed:
        return ZERO
    cap = Decimal(max(0, min(settings_cap, type_cap)))
    return decimal_days(max(ZERO, min(decimal_days(previous_remaining), cap)))


def sick_tiers(total_used: Decimal, *, probation: bool = False) -> tuple[Decimal, Decimal, Decimal]:
    remaining = max(ZERO, decimal_days(total_used))
    if probation:
        return ZERO, ZERO, remaining
    full = min(remaining, SICK_FULL_PAY_LIMIT)
    remaining -= full
    half = min(remaining, SICK_HALF_PAY_LIMIT)
    remaining -= half
    return decimal_days(full), decimal_days(half), decimal_days(remaining)


@dataclass(frozen=True, slots=True)
class BalanceInputs:
    entitlement: Decimal
    accrual_type: str
    leave_year: int
    business_date: date
    employment_start_date: date | None
    min_service_months: int = 0
    eligible: bool = True
    previous_remaining: Decimal = ZERO
    carry_forward_enabled: bool = True
    carry_forward_allowed: bool = False
    settings_carry_forward_cap: int = 0
    type_carry_forward_cap: int = 0
    used_days: Decimal = ZERO
    pending_days: Decimal = ZERO
    sick_full_pay_used: Decimal = ZERO
    sick_half_pay_used: Decimal = ZERO
    sick_unpaid_used: Decimal = ZERO
    hajj_taken: bool = False
    once_per_career: bool = False
    unlimited: bool = False


def recompute_balance(values: BalanceInputs) -> dict[str, Decimal | bool]:
    entitled = decimal_days(values.entitlement)
    accrued = accrued_days(
        entitled,
        accrual_type=values.accrual_type,
        leave_year=values.leave_year,
        business_date=values.business_date,
        employment_start_date=values.employment_start_date,
        min_service_months=values.min_service_months,
        eligible=values.eligible,
    )
    carried = carry_forward(
        values.previous_remaining,
        enabled=values.carry_forward_enabled,
        type_allowed=values.carry_forward_allowed,
        settings_cap=values.settings_carry_forward_cap,
        type_cap=values.type_carry_forward_cap,
    )
    used = decimal_days(values.used_days)
    pending = decimal_days(values.pending_days)
    if values.once_per_career and values.hajj_taken and used == ZERO:
        entitled = ZERO
        accrued = ZERO
        carried = ZERO
    remaining = (
        ZERO if values.unlimited else decimal_days(max(ZERO, accrued + carried - used - pending))
    )
    return {
        "entitled_days": entitled,
        "accrued_days": accrued,
        "used_days": used,
        "pending_days": pending,
        "carried_forward": carried,
        "remaining_days": remaining,
        "sick_full_pay_used": decimal_days(values.sick_full_pay_used),
        "sick_half_pay_used": decimal_days(values.sick_half_pay_used),
        "sick_unpaid_used": decimal_days(values.sick_unpaid_used),
        "hajj_taken": values.hajj_taken,
    }
