import asyncio
import logging
import uuid
from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import (
    ApplicationUserLookupError,
    ApplicationUserResolver,
    ApplicationUserUnavailableError,
    AuthorizationPrincipal,
)
from app.auth.dependencies import (
    AuthenticatedAuthorizationPrincipal,
    require_access_token,
)
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.models.identity import AccountStatus, AppRole

ISSUER = c.SEED_ISSUER
SUBJECT = "opaque-synthetic-subject"


class StubResult:
    def __init__(self, rows: Sequence[tuple[object, ...]]) -> None:
        self._rows = rows

    def tuples(self) -> "StubResult":
        return self

    def all(self) -> Sequence[tuple[object, ...]]:
        return self._rows


class StubConnection:
    def __init__(
        self,
        rows: Sequence[tuple[object, ...]] = (),
        failure: Exception | None = None,
    ) -> None:
        self.rows = rows
        self.failure = failure
        self.statements: list[Any] = []
        self.parameters: list[dict[str, str] | None] = []

    async def execute(
        self, statement: Any, _parameters: dict[str, str] | None = None
    ) -> StubResult:
        self.statements.append(statement)
        self.parameters.append(_parameters)
        if self.failure is not None:
            raise self.failure
        return StubResult(self.rows)

    def begin(self) -> "StubTransactionContext":
        return StubTransactionContext()


class StubTransactionContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


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


def fixture_resolution(subject: str) -> tuple[tuple[object, ...], AuthorizationPrincipal]:
    rows = build_rows()
    app_user = next(
        row.values
        for row in rows
        if row.table == "app_users" and row.values["identity_subject"] == subject
    )
    profile = next(
        row.values
        for row in rows
        if row.table == "user_profiles" and row.values["app_user_id"] == app_user["id"]
    )
    company_id = profile["company_id"]
    employee = next(
        (
            row.values
            for row in rows
            if row.table == "employees" and row.values["id"] == profile["employee_id"]
        ),
        None,
    )
    branch = next(
        (
            row.values
            for row in rows
            if row.table == "branches"
            and employee is not None
            and row.values["id"] == employee["branch_id"]
        ),
        None,
    )
    role = AppRole(cast(str, profile["role"]))
    employee_id = cast(uuid.UUID | None, profile["employee_id"])
    branch_id = cast(uuid.UUID | None, employee["branch_id"] if employee is not None else None)
    result = (
        app_user["id"],
        app_user["status"],
        profile["app_user_id"],
        company_id,
        profile["role"],
        employee_id,
        company_id,
        employee["id"] if employee is not None else None,
        employee["company_id"] if employee is not None else None,
        branch_id,
        employee["active"] if employee is not None else None,
        employee["employment_status"] if employee is not None else None,
        branch["id"] if branch is not None else None,
        branch["company_id"] if branch is not None else None,
    )
    principal = AuthorizationPrincipal(
        app_user_id=cast(uuid.UUID, app_user["id"]),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=cast(uuid.UUID, company_id),
        employee_id=employee_id,
        branch_id=branch_id,
    )
    return result, principal


@pytest.mark.parametrize(
    "subject",
    [
        "hr.admin@horizon.test",
        "aisha.manager@horizon.test",
        "ravi.employee@horizon.test",
    ],
    ids=["admin", "manager", "employee"],
)
@pytest.mark.asyncio
async def test_valid_synthetic_fixture_resolves_to_exact_principal(subject: str) -> None:
    row, expected = fixture_resolution(subject)
    resolver, engine = make_resolver(StubConnection([row]))

    principal = await resolver.resolve(issuer=ISSUER, subject=subject)

    assert principal == expected
    assert principal.id == principal.app_user_id
    assert engine.connect_count == 1
    assert len(engine.connection.statements) == 2
    context_statement, statement = engine.connection.statements
    assert engine.connection.parameters[0] == {
        "identity_issuer": ISSUER,
        "identity_subject": subject,
    }
    assert "workloop.identity_issuer" in str(context_statement)
    assert "workloop.identity_subject" in str(context_statement)
    assert subject not in str(context_statement)
    assert statement.compile().params == {
        "identity_issuer_1": ISSUER,
        "identity_subject_1": subject,
        "param_1": 2,
    }
    sql = str(statement).lower()
    assert "left outer join user_profiles" in sql
    assert "left outer join employees" in sql
    assert "left outer join branches" in sql
    assert "email" not in sql


@pytest.mark.parametrize(
    "subject",
    ["maria.employee@horizon.test", "noor.employee@horizon.test"],
    ids=["probation", "on-leave"],
)
@pytest.mark.asyncio
async def test_each_eligible_employee_status_resolves(subject: str) -> None:
    row, expected = fixture_resolution(subject)
    resolver, _ = make_resolver(StubConnection([row]))

    assert await resolver.resolve(issuer=ISSUER, subject=subject) == expected


def staff_row(
    *,
    role: object = AppRole.EMPLOYEE.value,
    active: object = True,
    employment_status: object = "Active",
) -> list[object]:
    app_user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    employee_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    return [
        app_user_id,
        AccountStatus.ACTIVE.value,
        app_user_id,
        company_id,
        role,
        employee_id,
        company_id,
        employee_id,
        company_id,
        branch_id,
        active,
        employment_status,
        branch_id,
        company_id,
    ]


def mutated_staff_row(index: int, value: object) -> tuple[object, ...]:
    row = staff_row()
    row[index] = value
    return tuple(row)


def duplicate_staff_rows() -> list[tuple[object, ...]]:
    row = tuple(staff_row())
    return [row, row]


def distinct_staff_rows() -> list[tuple[object, ...]]:
    return [tuple(staff_row()), tuple(staff_row())]


def missing_profile_row() -> tuple[object, ...]:
    row = staff_row()
    row[2:] = [None] * 12
    return tuple(row)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        distinct_staff_rows(),
        [mutated_staff_row(0, "not-an-application-uuid")],
        [mutated_staff_row(1, "pending_identity")],
        [mutated_staff_row(1, "disabled")],
        [mutated_staff_row(1, "unexpected_status")],
    ],
    ids=["missing", "duplicate", "bad-id", "pending", "disabled", "bad-status"],
)
@pytest.mark.asyncio
async def test_unavailable_or_malformed_account_fails_closed(
    rows: Sequence[tuple[object, ...]],
) -> None:
    resolver, _ = make_resolver(StubConnection(rows))

    with pytest.raises(ApplicationUserUnavailableError):
        await resolver.resolve(issuer=ISSUER, subject=SUBJECT)


@pytest.mark.parametrize(
    "rows",
    [
        [missing_profile_row()],
        duplicate_staff_rows(),
    ],
    ids=["missing-profile", "duplicate-profile"],
)
@pytest.mark.asyncio
async def test_missing_or_duplicate_profile_fails_closed(
    rows: Sequence[tuple[object, ...]],
) -> None:
    resolver, _ = make_resolver(StubConnection(rows))

    with pytest.raises(ApplicationUserUnavailableError):
        await resolver.resolve(issuer=ISSUER, subject=SUBJECT)


@pytest.mark.parametrize(
    "mutation",
    [
        (4, "owner"),
        (5, None),
        (4, AppRole.ADMIN.value),
        (2, uuid.uuid4()),
        (3, "not-a-company-uuid"),
        (6, None),
    ],
    ids=[
        "invalid-role",
        "staff-without-link",
        "admin-with-link",
        "profile-for-other-user",
        "malformed-company",
        "missing-company",
    ],
)
@pytest.mark.asyncio
async def test_invalid_role_or_profile_link_fails_closed(
    mutation: tuple[int, object],
) -> None:
    row = staff_row()
    row[mutation[0]] = mutation[1]
    resolver, _ = make_resolver(StubConnection([tuple(row)]))

    with pytest.raises(ApplicationUserUnavailableError):
        await resolver.resolve(issuer=ISSUER, subject=SUBJECT)


@pytest.mark.parametrize(
    ("index", "value"),
    [
        (10, False),
        (11, "Terminated"),
        (7, None),
        (8, uuid.uuid4()),
        (12, None),
        (13, uuid.uuid4()),
        (9, uuid.uuid4()),
    ],
    ids=[
        "inactive",
        "terminated",
        "missing-employee",
        "cross-company-employee",
        "missing-branch",
        "cross-company-branch",
        "cross-branch-employee",
    ],
)
@pytest.mark.asyncio
async def test_ineligible_or_inconsistent_employee_link_fails_closed(
    index: int, value: object
) -> None:
    row = staff_row()
    row[index] = value
    resolver, _ = make_resolver(StubConnection([tuple(row)]))

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
        async def execute(
            self, statement: Any, parameters: dict[str, str] | None = None
        ) -> StubResult:
            await asyncio.sleep(1)
            return await super().execute(statement, parameters)

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

    async def protected(_principal: AuthenticatedAuthorizationPrincipal) -> dict[str, bool]:
        return {"authenticated": True}

    application.dependency_overrides[require_access_token] = verified_claims
    application.add_api_route("/protected", protected, methods=["GET"])
    return application


@pytest.mark.parametrize(
    "rows",
    [[], duplicate_staff_rows(), [missing_profile_row()]],
    ids=["missing-account", "duplicate-profile", "missing-profile"],
)
@pytest.mark.asyncio
async def test_account_failures_return_the_same_safe_403(
    rows: Sequence[tuple[object, ...]],
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
    sensitive_values = (
        "database-url-and-record-detail",
        SUBJECT,
        str(uuid.uuid4()),
        "private-profile-value",
        "synthetic-bearer-token",
    )
    resolver, _ = make_resolver(StubConnection(failure=RuntimeError(" ".join(sensitive_values))))
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
    output = response.text + caplog.text
    assert all(value not in output for value in sensitive_values)


def test_principal_is_immutable() -> None:
    _, principal = fixture_resolution("aisha.manager@horizon.test")

    with pytest.raises(FrozenInstanceError):
        principal.company_id = uuid.uuid4()  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises((AttributeError, TypeError)):
        principal.browser_role = "admin"  # pyright: ignore[reportAttributeAccessIssue]
    assert not hasattr(principal, "__dict__")
