#!/usr/bin/env python3
"""Check the documentation-only Phase 8A contract package."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "docs/migration/phase-8"
CONTRACT = PHASE / "PART_8A_DOMAIN_CONTRACT.md"
INVENTORY = PHASE / "PART_8A_DEPENDENCY_INVENTORY.md"
RECORD_DIR = PHASE / "cutover"
SCHEMA = ROOT / "docs/migration/phase-6/cutover-record.schema.json"
TABLES = {
    "leave_settings",
    "leave_types",
    "public_holidays",
    "leave_requests",
    "leave_audit_log",
    "leave_balances",
    "leave_approval_delegates",
}


def fail(message: str) -> None:
    raise SystemExit(f"Phase 8A contract check failed: {message}")


def main() -> None:
    for path in (CONTRACT, INVENTORY, SCHEMA):
        if not path.is_file():
            fail(f"missing {path.relative_to(ROOT)}")

    contract = CONTRACT.read_text(encoding="utf-8")
    inventory = INVENTORY.read_text(encoding="utf-8")
    for table in TABLES:
        if f"`{table}`" not in contract or f"`{table}`" not in inventory:
            fail(f"table {table} is not accounted for in both documents")

    ids = re.findall(r"\bphase8a-[a-z0-9-]+\b", inventory)
    if len(ids) < 20 or len(ids) != len(set(ids)):
        fail("inventory IDs must contain at least 20 unique phase8a-* identifiers")
    for owner in ("Phase 9", "Phase 10", "Phase 11", "Phase 12"):
        if owner not in inventory:
            fail(f"inventory has no assignment for {owner}")

    if "Alembic revisions are unchanged" not in contract:
        fail("contract does not state the Alembic no-change assertion")
    forbidden = (
        "backend/app/",
        "src/",
        "alembic revision",
        "CREATE TABLE",
        "CREATE POLICY",
    )
    if any(marker in contract for marker in forbidden):
        fail("contract contains implementation or amendment SQL instead of a proposal")

    record_names = sorted(RECORD_DIR.glob("leave-*.json"))
    expected = {
        "leave-configuration.json",
        "leave-balances-and-reads.json",
        "leave-attachments.json",
        "leave-request-submission.json",
        "leave-approval-workflows.json",
    }
    if {path.name for path in record_names} != expected:
        fail("the five required preparation records are not present")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = set(schema["required"])
    for path in record_names:
        record = json.loads(path.read_text(encoding="utf-8"))
        if set(record) != required | {"$schema"}:
            fail(f"{path.name} does not use the cutover record top-level contract")
        allowed_statuses = {"preparation"}
        if path.name in {
            "leave-configuration.json",
            "leave-balances-and-reads.json",
        }:
            allowed_statuses.add("completed")
        if record["status"]["current"] not in allowed_statuses:
            fail(f"{path.name} has an unsupported status for the current phase")
        if record["dataClassification"] != "synthetic":
            fail(f"{path.name} is not synthetic-only")
        if len(record["rollback"]["steps"]) < 5:
            fail(f"{path.name} lacks the five rollback controls")
        if len(record["dependencies"]["requiredIds"]) < 1:
            fail(f"{path.name} has no dependency IDs")
        inventory_ids = set(ids) | set(re.findall(r"\bphase8a-[a-z0-9-]+\b", contract))
        required_ids = set(record["dependencies"]["requiredIds"])
        declared_ids = {item["id"] for item in record["dependencies"]["declared"]}
        if required_ids != declared_ids or not required_ids.issubset(inventory_ids):
            fail(f"{path.name} dependency IDs do not match the Phase 8A sources")

    print(
        f"Phase 8A structural contract check passed: {len(record_names)} records, {len(ids)} inventory IDs"
    )


if __name__ == "__main__":
    main()
