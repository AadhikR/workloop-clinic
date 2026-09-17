#!/usr/bin/env python3
"""Verify the tracked Phase 9E payroll-input boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Phase 9E payroll-input check failed: missing {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, *markers: str) -> str:
    source = read(path)
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise SystemExit(f"Phase 9E payroll-input check failed: {path} lacks {missing}")
    return source


def main() -> None:
    require(
        "backend/app/repositories/payroll.py",
        "lock_leave_inputs",
        "attendance_input_projection",
        "roster_input_projection",
        "lock_expense_inputs",
        "lock_advance_inputs",
        "FOR UPDATE OF claim",
        "FOR UPDATE OF advance",
    )
    require(
        "backend/app/services/payroll.py",
        '"leave"',
        '"expense"',
        '"advance"',
        '"attendance_input_not_ready"',
        '"roster_input_not_ready"',
        'action="payroll_inputs_refreshed"',
    )
    require(
        "backend/alembic/versions/d7f1b3c5e9a2_add_phase9e_payroll_input_audit.py",
        'revision: str = "d7f1b3c5e9a2"',
        'down_revision: str | Sequence[str] | None = "c5e7a9b1d3f4"',
        "payroll_inputs_refreshed",
        "_append_audit_event_phase9e_prior",
    )
    frontend = require(
        "migration/src/Payroll.jsx",
        "Automatic payroll inputs refreshed.",
        "Source warnings",
        "sourceExplanations",
    )
    if "supabase" in frontend.lower():
        raise SystemExit("Phase 9E payroll-input check failed: migration payroll uses Supabase")
    legacy = require(
        "src/components/PayrollEditor.jsx",
        "Automatic payroll inputs have moved to the migration payroll workspace.",
    )
    if "getAttendancePayrollData(payroll.period)" in legacy:
        raise SystemExit(
            "Phase 9E payroll-input check failed: legacy attendance input is not frozen"
        )
    cutover = json.loads(read("docs/migration/phase-9/cutover/payroll-inputs.json"))
    if cutover["status"]["current"] not in {"validation", "completed"}:
        raise SystemExit("Phase 9E payroll-input check failed: cutover is not validated")
    if cutover["authority"]["writableSystems"] != ["migration-fastapi"]:
        raise SystemExit("Phase 9E payroll-input check failed: migration is not sole authority")
    print("Phase 9E payroll-input contract check passed")


if __name__ == "__main__":
    main()
