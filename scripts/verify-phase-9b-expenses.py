#!/usr/bin/env python3
"""Verify the tracked Phase 9B expense implementation and cutover boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Phase 9B expense check failed: missing {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, *markers: str) -> str:
    source = read(path)
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise SystemExit(f"Phase 9B expense check failed: {path} lacks {missing}")
    return source


def main() -> None:
    require(
        "backend/app/expense_api.py",
        'operation_id="create_self_expense"',
        'operation_id="manager_approve_expense"',
        'operation_id="admin_approve_expense"',
        'operation_id="create_expense_receipt_submission"',
        'operation_id="upload_expense_receipt"',
        'operation_id="download_expense_receipt"',
        'ServiceExecutionError("idempotency_key_reused")',
    )
    require(
        "backend/app/services/expenses.py",
        '"manager_approved" if approve else "manager_rejected"',
        'new_status = "approved"',
        'new_status = "rejected"',
        'raise ServiceExecutionError("stale_financial_state")',
    )
    require(
        "backend/app/repositories/expenses.py",
        "lock_expense_claim",
        "lock_expense_direct_report",
        "request_receipt_cleanup",
    )
    require(
        "backend/alembic/versions/f9b2c4d6e8a1_add_phase9b_expense_receipts.py",
        'revision: str = "f9b2c4d6e8a1"',
        'down_revision: str | Sequence[str] | None = "e8f4c7b2a610"',
        "expense_receipts",
        "expense_receipt_uploaded",
        "expense_receipt_cleanup_requested",
        "lock_expense_claim",
        "lock_expense_direct_report",
    )
    frontend = require(
        "migration/src/expenseApi.js",
        "/api/v1/expenses/self",
        "/api/v1/expenses/manager-queue",
        "/api/v1/expenses/receipt-submissions",
        "Idempotency-Key",
    )
    if "supabase" in frontend.lower():
        raise SystemExit("Phase 9B expense check failed: migration client uses Supabase")
    require(
        "src/utils/expenseStorage.js",
        "Expense claims and receipts have moved to the migration expense workspace.",
        "expenseMoved();",
    )
    require(
        ".github/workflows/migration-foundation.yml",
        "verify-phase-9b-revision.sh",
        "verify-phase-9b-database.py",
        "verify-phase-9b-expenses.py",
    )
    cutover = json.loads(read("docs/migration/phase-9/cutover/expenses.json"))
    assert cutover["status"]["current"] == "completed"
    assert cutover["authority"] == {
        "readSystem": "migration-fastapi",
        "writeSystem": "migration-fastapi",
        "writableSystems": ["migration-fastapi"],
    }
    print("Phase 9B expense contract check passed")


if __name__ == "__main__":
    main()
