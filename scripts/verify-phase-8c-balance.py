#!/usr/bin/env python3
"""Verify the Phase 8C balance and leave-read boundary without a database."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend/app"
MIGRATION = ROOT / "migration/src"
CONTRACT = ROOT / "docs/migration/phase-8/PART_8A_DOMAIN_CONTRACT.md"
INVENTORY = ROOT / "docs/migration/phase-8/PART_8A_DEPENDENCY_INVENTORY.md"
CUTOVER = ROOT / "docs/migration/phase-8/cutover/leave-balances-and-reads.json"


def fail(message: str) -> None:
    raise SystemExit(f"Phase 8C balance check failed: {message}")


def exported_function(source: str, name: str) -> str:
    match = re.search(
        rf"export async function {name}\([^)]*\) \{{(?P<body>[\s\S]*?)\n\}}",
        source,
    )
    if match is None:
        fail(f"legacy function {name} is missing")
    return match.group("body")


def main() -> None:
    required = (
        BACKEND / "repositories/leave_balance.py",
        BACKEND / "schemas/leave_balance.py",
        BACKEND / "services/leave_balance.py",
        BACKEND / "services/leave_balance_service.py",
        BACKEND / "leave_balance_api.py",
        ROOT / "backend/tests/test_leave_balance_service.py",
        ROOT / "scripts/verify-phase-8c-balance-database.py",
        ROOT / "scripts/verify-phase-8c-route-inventory.py",
        MIGRATION / "leaveBalanceApi.js",
        MIGRATION / "LeaveOverview.jsx",
        ROOT / "tests/migration-leave-balances.test.js",
        ROOT / "tests/phase-8c-legacy-freeze.test.js",
        ROOT / "docs/migration/phase-8/PART_8C_COMPLETION.md",
    )
    for path in required:
        if not path.is_file():
            fail(f"missing Phase 8C file {path.relative_to(ROOT)}")

    contract = CONTRACT.read_text(encoding="utf-8")
    for marker in (
        "leaveBalance",
        "leaveRequest",
        "Alembic revisions are unchanged",
    ):
        if marker not in contract:
            fail(f"Phase 8A contract marker is missing: {marker}")

    api = (BACKEND / "leave_balance_api.py").read_text(encoding="utf-8")
    operations = (
        "get_employee_leave_balances",
        "get_employee_leave_request_calendar",
        "get_admin_leave_balances",
        "get_admin_leave_request_calendar",
        "get_approver_leave_balances",
        "initialize_leave_balances",
        "recalculate_leave_balances",
    )
    for operation in operations:
        if f'operation_id="{operation}"' not in api:
            fail(f"missing operation {operation}")
    for marker in (
        "SelfBalanceQuery",
        "ApproverBalanceQuery",
        "LeaveBalanceYearRequest",
    ):
        if marker not in api:
            fail(f"strict route input is missing {marker}")

    repository = (BACKEND / "repositories/leave_balance.py").read_text(encoding="utf-8")
    lock_markers = tuple(
        f'"{table}"'
        for table in ("employees", "leave_types", "leave_requests", "leave_balances")
    )
    lock_start = repository.find("lock_recalculation_state")
    lock_positions = [repository.find(marker, lock_start) for marker in lock_markers]
    if any(position < 0 for position in lock_positions) or lock_positions != sorted(
        lock_positions
    ):
        fail("recalculation tables are not locked in the approved order")
    if "IN SHARE ROW EXCLUSIVE MODE" not in repository:
        fail("recalculation does not use a writer-blocking table lock")
    if (
        "on_conflict_do_nothing" not in repository
        or "on_conflict_do_update" not in repository
    ):
        fail("initialization or recalculation upsert behavior is missing")
    if "can_act_for_delegated_leave" not in repository:
        fail("protected delegate authorization is missing")

    arithmetic = (BACKEND / "services/leave_balance.py").read_text(encoding="utf-8")
    for marker in (
        "Decimal",
        "leave_days",
        "accrued_days",
        "sick_tiers",
        "recompute_balance",
    ):
        if marker not in arithmetic:
            fail(f"server arithmetic is missing {marker}")

    schemas = (BACKEND / "schemas/leave_balance.py").read_text(encoding="utf-8")
    for name in (
        "LeaveBalanceResponse",
        "LeaveRequestResponse",
        "LeaveBalanceYearRequest",
    ):
        if f"class {name}" not in schemas:
            fail(f"strict projection is missing {name}")

    main_source = (BACKEND / "main.py").read_text(encoding="utf-8")
    if (
        "leave_balance_router" not in main_source
        or "leave_balance_cursor_codec" not in main_source
    ):
        fail(
            "FastAPI application does not register the Phase 8C router and cursor codec"
        )

    client = (MIGRATION / "leaveBalanceApi.js").read_text(encoding="utf-8")
    view = (MIGRATION / "LeaveOverview.jsx").read_text(encoding="utf-8")
    for marker in (
        "parseLeaveBalance",
        "parseLeaveRequest",
        "readEmployeeLeaveBalances",
        "readAdminLeaveBalances",
        "readApproverLeaveBalances",
        "initializeLeaveBalances",
        "recalculateLeaveBalances",
    ):
        if marker not in client:
            fail(f"migration client is missing {marker}")
    forbidden = re.compile(r"supabase|createClient|@supabase", re.IGNORECASE)
    for path, source in (
        (MIGRATION / "leaveBalanceApi.js", client),
        (MIGRATION / "LeaveOverview.jsx", view),
    ):
        if forbidden.search(source):
            fail(f"Supabase path found in {path.relative_to(ROOT)}")

    legacy = (ROOT / "src/utils/leaveStorage.js").read_text(encoding="utf-8")
    moved = re.compile(r"ha(?:s|ve) moved to the migration leave view")
    for name in (
        "getLeaveBalances",
        "getAllLeaveBalances",
        "upsertLeaveBalance",
        "recalculateAllBalances",
    ):
        body = exported_function(legacy, name)
        if not moved.search(body) or re.search(
            r"supabase|leave_balances", body, re.IGNORECASE
        ):
            fail(f"legacy balance function {name} is not frozen")
    for name in (
        "getLeaveRequests",
        "submitLeaveRequest",
        "cancelLeaveRequest",
        "updateLeaveRequestStatus",
        "uploadLeaveAttachment",
    ):
        if moved.search(exported_function(legacy, name)):
            fail(f"later-phase legacy function {name} was frozen early")

    inventory_ids = set(
        re.findall(r"\bphase8a-[a-z0-9-]+\b", INVENTORY.read_text(encoding="utf-8"))
    )
    cutover = json.loads(CUTOVER.read_text(encoding="utf-8"))
    if not set(cutover["dependencies"]["requiredIds"]).issubset(inventory_ids):
        fail("cutover dependency IDs do not exist in the Phase 8A inventory")
    if cutover["status"]["current"] != "completed":
        fail("balance cutover is not completed")
    authority = cutover["authority"]
    if authority != {
        "readSystem": "migration-fastapi",
        "writeSystem": "migration-fastapi",
        "writableSystems": ["migration-fastapi"],
    }:
        fail("migration FastAPI is not the sole balance authority")

    completion = (ROOT / "docs/migration/phase-8/PART_8C_COMPLETION.md").read_text(
        encoding="utf-8"
    )
    if "Status: complete" not in completion:
        fail("Phase 8C completion record is not closed")

    print("Phase 8C balance and leave-read boundary check passed")


if __name__ == "__main__":
    main()
