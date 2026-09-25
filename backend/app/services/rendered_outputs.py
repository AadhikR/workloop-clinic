from __future__ import annotations

import asyncio
import hashlib
import io
import json
import textwrap
import unicodedata
import uuid
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.reports import ReportResponse
from app.services.execution import ServiceExecutionError
from app.services.outputs import RenderedOutput, canonical_digest, safe_filename

PDF_RENDERER_VERSION = "phase12g-pdf-v1"
ZIP_RENDERER_VERSION = "phase12g-zip-v1"
MAX_PDF_PAGES = 50
MAX_ZIP_ENTRIES = 200
MAX_RENDERED_BYTES = 16 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
PDF_PAGE_WIDTH = 595
PDF_PAGE_HEIGHT = 842
PDF_MARGIN = 48
PDF_LINES_PER_PAGE = 48
ZIP_COMPRESSION_LEVEL = 9
_ASSET_ROOT = Path(__file__).resolve().parents[1] / "render_assets"
_ASSETS = {
    "phase12g_font_metrics.json": (
        "7f69a89fdb94a0238ded3b476abc4669c792cb91f7e2ea34eea95504aa951b89"
    ),
    "phase12g_logo.svg": "85117793b9bc938bff9b6021d7f1df4d438d5e041e1595a055a2b4fa439fccad",
}

_GLOBAL_RENDER_SLOTS = asyncio.Semaphore(4)
_PRINCIPAL_RENDER_SLOTS: dict[uuid.UUID, asyncio.Semaphore] = {}


async def render_bounded[T](principal_id: uuid.UUID, operation: Callable[[], T]) -> T:
    principal_slot = _PRINCIPAL_RENDER_SLOTS.setdefault(principal_id, asyncio.Semaphore(1))
    async with _GLOBAL_RENDER_SLOTS, principal_slot:
        try:
            async with asyncio.timeout(10):
                return await asyncio.to_thread(operation)
        except TimeoutError:
            raise ServiceExecutionError("output_limit_exceeded") from None


def _verify_assets() -> None:
    for name, expected in _ASSETS.items():
        try:
            content = (_ASSET_ROOT / name).read_bytes()
        except OSError:
            raise ServiceExecutionError("report_source_unavailable") from None
        if hashlib.sha256(content).hexdigest() != expected:
            raise ServiceExecutionError("report_source_unavailable")


def _source_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ServiceExecutionError("validation_failed") from None
    else:
        raise ServiceExecutionError("validation_failed")
    if parsed.tzinfo is None:
        raise ServiceExecutionError("validation_failed")
    return parsed.astimezone(UTC)


def _pdf_date(value: datetime) -> str:
    return value.astimezone(UTC).strftime("D:%Y%m%d%H%M%SZ")


def _visible_text(value: object) -> str:
    text = unicodedata.normalize("NFC", "" if value is None else str(value))
    output: list[str] = []
    for character in text:
        codepoint = ord(character)
        if character in "\r\n\t":
            output.append(" ")
        elif 32 <= codepoint <= 126 or 160 <= codepoint <= 255:
            output.append(character)
        else:
            output.append(f"[U+{codepoint:04X}]")
    return "".join(output)


def _pdf_literal(value: str) -> bytes:
    escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("latin-1", errors="strict")


def _wrapped_lines(lines: list[str]) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        visible = _visible_text(line)
        wrapped.extend(
            textwrap.wrap(
                visible,
                width=92,
                replace_whitespace=True,
                drop_whitespace=True,
                break_long_words=True,
                break_on_hyphens=False,
            )
            or [""]
        )
    return wrapped


def _pdf_bytes(
    *,
    title: str,
    document_id: str,
    source_timestamp: datetime,
    lines: list[str],
    source_digest: str,
) -> bytes:
    _verify_assets()
    visible_lines = _wrapped_lines(lines)
    chunks: list[list[str]] = [
        visible_lines[offset : offset + PDF_LINES_PER_PAGE]
        for offset in range(0, max(1, len(visible_lines)), PDF_LINES_PER_PAGE)
    ]
    if len(chunks) > MAX_PDF_PAGES:
        raise ServiceExecutionError("output_limit_exceeded")

    page_object_ids = [5 + index * 2 for index in range(len(chunks))]
    content_object_ids = [value + 1 for value in page_object_ids]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            b"<< /Type /Pages /Count "
            + str(len(chunks)).encode("ascii")
            + b" /Kids ["
            + b" ".join(f"{value} 0 R".encode("ascii") for value in page_object_ids)
            + b"] >>"
        ),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: (
            b"<< /Title ("
            + _pdf_literal(_visible_text(title))
            + b") /Subject ("
            + _pdf_literal(_visible_text(document_id))
            + b") /Creator (Workloop) /Producer (Workloop Phase 12G PDF renderer) "
            + b"/CreationDate ("
            + _pdf_date(source_timestamp).encode("ascii")
            + b") /ModDate ("
            + _pdf_date(source_timestamp).encode("ascii")
            + b") /Trapped /False >>"
        ),
    }
    for index, chunk in enumerate(chunks):
        page_id = page_object_ids[index]
        content_id = content_object_ids[index]
        commands = [
            b"q 0.086 0.196 0.310 rg 48 790 24 24 re f Q",
            b"BT /F1 16 Tf 78 798 Td (" + _pdf_literal(_visible_text(title)) + b") Tj ET",
            b"BT /F1 8 Tf 48 775 Td ("
            + _pdf_literal(
                _visible_text(f"Document {document_id} | Page {index + 1} of {len(chunks)}")
            )
            + b") Tj ET",
            b"BT /F1 9 Tf 48 752 Td 0 -14 Td",
        ]
        for line in chunk:
            commands.append(b"(" + _pdf_literal(line) + b") Tj 0 -14 Td")
        commands.append(b"ET")
        stream = b"\n".join(commands) + b"\n"
        objects[page_id] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + f"{content_id} 0 R".encode("ascii")
            + b" >>"
        )
        objects[content_id] = (
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"endstream"
        )

    output = io.BytesIO()
    output.write(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects) + 1):
        offsets.append(output.tell())
        output.write(f"{object_id} 0 obj\n".encode("ascii"))
        output.write(objects[object_id])
        output.write(b"\nendobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    file_id = source_digest.removeprefix("sha256:")[:32]
    output.write(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R /Info 4 0 R "
            f"/ID [<{file_id}><{file_id}>] >>\nstartxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    content = output.getvalue()
    if len(content) > MAX_RENDERED_BYTES:
        raise ServiceExecutionError("output_limit_exceeded")
    return content


def _render_pdf(
    *,
    title: str,
    document_id: str,
    source_timestamp: object,
    lines: list[str],
    filename_base: str,
    filter_material: object,
    source_material: object,
) -> RenderedOutput:
    source_digest = canonical_digest(source_material)
    content = _pdf_bytes(
        title=title,
        document_id=document_id,
        source_timestamp=_source_timestamp(source_timestamp),
        lines=lines,
        source_digest=source_digest,
    )
    return RenderedOutput(
        content=content,
        filename=safe_filename(filename_base, "pdf"),
        content_type="application/pdf",
        source_digest=source_digest,
        filter_digest=canonical_digest(filter_material),
        renderer_version=PDF_RENDERER_VERSION,
        row_count=max(1, len(lines)),
    )


def render_report_pdf(report: ReportResponse) -> RenderedOutput:
    source = report.model_dump(mode="json", by_alias=True, exclude={"next_cursor"})
    headings = " | ".join(column.label for column in report.columns)
    rows = [
        " | ".join(_visible_text(row.get(column.key)) for column in report.columns)
        for row in report.rows
    ]
    lines = [headings, "-" * min(92, len(headings)), *rows]
    return _render_pdf(
        title=f"{report.report_id} report",
        document_id=f"report:{report.report_id}:{report.source_version}",
        source_timestamp=report.as_of,
        lines=lines,
        filename_base=f"{report.report_id}_report",
        filter_material=report.filters,
        source_material=source,
    )


def render_payslip_pdf(source: dict[str, Any]) -> RenderedOutput:
    lines = [
        f"Employee: {source['employeeName']}",
        f"Period: {source['period']}",
        f"Payment date: {source['paymentDate']}",
        "Earnings",
        *[f"{item['label']}: AED {item['amount']}" for item in source["earnings"]],
        "Deductions",
        *[f"{item['label']}: AED {item['amount']}" for item in source["deductions"]],
        f"Gross pay: AED {source['grossPay']}",
        f"Total deductions: AED {source['totalDeductions']}",
        f"Net pay: AED {source['netPay']}",
    ]
    return _render_pdf(
        title="Payslip",
        document_id=f"payslip:{source['id']}",
        source_timestamp=source["issuedAt"],
        lines=lines,
        filename_base=f"payslip_{source['period']}_{source.get('employeeNumber') or source['id']}",
        filter_material={"payslipId": source["id"]},
        source_material=source,
    )


def render_letter_request_pdf(source: dict[str, Any]) -> RenderedOutput:
    lines = [
        f"Reference: {source['requestId']}",
        f"Completed: {str(source['completedAt'])[:10]}",
        f"To: {source['purpose']}",
        "",
        f"This letter confirms the employment of {source['employeeName']}.",
        f"Job title: {source['jobTitle']}",
        f"Department: {source['department']}",
        f"Branch: {source['branchName']}",
        f"Employment start date: {source['employmentStartDate'] or 'Not recorded'}",
    ]
    if source["basicSalary"] is not None:
        lines.append(f"Basic salary: AED {source['basicSalary']}")
    if source["allowance"] is not None:
        lines.append(f"Allowance: AED {source['allowance']}")
    return _render_pdf(
        title="Employment letter",
        document_id=f"letter-request:{source['requestId']}",
        source_timestamp=source["completedAt"],
        lines=lines,
        filename_base=f"letter_{source['requestId']}",
        filter_material={"requestId": source["requestId"]},
        source_material=source,
    )


def render_offboarding_letter_pdf(source: dict[str, Any], letter_kind: str) -> RenderedOutput:
    if letter_kind not in {"noc", "experience"}:
        raise ServiceExecutionError("validation_failed")
    if letter_kind == "noc":
        body = [
            f"This confirms that {source['employeeName']} completed the offboarding process.",
            "The company records no pending objection within the completed checklist.",
        ]
        title = "No objection certificate"
    else:
        body = [
            f"This confirms that {source['employeeName']} worked as {source['jobTitle']}.",
            f"Employment period: {source['employmentStartDate']} to {source['terminationDate']}.",
        ]
        title = "Experience letter"
    lines = [
        f"Reference: {source['checklistId']}",
        f"Completed: {str(source['completedAt'])[:10]}",
        f"Branch: {source['branchName']}",
        "",
        *body,
    ]
    return _render_pdf(
        title=title,
        document_id=f"offboarding:{source['checklistId']}:{letter_kind}",
        source_timestamp=source["completedAt"],
        lines=lines,
        filename_base=f"{letter_kind}_{source['checklistId']}",
        filter_material={"checklistId": source["checklistId"], "letterKind": letter_kind},
        source_material={"letterKind": letter_kind, "source": source},
    )


def render_final_settlement_pdf(source: dict[str, Any]) -> RenderedOutput:
    amount_fields = (
        ("Final salary", "finalSalary"),
        ("Leave encashment", "leaveEncashment"),
        ("Gratuity", "gratuity"),
        ("Notice pay", "noticePay"),
        ("Other earnings", "otherEarnings"),
        ("Advance deduction", "advanceDeduction"),
        ("Asset deduction", "assetDeduction"),
        ("Notice deduction", "noticeDeduction"),
        ("Other deductions", "otherDeductions"),
        ("Gross amount", "grossAmount"),
        ("Total deductions", "totalDeductions"),
        ("Net amount", "netAmount"),
    )
    lines = [
        f"Settlement ID: {source['id']}",
        f"Employee ID: {source['employeeId']}",
        f"Policy: {source['policyVersion']} ({source['policyDigest']})",
        f"Source digest: {source['sourceDigest']}",
        f"Completed: {source['completedAt']}",
        "",
        *[f"{label}: AED {source[key]}" for label, key in amount_fields],
    ]
    return _render_pdf(
        title="Final settlement",
        document_id=f"final-settlement:{source['id']}",
        source_timestamp=source["completedAt"],
        lines=lines,
        filename_base=f"final_settlement_{source['id']}",
        filter_material={"settlementId": source["id"]},
        source_material=source,
    )


def render_payslip_zip(
    *,
    run_id: uuid.UUID,
    finalized_at: object,
    payslips: list[dict[str, Any]],
) -> RenderedOutput:
    timestamp = _source_timestamp(finalized_at)
    if not payslips or len(payslips) > MAX_ZIP_ENTRIES:
        raise ServiceExecutionError("output_limit_exceeded")
    ordered = sorted(
        payslips,
        key=lambda item: (
            str(item.get("employeeNumber") or ""),
            str(item["employeeId"]),
            str(item["id"]),
        ),
    )
    rendered: list[tuple[str, bytes]] = []
    used_names: set[str] = set()
    for source in ordered:
        output = render_payslip_pdf(source)
        filename = output.filename
        if filename in used_names:
            filename = safe_filename(f"{filename[:-4]}_{source['id']}", "pdf")
        if filename in used_names or "/" in filename or "\\" in filename:
            raise ServiceExecutionError("validation_failed")
        used_names.add(filename)
        rendered.append((filename, output.content))
    total_uncompressed = sum(len(content) for _name, content in rendered)
    if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
        raise ServiceExecutionError("output_limit_exceeded")
    manifest = {
        "rendererVersion": ZIP_RENDERER_VERSION,
        "payrollRunId": str(run_id),
        "entries": [
            {
                "filename": name,
                "byteCount": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
            for name, content in rendered
        ],
    }
    manifest_bytes = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    zip_time = (
        max(1980, timestamp.year),
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second - timestamp.second % 2,
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", allowZip64=False) as archive:
        for name, content in [*rendered, ("manifest.json", manifest_bytes)]:
            info = zipfile.ZipInfo(name, zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.flag_bits |= 0x800
            archive.writestr(
                info,
                content,
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=ZIP_COMPRESSION_LEVEL,
            )
    content = buffer.getvalue()
    if len(content) > MAX_RENDERED_BYTES:
        raise ServiceExecutionError("output_limit_exceeded")
    source_material = {"runId": str(run_id), "finalizedAt": timestamp, "payslips": ordered}
    return RenderedOutput(
        content=content,
        filename=safe_filename(f"payslips_{run_id}", "zip"),
        content_type="application/zip",
        source_digest=canonical_digest(source_material),
        filter_digest=canonical_digest({"runId": str(run_id)}),
        renderer_version=ZIP_RENDERER_VERSION,
        row_count=len(rendered),
    )
