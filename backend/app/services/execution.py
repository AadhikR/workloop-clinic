from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.db.authorization_context import (
    AuthorizationBranchUnavailableError,
    AuthorizationContextError,
    AuthorizationContextUnavailableError,
    AuthorizationTransactionFactory,
)

ResultType = TypeVar("ResultType")


class ServiceDeadlineExceeded(Exception):
    pass


class ServiceExecutionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AuthorizedServiceExecutor:
    def __init__(
        self, transaction_factory: AuthorizationTransactionFactory, *, deadline_seconds: float
    ) -> None:
        self._transaction_factory = transaction_factory
        self._deadline_seconds = deadline_seconds

    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[ResultType]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> ResultType:
        try:
            async with asyncio.timeout(self._deadline_seconds):
                async with self._transaction_factory.transaction(
                    claims=claims,
                    principal=principal,
                    verified_admin_branch_id=selected_admin_branch_id,
                ) as connection:
                    return await operation(connection)
        except TimeoutError:
            raise ServiceDeadlineExceeded from None
        except AuthorizationBranchUnavailableError:
            raise ServiceExecutionError("resource_not_found") from None
        except AuthorizationContextUnavailableError:
            raise ServiceExecutionError("application_account_lookup_unavailable") from None
        except AuthorizationContextError:
            raise ServiceExecutionError("application_account_unavailable") from None
