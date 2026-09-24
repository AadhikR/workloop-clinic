from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import (
    AuthenticatedReadPrincipal,
    VerifiedAccessToken,
    branch_required_error,
    invalid_branch_error,
)
from app.http.errors import (
    correlation_id_for,
    error_response_documentation,
    success_response_documentation,
)
from app.http.schemas import DataResponse
from app.models.identity import AppRole
from app.repositories.tasks import SqlTaskRepository
from app.schemas.tasks import TaskListResponse
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.tasks import TaskListQuery, TaskService

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

ERRORS = error_response_documentation(
    "invalid_request",
    "validation_failed",
    "invalid_access_token",
    "application_account_unavailable",
    "resource_not_found",
    "invalid_branch",
    "branch_required",
    "invalid_cursor",
    "rate_limit_exceeded",
    "application_account_lookup_unavailable",
    "task_source_unavailable",
    "service_unavailable",
    "request_timeout",
    "internal_error",
)


def _executor(request: Request) -> AuthorizedServiceExecutor:
    return request.app.state.authorized_service_executor


def _service(request: Request, connection: AsyncConnection) -> TaskService:
    factory = getattr(request.app.state, "task_service_factory", None)
    if factory is not None:
        return cast(TaskService, factory(connection))
    return TaskService(SqlTaskRepository(connection), request.app.state.task_cursor_codec)


def _task_branch(request: Request, principal: AuthorizationPrincipal) -> uuid.UUID:
    values = request.headers.getlist("x-workloop-branch-id")
    if principal.role is not AppRole.ADMIN:
        if values:
            raise invalid_branch_error()
        if principal.branch_id is None:
            raise ServiceExecutionError("resource_not_found")
        return principal.branch_id
    if not values:
        raise branch_required_error()
    if len(values) != 1 or values[0] != values[0].strip():
        raise invalid_branch_error()
    try:
        branch_id = uuid.UUID(values[0])
    except (AttributeError, ValueError):
        raise invalid_branch_error() from None
    if branch_id.version is None or str(branch_id) != values[0]:
        raise invalid_branch_error()
    return branch_id


async def _execute(
    *,
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthorizationPrincipal,
    operation: Callable[[TaskService, uuid.UUID], Awaitable[TaskListResponse]],
) -> TaskListResponse:
    branch_id = _task_branch(request, principal)
    result = await _executor(request).execute(
        claims=claims,
        principal=principal,
        selected_admin_branch_id=branch_id if principal.role is AppRole.ADMIN else None,
        operation=lambda connection: operation(_service(request, connection), branch_id),
    )
    return result


@router.get(
    "",
    response_model=DataResponse[TaskListResponse],
    operation_id="list_tasks",
    responses={**success_response_documentation(200, "Role-derived task catalogue"), **ERRORS},
)
async def list_tasks(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    category: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    urgency: Annotated[
        Literal["action", "expired", "urgent", "warning", "info"] | None, Query()
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> DataResponse[TaskListResponse] | JSONResponse:
    result = await _execute(
        request=request,
        claims=claims,
        principal=principal,
        operation=lambda service, branch_id: service.list(
            principal,
            branch_id,
            TaskListQuery(
                category=category,
                urgency=urgency,
                limit=limit,
                cursor=cursor,
            ),
        ),
    )
    if result.source_unavailable:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "task_source_unavailable",
                    "message": "One or more task sources are unavailable",
                    "correlationId": correlation_id_for(request),
                    "details": [],
                },
                "data": result.model_dump(mode="json", by_alias=True),
            },
            headers={"Cache-Control": "no-store"},
        )
    return DataResponse(data=result)
