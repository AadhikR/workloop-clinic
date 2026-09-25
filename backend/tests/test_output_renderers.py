from __future__ import annotations

import uuid
from datetime import date
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
