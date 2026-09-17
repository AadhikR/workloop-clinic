#!/usr/bin/env python3
"""Verify the tracked Phase 9F payroll approval and payslip boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Phase 9F check failed: missing {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, *markers: str) -> str:
    source = read(path)
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise SystemExit(f"Phase 9F check failed: {path} lacks {missing}")
    return source


def main() -> None:
    require(
        "backend/app/services/payroll.py",
        "async def submit(",
        "async def recall(",
        "async def approve(",
        "async def reject(",
        "async def generate(",
        'action="payslips_issued"',
        'action="expense_paid"',
        'action="salary_advance_repayment_recorded"',
    )
    require(
        "backend/alembic/versions/b8e2c4d6f9a1_add_phase9f_payroll_approval.py",
        'revision: str = "b8e2c4d6f9a1"',
        'down_revision: str | Sequence[str] | None = "d7f1b3c5e9a2"',
        "transition_payroll_run",
        "finalize_payroll_run",
        "trg_payslips_immutable",
    )
    frontend = require(
        "migration/src/Payroll.jsx",
        "Submit for approval",
        "Generate payroll",
        "Approval history",
    )
    employee = require("migration/src/Payslips.jsx", "My payslips", "readSelfPayslips")
    if "supabase" in (frontend + employee).lower():
        raise SystemExit("Phase 9F check failed: migration payroll uses Supabase")
    cutover = json.loads(read("docs/migration/phase-9/cutover/payroll-approval-and-payslips.json"))
    if cutover["status"]["current"] not in {"validation", "completed"}:
        raise SystemExit("Phase 9F check failed: cutover is not validated")
    if cutover["authority"]["writableSystems"] != ["migration-fastapi"]:
        raise SystemExit("Phase 9F check failed: migration is not sole authority")
    print("Phase 9F approval and payslip contract check passed")


if __name__ == "__main__":
    main()
