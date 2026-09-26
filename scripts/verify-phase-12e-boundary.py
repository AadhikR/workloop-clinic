#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPORT_IDS = {
    "attendanceSummary",
    "documentExpiry",
    "emiratization",
    "eosLiability",
    "headcount",
    "leaveBalance",
    "leaveUtilization",
    "overtime",
    "payrollCost",
    "salaryMovement",
    "staffingCompliance",
    "turnover",
    "wpsCompliance",
}


def source(path: str) -> str:
    target = ROOT / path
    assert target.is_file(), f"missing Part 12E artifact: {path}"
    return target.read_text(encoding="utf-8")


def main() -> None:
    schemas = source("backend/app/schemas/reports.py")
    repository = source("backend/app/repositories/reports.py")
    service = source("backend/app/services/reports.py")
    api = source("backend/app/report_api.py")
    client = source("src/reportApi.js")
    screen = source("src/Reports.jsx")
    shell = source("src/OrganizationPanel.jsx")

    assert '"/{report_id}"' in api
    assert "unknown_filter" in api
    assert "AppRole.ADMIN" in service
    assert "resolve_employee" in service and "resolve_department" in service
    assert "ReportCursorCodec" in service
    assert "source_version" in schemas and "next_cursor" in schemas
    assert 'scope: Literal["filtered"]' in schemas
    for report_id in REPORT_IDS:
        assert f'"{report_id}"' in service
    assert "status='Approved'" in repository
    assert "status='generated' AND run.approval_status='approved'" in repository
    assert "month.status='published'" in repository
    assert "violation_snapshot" in repository
    assert "FROM public.nafis_reports" in repository
    assert "FROM public.leave_balances" in repository
    assert "semantic_version='1.0.0'" in repository
    assert "source_stale=false" in repository
    for mutation in ("INSERT ", "UPDATE ", "DELETE "):
        assert mutation not in repository
    assert not any((ROOT / "backend" / "alembic" / "versions").glob("*phase12e*"))
    assert "supabase" not in (client + screen).lower()
    assert "reportUtils" not in (client + screen)
    assert "<Reports authentication={authentication}" in shell

    print("Phase 12E boundary verification passed")


if __name__ == "__main__":
    main()
