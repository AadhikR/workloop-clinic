from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationReadAllResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY = uuid.UUID("b3000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("b3000000-0000-4000-8000-000000000002")
USER = uuid.UUID("b3000000-0000-4000-8000-000000000003")
EMPLOYEE = uuid.UUID("b3000000-0000-4000-8000-000000000004")
NOTIFICATION = uuid.UUID("b3000000-0000-4000-8000-000000000005")
KEY = "b3000000-0000-4000-8000-000000000006"
NOW = datetime(2026, 9, 24, 8, tzinfo=UTC)


def claims() -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer="https://seed.workloop.test",
        subject="subject",
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def principal(role: AppRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=USER,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY,
        employee_id=None if role is AppRole.ADMIN else EMPLOYEE,
        branch_id=None if role is AppRole.ADMIN else BRANCH,
    )


def notification() -> NotificationResponse:
    return NotificationResponse(
        id=NOTIFICATION,
        type="leave_approved",
        title="Leave approved",
        body="Your leave request was approved.",
        related_entity_type="leave_request",
        related_entity_id=str(uuid.uuid4()),
        read_at=NOW,
        created_at=NOW,
    )


class StubService:
    async def list(self, *_values: object) -> NotificationListResponse:
        return NotificationListResponse(
            items=[notification()],
            next_cursor=None,
            as_of=NOW,
            source_version="sha256:" + "a" * 64,
        )

    async def unread_count(self, *_values: object) -> NotificationUnreadCountResponse:
        return NotificationUnreadCountResponse(count=1, as_of=NOW)

    async def read_one(self, *_values: object) -> NotificationResponse:
        return notification()

    async def read_all(self, *_values: object) -> NotificationReadAllResponse:
        return NotificationReadAllResponse(changed_count=1, unread_count=0, as_of=NOW)

    async def authorize_replay(self, *_values: object) -> None:
        return None


class ImmediateIdempotency:
    async def execute(self, **values: object) -> IdempotentResponse:
        return await cast(Callable[[], Awaitable[IdempotentResponse]], values["mutation"])()


class RecordingExecutor:
    def __init__(self, expected_branch: uuid.UUID | None) -> None:
        self.expected_branch = expected_branch

    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> object:
        assert selected_admin_branch_id == self.expected_branch
        return await operation(cast(AsyncConnection, object()))


def service_factory(_connection: AsyncConnection) -> StubService:
    return StubService()


def idempotency_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
    return ImmediateIdempotency()


@asynccontextmanager
async def client_for(role: AppRole) -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app

    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = RecordingExecutor(
        BRANCH if role is AppRole.ADMIN else None
    )
    application.state.notification_service_factory = service_factory
    application.state.idempotency_coordinator_factory = idempotency_factory
    application.dependency_overrides[require_access_token] = claims
    application.dependency_overrides[require_authorization_principal] = lambda: principal(role)
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.ADMIN, AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_notification_routes_have_exact_safe_shapes_for_each_role(role: AppRole) -> None:
    branch_headers = {"X-Workloop-Branch-ID": str(BRANCH)} if role is AppRole.ADMIN else {}
    async with client_for(role) as client:
        listed = await client.get("/api/v1/notifications?limit=30", headers=branch_headers)
        counted = await client.get("/api/v1/notifications/unread-count", headers=branch_headers)
        read = await client.put(
            f"/api/v1/notifications/{NOTIFICATION}/read", headers=branch_headers
        )
        all_read = await client.post(
            "/api/v1/notifications/read-all",
            headers={**branch_headers, "Idempotency-Key": KEY},
            json={},
        )
    assert {
        listed.status_code,
        counted.status_code,
        read.status_code,
        all_read.status_code,
    } == {200}
    assert set(listed.json()["data"]) == {"items", "nextCursor", "asOf", "sourceVersion"}
    assert set(listed.json()["data"]["items"][0]) == {
        "id",
        "type",
        "title",
        "body",
        "relatedEntityType",
        "relatedEntityId",
        "readAt",
        "createdAt",
    }
    assert counted.json()["data"]["count"] == 1
    assert all_read.json()["data"]["unreadCount"] == 0


@pytest.mark.asyncio
async def test_notification_scope_rejects_missing_or_caller_supplied_branch() -> None:
    async with client_for(AppRole.ADMIN) as client:
        missing = await client.get("/api/v1/notifications")
    async with client_for(AppRole.EMPLOYEE) as client:
        forged = await client.get(
            "/api/v1/notifications", headers={"X-Workloop-Branch-ID": str(BRANCH)}
        )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "branch_required"
    assert forged.status_code == 422
    assert forged.json()["error"]["code"] == "invalid_branch"
