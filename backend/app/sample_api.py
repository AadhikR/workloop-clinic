from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import AuthenticatedReadPrincipal, VerifiedAccessToken
from app.http.errors import api_error
from app.http.sample_schemas import CurrentAccountResponse, PublicStatusResponse
from app.http.schemas import DataResponse
from app.services.execution import AuthorizedServiceExecutor


async def reject_account_query_input(request: Request) -> None:
    query_items = list(request.query_params.multi_items())
    if not query_items:
        return

    counts: dict[str, int] = {}
    for name, _value in query_items:
        counts[name] = counts.get(name, 0) + 1
    details = [
        {
            "path": f"query.{name}",
            "code": "duplicate_parameter" if count > 1 else "unknown_field",
            "message": "Parameter must appear once" if count > 1 else "Field is not allowed",
        }
        for name, count in counts.items()
    ]
    details.sort(key=lambda item: (item["path"], item["code"], item["message"]))
    raise api_error("validation_failed", details=details[:20])


NoAccountQueryInput = Annotated[None, Depends(reject_account_query_input)]


async def get_public_status() -> DataResponse[PublicStatusResponse]:
    return DataResponse(data=PublicStatusResponse(status="ok"))


async def get_current_account(
    request: Request,
    claims: VerifiedAccessToken,
    principal: AuthenticatedReadPrincipal,
    _query_input: NoAccountQueryInput,
) -> DataResponse[CurrentAccountResponse]:
    executor: AuthorizedServiceExecutor = request.app.state.authorized_service_executor

    async def read_current_account(_connection: AsyncConnection) -> CurrentAccountResponse:
        return _account_response(principal)

    account = await executor.execute(
        claims=claims,
        principal=principal,
        operation=read_current_account,
    )
    return DataResponse(data=account)


def _account_response(principal: AuthorizationPrincipal) -> CurrentAccountResponse:
    return CurrentAccountResponse(
        app_user_id=principal.app_user_id,
        role=principal.role,
        company_id=principal.company_id,
        employee_id=principal.employee_id,
        branch_id=principal.branch_id,
    )
