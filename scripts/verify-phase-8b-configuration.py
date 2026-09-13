"""Verify the Phase 8B configuration boundary without touching a database."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend/app"
MIGRATION = ROOT / "migration/src"
MODEL = BACKEND / "models/leave.py"
CONTRACT = ROOT / "docs/migration/phase-8/PART_8A_DOMAIN_CONTRACT.md"
PLAN = ROOT / "docs/migration/phase-8/SUBPHASE_PLAN.md"


def fail(message: str) -> None:
    raise SystemExit(f"Phase 8B configuration check failed: {message}")


def main() -> None:
    required = {
        "app/repositories/leave_configuration.py",
        "app/services/leave_configuration.py",
        "app/schemas/leave_configuration.py",
        "app/leave_configuration_api.py",
    }
    missing = [path for path in required if not (BACKEND / path.removeprefix("app/")).is_file()]
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

    forbidden = re.compile(r"supabase|createClient|from ['\"]@supabase", re.IGNORECASE)
    config_files = list(MIGRATION.glob("*Leave*")) + list(MIGRATION.glob("*leave*"))
    for path in config_files:
        if path.is_file() and forbidden.search(path.read_text(encoding="utf-8")):
            fail(f"Supabase path found in {path.relative_to(ROOT)}")

    plan = PLAN.read_text(encoding="utf-8")
    if "## 8B: Leave settings, types, and public holidays" not in plan:
        fail("Phase 8B plan section is missing")
    if "Status: complete" not in (ROOT / "docs/migration/phase-8/PART_8B_COMPLETION.md").read_text(
        encoding="utf-8"
    ):
        fail("completion record is not closed")

    print("Phase 8B configuration boundary check passed")


if __name__ == "__main__":
    main()
