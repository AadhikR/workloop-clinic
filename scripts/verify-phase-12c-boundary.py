#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    target = ROOT / path
    assert target.is_file(), f"missing Part 12C artifact: {path}"
    return target.read_text(encoding="utf-8")


def main() -> None:
    service = source("backend/app/services/tasks.py")
    repository = source("backend/app/repositories/tasks.py")
    api = source("backend/app/task_api.py")
    client = source("src/taskApi.js")
    screen = source("src/Tasks.jsx")
    shell = source("src/OrganizationPanel.jsx")

    assert 'prefix="/api/v1/tasks"' in api
    assert "employee_id" not in api
    assert "TASK_CATEGORY_REGISTRY" in service
    assert "task_source_unavailable" in service
    assert "source_unavailable=bool(failed)" in service
    assert "employee.reporting_manager_id=CAST(:employee_id AS uuid)" in repository
    for current_name in ("document_type", "period", "emirates_id_expiry"):
        assert current_name in repository
    for stale_name in ("doc_type", "eid_expiry"):
        assert stale_name not in repository
    assert not any((ROOT / "backend" / "alembic" / "versions").glob("*phase12c*"))
    assert "supabase" not in (client + screen).lower()
    assert "<Tasks" in shell

    print("Phase 12C boundary verification passed")


if __name__ == "__main__":
    main()
