from __future__ import annotations

import asyncio
import io
import json
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import pytest

from app.schemas.reports import ReportColumn
from app.schemas.wps import SifEntryResponse, SifHeaderResponse, SifInputResponse
from app.services.execution import ServiceExecutionError
from app.services.outputs import (
    content_disposition,
    delivery_headers,
    parse_sif_preview,
    render_csv,
    render_sif,
    safe_filename,
)
from app.services.rendered_outputs import (
    MAX_PDF_PAGES,
    render_bounded,
    render_final_settlement_pdf,
    render_letter_request_pdf,
    render_payslip_pdf,
    render_payslip_zip,
)


def test_csv_is_rfc4180_utf8_formula_safe_and_deterministic() -> None:
    columns = [
        ReportColumn(key="text", label="Text", type="string"),
        ReportColumn(key="optional", label="Optional", type="string", nullable=True),
        ReportColumn(key="enabled", label="Enabled", type="boolean"),
    ]
    rows = [
        {"text": 'comma, quote " and\r\nArabic مرحبا', "optional": None, "enabled": True},
        {"text": "=SUM(A1:A2)", "optional": "\tformula", "enabled": False},
    ]
    first = render_csv(
        columns=columns,
        rows=rows,
        filename_base="تقرير output",
        filter_material={"branch": "a"},
        source_material=rows,
    )
    second = render_csv(
        columns=columns,
        rows=rows,
        filename_base="تقرير output",
        filter_material={"branch": "a"},
        source_material=rows,
    )
    assert first == second
    assert not first.content.startswith(b"\xef\xbb\xbf")
    assert first.content.decode() == (
        "Text,Optional,Enabled\r\n"
        '"comma, quote "" and\r\nArabic مرحبا",,true\r\n'
        "'=SUM(A1:A2),'\tformula,false\r\n"
    )
    assert first.filename == "تقرير_output.csv"
    assert content_disposition(first.filename).startswith('attachment; filename="')


def test_roster_csv_is_the_only_bom_variant() -> None:
    output = render_csv(
        columns=[ReportColumn(key="value", label="Value", type="string")],
        rows=[{"value": "one"}],
        filename_base="roster_2026-09",
        filter_material={},
        source_material={},
        bom=True,
    )
    assert output.content == b"\xef\xbb\xbfValue\r\none\r\n"


def projection(mode: Literal["full", "rejected"] = "full") -> SifInputResponse:
    entries = [
        SifEntryResponse(
            payroll_entry_id=uuid.UUID("c9000000-0000-4000-8000-000000000012"),
            employee_mol_id="90000000000001",
            bank_routing_code="999000001",
            iban="AE000000000000000000001",
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            paid_days=31,
            basic_pay=1001,
            variable_pay=201,
            total_pay=1202,
        ),
        SifEntryResponse(
            payroll_entry_id=uuid.UUID("c9000000-0000-4000-8000-000000000013"),
            employee_mol_id="90000000000002",
            bank_routing_code="999000001",
            iban="AE000000000000000000002",
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            paid_days=30,
            basic_pay=12000,
            variable_pay=5238,
            total_pay=17238,
        ),
    ]
    return SifInputResponse(
        mode=mode,
        digest="a" * 64,
        header=SifHeaderResponse(
            employer_mol_id="9000000816726",
            branch_routing_code="999000001",
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            payment_date=date(2026, 8, 25),
            employee_count=2,
            total_integer_pay=18440,
        ),
        entries=entries,
    )


def test_sif_uses_one_ascii_renderer_for_preview_and_download() -> None:
    first = render_sif(projection(), scope="all")
    second = render_sif(projection(), scope="all")
    assert first == second
    assert first.content.isascii()
    assert first.content.endswith(b"\r\n")
    assert first.content.count(b"\r\n") == 3
    assert b"EDR,90000000000001" in first.content
    assert b"SCR,9000000816726,999000001,2026-08-25" in first.content
    assert b",2,18440,AED,Salary for 082026\r\n" in first.content
    records = parse_sif_preview(first)
    assert [record["type"] for record in records] == ["EDR", "EDR", "SCR"]
    assert records[-1]["totalPay"] == 18440
    assert first.source_digest == "sha256:" + "a" * 64


def test_sif_rejects_scope_mode_mismatch_and_unsafe_ascii_fields() -> None:
    with pytest.raises(ServiceExecutionError, match="validation_failed"):
        render_sif(projection(), scope="rejected")
    unsafe = projection()
    unsafe.entries[0].employee_mol_id = "مول"
    with pytest.raises(ServiceExecutionError, match="validation_failed"):
        render_sif(unsafe, scope="all")


def test_delivery_headers_bind_bytes_renderer_and_source() -> None:
    output = render_sif(projection(), scope="all")
    request_id = "00f202d5-2ef0-4d6f-9553-830e5dcfb833"
    headers = delivery_headers(output, request_id)
    assert headers["Content-Length"] == str(len(output.content))
    assert headers["Digest"].startswith("sha-256=")
    assert headers["ETag"].startswith('"')
    assert headers["X-Request-ID"] == request_id
    assert headers["Vary"] == "Authorization"
    assert safe_filename("../bad\\name\x00", "csv") == "bad_name.csv"


def payslip_source(index: int = 1, *, name: str = "Synthetic Employee") -> dict[str, object]:
    return {
        "id": f"c9000000-0000-4000-8000-{index:012d}",
        "employeeId": f"c9000000-0000-4000-9000-{index:012d}",
        "employeeNumber": f"SYN-{index:03d}",
        "period": "2026-08",
        "paymentDate": "2026-08-25",
        "employeeName": name,
        "earnings": [{"label": "Basic salary", "amount": "10000.00"}],
        "deductions": [{"label": "Advance", "amount": "500.00"}],
        "grossPay": "10000.00",
        "totalDeductions": "500.00",
        "netPay": "9500.00",
        "wpsBasicPay": "10000.00",
        "wpsVariablePay": "-500.00",
        "issuedAt": "2026-08-25T08:00:00.000Z",
    }


def test_pdf_uses_source_time_fixed_metadata_and_deterministic_bytes() -> None:
    first = render_payslip_pdf(payslip_source(name="موظف تجريبي"))
    second = render_payslip_pdf(payslip_source(name="موظف تجريبي"))
    assert first == second
    assert first.content.startswith(b"%PDF-1.7")
    assert b"D:20260825080000Z" in first.content
    assert b"/BaseFont /Helvetica" in first.content
    assert b"/CreationDate" in first.content
    assert b"/ID [<" in first.content


def test_pdf_bytes_match_across_processes() -> None:
    source = json.dumps(payslip_source(name="Synthetic Employee"), separators=(",", ":"))
    program = (
        "import hashlib,json,sys;"
        "from app.services.rendered_outputs import render_payslip_pdf;"
        "print(hashlib.sha256(render_payslip_pdf(json.loads(sys.argv[1])).content).hexdigest())"
    )
    first = subprocess.run(
        [sys.executable, "-c", program, source],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    second = subprocess.run(
        [sys.executable, "-c", program, source],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert first == second
    assert first == "13311323d14dc13836e0a39a63287569768fcfa4d419bb1f56bc10b025dbcc08"


def test_pdf_fails_closed_when_an_approved_asset_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("app.services.rendered_outputs._ASSET_ROOT", tmp_path)
    with pytest.raises(ServiceExecutionError, match="report_source_unavailable"):
        render_payslip_pdf(payslip_source())


@pytest.mark.asyncio
async def test_render_worker_serializes_one_principal() -> None:
    principal_id = uuid.UUID("c9000000-0000-4000-8000-000000000299")
    lock = threading.Lock()
    active = 0
    maximum = 0

    def operation() -> str:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return "done"

    results = await asyncio.gather(
        render_bounded(principal_id, operation),
        render_bounded(principal_id, operation),
    )
    assert results == ["done", "done"]
    assert maximum == 1


def test_letter_and_settlement_render_only_supplied_source_values() -> None:
    letter = render_letter_request_pdf(
        {
            "requestId": "c9000000-0000-4000-8000-000000000101",
            "requestKind": "letter",
            "letterType": "salary_certificate_bank",
            "purpose": "Synthetic Bank",
            "employeeName": "Synthetic Employee",
            "jobTitle": "Clinician",
            "department": "Clinical",
            "employmentStartDate": "2024-01-01",
            "branchName": "Synthetic Branch",
            "basicSalary": "10000.00",
            "allowance": "2500.00",
            "requestedAt": "2026-08-24T08:00:00.000Z",
            "completedAt": "2026-08-25T08:00:00.000Z",
        }
    )
    settlement = render_final_settlement_pdf(
        {
            "id": "c9000000-0000-4000-8000-000000000102",
            "checklistId": "c9000000-0000-4000-8000-000000000103",
            "employeeId": "c9000000-0000-4000-8000-000000000104",
            "policyVersion": "1.0.0",
            "policyDigest": "sha256:" + "a" * 64,
            "sourceDigest": "sha256:" + "b" * 64,
            "sourceCapturedAt": "2026-08-25T07:00:00.000Z",
            "serviceDays": "1000",
            "gratuityDays": "50",
            "leaveDays": "5",
            "finalSalary": "1000.00",
            "leaveEncashment": "200.00",
            "gratuity": "3000.00",
            "noticePay": "0.00",
            "otherEarnings": "0.00",
            "advanceDeduction": "100.00",
            "assetDeduction": "0.00",
            "noticeDeduction": "0.00",
            "otherDeductions": "0.00",
            "grossAmount": "4200.00",
            "totalDeductions": "100.00",
            "netAmount": "4100.00",
            "completedAt": "2026-08-25T08:00:00.000Z",
        }
    )
    assert b"Synthetic Bank" in letter.content
    assert b"Net amount: AED 4100.00" in settlement.content
    assert b"payrollCalculator" not in settlement.content


def test_bulk_payslip_zip_has_fixed_order_manifest_metadata_and_bytes() -> None:
    sources = [
        payslip_source(3, name="موظف"),
        payslip_source(1, name="Synthetic One"),
        payslip_source(2, name=""),
    ]
    first = render_payslip_zip(
        run_id=uuid.UUID("c9000000-0000-4000-8000-000000000201"),
        finalized_at=datetime(2026, 8, 25, 8, 0, 1, tzinfo=UTC),
        payslips=sources,
    )
    second = render_payslip_zip(
        run_id=uuid.UUID("c9000000-0000-4000-8000-000000000201"),
        finalized_at=datetime(2026, 8, 25, 8, 0, 1, tzinfo=UTC),
        payslips=sources,
    )
    assert first == second
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        names = archive.namelist()
        assert names == [
            "payslip_2026-08_SYN-001.pdf",
            "payslip_2026-08_SYN-002.pdf",
            "payslip_2026-08_SYN-003.pdf",
            "manifest.json",
        ]
        manifest = json.loads(archive.read("manifest.json"))
        assert [item["filename"] for item in manifest["entries"]] == names[:-1]
        for info in archive.infolist():
            assert info.date_time == (2026, 8, 25, 8, 0, 0)
            assert info.compress_type == zipfile.ZIP_DEFLATED
            assert info.external_attr >> 16 == 0o100644


def test_bulk_payslip_zip_rejects_path_material_in_filenames() -> None:
    source = payslip_source()
    source["employeeNumber"] = "../unsafe\\name\x00"
    output = render_payslip_zip(
        run_id=uuid.UUID("c9000000-0000-4000-8000-000000000202"),
        finalized_at=datetime(2026, 8, 25, 8, 0, tzinfo=UTC),
        payslips=[source],
    )
    with zipfile.ZipFile(io.BytesIO(output.content)) as archive:
        filename = archive.namelist()[0]
    assert filename == "payslip_2026-08_.._unsafe_name.pdf"
    assert "/" not in filename and "\\" not in filename


def test_pdf_page_limit_fails_before_bytes_are_returned() -> None:
    source = payslip_source()
    source["earnings"] = [
        {"label": f"Line {index}", "amount": "1.00"} for index in range(MAX_PDF_PAGES * 50)
    ]
    with pytest.raises(ServiceExecutionError, match="output_limit_exceeded"):
        render_payslip_pdf(source)
