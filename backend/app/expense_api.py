from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from datetime import UTC, date, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedReadPrincipal,
    AuthenticatedWritePrincipal,
    VerifiedAccessToken,
)
from app.http.errors import api_error, error_response_documentation, success_response_documentation
from app.http.idempotency import parse_idempotency_key
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import CollectionResponse, DataResponse, Page
from app.models.identity import AppRole
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.expense import (
    EXPENSE_STATUSES,
    ExpenseCreateRequest,
    ExpenseDecisionRequest,
    ExpenseDeleteRequest,
    ExpenseQueueResponse,
    ExpenseResponse,
)
from app.schemas.expense_receipt import (
    ExpenseReceiptResponse,
    ReceiptDownloadResponse,
    ReceiptSubmissionRequest,
    ReceiptSubmissionResponse,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.expense_receipt import (
    ClaimedReceiptCleanup,
    ExpenseReceiptService,
)
from app.services.expenses import ExpenseCleanup, ExpenseListQuery, ExpenseService
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.leave_attachment import parse_upload
from app.storage.base import StorageError, StorageNotFoundError

router = APIRouter(prefix="/api/v1/expenses", tags=["expenses"])
logger = logging.getLogger(__name__)
ERRORS = error_response_documentation(
    "invalid_request",
    "invalid_access_token",
    "application_account_unavailable",
    "operation_not_permitted",
    "resource_not_found",
    "method_not_allowed",
    "not_acceptable",
    "request_too_large",
    "unsupported_media_type",
    "validation_failed",
    "invalid_branch",
    "branch_required",
    "invalid_cursor",
    "stale_financial_state",
    "idempotency_key_required",
    "invalid_idempotency_key",
    "idempotency_conflict",
    "idempotency_key_reused",
    "idempotency_in_progress",
    "attachment_submission_unavailable",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> ExpenseService:
    return ExpenseService(connection, request.app.state.expense_cursor_codec)


def _receipt_service(request: Request, connection: AsyncConnection) -> ExpenseReceiptService:
    return ExpenseReceiptService(
        connection,
        object_key_hmac_key=request.app.state.settings.decoded_attachment_object_key_hmac_key(),
        scanner_definition=request.app.state.settings.malware_scanner_definition,
    )


def _idempotency(request: Request, connection: AsyncConnection) -> IdempotencyCoordinator:
    factory = getattr(request.app.state, "idempotency_coordinator_factory", None)
    if factory is not None:
        return cast(IdempotencyCoordinator, factory(connection))
    return IdempotencyCoordinator(IdempotencyRepository(connection))


def _branch(principal: AuthorizationPrincipal, raw_branch: str | None) -> uuid.UUID:
    if principal.role is AppRole.ADMIN:
        if raw_branch is None:
            raise api_error("branch_required")
        try:
            branch_id = uuid.UUID(raw_branch)
        except ValueError:
            raise api_error("invalid_branch") from None
        if str(branch_id) != raw_branch:
            raise api_error("invalid_branch")
        return branch_id
    if raw_branch is not None or principal.branch_id is None:
        raise api_error("operation_not_permitted")
    return principal.branch_id


def _query(
    limit: int,
    cursor: str | None,
    claim_status: str | None,
    employee_id: uuid.UUID | None,
    from_date: date | None,
    to_date: date | None,
) -> ExpenseListQuery:
    if (claim_status is not None and claim_status not in EXPENSE_STATUSES) or (
        from_date is not None and to_date is not None and to_date < from_date
    ):
        raise api_error("validation_failed")
    return ExpenseListQuery(limit, cursor, claim_status, employee_id, from_date, to_date)


@router.get(
    "/self",
    response_model=CollectionResponse[ExpenseResponse],
    operation_id="list_self_expenses",
    responses={**success_response_documentation(200, "Own expense claims"), **ERRORS},
)
async def list_self_expenses(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    claim_status: Annotated[str | None, Query(alias="status")] = None,
    from_date: Annotated[date | None, Query(alias="fromDate")] = None,
    to_date: Annotated[date | None, Query(alias="toDate")] = None,
) -> CollectionResponse[ExpenseResponse]:
    query = _query(limit, cursor, claim_status, None, from_date, to_date)
    items, next_cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_self(principal, query),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "/manager-queue",
    response_model=CollectionResponse[ExpenseQueueResponse],
    operation_id="list_manager_expenses",
    responses={**success_response_documentation(200, "Direct-report expense queue"), **ERRORS},
)
async def list_manager_expenses(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    claim_status: Annotated[str | None, Query(alias="status")] = None,
    employee_id: Annotated[uuid.UUID | None, Query(alias="employeeId")] = None,
    from_date: Annotated[date | None, Query(alias="fromDate")] = None,
    to_date: Annotated[date | None, Query(alias="toDate")] = None,
) -> CollectionResponse[ExpenseQueueResponse]:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    branch_id = principal.branch_id
    query = _query(limit, cursor, claim_status, employee_id, from_date, to_date)
    items, next_cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        operation=lambda connection: _service(request, connection).list_queue(
            principal, branch_id, query, admin=False
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


@router.get(
    "",
    response_model=CollectionResponse[ExpenseQueueResponse],
    operation_id="list_admin_expenses",
    responses={**success_response_documentation(200, "Selected-branch expense queue"), **ERRORS},
)
async def list_admin_expenses(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    selected: AdminSelectedBranch,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    claim_status: Annotated[str | None, Query(alias="status")] = None,
    employee_id: Annotated[uuid.UUID | None, Query(alias="employeeId")] = None,
    from_date: Annotated[date | None, Query(alias="fromDate")] = None,
    to_date: Annotated[date | None, Query(alias="toDate")] = None,
) -> CollectionResponse[ExpenseQueueResponse]:
    query = _query(limit, cursor, claim_status, employee_id, from_date, to_date)
    items, next_cursor = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _service(request, connection).list_queue(
            principal, selected, query, admin=True
        ),
    )
    return CollectionResponse(
        data=items,
        page=Page(limit=limit, next_cursor=next_cursor, has_more=next_cursor is not None),
    )


def _json_response(outcome: IdempotentResponse) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if outcome.location is not None:
        headers["Location"] = outcome.location
    if outcome.replayed:
        headers["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=outcome.status, content=outcome.body, headers=headers)


async def _idempotent_mutation(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    branch_id: uuid.UUID,
    selected: uuid.UUID | None,
    operation_id: str,
    method: str,
    route_parameters: dict[str, object],
    body: dict[str, object],
    mutate: Callable[[ExpenseService], Awaitable[IdempotentResponse]],
    authorize_replay: bool = True,
) -> JSONResponse:
    key = parse_idempotency_key(request, required=True)
    assert key is not None
    command = IdempotencyCommand(
        key=key,
        operation_id=operation_id,
        method=method,
        route_parameters=route_parameters,
        fingerprint=request_fingerprint(
            operation_id=operation_id,
            method=method,
            route_parameters=route_parameters,
            effective_query_parameters={},
            body=body,
        ),
        branch_id=branch_id,
    )

    async def operation(connection: AsyncConnection) -> IdempotentResponse:
        service = _service(request, connection)

        async def replay(kind: str, resource_id: uuid.UUID | None) -> None:
            if authorize_replay:
                await service.authorize_replay(principal, branch_id, kind, resource_id)

        try:
            return await _idempotency(request, connection).execute(
                principal=principal,
                command=command,
                authorize_replay=replay,
                mutation=lambda: mutate(service),
            )
        except ServiceExecutionError as error:
            if error.code == "idempotency_conflict":
                raise ServiceExecutionError("idempotency_key_reused") from None
            raise

    outcome = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=operation,
    )
    return _json_response(outcome)


@router.post(
    "/self",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[ExpenseResponse],
    operation_id="create_self_expense",
    responses={**success_response_documentation(201, "Expense claim created"), **ERRORS},
)
async def create_self_expense(
    request: Request,
    body: ExpenseCreateRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")

    async def mutate(service: ExpenseService) -> IdempotentResponse:
        result = await service.create(principal, body)
        return IdempotentResponse(
            status=201,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=f"/api/v1/expenses/self/{result.id}",
            resource_kind="expense_claim",
            resource_id=result.id,
        )

    return await _idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=principal.branch_id,
        selected=None,
        operation_id="create_self_expense",
        method="POST",
        route_parameters={},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


async def _decision(
    *,
    request: Request,
    body: ExpenseDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    claim_id: uuid.UUID,
    branch_id: uuid.UUID,
    selected: uuid.UUID | None,
    stage: Literal["manager", "admin"],
    approve: bool,
    operation_id: str,
) -> JSONResponse:
    route_parameters: dict[str, object] = {"claimId": str(claim_id)}

    async def mutate(service: ExpenseService) -> IdempotentResponse:
        result = await service.decide(
            principal,
            branch_id,
            claim_id,
            body,
            stage=stage,
            approve=approve,
        )
        return IdempotentResponse(
            status=200,
            body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
            location=None,
            resource_kind="expense_claim",
            resource_id=result.id,
        )

    return await _idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected=selected,
        operation_id=operation_id,
        method="POST",
        route_parameters=route_parameters,
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
    )


@router.post(
    "/{claim_id}/manager-approve", operation_id="manager_approve_expense", responses=ERRORS
)
async def manager_approve_expense(
    claim_id: uuid.UUID,
    request: Request,
    body: ExpenseDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    return await _decision(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        claim_id=claim_id,
        branch_id=principal.branch_id,
        selected=None,
        stage="manager",
        approve=True,
        operation_id="manager_approve_expense",
    )


@router.post("/{claim_id}/manager-reject", operation_id="manager_reject_expense", responses=ERRORS)
async def manager_reject_expense(
    claim_id: uuid.UUID,
    request: Request,
    body: ExpenseDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    return await _decision(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        claim_id=claim_id,
        branch_id=principal.branch_id,
        selected=None,
        stage="manager",
        approve=False,
        operation_id="manager_reject_expense",
    )


@router.post("/{claim_id}/approve", operation_id="admin_approve_expense", responses=ERRORS)
async def admin_approve_expense(
    claim_id: uuid.UUID,
    request: Request,
    body: ExpenseDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decision(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        claim_id=claim_id,
        branch_id=selected,
        selected=selected,
        stage="admin",
        approve=True,
        operation_id="admin_approve_expense",
    )


@router.post("/{claim_id}/reject", operation_id="admin_reject_expense", responses=ERRORS)
async def admin_reject_expense(
    claim_id: uuid.UUID,
    request: Request,
    body: ExpenseDecisionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _decision(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        claim_id=claim_id,
        branch_id=selected,
        selected=selected,
        stage="admin",
        approve=False,
        operation_id="admin_reject_expense",
    )


async def _finish_cleanup(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    selected: uuid.UUID | None,
    claimed: ExpenseCleanup | ClaimedReceiptCleanup,
) -> None:
    try:
        async with asyncio.timeout(45):
            with suppress(StorageNotFoundError):
                await request.app.state.object_storage.delete_object(key=claimed.object_key)
        receipt_cleanup = ClaimedReceiptCleanup(
            receipt_id=claimed.receipt_id,
            operation_id=claimed.operation_id,
            object_key=claimed.object_key,
        )
        await _executor(request).execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=selected,
            operation=lambda connection: _receipt_service(request, connection).complete_cleanup(
                receipt_cleanup
            ),
        )
    except Exception:
        logger.error(
            "expense_receipt_cleanup_deferred",
            extra={"operation_id": str(claimed.operation_id), "error_code": "provider_error"},
        )


async def _delete(
    *,
    request: Request,
    body: ExpenseDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    claim_id: uuid.UUID,
    branch_id: uuid.UUID,
    selected: uuid.UUID | None,
    admin: bool,
    operation_id: str,
) -> JSONResponse:
    claimed: ExpenseCleanup | None = None

    async def mutate(service: ExpenseService) -> IdempotentResponse:
        nonlocal claimed
        claimed = await service.delete(
            principal, branch_id, claim_id, body.expected_updated_at, admin=admin
        )
        return IdempotentResponse(
            status=200,
            body={"data": {"id": str(claim_id), "deleted": True}},
            location=None,
            resource_kind="expense_claim",
            resource_id=claim_id,
        )

    outcome = await _idempotent_mutation(
        request=request,
        claims=claims,
        principal=principal,
        branch_id=branch_id,
        selected=selected,
        operation_id=operation_id,
        method="DELETE",
        route_parameters={"claimId": str(claim_id)},
        body=cast(dict[str, object], body.model_dump(mode="json", by_alias=True)),
        mutate=mutate,
        authorize_replay=False,
    )
    if claimed is not None:
        await _finish_cleanup(request, claims, principal, selected, claimed)
    return outcome


@router.delete("/self/{claim_id}", operation_id="delete_self_expense", responses=ERRORS)
async def delete_self_expense(
    claim_id: uuid.UUID,
    request: Request,
    body: ExpenseDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
) -> JSONResponse:
    if principal.branch_id is None:
        raise api_error("operation_not_permitted")
    return await _delete(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        claim_id=claim_id,
        branch_id=principal.branch_id,
        selected=None,
        admin=False,
        operation_id="delete_self_expense",
    )


@router.delete("/{claim_id}", operation_id="delete_admin_expense", responses=ERRORS)
async def delete_admin_expense(
    claim_id: uuid.UUID,
    request: Request,
    body: ExpenseDeleteRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    selected: AdminSelectedBranch,
) -> JSONResponse:
    return await _delete(
        request=request,
        body=body,
        claims=claims,
        principal=principal,
        claim_id=claim_id,
        branch_id=selected,
        selected=selected,
        admin=True,
        operation_id="delete_admin_expense",
    )


@router.post(
    "/receipt-submissions",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[ReceiptSubmissionResponse],
    operation_id="create_expense_receipt_submission",
    responses={**success_response_documentation(201, "Expense receipt upload intent"), **ERRORS},
)
async def create_receipt_submission(
    request: Request,
    response: Response,
    body: ReceiptSubmissionRequest,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    raw_branch: str | None = Header(None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[ReceiptSubmissionResponse]:
    branch_id = _branch(principal, raw_branch)
    selected = branch_id if principal.role is AppRole.ADMIN else None
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _receipt_service(request, connection).create_submission(
            principal, branch_id, body
        ),
    )
    response.headers["Location"] = f"/api/v1/expenses/receipt-submissions/{data.id}"
    return DataResponse(data=data)


@router.post(
    "/receipt-submissions/{submission_id}/file",
    status_code=status.HTTP_201_CREATED,
    response_model=DataResponse[ExpenseReceiptResponse],
    operation_id="upload_expense_receipt",
    responses={**success_response_documentation(201, "Expense receipt uploaded"), **ERRORS},
)
async def upload_receipt(
    submission_id: uuid.UUID,
    request: Request,
    response: Response,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    raw_branch: str | None = Header(None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[ExpenseReceiptResponse]:
    branch_id = _branch(principal, raw_branch)
    content_type = request.headers.get("content-type")
    if content_type is None:
        raise api_error("unsupported_media_type")
    upload = parse_upload(content_type, await request.body())
    selected = branch_id if principal.role is AppRole.ADMIN else None
    claimed = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _receipt_service(request, connection).claim_upload(
            principal, branch_id, submission_id, upload
        ),
    )
    try:
        async with asyncio.timeout(45):
            await request.app.state.object_storage.put_object(
                key=claimed.object_key,
                body=upload.body,
                content_type=upload.content_type,
                sha256=upload.sha256,
                if_absent=True,
            )
            metadata = await request.app.state.object_storage.head_object(key=claimed.object_key)
            if (
                metadata.size_bytes != len(upload.body)
                or metadata.content_type != upload.content_type
                or metadata.sha256 != upload.sha256
            ):
                raise StorageError
    except (StorageError, TimeoutError):
        await _executor(request).execute(
            claims=claims,
            principal=principal,
            selected_admin_branch_id=selected,
            operation=lambda connection: _receipt_service(request, connection).fail_upload(claimed),
        )
        raise api_error("service_unavailable") from None
    data = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _receipt_service(request, connection).complete_upload(
            principal, claimed, upload
        ),
    )
    response.headers["Location"] = f"/api/v1/expenses/receipts/{data.id}"
    return DataResponse(data=data)


@router.post(
    "/receipts/{receipt_id}/download",
    response_model=DataResponse[ReceiptDownloadResponse],
    operation_id="download_expense_receipt",
    responses={
        **success_response_documentation(200, "Authorized expense receipt download"),
        **ERRORS,
    },
)
async def download_receipt(
    receipt_id: uuid.UUID,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedWritePrincipal,
    raw_branch: str | None = Header(None, alias="X-Workloop-Branch-ID"),
) -> DataResponse[ReceiptDownloadResponse]:
    if await request.body():
        raise api_error("invalid_request")
    branch_id = _branch(principal, raw_branch)
    selected = branch_id if principal.role is AppRole.ADMIN else None
    metadata = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=selected,
        operation=lambda connection: _receipt_service(request, connection).load_for_download(
            principal, branch_id, receipt_id
        ),
    )
    try:
        async with asyncio.timeout(45):
            if metadata["status"] == "staged" and cast(
                datetime, metadata["expires_at"]
            ) <= datetime.now(UTC):
                raise StorageError
            actual = await request.app.state.object_storage.head_object(
                key=cast(str, metadata["object_key"])
            )
            if (
                actual.size_bytes != metadata["size_bytes"]
                or actual.content_type != metadata["content_type"]
                or actual.sha256 != metadata["sha256"]
            ):
                raise StorageError
            signed = await request.app.state.object_storage.create_download_url(
                key=cast(str, metadata["object_key"]),
                expires_in_seconds=300,
                download_name=cast(str, metadata["file_name"]),
                content_type=cast(str, metadata["content_type"]),
            )
    except (StorageError, TimeoutError):
        can_cleanup = principal.role is AppRole.ADMIN or (
            principal.employee_id == metadata["employee_id"]
            and principal.app_user_id == metadata["created_by_app_user_id"]
        )
        if can_cleanup:
            try:
                claimed = await _executor(request).execute(
                    claims=claims,
                    principal=principal,
                    selected_admin_branch_id=selected,
                    operation=lambda connection: _receipt_service(
                        request, connection
                    ).request_cleanup(
                        principal,
                        branch_id,
                        receipt_id,
                        "staged_expired"
                        if metadata["status"] == "staged"
                        and cast(datetime, metadata["expires_at"]) <= datetime.now(UTC)
                        else "missing_object",
                    ),
                )
                await _finish_cleanup(request, claims, principal, selected, claimed)
            except Exception:
                logger.error(
                    "expense_receipt_cleanup_failed", extra={"error_code": "cleanup_failed"}
                )
        raise api_error("service_unavailable") from None
    return DataResponse(data=ReceiptDownloadResponse(url=signed.url, expires_at=signed.expires_at))
