from dataclasses import replace
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.services.attendance_calculation import CalculationSnapshot, ShiftSnapshot, calculate

DXB = ZoneInfo("Asia/Dubai")


def _snapshot(*events: tuple[str, datetime]) -> CalculationSnapshot:
    from datetime import date

    return CalculationSnapshot(
        date(2026, 8, 27),
        ShiftSnapshot(None, "fixed", Decimal("8"), 60, 10, 10, time(8), time(17)),
        events,
        False,
        False,
        False,
        False,
        False,
        True,
        Decimal("12000"),
        "per_minute",
        Decimal("1.25"),
        Decimal("2"),
    )


def test_phase10d_standard_day_uses_decimal_hours() -> None:
    result = calculate(
        _snapshot(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 17, tzinfo=DXB)),
        )
    )
    assert result.status == "PRESENT"
    assert result.total_hours == Decimal("8.00")


def test_phase10d_late_deduction_rounds_once() -> None:
    result = calculate(
        _snapshot(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, 16, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 17, tzinfo=DXB)),
        )
    )
    assert (result.status, result.late_minutes, result.late_deduction) == (
        "LATE",
        6,
        Decimal("7.50"),
    )


def test_phase10d_missing_out_is_a_blocker() -> None:
    result = calculate(_snapshot(("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB))))
    assert result.status == "MISSING_CLOCK_OUT"
    assert result.missing_clock_out is True


def test_phase10d_overtime_matches_golden_money_case() -> None:
    result = calculate(
        _snapshot(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 19, tzinfo=DXB)),
        )
    )
    assert (result.overtime_hours, result.overtime_amount) == (Decimal("2.00"), Decimal("144.23"))


def test_phase10d_leave_precedes_a_nonworking_day_without_events() -> None:
    result = calculate(replace(_snapshot(), weekend=True, approved_leave=True, working_day=False))
    assert result.status == "ON_LEAVE"


def test_phase10d_unexplained_absence_uses_daily_rate() -> None:
    result = calculate(_snapshot())
    assert (result.status, result.absence_deduction) == ("UNEXPLAINED_ABSENCE", Decimal("400.00"))


def test_phase10d_overnight_pairs_are_owned_by_start_date() -> None:
    from datetime import date

    result = calculate(
        CalculationSnapshot(
            date(2026, 8, 26),
            ShiftSnapshot(None, "overnight", Decimal("11"), 60, 10, 10, time(20), time(8)),
            (
                ("CLOCK_IN", datetime(2026, 8, 26, 20, 2, tzinfo=DXB)),
                ("CLOCK_OUT", datetime(2026, 8, 27, 8, 1, tzinfo=DXB)),
            ),
            False,
            False,
            False,
            False,
            False,
            True,
            Decimal("12000"),
            "none",
            Decimal("0"),
            Decimal("2"),
        )
    )
    assert result.status == "PRESENT"
    assert result.total_hours == Decimal("10.98")


def test_phase10d_four_worked_hours_is_half_day() -> None:
    result = calculate(
        _snapshot(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 13, tzinfo=DXB)),
        )
    )
    assert (result.status, result.total_hours) == ("HALF_DAY", Decimal("4.00"))


def test_phase10d_rest_day_counts_all_work_as_overtime() -> None:
    result = calculate(
        replace(
            _snapshot(
                ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
                ("CLOCK_OUT", datetime(2026, 8, 27, 11, tzinfo=DXB)),
            ),
            weekend=True,
            working_day=False,
        )
    )
    assert (result.overtime_hours, result.overtime_amount, result.overtime_type) == (
        Decimal("2.00"),
        Decimal("173.08"),
        "REST_DAY_NO_SUB",
    )


def test_phase10d_early_departure_uses_grace() -> None:
    result = calculate(
        _snapshot(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 16, 44, tzinfo=DXB)),
        )
    )
    assert (result.status, result.early_departure_minutes) == ("EARLY_DEPARTURE", 6)


def test_phase10d_nonworking_statuses_apply_only_without_work() -> None:
    assert calculate(replace(_snapshot(), holiday=True, working_day=False)).status == (
        "PUBLIC_HOLIDAY"
    )
    assert calculate(replace(_snapshot(), weekend=True, working_day=False)).status == "WEEKEND"
    worked_holiday = calculate(
        replace(
            _snapshot(
                ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
                ("CLOCK_OUT", datetime(2026, 8, 27, 17, tzinfo=DXB)),
            ),
            holiday=True,
            working_day=False,
        )
    )
    assert worked_holiday.worked_on_rest_day
    assert worked_holiday.status == "OVERTIME"


def test_phase10d_ramadan_reduces_expected_hours_to_six() -> None:
    result = calculate(
        replace(
            _snapshot(
                ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
                ("CLOCK_OUT", datetime(2026, 8, 27, 15, tzinfo=DXB)),
            ),
            ramadan=True,
        )
    )
    assert (result.status, result.total_hours, result.expected_hours) == (
        "PRESENT",
        Decimal("6.00"),
        Decimal("6.00"),
    )


def test_phase10d_flexible_shift_uses_minimum_presence_threshold() -> None:
    flexible = replace(
        _snapshot(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 14, tzinfo=DXB)),
        ),
        shift=ShiftSnapshot(
            None,
            "flexible",
            Decimal("8"),
            0,
            0,
            0,
            min_hours_flexible=Decimal("6"),
        ),
    )
    assert calculate(flexible).status == "PRESENT"
    half = replace(
        flexible,
        events=(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 12, tzinfo=DXB)),
        ),
    )
    assert calculate(half).status == "HALF_DAY"


def test_phase10d_split_shift_requires_both_intervals_and_subtracts_break_once() -> None:
    split = replace(
        _snapshot(
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 12, tzinfo=DXB)),
            ("CLOCK_IN", datetime(2026, 8, 27, 14, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 19, tzinfo=DXB)),
        ),
        shift=ShiftSnapshot(
            None,
            "split",
            Decimal("8"),
            60,
            10,
            10,
            time(8),
            time(12),
            time(14),
            time(19),
        ),
    )
    complete = calculate(split)
    assert (complete.status, complete.total_hours, complete.blocker_flags) == (
        "PRESENT",
        Decimal("8.00"),
        (),
    )
    incomplete = calculate(replace(split, events=split.events[:2]))
    assert "missing_split_interval" in incomplete.blocker_flags


def test_phase10d_wfh_and_rest_day_substitute_money_rules() -> None:
    worked = _snapshot(
        ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
        ("CLOCK_OUT", datetime(2026, 8, 27, 17, tzinfo=DXB)),
    )
    assert calculate(replace(worked, approved_wfh=True)).status == "PRESENT_REMOTE"
    substitute = calculate(
        replace(worked, weekend=True, working_day=False, rest_day_substitute=True)
    )
    assert (substitute.overtime_type, substitute.overtime_amount) == (
        "REST_DAY_WITH_SUB",
        Decimal("0.00"),
    )


def test_phase10d_ambiguous_and_unmatched_events_are_blockers() -> None:
    result = calculate(
        _snapshot(
            ("CLOCK_OUT", datetime(2026, 8, 27, 7, tzinfo=DXB)),
            ("CLOCK_IN", datetime(2026, 8, 27, 8, tzinfo=DXB)),
            ("CLOCK_IN", datetime(2026, 8, 27, 8, 1, tzinfo=DXB)),
            ("CLOCK_OUT", datetime(2026, 8, 27, 17, tzinfo=DXB)),
        )
    )
    assert set(result.blocker_flags) == {"ambiguous_events", "unmatched_clock_out"}


def test_phase10d_night_overtime_uses_one_point_five_multiplier() -> None:
    from datetime import date

    result = calculate(
        CalculationSnapshot(
            date(2026, 8, 26),
            ShiftSnapshot(None, "overnight", Decimal("8"), 0, 0, 0, time(20), time(4)),
            (
                ("CLOCK_IN", datetime(2026, 8, 26, 20, tzinfo=DXB)),
                ("CLOCK_OUT", datetime(2026, 8, 27, 6, tzinfo=DXB)),
            ),
            False,
            False,
            False,
            False,
            False,
            True,
            Decimal("12000"),
            "none",
            Decimal("0"),
            Decimal("2"),
        )
    )
    assert (result.overtime_hours, result.overtime_type, result.overtime_amount) == (
        Decimal("2.00"),
        "NIGHT_SHIFT",
        Decimal("173.08"),
    )
