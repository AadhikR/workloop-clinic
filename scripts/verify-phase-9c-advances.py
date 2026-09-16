#!/usr/bin/env python3
"""Verify the tracked Phase 9C advance implementation and cutover boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Phase 9C advance check failed: missing {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, *markers: str) -> str:
    source = read(path)
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise SystemExit(f"Phase 9C advance check failed: {path} lacks {missing}")
    return source


def main() -> None:
    require(
        "backend/app/advance_api.py",
        'operation_id="create_self_advance"',
        'operation_id="withdraw_self_advance"',
        'operation_id="create_admin_advance"',
        'operation_id="replace_advance_schedule"',
        'operation_id="record_advance_repayment"',
        'operation_id="settle_advance"',
        'ServiceExecutionError("idempotency_key_reused")',
    )
    require(
        "backend/app/services/advances.py",
        "ROUND_HALF_UP",
        'raise ServiceExecutionError("stale_financial_state")',
        'row["creator_app_user_id"] == principal.app_user_id',
        'action="salary_advance_repayment_recorded"',
    )
    require(
        "backend/app/repositories/advances.py",
        "lock_salary_advance",
        "record_advance_repayment",
        "salary_advance_requested",
    )
    require(
        "backend/alembic/versions/a1c3e5f7b9d2_add_phase9c_advance_authority.py",
        'revision: str = "a1c3e5f7b9d2"',
        'down_revision: str | Sequence[str] | None = "f9b2c4d6e8a1"',
        "salary_advance_schedule_changed",
        "advance_repayment_untrusted_paid_date",
        "_record_advance_repayment_phase9c_prior",
    )
    frontend = require(
        "migration/src/advanceApi.js",
        "/api/v1/advances/self",
        "/api/v1/advances",
        "Idempotency-Key",
        "expectedUpdatedAt",
    )
    if "supabase" in frontend.lower():
        raise SystemExit("Phase 9C advance check failed: migration client uses Supabase")
    require(
        "src/utils/storage.js",
        "Salary advance changes have moved to the migration advance workspace.",
        "advanceWritesMoved();",
        "export async function getAdvances(employeeId)",
    )
    cutover = json.loads(read("docs/migration/phase-9/cutover/advances-and-repayments.json"))
    if cutover["status"]["current"] not in {"validation", "completed"}:
        raise SystemExit("Phase 9C advance check failed: cutover is not validated")
    print("Phase 9C advance contract check passed")


if __name__ == "__main__":
    main()
