import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import cast

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.departments import DepartmentResponse, StaffingRuleResponse
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
DEPARTMENT_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698d1")
RULE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698f1")
NOW = datetime(2026, 9, 11, 8, tzinfo=UTC)
KEY = "7e000000-0000-4000-8000-000000000001"


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
    staff = role is not AppRole.ADMIN
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=uuid.uuid4() if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


def department() -> DepartmentResponse:
    return DepartmentResponse(
        id=DEPARTMENT_ID,
        name="Clinical",
        parent_id=None,
        head_employee_id=None,
        color="#6366f1",
        description="Patient care",
        sort_order=1,
        created_at=NOW,
    )


def staffing_rule() -> StaffingRuleResponse:
    return StaffingRuleResponse(
        id=RULE_ID,
        department="Clinical",
        shift_category="morning",
        min_staff=2,
        effective_from=date(2026, 9, 1),
        effective_to=None,
    )


class StubService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def list_departments(self, *_values: object) -> tuple[list[DepartmentResponse], None]:
        self.calls.append("list_departments")
        return [department()], None

    async def create_department(self, *_values: object) -> DepartmentResponse:
        self.calls.append("create_department")
        return department()

    async def update_department(self, *_values: object) -> DepartmentResponse:
        self.calls.append("update_department")
        return department()

    async def authorize_department_replay(self, *_values: object) -> None:
        self.calls.append("authorize_department_replay")

    async def delete_department(self, *_values: object) -> None:
        self.calls.append("delete_department")

    async def list_staffing_rules(
        self, *_values: object
    ) -> tuple[list[StaffingRuleResponse], None]:
        self.calls.append("list_staffing_rules")
        return [staffing_rule()], None

    async def create_staffing_rule(self, *_values: object) -> StaffingRuleResponse:
        self.calls.append("create_staffing_rule")
        return staffing_rule()

    async def update_staffing_rule(self, *_values: object) -> StaffingRuleResponse:
        self.calls.append("update_staffing_rule")
        return staffing_rule()

    async def delete_staffing_rule(self, *_values: object) -> None:
        self.calls.append("delete_staffing_rule")


class ImmediateIdempotency:
    async def execute(self, **values: object) -> IdempotentResponse:
        mutation = cast(Callable[[], Awaitable[IdempotentResponse]], values["mutation"])
        return await mutation()


class RecordingExecutor:
    def __init__(self) -> None:
        self.selected: list[uuid.UUID | None] = []

    async def execute(
        self,
        *,
        claims: AccessTokenClaims,
        principal: AuthorizationPrincipal,
        operation: Callable[[AsyncConnection], Awaitable[object]],
        selected_admin_branch_id: uuid.UUID | None = None,
    ) -> object:
        assert claims == globals()["claims"]()
        self.selected.append(selected_admin_branch_id)
        return await operation(cast(AsyncConnection, object()))


@asynccontextmanager
async def client_for(
    role: AppRole,
) -> AsyncGenerator[tuple[AsyncClient, StubService, RecordingExecutor]]:
    from app.main import create_app

    service = StubService()
    executor = RecordingExecutor()
    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = executor

    def department_service_factory(_connection: AsyncConnection) -> StubService:
        return service

    def idempotency_coordinator_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application.state.department_service_factory = department_service_factory
    application.state.idempotency_coordinator_factory = idempotency_coordinator_factory

    async def verified_claims() -> AccessTokenClaims:
        return claims()

    async def resolved_principal() -> AuthorizationPrincipal:
        return principal(role)

    application.dependency_overrides[require_access_token] = verified_claims
    application.dependency_overrides[require_authorization_principal] = resolved_principal
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, service, executor


def department_body() -> dict[str, object]:
    return {
        "name": "Clinical",
        "parentId": None,
        "headEmployeeId": None,
        "color": "#6366f1",
        "description": "Patient care",
        "sortOrder": 1,
    }


def rule_body() -> dict[str, object]:
    return {
        "department": "Clinical",
        "shiftCategory": "morning",
        "minStaff": 2,
        "effectiveFrom": "2026-09-01",
        "effectiveTo": None,
    }


@pytest.mark.asyncio
async def test_admin_lists_exact_branch_scoped_projections() -> None:
    async with client_for(AppRole.ADMIN) as (client, _service, executor):
        departments = await client.get(
            "/api/v1/departments", headers={"X-Workloop-Branch-ID": str(BRANCH_ID)}
        )
        rules = await client.get(
            "/api/v1/department-staffing-rules",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
        )
    assert departments.status_code == rules.status_code == 200
    assert set(departments.json()["data"][0]) == {
        "id",
        "name",
        "parentId",
        "headEmployeeId",
        "color",
        "description",
        "sortOrder",
        "createdAt",
    }
    assert set(rules.json()["data"][0]) == {
        "id",
        "department",
        "shiftCategory",
        "minStaff",
        "effectiveFrom",
        "effectiveTo",
    }
    assert executor.selected == [BRANCH_ID, BRANCH_ID]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_staff_cannot_read_or_write_department_tables(role: AppRole) -> None:
    async with client_for(role) as (client, service, executor):
        listing = await client.get(
            "/api/v1/departments", headers={"X-Workloop-Branch-ID": str(BRANCH_ID)}
        )
        created = await client.post(
            "/api/v1/departments",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            json=department_body(),
        )
    assert listing.status_code == created.status_code == 403
    assert service.calls == []
    assert executor.selected == []


@pytest.mark.asyncio
async def test_department_rename_requires_idempotency_and_exact_snapshot() -> None:
    body = {"expected": department_body(), "name": "Care"}
    async with client_for(AppRole.ADMIN) as (client, service, executor):
        missing = await client.patch(
            f"/api/v1/departments/{DEPARTMENT_ID}",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            json=body,
        )
        accepted = await client.patch(
            f"/api/v1/departments/{DEPARTMENT_ID}",
            headers={
                "X-Workloop-Branch-ID": str(BRANCH_ID),
                "Idempotency-Key": KEY,
            },
            json=body,
        )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "idempotency_key_required"
    assert accepted.status_code == 200
    assert service.calls == ["update_department"]
    assert executor.selected == [BRANCH_ID]


@pytest.mark.asyncio
async def test_department_and_staffing_mutations_use_selected_branch() -> None:
    async with client_for(AppRole.ADMIN) as (client, service, executor):
        created_department = await client.post(
            "/api/v1/departments",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            json=department_body(),
        )
        deleted_department = await client.request(
            "DELETE",
            f"/api/v1/departments/{DEPARTMENT_ID}",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            json={"expected": department_body()},
        )
        created_rule = await client.post(
            "/api/v1/department-staffing-rules",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            json=rule_body(),
        )
        updated_rule = await client.patch(
            f"/api/v1/department-staffing-rules/{RULE_ID}",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            json={"expected": rule_body(), "minStaff": 3},
        )
    assert created_department.status_code == created_rule.status_code == 201
    assert deleted_department.status_code == 204
    assert updated_rule.status_code == 200
    assert service.calls == [
        "create_department",
        "delete_department",
        "create_staffing_rule",
        "update_staffing_rule",
    ]
    assert executor.selected == [BRANCH_ID] * 4


@pytest.mark.asyncio
async def test_queries_and_bodies_reject_unknown_or_invalid_values() -> None:
    async with client_for(AppRole.ADMIN) as (client, service, executor):
        responses = [
            await client.get(
                "/api/v1/departments?companyId=foreign",
                headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            ),
            await client.get(
                "/api/v1/departments?parentId=foreign",
                headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            ),
            await client.get(
                "/api/v1/department-staffing-rules?shiftCategory=day",
                headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            ),
            await client.post(
                "/api/v1/departments",
                headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
                json={**department_body(), "companyId": str(COMPANY_ID)},
            ),
        ]
    assert [response.status_code for response in responses] == [422, 422, 422, 422]
    assert service.calls == []
    assert executor.selected == []
