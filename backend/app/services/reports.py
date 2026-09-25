from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import uuid
import zlib
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol, cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.schemas.reports import ReportColumn, ReportResponse, ReportTotals
from app.services.execution import ServiceExecutionError
from app.services.offboarding import calculate_gratuity


@dataclass(frozen=True, slots=True)
class ReportQuery:
    date_from: date | None = None
    date_to: date | None = None
    period: str | None = None
    status: str | None = None
    employee_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    limit: int = 50
    cursor: str | None = None


@dataclass(frozen=True, slots=True)
class ReportSpec:
    filters: frozenset[str]
    columns: tuple[ReportColumn, ...]
    decimal_totals: tuple[str, ...] = ()
    integer_totals: tuple[str, ...] = ()


def column(
    key: str,
    label: str,
    kind: str = "string",
    *,
    scale: int | None = None,
    nullable: bool = False,
) -> ReportColumn:
    return ReportColumn(key=key, label=label, type=kind, scale=scale, nullable=nullable)  # type: ignore[arg-type]


COMMON_PAGE_FILTERS = frozenset({"limit", "cursor"})

REPORT_SPECS: dict[str, ReportSpec] = {
    "headcount": ReportSpec(
        COMMON_PAGE_FILTERS | {"status", "departmentId"},
        (
            column("employeeId", "Employee ID"),
            column("employeeNumber", "Employee number"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("nationality", "Nationality"),
            column("contractType", "Contract type"),
            column("gender", "Gender"),
            column("status", "Status"),
        ),
    ),
    "payrollCost": ReportSpec(
        COMMON_PAGE_FILTERS | {"period"},
        (
            column("runId", "Run ID"),
            column("period", "Period"),
            column("paymentDate", "Payment date", "date", nullable=True),
            column("employeeCount", "Employees", "integer"),
            column("basic", "Basic", "decimal", scale=2),
            column("allowances", "Allowances", "decimal", scale=2),
            column("otherEarnings", "Other earnings", "decimal", scale=2),
            column("gross", "Gross", "decimal", scale=2),
            column("deductions", "Deductions", "decimal", scale=2),
            column("net", "Net", "decimal", scale=2),
        ),
        decimal_totals=("basic", "allowances", "otherEarnings", "gross", "deductions", "net"),
        integer_totals=("employeeCount",),
    ),
    "leaveUtilization": ReportSpec(
        COMMON_PAGE_FILTERS | {"from", "to", "employeeId", "departmentId"},
        (
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("leaveType", "Leave type"),
            column("requestCount", "Requests", "integer"),
            column("days", "Days", "decimal", scale=2),
        ),
        decimal_totals=("days",),
        integer_totals=("requestCount",),
    ),
    "attendanceSummary": ReportSpec(
        COMMON_PAGE_FILTERS | {"period", "status", "employeeId", "departmentId"},
        (
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("days", "Days", "integer"),
            column("present", "Present", "integer"),
            column("absent", "Absent", "integer"),
            column("late", "Late", "integer"),
            column("earlyDeparture", "Early departure", "integer"),
            column("hours", "Hours", "decimal", scale=2),
        ),
        decimal_totals=("hours",),
        integer_totals=("days", "present", "absent", "late", "earlyDeparture"),
    ),
    "overtime": ReportSpec(
        COMMON_PAGE_FILTERS | {"period", "employeeId", "departmentId"},
        (
            column("recordId", "Record ID"),
            column("date", "Date", "date"),
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("hours", "Approved hours", "decimal", scale=2),
            column("amount", "Approved amount", "decimal", scale=2),
            column("approvedAt", "Approved at", "timestamp", nullable=True),
        ),
        decimal_totals=("hours", "amount"),
    ),
    "documentExpiry": ReportSpec(
        COMMON_PAGE_FILTERS | {"from", "to", "status", "employeeId", "departmentId"},
        (
            column("sourceId", "Source ID"),
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("sourceKind", "Source kind"),
            column("documentType", "Document type"),
            column("expiryDate", "Expiry date", "date"),
            column("status", "Status"),
        ),
    ),
    "salaryMovement": ReportSpec(
        COMMON_PAGE_FILTERS | {"from", "to", "employeeId", "departmentId"},
        (
            column("eventId", "Event ID"),
            column("effectiveAt", "Effective at", "timestamp"),
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("oldSalary", "Old salary", "decimal", scale=2),
            column("newSalary", "New salary", "decimal", scale=2),
            column("reason", "Reason"),
        ),
    ),
    "turnover": ReportSpec(
        COMMON_PAGE_FILTERS | {"from", "to", "status", "departmentId"},
        (
            column("employeeId", "Employee ID"),
            column("eventType", "Event type"),
            column("eventDate", "Event date", "date"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("status", "Status"),
            column("tenureDays", "Tenure days", "integer", nullable=True),
        ),
    ),
    "staffingCompliance": ReportSpec(
        COMMON_PAGE_FILTERS | {"period", "departmentId"},
        (
            column("overrideId", "Override ID"),
            column("date", "Date", "date"),
            column("department", "Department"),
            column("shiftCategory", "Shift category"),
            column("required", "Required", "integer"),
            column("assigned", "Assigned", "integer"),
            column("shortage", "Shortage", "integer"),
            column("overridden", "Overridden", "boolean"),
            column("overrideReason", "Override reason"),
        ),
        integer_totals=("required", "assigned", "shortage"),
    ),
    "wpsCompliance": ReportSpec(
        COMMON_PAGE_FILTERS | {"period", "status", "employeeId", "departmentId"},
        (
            column("entryId", "Entry ID"),
            column("period", "Period"),
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("runStatus", "Run status"),
            column("entryStatus", "Entry status"),
            column("rejectionReason", "Rejection reason"),
        ),
    ),
    "emiratization": ReportSpec(
        COMMON_PAGE_FILTERS | {"period"},
        (
            column("snapshotId", "Snapshot ID"),
            column("period", "Period"),
            column("headcount", "Headcount", "integer"),
            column("emiratiCount", "Emirati employees", "integer"),
            column("ratioPercent", "Ratio", "decimal", scale=2),
            column("requiredPercent", "Required ratio", "decimal", scale=2),
            column("compliant", "Compliant", "boolean"),
            column("generatedAt", "Generated at", "timestamp"),
        ),
        integer_totals=("headcount", "emiratiCount"),
    ),
    "eosLiability": ReportSpec(
        COMMON_PAGE_FILTERS | {"status", "employeeId", "departmentId"},
        (
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("status", "Status"),
            column("policyVersion", "Policy version"),
            column("serviceDays", "Paid service days", "integer", nullable=True),
            column("liability", "Liability", "decimal", scale=2, nullable=True),
            column("unavailableReason", "Unavailable reason", nullable=True),
        ),
        decimal_totals=("liability",),
    ),
    "leaveBalance": ReportSpec(
        COMMON_PAGE_FILTERS | {"from", "to", "employeeId", "departmentId"},
        (
            column("balanceId", "Balance ID"),
            column("employeeId", "Employee ID"),
            column("employeeName", "Employee"),
            column("department", "Department"),
            column("leaveYear", "Year", "integer"),
            column("leaveType", "Leave type"),
            column("entitled", "Entitled", "decimal", scale=2),
            column("accrued", "Accrued", "decimal", scale=2),
            column("used", "Used", "decimal", scale=2),
            column("pending", "Pending", "decimal", scale=2),
            column("carriedForward", "Carried forward", "decimal", scale=2),
            column("remaining", "Remaining", "decimal", scale=2),
        ),
        decimal_totals=("entitled", "accrued", "used", "pending", "carriedForward", "remaining"),
    ),
}


class ReportRepository(Protocol):
    async def resolve_employee(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> bool: ...
    async def resolve_department(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, department_id: uuid.UUID
    ) -> str | None: ...
    async def read(
        self,
        report_id: str,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        filters: dict[str, object],
    ) -> tuple[datetime, list[dict[str, object]]]: ...


class ReportCursorCodec:
    def __init__(self, key: bytes, *, clock: Callable[[], datetime] | None = None) -> None:
        if len(key) != 32:
            raise ValueError("cursor key must contain 32 bytes")
        self._cipher = AESGCM(key)
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_base64url(cls, value: str) -> ReportCursorCodec:
        try:
            key = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("invalid cursor key") from None
        return cls(key)

    @staticmethod
    def _context(report_id: str, query: ReportQuery) -> str:
        values = asdict(query)
        values.pop("cursor")
        values.pop("limit")
        raw = json.dumps(values, default=str, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(report_id.encode() + b":" + raw).hexdigest()

    def encode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        report_id: str,
        query: ReportQuery,
        offset: int,
        source_version: str,
    ) -> str:
        payload = {
            "appUserId": str(principal.app_user_id),
            "branchId": str(branch_id),
            "companyId": str(principal.company_id),
            "context": self._context(report_id, query),
            "expiresAt": int((self._clock() + timedelta(minutes=15)).timestamp()),
            "offset": offset,
            "reportId": report_id,
            "role": principal.role.value,
            "sourceVersion": source_version,
            "version": 1,
        }
        plaintext = zlib.compress(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), 9
        )
        nonce = secrets.token_bytes(12)
        encrypted = self._cipher.encrypt(nonce, plaintext, b"workloop:reports:v1")
        return base64.urlsafe_b64encode(b"\x01" + nonce + encrypted).decode().rstrip("=")

    def decode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        report_id: str,
        query: ReportQuery,
    ) -> tuple[int, str] | None:
        if query.cursor is None:
            return None
        try:
            raw = base64.b64decode(
                query.cursor + "=" * (-len(query.cursor) % 4), altchars=b"-_", validate=True
            )
            if len(raw) < 30 or raw[0] != 1:
                raise ValueError
            value = cast(
                dict[str, Any],
                json.loads(
                    zlib.decompress(
                        self._cipher.decrypt(raw[1:13], raw[13:], b"workloop:reports:v1")
                    ).decode()
                ),
            )
        except (
            InvalidTag,
            UnicodeError,
            ValueError,
            binascii.Error,
            json.JSONDecodeError,
            zlib.error,
        ):
            raise ValueError("invalid cursor") from None
        expected = {
            "appUserId",
            "branchId",
            "companyId",
            "context",
            "expiresAt",
            "offset",
            "reportId",
            "role",
            "sourceVersion",
            "version",
        }
        if (
            set(value) != expected
            or value.get("version") != 1
            or value.get("reportId") != report_id
            or value.get("role") != principal.role.value
            or value.get("appUserId") != str(principal.app_user_id)
            or value.get("companyId") != str(principal.company_id)
            or value.get("branchId") != str(branch_id)
            or value.get("context") != self._context(report_id, query)
            or not isinstance(value.get("expiresAt"), int)
            or cast(int, value["expiresAt"]) <= int(self._clock().timestamp())
            or not isinstance(value.get("offset"), int)
            or cast(int, value["offset"]) < 0
            or not isinstance(value.get("sourceVersion"), str)
        ):
            raise ValueError("invalid cursor")
        return cast(int, value["offset"]), cast(str, value["sourceVersion"])


def _json_value(value: object, scale: int | None = None) -> str | int | bool | None:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, Decimal):
        return f"{value:.{scale if scale is not None else 2}f}"
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"unsupported report value: {type(value).__name__}")


class ReportService:
    def __init__(self, repository: ReportRepository, cursor_codec: ReportCursorCodec) -> None:
        self.repository = repository
        self.cursor_codec = cursor_codec

    async def read(
        self,
        report_id: str,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: ReportQuery,
    ) -> ReportResponse:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        spec = REPORT_SPECS.get(report_id)
        if spec is None:
            raise ServiceExecutionError("resource_not_found")
        department: str | None = None
        try:
            if query.employee_id is not None and not await self.repository.resolve_employee(
                principal.company_id, branch_id, query.employee_id
            ):
                raise ServiceExecutionError("resource_not_found")
            if query.department_id is not None:
                department = await self.repository.resolve_department(
                    principal.company_id, branch_id, query.department_id
                )
                if department is None:
                    raise ServiceExecutionError("resource_not_found")
        except ServiceExecutionError:
            raise
        except Exception:
            raise ServiceExecutionError("report_source_unavailable") from None
        filters: dict[str, object] = {
            "date_from": query.date_from,
            "date_to": query.date_to,
            "period": query.period,
            "status": query.status,
            "employee_id": query.employee_id,
            "department": department,
        }
        try:
            decoded = self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                report_id=report_id,
                query=query,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        try:
            as_of, raw_rows = await self.repository.read(
                report_id, company_id=principal.company_id, branch_id=branch_id, filters=filters
            )
        except ServiceExecutionError:
            raise
        except Exception:
            raise ServiceExecutionError("report_source_unavailable") from None
        if report_id == "eosLiability":
            raw_rows = self._eos_rows(raw_rows)
        scales = {item.key: item.scale for item in spec.columns}
        rows = [
            {key: _json_value(value, scales.get(key)) for key, value in row.items()}
            for row in raw_rows
        ]
        canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"))
        source_version = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
        offset = 0 if decoded is None else decoded[0]
        if decoded is not None and decoded[1] != source_version:
            raise ServiceExecutionError("invalid_cursor")
        if offset > len(rows):
            raise ServiceExecutionError("invalid_cursor")
        totals_values: dict[str, str | int | dict[str, int]] = {}
        for key in spec.decimal_totals:
            values = [Decimal(cast(str, row[key])) for row in rows if row.get(key) is not None]
            totals_values[key] = f"{sum(values, Decimal('0')):.2f}"
        for key in spec.integer_totals:
            totals_values[key] = sum(cast(int, row.get(key, 0)) for row in rows)
        if report_id == "headcount":
            totals_values["activeEmployees"] = len(rows)
            for field, total_key in (
                ("department", "byDepartment"),
                ("nationality", "byNationality"),
                ("contractType", "byContractType"),
                ("gender", "byGender"),
                ("status", "byStatus"),
            ):
                groups: dict[str, int] = {}
                for row in rows:
                    group = cast(str, row[field])
                    groups[group] = groups.get(group, 0) + 1
                totals_values[total_key] = dict(sorted(groups.items()))
        visible = rows[offset : offset + query.limit]
        next_offset = offset + len(visible)
        next_cursor = None
        if next_offset < len(rows):
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                report_id=report_id,
                query=query,
                offset=next_offset,
                source_version=source_version,
            )
        normalized_filters = {
            "from": query.date_from.isoformat() if query.date_from else None,
            "to": query.date_to.isoformat() if query.date_to else None,
            "period": query.period,
            "status": query.status,
            "employeeId": str(query.employee_id) if query.employee_id else None,
            "departmentId": str(query.department_id) if query.department_id else None,
            "limit": query.limit,
        }
        return ReportResponse(
            report_id=report_id,
            columns=list(spec.columns),
            rows=visible,
            totals=ReportTotals(row_count=len(rows), values=totals_values),
            filters={
                key: value
                for key, value in normalized_filters.items()
                if key in spec.filters or key == "limit"
            },
            as_of=as_of,
            source_version=source_version,
            next_cursor=next_cursor,
        )

    async def read_export(
        self,
        report_id: str,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: ReportQuery,
        *,
        maximum_rows: int = 5_000,
    ) -> ReportResponse:
        active_query = replace(query, limit=200, cursor=None)
        first = await self.read(report_id, principal, branch_id, active_query)
        rows = list(first.rows)
        next_cursor = first.next_cursor
        while next_cursor is not None:
            if len(rows) >= maximum_rows:
                raise ServiceExecutionError("output_limit_exceeded")
            active_query = replace(active_query, cursor=next_cursor)
            page = await self.read(report_id, principal, branch_id, active_query)
            if page.source_version != first.source_version or page.columns != first.columns:
                raise ServiceExecutionError("report_source_unavailable")
            rows.extend(page.rows)
            next_cursor = page.next_cursor
        if len(rows) > maximum_rows:
            raise ServiceExecutionError("output_limit_exceeded")
        filters = dict(first.filters)
        filters.pop("limit", None)
        return first.model_copy(update={"rows": rows, "filters": filters, "next_cursor": None})

    @staticmethod
    def _eos_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in rows:
            reason: str | None = None
            nationality = str(row.pop("nationality"))
            location = str(row.pop("workLocationType"))
            policy_available = bool(row.pop("policyAvailable"))
            basic = Decimal(cast(Decimal, row.pop("basicSalary")))
            service_days = cast(int, row["serviceDays"])
            if not policy_available:
                reason = "policy_unavailable"
            elif not nationality:
                reason = "nationality_unavailable"
            elif nationality.casefold() in {"uae", "emirati", "united arab emirates"}:
                reason = "uae_national_not_supported"
            elif location != "mainland":
                reason = "work_location_not_supported"
            liability = None if reason else calculate_gratuity(basic, Decimal(service_days))[0]
            result.append(
                {
                    **row,
                    "status": "unavailable" if reason else "available",
                    "liability": liability,
                    "unavailableReason": reason,
                }
            )
        return result
