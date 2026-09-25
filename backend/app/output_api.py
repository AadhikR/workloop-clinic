from __future__ import annotations

import calendar
import re
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated, cast

from fastapi import APIRouter, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    VerifiedAccessToken,
)
from app.db.output_audit import append_output_audit
from app.http.errors import error_response_documentation, success_response_documentation
from app.repositories.outputs import OutputRepository
from app.repositories.reports import SqlReportRepository
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.outputs import RenderedOutput, delivery_headers, render_csv
from app.services.reports import ReportCursorCodec, ReportQuery, ReportService, column

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])

ERRORS = error_response_documentation(
    "validation_failed",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "invalid_branch",
    "branch_required",
    "output_limit_exceeded",
    "report_source_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)
PERIOD = re.compile(r"^(?:19|20)[0-9]{2}-(?:0[1-9]|1[0-2])$")

EMPLOYEE_COLUMNS = [
    column("employeeNumber", "Emp No"),
    column("employeeName", "Name"),
    column("molId", "MOL ID"),
    column("jobTitle", "Job Title"),
    column("department", "Department"),
    column("status", "Status"),
    column("basicSalary", "Basic Salary", "decimal", scale=2),
    column("housing", "Housing", "decimal", scale=2),
    column("transport", "Transport", "decimal", scale=2),
    column("totalPackage", "Total Package", "decimal", scale=2),
    column("bank", "Bank"),
    column("bankRoutingCode", "Bank Routing Code"),
    column("iban", "IBAN"),
    column("nationality", "Nationality"),
    column("visaType", "Visa Type"),
    column("visaExpiry", "Visa Expiry", "date", nullable=True),
    column("passportExpiry", "Passport Expiry", "date", nullable=True),
    column("emiratesId", "Emirates ID"),
    column("emiratesIdExpiry", "EID Expiry", "date", nullable=True),
    column("labourCardExpiry", "Labour Card Expiry", "date", nullable=True),
]
TEMPLATE_COLUMNS = [
    column(key, label)
    for key, label in (
        ("number", "No"),
        ("month", "Month"),
        ("name", "Name"),
        ("labourCard", "Labor Card No"),
        ("bank", "Bank"),
        ("routing", "Bank / Routing Code"),
        ("account", "Bank Account No"),
        ("basic", "Basic"),
        ("allowance", "Allowance"),
        ("increment", "Increment"),
        ("bonus", "Bonus"),
        ("otherPay", "Other Pay"),
        ("leaveDeduction", "Leave Deduction"),
        ("salaryDeduction", "Salary Deduction"),
        ("loanDeduction", "Loan Deduction"),
        ("otherDeduction", "Other Deduction"),
        ("wpsBasic", "WPS BASIC"),
        ("wpsAllowance", "WPS ALLOW"),
        ("total", "TOTAL"),
    )
]
TEMPLATE_ROW = {
    "number": "1",
    "month": "May 2026",
    "name": "Sample Employee",
    "labourCard": "10003048635715",
    "bank": "ENBD",
    "routing": "302620122",
    "account": "AE080260001014950445301",
    "basic": "5000.00",
    "allowance": "3000.00",
    "increment": "0",
    "bonus": "0",
    "otherPay": "0",
    "leaveDeduction": "0",
    "salaryDeduction": "0",
    "loanDeduction": "0",
    "otherDeduction": "0",
    "wpsBasic": "5000.00",
    "wpsAllowance": "3000.00",
    "total": "8000.00",
}
ROSTER_COLUMNS = [
    column("date", "Date", "date"),
    column("employeeNumber", "Employee number"),
    column("employeeName", "Employee"),
    column("department", "Department"),
    column("shiftCode", "Shift code"),
    column("shiftName", "Shift"),
    column("shiftCategory", "Shift category"),
    column("plannedHours", "Planned hours", "decimal", scale=2),
]
NAFIS_COLUMNS = [
    column("employeeId", "Employee ID"),
    column("employeeName", "Employee"),
    column("nafisRegistrationNumber", "Nafis registration number", nullable=True),
    column("qualifyingBasicWage", "Qualifying basic wage", "decimal", scale=2),
]


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _report_service(request: Request, connection: AsyncConnection) -> ReportService:
    codec = cast(ReportCursorCodec, request.app.state.report_cursor_codec)
    return ReportService(SqlReportRepository(connection), codec)


async def _audit(
    connection: AsyncConnection,
    output: RenderedOutput,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
) -> None:
    await append_output_audit(
        connection,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        format="csv",
        filter_digest=output.filter_digest,
        source_digest=output.source_digest,
        renderer_version=output.renderer_version,
        row_count=output.row_count,
        byte_count=len(output.content),
    )


async def _execute(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    operation: Callable[[AsyncConnection], Awaitable[RenderedOutput]],
) -> Response:
    output = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id,
        operation=operation,
    )
    return Response(
        content=output.content,
        media_type=output.content_type,
        headers=delivery_headers(output, str(request.state.correlation_id)),
    )


@router.get(
    "/employees/template.csv",
    response_class=Response,
    responses={**success_response_documentation(200, "Employee CSV template"), **ERRORS},
)
async def employee_template(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> Response:
    async def operation(connection: AsyncConnection) -> RenderedOutput:
        output = render_csv(
            columns=TEMPLATE_COLUMNS,
            rows=[TEMPLATE_ROW],
            filename_base="employee_import_template",
            filter_material={"kind": "template"},
            source_material={"version": 1, "columns": [item.key for item in TEMPLATE_COLUMNS]},
        )
        await _audit(
            connection,
            output,
            action="employee_csv_exported",
            entity_type="employee_export",
            entity_id=selected,
        )
        return output

    return await _execute(request, claims, principal, selected, operation)


@router.get(
    "/employees.csv",
    response_class=Response,
    responses={**success_response_documentation(200, "Employee CSV export"), **ERRORS},
)
async def employee_export(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    employee_id: Annotated[uuid.UUID | None, Query(alias="employeeId")] = None,
) -> Response:
    async def operation(connection: AsyncConnection) -> RenderedOutput:
        rows = await OutputRepository(connection).employees(
            principal.company_id, selected, employee_id
        )
        output = render_csv(
            columns=EMPLOYEE_COLUMNS,
            rows=rows,
            filename_base="employees_export",
            filter_material={"employeeId": employee_id},
            source_material=rows,
        )
        await _audit(
            connection,
            output,
            action="employee_csv_exported",
            entity_type="employee_export",
            entity_id=selected,
        )
        return output

    return await _execute(request, claims, principal, selected, operation)


@router.get(
    "/leave-balances.csv",
    response_class=Response,
    responses={**success_response_documentation(200, "Leave balance CSV export"), **ERRORS},
)
async def leave_balance_export(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    year: Annotated[int, Query(ge=1900, le=2100)],
) -> Response:
    async def operation(connection: AsyncConnection) -> RenderedOutput:
        report = await _report_service(request, connection).read_export(
            "leaveBalance",
            principal,
            selected,
            ReportQuery(date_from=date(year, 1, 1), date_to=date(year, 12, 31)),
        )
        output = render_csv(
            columns=report.columns,
            rows=report.rows,
            filename_base=f"leave_balances_{year}",
            filter_material={"year": year},
            source_material={"rows": report.rows, "sourceVersion": report.source_version},
        )
        await _audit(
            connection,
            output,
            action="leave_balance_csv_exported",
            entity_type="leave_balance_year",
            entity_id=selected,
        )
        return output

    return await _execute(request, claims, principal, selected, operation)


@router.get(
    "/attendance/{period_id}.csv",
    response_class=Response,
    responses={**success_response_documentation(200, "Attendance CSV export"), **ERRORS},
)
async def attendance_export(
    period_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> Response:
    async def operation(connection: AsyncConnection) -> RenderedOutput:
        period = await OutputRepository(connection).attendance_period(
            principal.company_id, selected, period_id
        )
        report = await _report_service(request, connection).read_export(
            "attendanceSummary", principal, selected, ReportQuery(period=period)
        )
        output = render_csv(
            columns=report.columns,
            rows=report.rows,
            filename_base=f"attendance_{period}",
            filter_material={"periodId": period_id, "period": period},
            source_material={"rows": report.rows, "sourceVersion": report.source_version},
        )
        await _audit(
            connection,
            output,
            action="attendance_csv_exported",
            entity_type="attendance_period",
            entity_id=period_id,
        )
        return output

    return await _execute(request, claims, principal, selected, operation)


@router.get(
    "/roster.csv",
    response_class=Response,
    responses={**success_response_documentation(200, "Roster CSV export"), **ERRORS},
)
async def roster_export(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    period: Annotated[str, Query(min_length=7, max_length=7)],
) -> Response:
    if PERIOD.fullmatch(period) is None:
        raise ServiceExecutionError("validation_failed")
    year, month = (int(value) for value in period.split("-"))
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])

    async def operation(connection: AsyncConnection) -> RenderedOutput:
        rows = await OutputRepository(connection).roster(principal.company_id, selected, start, end)
        output = render_csv(
            columns=ROSTER_COLUMNS,
            rows=rows,
            filename_base=f"roster_{period}",
            filter_material={"period": period},
            source_material=rows,
            bom=True,
        )
        await _audit(
            connection,
            output,
            action="roster_csv_exported",
            entity_type="roster_month",
            entity_id=selected,
        )
        return output

    return await _execute(request, claims, principal, selected, operation)


@router.get(
    "/nafis/{snapshot_id}.csv",
    response_class=Response,
    responses={**success_response_documentation(200, "Nafis CSV export"), **ERRORS},
)
async def nafis_export(
    snapshot_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
) -> Response:
    async def operation(connection: AsyncConnection) -> RenderedOutput:
        period, rows, source = await OutputRepository(connection).nafis(
            principal.company_id, selected, snapshot_id
        )
        output = render_csv(
            columns=NAFIS_COLUMNS,
            rows=rows,
            filename_base=f"Nafis_Emiratization_Report_{period}",
            filter_material={"snapshotId": snapshot_id},
            source_material=source,
        )
        await _audit(
            connection,
            output,
            action="nafis_csv_exported",
            entity_type="nafis_report",
            entity_id=snapshot_id,
        )
        return output

    return await _execute(request, claims, principal, selected, operation)
