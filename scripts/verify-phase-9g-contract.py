#!/usr/bin/env python3
"""Verify the tracked Phase 9G WPS and Nafis boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    if not target.is_file():
        raise SystemExit(f"Phase 9G check failed: missing {path}")
    return target.read_text(encoding="utf-8")


def require(path: str, *markers: str) -> str:
    source = read(path)
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise SystemExit(f"Phase 9G check failed: {path} lacks {missing}")
    return source


def main() -> None:
    require(
        "backend/app/services/wps.py",
        "class WpsService",
        "async def sif_input(",
        "async def record_sif_projection(",
        "async def mark_entry_paid(",
        "async def reject_entry(",
        "async def create_compliance_override(",
        "async def replace_nafis_snapshot(",
    )
    require(
        "backend/alembic/versions/e3a7c9d1f5b2_add_phase9g_wps_nafis.py",
        'revision: str = "e3a7c9d1f5b2"',
        'down_revision: str | Sequence[str] | None = "b8e2c4d6f9a1"',
        "transition_payroll_wps",
        "transition_wps_entry",
        "trg_compliance_overrides_immutable",
    )
    frontend = require(
        "src/WpsNafis.jsx",
        "WPS and SIF",
        "Compliance override",
        "Nafis snapshots",
    )
    client = require(
        "src/wpsNafisApi.js",
        "/sif-input",
        "/compliance-overrides",
        "/api/v1/nafis-snapshots",
    )
    if "supabase" in (frontend + client).lower():
        raise SystemExit("Phase 9G check failed: migration WPS or Nafis uses Supabase")
    if (ROOT / "src/utils/storage.js").exists():
        raise SystemExit("Phase 9G check failed: retired shared storage source was restored")
    cutover = json.loads(read("docs/migration/phase-9/cutover/wps-and-nafis.json"))
    if cutover["status"]["current"] not in {"validation", "completed"}:
        raise SystemExit("Phase 9G check failed: cutover is not validated")
    if cutover["authority"]["writableSystems"] != ["migration-fastapi"]:
        raise SystemExit("Phase 9G check failed: migration is not sole authority")
    print("Phase 9G WPS and Nafis contract check passed")


if __name__ == "__main__":
    main()
