import asyncio
import uuid
from dataclasses import dataclass
from typing import TypeGuard

from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models.identity import AccountStatus, AppUser


class ApplicationUserError(Exception):
    pass


class ApplicationUserUnavailableError(ApplicationUserError):
    pass


class ApplicationUserLookupError(ApplicationUserError):
    pass


@dataclass(frozen=True, slots=True)
class ApplicationUser:
    id: uuid.UUID


def is_application_user_id(value: object) -> TypeGuard[uuid.UUID]:
    return isinstance(value, uuid.UUID)


class ApplicationUserResolver:
    def __init__(self, *, engine: AsyncEngine, issuer: str, timeout_seconds: float) -> None:
        self._engine = engine
        self._issuer = issuer
        self._timeout_seconds = timeout_seconds

    async def resolve(self, *, issuer: str, subject: str) -> ApplicationUser:
        if (
            issuer != self._issuer
            or not subject
            or len(subject) > 255
            or subject.isspace()
            or "\x00" in subject
        ):
            raise ApplicationUserUnavailableError

        app_users = AppUser.__table__.c
        statement = (
            select(app_users.id, cast(app_users.status, Text))
            .where(
                app_users.identity_issuer == issuer,
                app_users.identity_subject == subject,
            )
            .limit(2)
        )
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._engine.connect() as connection:
                    rows = (await connection.execute(statement)).tuples().all()
        except Exception as error:
            raise ApplicationUserLookupError from error

        if len(rows) != 1:
            raise ApplicationUserUnavailableError
        app_user_id, account_status = rows[0]
        if not is_application_user_id(app_user_id) or account_status != AccountStatus.ACTIVE.value:
            raise ApplicationUserUnavailableError
        return ApplicationUser(id=app_user_id)
