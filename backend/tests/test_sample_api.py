import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.http.rate_limit import RATE_LIMITS_PER_MINUTE, RateLimitClass
from app.models.identity import AccountStatus, AppRole
from app.services.execution import ServiceExecutionError
from tests.test_http_boundary import make_settings


class RecordingRateLimiter:
    def __init__(self) -> None:
        self.calls: list[tuple[RateLimitClass, str]] = []

    async def check(self, request_class: RateLimitClass, trusted_key: str) -> None:
        self.calls.append((request_class, trusted_key))


class RecordingExecutor:
    def __init__(self, failure: Exception | None = None) -> None:
        self.calls: list[tuple[AccessTokenClaims, AuthorizationPrincipal, uuid.UUID | None]] = []
        self.operation_calls = 0
        self.failure = failure

    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> object:
        self.calls.append((claims, principal, selected_admin_branch_id))
        if self.failure is not None:
            raise self.failure
        self.operation_calls += 1
        return await operation(cast(AsyncConnection, object()))


def claims() -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer="https://seed.workloop.test",
        subject="synthetic-subject",
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def principal(role: AppRole) -> AuthorizationPrincipal:
    staff = role in {AppRole.MANAGER, AppRole.EMPLOYEE}
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=uuid.uuid4(),
        employee_id=uuid.uuid4() if staff else None,
        branch_id=uuid.uuid4() if staff else None,
    )


@asynccontextmanager
async def client_for(
    *,
    active_principal: AuthorizationPrincipal | None = None,
    executor: RecordingExecutor | None = None,
    rate_limiter: RecordingRateLimiter | None = None,
) -> AsyncGenerator[tuple[AsyncClient, FastAPI, RecordingExecutor, RecordingRateLimiter]]:
    from app.main import create_app

    application = create_app(
        settings=make_settings(api_request_timeout_seconds=1),
        rate_limiter=rate_limiter or RecordingRateLimiter(),
    )
    active_executor = executor or RecordingExecutor()
    active_limiter = cast(RecordingRateLimiter, application.state.rate_limiter)
    application.state.authorized_service_executor = active_executor

    async def verified_claims() -> AccessTokenClaims:
        return claims()

    async def resolved_principal() -> AuthorizationPrincipal:
        assert active_principal is not None
        return active_principal

    if active_principal is not None:
        application.dependency_overrides[require_access_token] = verified_claims
        application.dependency_overrides[require_authorization_principal] = resolved_principal

    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, application, active_executor, active_limiter


@pytest.mark.asyncio
async def test_public_status_has_exact_envelope_and_no_authentication_dependency() -> None:
    async with client_for() as (client, _application, executor, limiter):
        response = await client.get("/api/v1/public/status")

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}
    assert response.headers["cache-control"] == "no-store"
    assert uuid.UUID(response.headers["x-correlation-id"]).version == 4
    assert executor.calls == []
    assert limiter.calls == [(RateLimitClass.PUBLIC, "127.0.0.1")]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", list(AppRole))
async def test_current_account_returns_only_the_verified_principal(role: AppRole) -> None:
    active_principal = principal(role)
    async with client_for(active_principal=active_principal) as (
        client,
        _application,
        executor,
        limiter,
    ):
        response = await client.get("/api/v1/account/me")

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "appUserId": str(active_principal.app_user_id),
            "role": role.value,
            "companyId": str(active_principal.company_id),
            "employeeId": (
                str(active_principal.employee_id)
                if active_principal.employee_id is not None
                else None
            ),
            "branchId": (
                str(active_principal.branch_id) if active_principal.branch_id is not None else None
            ),
        }
    }
    assert response.headers["cache-control"] == "no-store"
    assert executor.operation_calls == 1
    assert len(executor.calls) == 1
    assert executor.calls[0][1] is active_principal
    assert executor.calls[0][2] is None
    assert limiter.calls == [
        (RateLimitClass.PROTECTED_ATTEMPT, "127.0.0.1"),
        (RateLimitClass.AUTHENTICATED_READ_USER, f"app_user:{active_principal.app_user_id}"),
        (
            RateLimitClass.AUTHENTICATED_READ_COMPANY,
            f"company:{active_principal.company_id}",
        ),
    ]


def test_authenticated_rate_limit_classes_pin_user_and_company_ceilings() -> None:
    assert RATE_LIMITS_PER_MINUTE == {
        RateLimitClass.PUBLIC: 60,
        RateLimitClass.AUTHENTICATION_CHECK: 30,
        RateLimitClass.PROTECTED_ATTEMPT: 600,
        RateLimitClass.INVALID_ACCESS_TOKEN: 60,
        RateLimitClass.AUTHENTICATED_READ_USER: 300,
        RateLimitClass.AUTHENTICATED_READ_COMPANY: 3_000,
        RateLimitClass.AUTHENTICATED_WRITE_USER: 60,
        RateLimitClass.AUTHENTICATED_WRITE_COMPANY: 600,
        RateLimitClass.FINANCIAL_OR_APPROVAL_USER: 20,
        RateLimitClass.FINANCIAL_OR_APPROVAL_COMPANY: 200,
    }


@pytest.mark.asyncio
async def test_current_account_needs_no_branch_header_and_rejects_identity_query_input() -> None:
    active_principal = principal(AppRole.ADMIN)
    async with client_for(active_principal=active_principal) as (
        client,
        _application,
        _executor,
        _limiter,
    ):
        accepted = await client.get("/api/v1/account/me")
        guessed = await client.get(
            "/api/v1/account/me",
            params={"appUserId": str(uuid.uuid4())},
        )
        guessed_path = await client.get(f"/api/v1/account/{uuid.uuid4()}")

    assert accepted.status_code == 200
    assert guessed.status_code == 422
    assert guessed.json()["error"]["details"] == [
        {
            "path": "query.appUserId",
            "code": "unknown_field",
            "message": "Field is not allowed",
        }
    ]
    assert guessed_path.status_code == 404
    assert guessed_path.json()["error"]["code"] == "resource_not_found"


@pytest.mark.asyncio
async def test_current_account_requires_authentication_and_maps_transaction_failure() -> None:
    async with client_for() as (client, _application, _executor, _limiter):
        unauthenticated = await client.get("/api/v1/account/me")

    active_principal = principal(AppRole.EMPLOYEE)
    executor = RecordingExecutor(ServiceExecutionError("application_account_lookup_unavailable"))
    async with client_for(active_principal=active_principal, executor=executor) as (
        client,
        _application,
        _executor,
        _limiter,
    ):
        unavailable = await client.get("/api/v1/account/me")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "invalid_access_token"
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "application_account_lookup_unavailable"
    assert "database" not in unavailable.text.lower()


@pytest.mark.asyncio
async def test_sample_openapi_contract_is_explicit_and_strict() -> None:
    async with client_for() as (client, _application, _executor, _limiter):
        document = (await client.get("/openapi.json")).json()

    public = document["paths"]["/api/v1/public/status"]["get"]
    assert public["operationId"] == "get_public_status"
    assert public.get("security", []) == []
    assert "X-Correlation-ID" in public["responses"]["200"]["headers"]
    assert public["responses"]["200"]["headers"]["Cache-Control"]["schema"] == {
        "type": "string",
        "const": "no-store",
    }

    protected = document["paths"]["/api/v1/account/me"]["get"]
    assert protected["operationId"] == "get_current_account"
    assert protected["security"] == [{"HTTPBearer": []}]
    assert "X-Correlation-ID" in protected["responses"]["200"]["headers"]
    assert "Cache-Control" in protected["responses"]["200"]["headers"]
    assert "401" in protected["responses"]
    assert "403" in protected["responses"]
    assert "503" in protected["responses"]
    response_ref = protected["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_ref["$ref"].endswith("DataResponse_CurrentAccountResponse_")
    schemas = document["components"]["schemas"]
    current_account = schemas["CurrentAccountResponse"]
    assert current_account["additionalProperties"] is False
    assert set(current_account["required"]) == {
        "appUserId",
        "role",
        "companyId",
        "employeeId",
        "branchId",
    }
