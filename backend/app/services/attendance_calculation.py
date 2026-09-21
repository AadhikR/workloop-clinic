"""Deterministic Phase 10D daily attendance calculation.

This module deliberately has no database dependency.  The repository builds one trusted
snapshot and this function turns it into a persisted daily result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

DUBAI = ZoneInfo("Asia/Dubai")
ZERO = Decimal("0")
HUNDREDTH = Decimal("0.01")


def _hours(value: timedelta) -> Decimal:
    return Decimal(value.total_seconds()) / Decimal(3600)


def _money(value: Decimal) -> Decimal:
    return value.quantize(HUNDREDTH, rounding=ROUND_HALF_UP)


def _decimal_hours(value: Decimal) -> Decimal:
    return value.quantize(HUNDREDTH, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ShiftSnapshot:
    shift_id: object | None
    shift_type: str
    expected_hours: Decimal
    break_minutes: int
    late_grace_minutes: int
    early_departure_grace_minutes: int
    start_time: time | None = None
    end_time: time | None = None
    split_start_time: time | None = None
    split_end_time: time | None = None
    min_hours_flexible: Decimal | None = None


@dataclass(frozen=True)
class CalculationSnapshot:
    attendance_date: date
    shift: ShiftSnapshot | None
    events: tuple[tuple[str, datetime], ...]
    weekend: bool
    holiday: bool
    approved_leave: bool
    approved_wfh: bool
    ramadan: bool
    working_day: bool
    monthly_basic: Decimal
    late_deduction_policy: str
    late_deduction_amount: Decimal
    max_daily_overtime_hours: Decimal
    default_expected_hours: Decimal = Decimal("8.00")
    rest_day_substitute: bool = False


@dataclass(frozen=True)
class CalculationResult:
    status: str
    clock_in: datetime | None
    clock_out: datetime | None
    total_hours: Decimal
    expected_hours: Decimal
    late_minutes: int
    early_departure_minutes: int
    overtime_hours: Decimal
    overtime_type: str | None
    overtime_amount: Decimal
    late_deduction: Decimal
    absence_deduction: Decimal
    worked_on_rest_day: bool
    missing_clock_out: bool
    blocker_flags: tuple[str, ...]


def _scheduled(snapshot: CalculationSnapshot) -> tuple[datetime | None, datetime | None]:
    shift = snapshot.shift
    if shift is None or shift.start_time is None or shift.end_time is None:
        return None, None
    start = datetime.combine(snapshot.attendance_date, shift.start_time, tzinfo=DUBAI)
    end_date = snapshot.attendance_date + timedelta(days=shift.shift_type == "overnight")
    end_time = shift.split_end_time if shift.shift_type == "split" else shift.end_time
    assert end_time is not None
    return start, datetime.combine(end_date, end_time, tzinfo=DUBAI)


def _overlaps_night(start: datetime, end: datetime) -> bool:
    day = start.date() - timedelta(days=1)
    while day <= end.date():
        night_start = datetime.combine(day, time(21), tzinfo=DUBAI)
        night_end = datetime.combine(day + timedelta(days=1), time(4), tzinfo=DUBAI)
        if start < night_end and end > night_start:
            return True
        day += timedelta(days=1)
    return False


def calculate(snapshot: CalculationSnapshot) -> CalculationResult:
    """Calculate one trusted daily snapshot using the Phase 10A precedence rules."""
    shift = snapshot.shift
    expected = shift.expected_hours if shift is not None else snapshot.default_expected_hours
    if snapshot.ramadan:
        expected = min(expected, Decimal("6.00"))
    ordered = tuple(sorted(snapshot.events, key=lambda item: item[1]))
    blockers: list[str] = []
    pairs: list[tuple[datetime, datetime]] = []
    open_in: datetime | None = None
    for event_type, event_time in ordered:
        local = event_time.astimezone(DUBAI)
        if event_type == "CLOCK_IN":
            if open_in is not None:
                blockers.append("ambiguous_events")
            open_in = local
        elif event_type == "CLOCK_OUT":
            if open_in is None:
                blockers.append("unmatched_clock_out")
            elif local <= open_in:
                blockers.append("negative_interval")
                open_in = None
            else:
                pairs.append((open_in, local))
                open_in = None
    if open_in is not None:
        blockers.append("missing_clock_out")

    if shift is not None and shift.shift_type == "split" and pairs:
        assert shift.start_time is not None and shift.end_time is not None
        assert shift.split_start_time is not None and shift.split_end_time is not None
        first_start = datetime.combine(snapshot.attendance_date, shift.start_time, tzinfo=DUBAI)
        first_end = datetime.combine(snapshot.attendance_date, shift.end_time, tzinfo=DUBAI)
        second_start = datetime.combine(
            snapshot.attendance_date, shift.split_start_time, tzinfo=DUBAI
        )
        second_end = datetime.combine(snapshot.attendance_date, shift.split_end_time, tzinfo=DUBAI)
        first_present = any(start < first_end and end > first_start for start, end in pairs)
        second_present = any(start < second_end and end > second_start for start, end in pairs)
        if not first_present or not second_present:
            blockers.append("missing_split_interval")

    clock_in = pairs[0][0] if pairs else open_in
    clock_out = pairs[-1][1] if pairs else None
    worked = sum((_hours(end - start) for start, end in pairs), ZERO)
    if pairs and shift is not None:
        worked = max(ZERO, worked - Decimal(shift.break_minutes) / Decimal(60))
    worked = _decimal_hours(worked)
    has_work = bool(pairs or open_in)
    rest_day = snapshot.weekend or snapshot.holiday
    late = early = 0
    scheduled_start, scheduled_end = _scheduled(snapshot)
    if scheduled_end is not None and shift is not None and expected < shift.expected_hours:
        scheduled_end -= timedelta(seconds=int((shift.expected_hours - expected) * 3600))
    if clock_in is not None and scheduled_start is not None:
        assert shift is not None
        late = max(
            0, int((clock_in - scheduled_start).total_seconds() // 60) - shift.late_grace_minutes
        )
    if clock_out is not None and scheduled_end is not None:
        assert shift is not None
        early = max(
            0,
            int((scheduled_end - clock_out).total_seconds() // 60)
            - shift.early_departure_grace_minutes,
        )

    overtime_basis = worked if rest_day else worked - expected
    overtime = max(ZERO, min(snapshot.max_daily_overtime_hours, overtime_basis))
    overtime_type: str | None = None
    overtime_amount = ZERO
    if overtime > ZERO:
        hourly = snapshot.monthly_basic * Decimal(12) / Decimal(52) / Decimal(48)
        if rest_day:
            overtime_type = (
                "REST_DAY_WITH_SUB" if snapshot.rest_day_substitute else "REST_DAY_NO_SUB"
            )
            multiplier = ZERO if snapshot.rest_day_substitute else Decimal("1.50")
        elif any(_overlaps_night(start, end) for start, end in pairs):
            overtime_type, multiplier = "NIGHT_SHIFT", Decimal("1.50")
        else:
            overtime_type, multiplier = "STANDARD", Decimal("1.25")
        overtime_amount = _money(hourly * multiplier * overtime)

    if not has_work and snapshot.approved_leave:
        status = "ON_LEAVE"
    elif not has_work and snapshot.holiday:
        status = "PUBLIC_HOLIDAY"
    elif not has_work and snapshot.weekend:
        status = "WEEKEND"
    elif "missing_clock_out" in blockers:
        status = "MISSING_CLOCK_OUT"
    elif snapshot.approved_wfh and worked >= expected:
        status = "PRESENT_REMOTE"
    elif not has_work and snapshot.working_day:
        status = "UNEXPLAINED_ABSENCE"
    elif (
        (
            shift is not None
            and shift.shift_type == "flexible"
            and worked < (shift.min_hours_flexible or expected)
            and worked >= (shift.min_hours_flexible or expected) / 2
        )
        or (worked <= expected / 2 and worked > ZERO)
        or (late and early)
    ):
        status = "HALF_DAY"
    elif late:
        status = "LATE"
    elif early:
        status = "EARLY_DEPARTURE"
    elif overtime:
        status = "OVERTIME"
    else:
        status = "PRESENT"
    late_deduction = ZERO
    if late:
        if snapshot.late_deduction_policy == "per_minute":
            late_deduction = _money(snapshot.late_deduction_amount * late)
        elif snapshot.late_deduction_policy == "per_occurrence":
            late_deduction = _money(snapshot.late_deduction_amount)
    absence_deduction = (
        _money(snapshot.monthly_basic / Decimal(30)) if status == "UNEXPLAINED_ABSENCE" else ZERO
    )
    return CalculationResult(
        status,
        clock_in,
        clock_out,
        worked,
        _decimal_hours(expected),
        late,
        early,
        _decimal_hours(overtime),
        overtime_type,
        overtime_amount,
        late_deduction,
        absence_deduction,
        rest_day and has_work,
        "missing_clock_out" in blockers,
        tuple(sorted(set(blockers))),
    )
