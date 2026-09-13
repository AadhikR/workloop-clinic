"""Verify the Phase 8B configuration boundary without touching a database."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend/app"
MIGRATION = ROOT / "migration/src"
MODEL = BACKEND / "models/leave.py"
CONTRACT = ROOT / "docs/migration/phase-8/PART_8A_DOMAIN_CONTRACT.md"
PLAN = ROOT / "docs/migration/phase-8/SUBPHASE_PLAN.md"
INVENTORY = ROOT / "docs/migration/phase-8/PART_8A_DEPENDENCY_INVENTORY.md"
CUTOVER = ROOT / "docs/migration/phase-8/cutover/leave-configuration.json"


def fail(message: str) -> None:
    raise SystemExit(f"Phase 8B configuration check failed: {message}")


def main() -> None:
    required = {
        "app/repositories/leave_configuration.py",
        "app/services/leave_configuration.py",
        "app/schemas/leave_configuration.py",
        "app/leave_configuration_api.py",
    }
    missing = [
        path for path in required if not (BACKEND / path.removeprefix("app/")).is_file()
    ]
    if missing:
        fail(f"missing implementation files: {', '.join(sorted(missing))}")

    model = MODEL.read_text(encoding="utf-8")
    for table in ("leave_settings", "leave_types", "public_holidays"):
        if f'__tablename__ = "{table}"' not in model:
            fail(f"model does not contain {table}")
    for constraint in (
        "uq_leave_settings_branch_id",
        "uq_leave_types_branch_id_code",
        "uq_public_holidays_branch_id_date",
    ):
        if constraint not in model:
            fail(f"canonical constraint {constraint} is missing")

    contract = CONTRACT.read_text(encoding="utf-8")
    for projection in ("leaveSettings", "leaveType", "publicHoliday"):
        if f"| {projection} |" not in contract:
            fail(f"contract projection {projection} is missing")
    if "Alembic revisions are unchanged" not in contract:
        fail("the Phase 8A no-schema-change boundary is missing")

    api = (BACKEND / "leave_configuration_api.py").read_text(encoding="utf-8")
    for operation in (
        "get_leave_settings",
        "update_leave_settings",
        "list_leave_types",
        "create_leave_type",
        "update_leave_type",
        "seed_leave_types",
        "list_public_holidays",
        "create_public_holiday",
        "update_public_holiday",
        "delete_public_holiday",
        "seed_public_holidays",
    ):
        if f'operation_id="{operation}"' not in api:
            fail(f"missing operation {operation}")
    for marker in ("parse_pagination", "LeaveTypeQuery", "HolidayQuery", "next_cursor"):
        if marker not in api:
            fail(f"pagination wiring is missing {marker}")

    schemas = (BACKEND / "schemas/leave_configuration.py").read_text(encoding="utf-8")
    for schema_name in (
        "LeaveTypeCreateRequest",
        "LeaveTypeUpdateRequest",
        "PublicHolidayCreateRequest",
        "PublicHolidayUpdateRequest",
        "PublicHolidaySnapshot",
    ):
        if f"class {schema_name}" not in schemas:
            fail(f"missing strict request schema {schema_name}")

    backend_test = ROOT / "backend/tests/test_leave_configuration_service.py"
    frontend_test = ROOT / "tests/migration-leave-configuration.test.js"
    freeze_test = ROOT / "tests/phase-8b-legacy-freeze.test.js"
    database_verifier = ROOT / "scripts/verify-phase-8b-configuration-database.py"
    for path in (backend_test, frontend_test, freeze_test, database_verifier):
        if not path.is_file():
            fail(f"missing focused test {path.relative_to(ROOT)}")

    client = (MIGRATION / "leaveConfigurationApi.js").read_text(encoding="utf-8")
    for marker in (
        "parseLeaveSettings",
        "parseLeaveType",
        "parsePublicHoliday",
        "updateLeaveSettings",
        "createLeaveType",
        "updateLeaveType",
        "createPublicHoliday",
        "updatePublicHoliday",
        "deletePublicHoliday",
    ):
        if marker not in client:
            fail(f"migration client is missing {marker}")
    if "body:" in client or "json:" not in client:
        fail("migration configuration mutations do not use the approved JSON transport")

    forbidden = re.compile(r"supabase|createClient|from ['\"]@supabase", re.IGNORECASE)
    config_files = list(MIGRATION.glob("*Leave*")) + list(MIGRATION.glob("*leave*"))
    for path in config_files:
        if path.is_file() and forbidden.search(path.read_text(encoding="utf-8")):
            fail(f"Supabase path found in {path.relative_to(ROOT)}")

    legacy = (ROOT / "src/utils/leaveStorage.js").read_text(encoding="utf-8")
    moved = "Leave configuration has moved to the migration settings screen."
    for function_name in (
        "getLeaveSettings",
        "saveLeaveSettings",
        "getLeaveTypes",
        "seedDefaultLeaveTypes",
        "saveLeaveType",
        "deleteLeaveType",
        "getPublicHolidays",
        "seedPublicHolidays",
        "seedPublicHolidaysForYear",
        "savePublicHoliday",
        "deletePublicHoliday",
    ):
        match = re.search(
            rf"export async function {function_name}\([^)]*\) \{{(?P<body>[\s\S]*?)\n\}}",
            legacy,
        )
        if match is None or moved not in match.group("body"):
            fail(f"legacy configuration function {function_name} is not frozen")

    inventory_ids = set(
        re.findall(r"\bphase8a-[a-z0-9-]+\b", INVENTORY.read_text(encoding="utf-8"))
    )
    cutover = json.loads(CUTOVER.read_text(encoding="utf-8"))
    required_ids = set(cutover["dependencies"]["requiredIds"])
    if not required_ids.issubset(inventory_ids):
        fail("cutover dependency IDs do not exist in the Phase 8A inventory")

    plan = PLAN.read_text(encoding="utf-8")
    if "## 8B: Leave settings, types, and public holidays" not in plan:
        fail("Phase 8B plan section is missing")
    if "Status: complete" not in (
        ROOT / "docs/migration/phase-8/PART_8B_COMPLETION.md"
    ).read_text(encoding="utf-8"):
        fail("completion record is not closed")

    print("Phase 8B configuration boundary check passed")


if __name__ == "__main__":
    main()
