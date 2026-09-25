from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from app.schemas.reports import ReportColumn, ReportResponse
from app.schemas.wps import SifInputResponse
from app.services.execution import ServiceExecutionError

CSV_RENDERER_VERSION = "phase12f-csv-v1"
SIF_RENDERER_VERSION = "phase12f-sif-v1"
MAX_CSV_ROWS = 5_000
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
SAFE_FILENAME = re.compile(r"[^\w.-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class RenderedOutput:
    content: bytes
    filename: str
    content_type: str
    source_digest: str
    filter_digest: str
    renderer_version: str
    row_count: int

    @property
    def byte_digest_hex(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def digest_header(self) -> str:
        raw = hashlib.sha256(self.content).digest()
        return "sha-256=" + base64.b64encode(raw).decode("ascii")

    @property
    def etag(self) -> str:
        material = f"{self.renderer_version}:{self.source_digest}".encode("ascii")
        return '"' + hashlib.sha256(material).hexdigest() + '"'


def canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def safe_filename(base: str, extension: str) -> str:
    normalized = unicodedata.normalize("NFC", base)
    normalized = "_".join(normalized.split())
    normalized = normalized.replace("/", "_").replace("\\", "_")
    normalized = "".join(
        character for character in normalized if not unicodedata.category(character).startswith("C")
    )
    normalized = SAFE_FILENAME.sub("_", normalized).strip("._-") or "output"
    while len(normalized.encode("utf-8")) > 120:
        normalized = normalized[:-1]
    return f"{normalized}.{extension}"


def content_disposition(filename: str, *, disposition: str = "attachment") -> str:
    fallback = "".join(
        character if character.isascii() and (character.isalnum() or character in "._-") else "_"
        for character in filename
    )
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"


def delivery_headers(output: RenderedOutput, request_id: str) -> dict[str, str]:
    return {
        "Content-Disposition": content_disposition(output.filename),
        "Content-Length": str(len(output.content)),
        "Digest": output.digest_header,
        "ETag": output.etag,
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "X-Content-Type-Options": "nosniff",
        "X-Request-ID": request_id,
        "Vary": "Authorization",
    }


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def render_csv(
    *,
    columns: list[ReportColumn],
    rows: list[dict[str, Any]],
    filename_base: str,
    filter_material: object,
    source_material: object,
    bom: bool = False,
) -> RenderedOutput:
    if len(rows) > MAX_CSV_ROWS:
        raise ServiceExecutionError("output_limit_exceeded")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, dialect="excel", lineterminator="\r\n")
    writer.writerow([column.label for column in columns])
    for row in rows:
        writer.writerow([_csv_value(row.get(column.key)) for column in columns])
    encoded = stream.getvalue().encode("utf-8")
    if bom:
        encoded = b"\xef\xbb\xbf" + encoded
    if len(encoded) > MAX_OUTPUT_BYTES:
        raise ServiceExecutionError("output_limit_exceeded")
    return RenderedOutput(
        content=encoded,
        filename=safe_filename(filename_base, "csv"),
        content_type="text/csv; charset=utf-8",
        source_digest=canonical_digest(source_material),
        filter_digest=canonical_digest(filter_material),
        renderer_version=CSV_RENDERER_VERSION,
        row_count=len(rows),
    )


def render_report_csv(report: ReportResponse) -> RenderedOutput:
    return render_csv(
        columns=report.columns,
        rows=report.rows,
        filename_base=f"{report.report_id}_report",
        filter_material=report.filters,
        source_material={
            "reportId": report.report_id,
            "columns": [column.model_dump(mode="json", by_alias=True) for column in report.columns],
            "rows": report.rows,
            "sourceVersion": report.source_version,
        },
    )


def _sif_field(value: object) -> str:
    text = str(value)
    if (
        not text.isascii()
        or "," in text
        or any(ord(character) < 32 or ord(character) == 127 for character in text)
    ):
        raise ServiceExecutionError("validation_failed")
    return text


def render_sif(projection: SifInputResponse, *, scope: str) -> RenderedOutput:
    if scope not in {"all", "rejected"}:
        raise ServiceExecutionError("validation_failed")
    expected_mode = "rejected" if scope == "rejected" else "full"
    if projection.mode != expected_mode or not projection.entries:
        raise ServiceExecutionError("validation_failed")
    entries = sorted(
        projection.entries,
        key=lambda item: (item.employee_mol_id, str(item.payroll_entry_id)),
    )
    if entries != projection.entries:
        raise ServiceExecutionError("validation_failed")
    lines: list[str] = []
    for entry in entries:
        if entry.basic_pay + entry.variable_pay != entry.total_pay:
            raise ServiceExecutionError("validation_failed")
        values = (
            "EDR",
            entry.employee_mol_id,
            entry.bank_routing_code,
            entry.iban,
            entry.period_start.isoformat(),
            entry.period_end.isoformat(),
            entry.paid_days,
            entry.basic_pay,
            entry.variable_pay,
            0,
        )
        lines.append(",".join(_sif_field(value) for value in values))
    total = sum(item.total_pay for item in entries)
    if (
        projection.header.employee_count != len(entries)
        or projection.header.total_integer_pay != total
    ):
        raise ServiceExecutionError("validation_failed")
    sequence = int(projection.digest[:8], 16) % 10_000
    period = projection.header.period_start.strftime("%m%Y")
    description = f"Salary for {period}"
    header_values = (
        "SCR",
        projection.header.employer_mol_id,
        projection.header.branch_routing_code,
        projection.header.payment_date.isoformat(),
        f"{sequence:04d}",
        period,
        len(entries),
        total,
        "AED",
        description,
    )
    lines.append(",".join(_sif_field(value) for value in header_values))
    content = ("\r\n".join(lines) + "\r\n").encode("ascii", errors="strict")
    if len(content) > MAX_OUTPUT_BYTES:
        raise ServiceExecutionError("output_limit_exceeded")
    suffix = int(projection.digest[-12:], 16) % 1_000_000
    filename_base = (
        f"{projection.header.employer_mol_id}"
        f"{projection.header.payment_date.strftime('%y%m%d')}"
        f"{suffix:06d}"
    )
    return RenderedOutput(
        content=content,
        filename=safe_filename(filename_base, "sif"),
        content_type="application/octet-stream",
        source_digest="sha256:" + projection.digest,
        filter_digest=canonical_digest({"scope": scope}),
        renderer_version=SIF_RENDERER_VERSION,
        row_count=len(entries) + 1,
    )


def parse_sif_preview(output: RenderedOutput) -> list[dict[str, str | int]]:
    records: list[dict[str, str | int]] = []
    decoded = output.content.decode("ascii", errors="strict")
    if not decoded.endswith("\r\n") or "\n" in decoded.replace("\r\n", ""):
        raise ServiceExecutionError("validation_failed")
    for line in decoded[:-2].split("\r\n"):
        fields = line.split(",")
        if fields[0] == "EDR" and len(fields) == 10:
            records.append(
                {
                    "type": "EDR",
                    "employeeMolId": fields[1],
                    "bankRoutingCode": fields[2],
                    "iban": fields[3],
                    "periodStart": fields[4],
                    "periodEnd": fields[5],
                    "paidDays": int(fields[6]),
                    "basicPay": int(fields[7]),
                    "variablePay": int(fields[8]),
                    "leaveDays": int(fields[9]),
                }
            )
        elif fields[0] == "SCR" and len(fields) == 10:
            records.append(
                {
                    "type": "SCR",
                    "employerMolId": fields[1],
                    "bankRoutingCode": fields[2],
                    "paymentDate": fields[3],
                    "sequence": fields[4],
                    "period": fields[5],
                    "employeeCount": int(fields[6]),
                    "totalPay": int(fields[7]),
                    "currency": fields[8],
                    "description": fields[9],
                }
            )
        else:
            raise ServiceExecutionError("validation_failed")
    return records
