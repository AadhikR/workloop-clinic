#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source(path: str) -> str:
    target = ROOT / path
    assert target.is_file(), f"missing Part 12D artifact: {path}"
    return target.read_text(encoding="utf-8")


def main() -> None:
    repository = source("backend/app/repositories/dashboards.py")
    service = source("backend/app/services/dashboards.py")
    api = source("backend/app/dashboard_api.py")
    client = source("src/dashboardApi.js")
    screen = source("src/Dashboards.jsx")
    shell = source("src/OrganizationPanel.jsx")

    for route in ('"/admin"', '"/clinical"', '"/self"'):
        assert route in api
    assert "validate_query_parameters(request, allowed=())" in api
    assert '"dashboard_source_unavailable"' in api
    assert "statement_timestamp()" in repository
    assert "public.workloop_business_date()" in repository
    assert "status='generated' AND approval_status='approved'" in repository
    assert "FROM public.nafis_reports" in repository
    assert "document.expiry_date-(SELECT business_date FROM snapshot)" not in repository
    for thresholds in ("ARRAY[60,30,14]", "ARRAY[90,30,14]", "ARRAY[60,30]", "ARRAY[14,7]"):
        assert thresholds in repository
    assert "public.file_security_scan_allows_download" in repository
    assert "month.status='published'" in repository
    assert "roster_assignments" not in repository
    assert "employee_id=principal.employee_id" in service
    assert "dashboard_source_unavailable" in service
    for mutation in ("INSERT ", "UPDATE ", "DELETE "):
        assert mutation not in repository
    assert not any((ROOT / "backend" / "alembic" / "versions").glob("*phase12d*"))
    assert "supabase" not in (client + screen).lower()
    assert 'kind="admin"' in shell
    assert 'kind="clinical"' in shell
    assert 'kind="self"' in shell

    print("Phase 12D boundary verification passed")


if __name__ == "__main__":
    main()
