#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TUPLES = {
    ("report_csv_exported", "report", "csv"),
    ("attendance_csv_exported", "attendance_period", "csv"),
    ("roster_csv_exported", "roster_month", "csv"),
    ("leave_balance_csv_exported", "leave_balance_year", "csv"),
    ("employee_csv_exported", "employee_export", "csv"),
    ("nafis_csv_exported", "nafis_report", "csv"),
    ("sif_previewed", "payroll_run", "sif_preview"),
    ("sif_exported", "payroll_run", "sif"),
}


def source(path: str) -> str:
    target = ROOT / path
    assert target.is_file(), f"missing Part 12F artifact: {path}"
    return target.read_text(encoding="utf-8")


def main() -> None:
    migration = source(
        "backend/alembic/versions/d6f8a0c2e4b7_add_phase12f_output_audit.py"
    )
    renderer = source("backend/app/services/outputs.py")
    report_api = source("backend/app/report_api.py")
    wps_api = source("backend/app/wps_api.py")
    output_api = source("backend/app/output_api.py")
    repository = source("backend/app/repositories/outputs.py")
    client = source("migration/src/outputApi.js")
    delivery = source("migration/src/outputDelivery.js")
    reports = source("migration/src/Reports.jsx")
    wps = source("migration/src/WpsNafis.jsx")

    assert 'down_revision: str | Sequence[str] | None = "c3e5a7b9d1f6"' in migration
    assert "SECURITY DEFINER" in migration
    assert "SET search_path TO pg_catalog, public" in migration
    assert "OWNER TO workloop_migration" in migration
    assert "REVOKE ALL" in migration and "GRANT EXECUTE" in migration
    assert "append_audit_event(" not in migration
    for action, entity_type, format_name in TUPLES:
        assert f"p_action = '{action}'" in migration
        assert f"p_entity_type = '{entity_type}'" in migration
        assert f"p_format = '{format_name}'" in migration
    for prohibited in (
        "report_pdf_exported",
        "payslip_pdf_exported",
        "payslip_zip_exported",
        "letter_pdf_exported",
    ):
        assert prohibited not in migration

    for marker in (
        'lineterminator="\\r\\n"',
        "FORMULA_PREFIXES",
        'errors="strict"',
        "ROUND_HALF_UP",
        "parse_sif_preview",
        "MAX_CSV_ROWS",
        "Content-Disposition",
        "Digest",
        "X-Request-ID",
        '"Vary": "Authorization"',
    ):
        if marker == "ROUND_HALF_UP":
            assert marker in source("backend/app/services/wps.py")
        else:
            assert marker in renderer
    assert '"/{report_id}.csv"' in report_api
    assert '"/{run_id}/sif/preview"' in wps_api
    assert '"/{run_id}/sif"' in wps_api
    for route in (
        "/employees/template.csv",
        "/employees.csv",
        "/leave-balances.csv",
        "/attendance/{period_id}.csv",
        "/roster.csv",
        "/nafis/{snapshot_id}.csv",
    ):
        assert f'"{route}"' in output_api
    assert "roster.published" in repository
    assert "company_id=:company" in repository and "branch_id=:branch" in repository
    assert "responseType: 'bytes'" in client
    assert "createObjectURL" in delivery and "revokeObjectURL" in delivery
    assert "downloadReportCsv" in reports
    assert "previewSif" in wps and "downloadSif" in wps
    assert "supabase" not in (client + delivery + reports + wps).lower()
    assert "jspdf" not in (renderer + report_api + wps_api + output_api).lower()
    assert "zip" not in (renderer + report_api + wps_api + output_api).lower()

    print("Phase 12F output boundary verification passed")


if __name__ == "__main__":
    main()
