import asyncio
import logging
import uuid
from collections.abc import Sequence
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import (
    ApplicationUser,
    ApplicationUserLookupError,
    ApplicationUserResolver,
    ApplicationUserUnavailableError,
)
from app.auth.dependencies import VerifiedApplicationUser, require_access_token
from app.models.identity import AccountStatus

ISSUER = "http://127.0.0.1:8080/realms/workloop-dev"
SUBJECT = "opaque-synthetic-subject"


class StubResult:
    def __init__(self, rows: Sequence[tuple[object, object]]) -> None:
        self._rows = rows

    def tuples(self) -> "StubResult":
        return self

    def all(self) -> Sequence[tuple[object, object]]:
        return self._rows


class StubConnection:
    def __init__(
        self,
        rows: Sequence[tuple[object, object]] = (),
        failure: Exception | None = None,
    ) -> None:
        self.rows = rows
        self.failure = failure
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> StubResult:
        self.statements.append(statement)
        if self.failure is not None:
            raise self.failure
        return StubResult(self.rows)


class StubConnectionContext:
    def __init__(self, connection: StubConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> StubConnection:
        return self.connection

    async def __aexit__(self, *args: object) -> None:
        return None


class StubEngine:
    def __init__(self, connection: StubConnection) -> None:
        self.connection = connection
        self.connect_count = 0

    def connect(self) -> StubConnectionContext:
        self.connect_count += 1
        return StubConnectionContext(self.connection)


def make_resolver(connection: StubConnection) -> tuple[ApplicationUserResolver, StubEngine]:
    engine = StubEngine(connection)
    return (
        ApplicationUserResolver(
            engine=cast(AsyncEngine, engine),
            issuer=ISSUER,
            timeout_seconds=1,
        ),
        engine,
    )


@pytest.mark.asyncio
async def test_one_active_mapping_is_resolved_by_issuer_and_subject_only() -> None:
    app_user_id = uuid.uuid4()
    connection = StubConnection([(app_user_id, AccountStatus.ACTIVE.value)])
    resolver, _ = make_resolver(connection)

    first = await resolver.resolve(issuer=ISSUER, subject=SUBJECT)
    second = await resolver.resolve(issuer=ISSUER, subject=SUBJECT)

    assert first == second == ApplicationUser(id=app_user_id)
    statement = connection.statements[0]
    assert statement.compile().params == {
        "identity_issuer_1": ISSUER,
        "identity_subject_1": SUBJECT,
        "param_1": 2,
    }
    sql = str(statement)
    assert "email" not in sql
    assert "role" not in sql
    assert "company" not in sql
    assert "employee" not in sql


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [(uuid.uuid4(), AccountStatus.ACTIVE.value), (uuid.uuid4(), AccountStatus.ACTIVE.value)],
        [(uuid.uuid4(), AccountStatus.PENDING_IDENTITY.value)],
        [(uuid.uuid4(), AccountStatus.DISABLED.value)],
        [(uuid.uuid4(), "unexpected_status")],
        [("not-an-application-uuid", AccountStatus.ACTIVE.value)],
    ],
    ids=["missing", "duplicate", "pending", "disabled", "bad-status", "bad-id"],
)
@pytest.mark.asyncio
async def test_unavailable_or_malformed_mapping_fails_closed(
    rows: Sequence[tuple[object, object]],
) -> None:
    resolver, _ = make_resolver(StubConnection(rows))

    with pytest.raises(ApplicationUserUnavailableError):
        await resolver.resolve(issuer=ISSUER, subject=SUBJECT)


@pytest.mark.parametrize(
    ("issuer", "subject"),
    [
        ("http://127.0.0.1:8080/realms/other", SUBJECT),
        (ISSUER, ""),
        (ISSUER, "   "),
        (ISSUER, "bad\x00subject"),
        (ISSUER, "x" * 256),
    ],
)
@pytest.mark.asyncio
async def test_malformed_identity_input_is_rejected_before_lookup(
    issuer: str,
    subject: str,
) -> None:
    resolver, engine = make_resolver(StubConnection())

    with pytest.raises(ApplicationUserUnavailableError):
        await resolver.resolve(issuer=issuer, subject=subject)

    assert engine.connect_count == 0


@pytest.mark.asyncio
async def test_database_failure_is_wrapped_without_sensitive_details() -> None:
    resolver, _ = make_resolver(StubConnection(failure=RuntimeError("sensitive SQL detail")))

    with pytest.raises(ApplicationUserLookupError) as captured:
        await resolver.resolve(issuer=ISSUER, subject=SUBJECT)

    assert str(captured.value) == ""


@pytest.mark.asyncio
async def test_stalled_database_lookup_obeys_deadline() -> None:
    class StalledConnection(StubConnection):
        async def execute(self, statement: Any) -> StubResult:
            await asyncio.sleep(1)
            return await super().execute(statement)

    engine = StubEngine(StalledConnection())
    resolver = ApplicationUserResolver(
        engine=cast(AsyncEngine, engine),
        issuer=ISSUER,
        timeout_seconds=0.01,
    )

    with pytest.raises(ApplicationUserLookupError):
        await resolver.resolve(issuer=ISSUER, subject=SUBJECT)


def protected_test_app(resolver: ApplicationUserResolver) -> FastAPI:
    application = FastAPI()
    application.state.application_user_resolver = resolver
    claims = AccessTokenClaims(
        issuer=ISSUER,
        subject=SUBJECT,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )

    async def verified_claims() -> AccessTokenClaims:
        return claims

    async def protected(_app_user: VerifiedApplicationUser) -> dict[str, bool]:
        return {"authenticated": True}

    application.dependency_overrides[require_access_token] = verified_claims
    application.add_api_route("/protected", protected, methods=["GET"])
    return application


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [(uuid.uuid4(), AccountStatus.ACTIVE.value), (uuid.uuid4(), AccountStatus.ACTIVE.value)],
        [(uuid.uuid4(), AccountStatus.PENDING_IDENTITY.value)],
        [(uuid.uuid4(), AccountStatus.DISABLED.value)],
    ],
)
@pytest.mark.asyncio
async def test_account_failures_return_the_same_safe_403(
    rows: Sequence[tuple[object, object]],
) -> None:
    resolver, _ = make_resolver(StubConnection(rows))

    async with AsyncClient(
        transport=ASGITransport(app=protected_test_app(resolver)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/protected")

    assert response.status_code == 403
    assert response.json() == {
        "detail": {
            "code": "application_account_unavailable",
            "message": "Application account unavailable",
        }
    }


@pytest.mark.asyncio
async def test_database_failure_returns_safe_503_without_log_or_response_leak(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_detail = "database-url-and-record-detail"
    resolver, _ = make_resolver(StubConnection(failure=RuntimeError(sensitive_detail)))
    caplog.set_level(logging.DEBUG)

    async with AsyncClient(
        transport=ASGITransport(app=protected_test_app(resolver)),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/protected")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "application_account_lookup_unavailable",
            "message": "Service temporarily unavailable",
        }
    }
    assert sensitive_detail not in response.text + caplog.text
    assert SUBJECT not in response.text + caplog.text
