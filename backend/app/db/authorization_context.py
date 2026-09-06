from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.models.identity import AccountStatus, AppRole

if TYPE_CHECKING:
    from app.auth.access_token import AccessTokenClaims
    from app.auth.application_user import AuthorizationPrincipal

DUBAI_TIME_ZONE = ZoneInfo("Asia/Dubai")

CONTEXT_KEYS = (
    "workloop.identity_issuer",
    "workloop.identity_subject",
    "workloop.app_user_id",
    "workloop.role",
    "workloop.company_id",
    "workloop.employee_id",
    "workloop.branch_id",
    "workloop.actor_kind",
    "workloop.actor_key",
    "workloop.business_date",
)

CONTEXT_READER_NAMES = (
    "workloop_identity_issuer",
    "workloop_identity_subject",
    "workloop_app_user_id",
    "workloop_role",
    "workloop_company_id",
    "workloop_employee_id",
    "workloop_branch_id",
    "workloop_actor_kind",
    "workloop_actor_key",
    "workloop_business_date",
)

_SET_IDENTITY_CONTEXT = text(
    """
SELECT
  pg_catalog.set_config('workloop.identity_issuer', :identity_issuer, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.identity_subject', :identity_subject, true) IS NOT NULL
"""
)

_SET_HUMAN_CONTEXT = text(
    """
SELECT
  pg_catalog.set_config('workloop.identity_issuer', :identity_issuer, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.identity_subject', :identity_subject, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.app_user_id', :app_user_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.role', :role, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.company_id', :company_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.employee_id', :employee_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.branch_id', :branch_id, true) IS NOT NULL
  AND pg_catalog.set_config('workloop.actor_kind', 'human', true) IS NOT NULL
  AND pg_catalog.set_config('workloop.actor_key', '', true) IS NOT NULL
  AND pg_catalog.set_config('workloop.business_date', :business_date, true) IS NOT NULL
"""
)

_REVALIDATE_HUMAN_CONTEXT = text(
    """
SELECT pg_catalog.count(*) = 1
FROM public.app_users AS app_user
JOIN public.user_profiles AS profile
  ON profile.app_user_id = app_user.id
LEFT JOIN public.employees AS employee
  ON employee.id = profile.employee_id
 AND employee.company_id = profile.company_id
LEFT JOIN public.branches AS employee_branch
  ON employee_branch.id = employee.branch_id
 AND employee_branch.company_id = employee.company_id
WHERE current_user = 'workloop_runtime'
  AND session_user = 'workloop_runtime'
  AND public.workloop_actor_kind() = 'human'
  AND public.workloop_actor_key() IS NULL
  AND public.workloop_business_date() IS NOT NULL
  AND app_user.id = public.workloop_app_user_id()
  AND app_user.identity_issuer = public.workloop_identity_issuer()
  AND app_user.identity_subject = public.workloop_identity_subject()
  AND app_user.status::text = 'active'
  AND profile.company_id = public.workloop_company_id()
  AND profile.role::text = public.workloop_role()
  AND (
    (
      public.workloop_role() = 'admin'
      AND profile.employee_id IS NULL
      AND public.workloop_employee_id() IS NULL
      AND (
        public.workloop_branch_id() IS NULL
        OR EXISTS (
          SELECT 1
          FROM public.branches AS selected_branch
          WHERE selected_branch.id = public.workloop_branch_id()
            AND selected_branch.company_id = public.workloop_company_id()
        )
      )
    )
    OR
    (
      public.workloop_role() IN ('manager', 'employee')
      AND profile.employee_id = public.workloop_employee_id()
      AND employee.id = public.workloop_employee_id()
      AND employee.company_id = public.workloop_company_id()
      AND employee.branch_id = public.workloop_branch_id()
      AND employee.active
      AND employee.employment_status IN ('Active', 'Probation', 'On Leave')
      AND employee_branch.id = public.workloop_branch_id()
    )
  )
"""
)


class AuthorizationContextError(Exception):
    pass


def _dubai_now() -> datetime:
    return datetime.now(DUBAI_TIME_ZONE)


async def set_identity_bootstrap_context(
    connection: AsyncConnection, *, issuer: str, subject: str
) -> None:
    await connection.execute(
        _SET_IDENTITY_CONTEXT,
        {"identity_issuer": issuer, "identity_subject": subject},
    )


class AuthorizationTransactionFactory:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        clock: Callable[[], datetime] = _dubai_now,
    ) -> None:
        self._engine = engine
        self._clock = clock

    @asynccontextmanager
    async def transaction(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        verified_admin_branch_id: uuid.UUID | None = None,
    ) -> AsyncGenerator[AsyncConnection]:
        values = self._human_values(
            claims=claims,
            principal=principal,
            verified_admin_branch_id=verified_admin_branch_id,
        )
        async with self._engine.connect() as connection, connection.begin():
            await connection.execute(_SET_HUMAN_CONTEXT, values)
            valid = (await connection.execute(_REVALIDATE_HUMAN_CONTEXT)).scalar_one()
            if valid is not True:
                raise AuthorizationContextError
            yield connection

    def _human_values(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        verified_admin_branch_id: uuid.UUID | None,
    ) -> dict[str, str]:
        if (
            not claims.issuer
            or len(claims.issuer) > 255
            or claims.issuer.isspace()
            or not claims.subject
            or len(claims.subject) > 255
            or claims.subject.isspace()
            or "\x00" in claims.issuer
            or "\x00" in claims.subject
            or principal.account_status is not AccountStatus.ACTIVE
        ):
            raise AuthorizationContextError

        if principal.role is AppRole.ADMIN:
            if principal.employee_id is not None or principal.branch_id is not None:
                raise AuthorizationContextError
            branch_id = verified_admin_branch_id
        elif principal.role in {AppRole.MANAGER, AppRole.EMPLOYEE}:
            if (
                principal.employee_id is None
                or principal.branch_id is None
                or verified_admin_branch_id is not None
            ):
                raise AuthorizationContextError
            branch_id = principal.branch_id
        else:
            raise AuthorizationContextError

        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise AuthorizationContextError
        business_date: date = now.astimezone(DUBAI_TIME_ZONE).date()

        return {
            "identity_issuer": claims.issuer,
            "identity_subject": claims.subject,
            "app_user_id": str(principal.app_user_id),
            "role": principal.role.value,
            "company_id": str(principal.company_id),
            "employee_id": "" if principal.employee_id is None else str(principal.employee_id),
            "branch_id": "" if branch_id is None else str(branch_id),
            "business_date": business_date.isoformat(),
        }
