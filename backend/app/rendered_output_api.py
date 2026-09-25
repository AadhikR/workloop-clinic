from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, Response
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import AuthenticatedReadPrincipal, VerifiedAccessToken
from app.db.output_audit import append_output_audit
from app.http.errors import error_response_documentation, success_response_documentation
from app.models.identity import AppRole
from app.report_api import report_branch, report_query, report_service
from app.repositories.outputs import OutputRepository
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.letter_requests import LetterRequestService
from app.services.offboarding import OffboardingService
from app.services.outputs import RenderedOutput, delivery_headers
from app.services.rendered_outputs import (
    render_bounded,
    render_final_settlement_pdf,
    render_letter_request_pdf,
    render_offboarding_letter_pdf,
    render_payslip_pdf,
    render_payslip_zip,
    render_report_pdf,
)

report_router = APIRouter(prefix="/api/v1/reports", tags=["rendered-outputs"])
payslip_router = APIRouter(prefix="/api/v1/payslips", tags=["rendered-outputs"])
payroll_router = APIRouter(prefix="/api/v1/payroll-runs", tags=["rendered-outputs"])
request_router = APIRouter(prefix="/api/v1/requests", tags=["rendered-outputs"])
offboarding_router = APIRouter(prefix="/api/v1/offboarding", tags=["rendered-outputs"])

ERRORS = error_response_documentation(
    "invalid_request",
    "unknown_filter",
    "validation_failed",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "invalid_branch",
    "branch_required",
    "state_conflict",
    "output_limit_exceeded",
    "report_source_unavailable",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _branch(request: Request, principal: AuthorizationPrincipal) -> uuid.UUID:
    if principal.role is AppRole.ADMIN:
        return report_branch(request, principal)
    if principal.role is AppRole.EMPLOYEE and principal.employee_id and principal.branch_id:
        if request.headers.getlist("x-workloop-branch-id"):
            raise ServiceExecutionError("operation_not_permitted")
        return principal.branch_id
    raise ServiceExecutionError("operation_not_permitted")


async def _deliver(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    producer: Callable[[AsyncConnection], Awaitable[tuple[RenderedOutput, str, str, uuid.UUID]]],
) -> Response:
    async def operation(
        connection: AsyncConnection,
    ) -> RenderedOutput:
        output, action, entity_type, entity_id = await producer(connection)
        await append_output_audit(
            connection,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            format="zip" if output.content_type == "application/zip" else "pdf",
            filter_digest=output.filter_digest,
            source_digest=output.source_digest,
            renderer_version=output.renderer_version,
            row_count=output.row_count,
            byte_count=len(output.content),
        )
        return output

    output = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation=operation,
    )
    return Response(
        content=output.content,
        media_type=output.content_type,
        headers=delivery_headers(output, str(request.state.correlation_id)),
    )


@report_router.get(
    "/{report_id}.pdf",
    response_class=Response,
    operation_id="download_report_pdf",
    responses={
        **success_response_documentation(200, "Administrator report PDF", cache_control="no-store"),
        **ERRORS,
    },
)
async def download_report_pdf(
    report_id: str,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    query = report_query(report_id, request)
    branch_id = report_branch(request, principal)

    async def producer(connection: AsyncConnection) -> tuple[RenderedOutput, str, str, uuid.UUID]:
        report = await report_service(request, connection).read_export(
            report_id, principal, branch_id, query, maximum_rows=2_250
        )
        output = await render_bounded(principal.app_user_id, lambda: render_report_pdf(report))
        return output, "report_pdf_exported", "report", branch_id

    return await _deliver(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        producer=producer,
    )


@payslip_router.get(
    "/self/{payslip_id}.pdf",
    response_class=Response,
    operation_id="download_self_payslip_pdf",
    responses={**success_response_documentation(200, "Own payslip PDF"), **ERRORS},
)
async def download_self_payslip_pdf(
    payslip_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    branch_id = _branch(request, principal)
    if principal.role is not AppRole.EMPLOYEE or principal.employee_id is None:
        raise ServiceExecutionError("operation_not_permitted")

    async def producer(connection: AsyncConnection) -> tuple[RenderedOutput, str, str, uuid.UUID]:
        source = await OutputRepository(connection).payslip(
            company_id=principal.company_id,
            branch_id=branch_id,
            payslip_id=payslip_id,
            employee_id=principal.employee_id,
        )
        output = await render_bounded(principal.app_user_id, lambda: render_payslip_pdf(source))
        return output, "payslip_pdf_exported", "payslip", payslip_id

    return await _deliver(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        producer=producer,
    )


@payslip_router.get(
    "/{payslip_id}.pdf",
    response_class=Response,
    operation_id="download_administrator_payslip_pdf",
    responses={**success_response_documentation(200, "Administrator payslip PDF"), **ERRORS},
)
async def download_administrator_payslip_pdf(
    payslip_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    branch_id = report_branch(request, principal)

    async def producer(connection: AsyncConnection) -> tuple[RenderedOutput, str, str, uuid.UUID]:
        source = await OutputRepository(connection).payslip(
            company_id=principal.company_id,
            branch_id=branch_id,
            payslip_id=payslip_id,
            employee_id=None,
        )
        output = await render_bounded(principal.app_user_id, lambda: render_payslip_pdf(source))
        return output, "payslip_pdf_exported", "payslip", payslip_id

    return await _deliver(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        producer=producer,
    )


@payroll_router.get(
    "/{run_id}/payslips.zip",
    response_class=Response,
    operation_id="download_payslip_zip",
    responses={**success_response_documentation(200, "Bulk payslip ZIP"), **ERRORS},
)
async def download_payslip_zip(
    run_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    branch_id = report_branch(request, principal)

    async def producer(connection: AsyncConnection) -> tuple[RenderedOutput, str, str, uuid.UUID]:
        finalized_at, payslips = await OutputRepository(connection).payslips_for_run(
            company_id=principal.company_id, branch_id=branch_id, run_id=run_id
        )
        output = await render_bounded(
            principal.app_user_id,
            lambda: render_payslip_zip(run_id=run_id, finalized_at=finalized_at, payslips=payslips),
        )
        return output, "payslip_zip_exported", "payroll_run", run_id

    return await _deliver(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        producer=producer,
    )


@request_router.get(
    "/{request_id}/letter.pdf",
    response_class=Response,
    operation_id="download_completed_request_letter_pdf",
    responses={**success_response_documentation(200, "Completed request letter PDF"), **ERRORS},
)
async def download_completed_request_letter_pdf(
    request_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    branch_id = _branch(request, principal)

    async def producer(connection: AsyncConnection) -> tuple[RenderedOutput, str, str, uuid.UUID]:
        projection = await LetterRequestService(connection).print_source(
            principal, branch_id, request_id
        )
        source = projection.model_dump(mode="json", by_alias=True)
        output = await render_bounded(
            principal.app_user_id, lambda: render_letter_request_pdf(source)
        )
        return output, "letter_pdf_exported", "letter_request", request_id

    return await _deliver(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        producer=producer,
    )


@offboarding_router.get(
    "/{checklist_id}/letters/{letter_kind}.pdf",
    response_class=Response,
    operation_id="download_offboarding_letter_pdf",
    responses={**success_response_documentation(200, "Offboarding letter PDF"), **ERRORS},
)
async def download_offboarding_letter_pdf(
    checklist_id: uuid.UUID,
    letter_kind: str,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    branch_id = report_branch(request, principal)
    if letter_kind not in {"noc", "experience"}:
        raise ServiceExecutionError("resource_not_found")

    async def producer(connection: AsyncConnection) -> tuple[RenderedOutput, str, str, uuid.UUID]:
        projection = await OffboardingService(
            connection, request.app.state.employee_cursor_codec
        ).letter_source(principal, branch_id, checklist_id)
        source = projection.model_dump(mode="json", by_alias=True)
        output = await render_bounded(
            principal.app_user_id,
            lambda: render_offboarding_letter_pdf(source, letter_kind),
        )
        return (
            output,
            "offboarding_letter_pdf_exported",
            "offboarding_checklist",
            checklist_id,
        )

    return await _deliver(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        producer=producer,
    )


@offboarding_router.get(
    "/{checklist_id}/final-settlement.pdf",
    response_class=Response,
    operation_id="download_final_settlement_pdf",
    responses={**success_response_documentation(200, "Final settlement PDF"), **ERRORS},
)
async def download_final_settlement_pdf(
    checklist_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
) -> Response:
    branch_id = report_branch(request, principal)

    async def producer(connection: AsyncConnection) -> tuple[RenderedOutput, str, str, uuid.UUID]:
        source = await OutputRepository(connection).final_settlement(
            company_id=principal.company_id,
            branch_id=branch_id,
            checklist_id=checklist_id,
        )
        output = await render_bounded(
            principal.app_user_id, lambda: render_final_settlement_pdf(source)
        )
        return (
            output,
            "final_settlement_pdf_exported",
            "final_settlement",
            uuid.UUID(str(source["id"])),
        )

    return await _deliver(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        producer=producer,
    )
