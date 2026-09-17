#!/usr/bin/env python3
"""Verify the tracked Phase 9D payroll draft implementation and cutover boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Phase 9D payroll check failed: missing {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, *markers: str) -> str:
    source = read(path)
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise SystemExit(f"Phase 9D payroll check failed: {path} lacks {missing}")
    return source


def main() -> None:
    require(
        "backend/app/payroll_api.py",
        'operation_id="create_payroll_run"',
        'operation_id="repeat_payroll_run"',
        'operation_id="refresh_payroll_run"',
        'operation_id="replace_payroll_entries"',
        'operation_id="delete_payroll_run"',
        'ServiceExecutionError("idempotency_key_reused")',
    )
    require(
        "backend/app/services/payroll.py",
        "ROUND_HALF_UP",
        'raise ServiceExecutionError("stale_financial_state")',
        'action="payroll_entries_replaced"',
        '"automaticInputs": automatic_inputs',
    )
    require(
        "backend/app/repositories/payroll.py",
        "workloop_business_date",
        "replace_payroll_entries",
        "FOR UPDATE",
    )
    require(
        "backend/alembic/versions/c5e7a9b1d3f4_add_phase9d_payroll_draft_authority.py",
        'revision: str = "c5e7a9b1d3f4"',
        'down_revision: str | Sequence[str] | None = "a1c3e5f7b9d2"',
        "source_snapshot_digest",
        "_replace_payroll_entries_phase9d_prior",
        "payroll_draft_deleted",
    )
    frontend = require(
        "migration/src/payrollApi.js",
        "/api/v1/payroll-runs",
        "Idempotency-Key",
        "expectedUpdatedAt",
        "payrollPreview",
    )
    if "supabase" in frontend.lower():
        raise SystemExit("Phase 9D payroll check failed: migration client uses Supabase")
    require(
        "src/utils/storage.js",
        "Payroll drafts have moved to the migration payroll workspace.",
        "export async function getPayrolls(companyId)",
        "export async function savePayroll(payroll)",
    )
    cutover = json.loads(
        read("docs/migration/phase-9/cutover/payroll-drafts-and-calculations.json")
    )
    if cutover["status"]["current"] not in {"validation", "completed"}:
        raise SystemExit("Phase 9D payroll check failed: cutover is not validated")
    print("Phase 9D payroll contract check passed")


if __name__ == "__main__":
    main()
