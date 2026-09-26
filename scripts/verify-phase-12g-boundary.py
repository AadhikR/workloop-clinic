"""Verify the static Part 12G rendered-output and cutover boundary."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROUTES = {
    '"/{report_id}.pdf"',
    '"/{payslip_id}.pdf"',
    '"/self/{payslip_id}.pdf"',
    '"/{run_id}/payslips.zip"',
    '"/{request_id}/letter.pdf"',
    '"/{checklist_id}/letters/{letter_kind}.pdf"',
    '"/{checklist_id}/final-settlement.pdf"',
}
EXPECTED_AUDIT_TUPLES = {
    "report_pdf_exported",
    "payslip_pdf_exported",
    "payslip_zip_exported",
    "letter_pdf_exported",
    "offboarding_letter_pdf_exported",
    "final_settlement_pdf_exported",
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> None:
    route_source = read("backend/app/rendered_output_api.py")
    renderer_source = read("backend/app/services/rendered_outputs.py")
    migration_source = read(
        "backend/alembic/versions/e8a1c3f5b7d9_extend_phase12g_output_audit.py"
    )
    frontend = "\n".join(
        read(path)
        for path in (
            "src/renderedOutputApi.js",
            "src/outputDelivery.js",
            "src/Reports.jsx",
            "src/Payroll.jsx",
            "src/Payslips.jsx",
            "src/LetterRequests.jsx",
            "src/Offboarding.jsx",
        )
    )
    for route in EXPECTED_ROUTES:
        assert route in route_source, route
    for action in EXPECTED_AUDIT_TUPLES:
        assert action in migration_source, action
    assert "d6f8a0c2e4b7" in migration_source
    assert "SET search_path TO pg_catalog, public" in migration_source
    assert "REVOKE ALL ON FUNCTION" in migration_source
    assert "MAX_PDF_PAGES" in renderer_source
    assert "MAX_ZIP_ENTRIES" in renderer_source
    assert "writestr" in renderer_source and "ZipInfo" in renderer_source
    assert "window.print" not in frontend
    assert "jspdf" not in frontend.lower()
    assert "payslipGenerator" not in frontend
    assert "letterTemplates" not in frontend
    assert "safePrint" not in frontend

    catalogue = json.loads(
        read("docs/migration/phase-12/cutover/dependency-catalogue.json")
    )
    ids = [item["id"] for item in catalogue["dependencies"]]
    assert len(ids) == 97
    assert len(set(ids)) == 97
    assert ids[0] == "P12-NOT-01" and ids[-1] == "P12-IND-08"
    assert catalogue["decisions"]["employeeDetailPrint"] == "omitted-no-approved-output"
    assert catalogue["decisions"]["leaveCalendarPrint"] == "omitted-no-approved-output"
    print("Phase 12G rendered-output and cutover boundary verification passed")


if __name__ == "__main__":
    main()
