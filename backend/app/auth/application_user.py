import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, TypeGuard
from typing import cast as type_cast

from sqlalchemy import Text, cast, select
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql.base import Executable

from app.models.identity import (
    AccountStatus,
    AppRole,
    AppUser,
    Branch,
    Company,
    Employee,
    UserProfile,
)

_ELIGIBLE_EMPLOYMENT_STATUSES = frozenset({"Active", "Probation", "On Leave"})


class ApplicationUserError(Exception):
    pass


class ApplicationUserUnavailableError(ApplicationUserError):
    pass


class ApplicationUserLookupError(ApplicationUserError):
    pass


class BranchUnavailableError(ApplicationUserError):
    pass


@dataclass(frozen=True, slots=True)
class AuthorizationPrincipal:
    app_user_id: uuid.UUID
    account_status: AccountStatus
    role: AppRole
    company_id: uuid.UUID
    employee_id: uuid.UUID | None
    branch_id: uuid.UUID | None

    @property
    def id(self) -> uuid.UUID:
        return self.app_user_id


ApplicationUser = AuthorizationPrincipal


def is_uuid(value: object) -> TypeGuard[uuid.UUID]:
    return isinstance(value, uuid.UUID)


class ApplicationUserResolver:
    def __init__(self, *, engine: AsyncEngine, issuer: str, timeout_seconds: float) -> None:
        self._engine = engine
        self._issuer = issuer
        self._timeout_seconds = timeout_seconds

    async def resolve(self, *, issuer: str, subject: str) -> AuthorizationPrincipal:
        if (
            issuer != self._issuer
            or not subject
            or len(subject) > 255
            or subject.isspace()
            or "\x00" in subject
        ):
            raise ApplicationUserUnavailableError

        app_users = AppUser.__table__.c
        profiles = UserProfile.__table__.c
        companies = Company.__table__.c
        employees = Employee.__table__.c
        branches = Branch.__table__.c
        statement = (
            select(
                app_users.id,
                cast(app_users.status, Text),
                profiles.app_user_id,
                profiles.company_id,
                cast(profiles.role, Text),
                profiles.employee_id,
                companies.id,
                employees.id,
                employees.company_id,
                employees.branch_id,
                employees.active,
                employees.employment_status,
                branches.id,
                branches.company_id,
            )
            .select_from(
                AppUser.__table__.outerjoin(
                    UserProfile.__table__, profiles.app_user_id == app_users.id
                )
                .outerjoin(Company.__table__, companies.id == profiles.company_id)
                .outerjoin(Employee.__table__, employees.id == profiles.employee_id)
                .outerjoin(Branch.__table__, branches.id == employees.branch_id)
            )
            .where(
                app_users.identity_issuer == issuer,
                app_users.identity_subject == subject,
            )
            .limit(2)
        )
        rows = await self._execute(statement)
        if len(rows) != 1:
            raise ApplicationUserUnavailableError

        (
            app_user_id,
            raw_account_status,
            profile_app_user_id,
            profile_company_id,
            raw_role,
            profile_employee_id,
            company_id,
            employee_id,
            employee_company_id,
            employee_branch_id,
            employee_active,
            employment_status,
            branch_id,
            branch_company_id,
        ) = rows[0]

        if (
            not is_uuid(app_user_id)
            or raw_account_status != AccountStatus.ACTIVE.value
            or profile_app_user_id != app_user_id
            or not is_uuid(profile_company_id)
            or company_id != profile_company_id
        ):
            raise ApplicationUserUnavailableError
        try:
            role = AppRole(raw_role)
        except (TypeError, ValueError):
            raise ApplicationUserUnavailableError from None

        if role is AppRole.ADMIN:
            if profile_employee_id is not None:
                raise ApplicationUserUnavailableError
            return AuthorizationPrincipal(
                app_user_id=app_user_id,
                account_status=AccountStatus.ACTIVE,
                role=role,
                company_id=profile_company_id,
                employee_id=None,
                branch_id=None,
            )

        if (
            role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or not is_uuid(profile_employee_id)
            or employee_id != profile_employee_id
            or employee_company_id != profile_company_id
            or not is_uuid(employee_branch_id)
            or employee_active is not True
            or employment_status not in _ELIGIBLE_EMPLOYMENT_STATUSES
            or branch_id != employee_branch_id
            or branch_company_id != profile_company_id
        ):
            raise ApplicationUserUnavailableError
        return AuthorizationPrincipal(
            app_user_id=app_user_id,
            account_status=AccountStatus.ACTIVE,
            role=role,
            company_id=profile_company_id,
            employee_id=profile_employee_id,
            branch_id=employee_branch_id,
        )

    async def resolve_admin_branch(
        self, *, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> uuid.UUID:
        branches = Branch.__table__.c
        statement = (
            select(branches.id)
            .where(branches.id == branch_id, branches.company_id == company_id)
            .limit(2)
        )
        rows = await self._execute(statement)
        if len(rows) != 1 or rows[0][0] != branch_id:
            raise BranchUnavailableError
        return branch_id

    async def _execute(self, statement: Executable) -> list[tuple[object, ...]]:
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._engine.connect() as connection:
                    result: Result[Any] = await connection.execute(statement)
                    return type_cast(list[tuple[object, ...]], list(result.tuples().all()))
        except ApplicationUserError:
            raise
        except Exception as error:
            raise ApplicationUserLookupError from error
