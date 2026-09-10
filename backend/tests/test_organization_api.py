import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.organization import (
    BranchAdminResponse,
    BranchSafeResponse,
    CompanyAdminResponse,
    SafeEmployerResponse,
)
from tests.test_http_boundary import make_settings

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
OTHER_BRANCH_ID = uuid.UUID("07186a4f-e0df-4799-916f-b524503743a4")
NOW = datetime(2026, 9, 9, 12, 30, 45, 123000, tzinfo=UTC)


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
        company_id=COMPANY_ID,
        employee_id=uuid.uuid4() if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


class StubService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def get_company(self, active: AuthorizationPrincipal) -> CompanyAdminResponse:
        self.calls.append(("company", active))
        return CompanyAdminResponse(
            id=COMPANY_ID,
            name="Horizon Clinic",
            sector="Healthcare",
            nafis_quota_percent="2.00",
            enable_nafis=True,
            created_at=NOW,
            updated_at=NOW,
        )

    async def get_employer(self, active: AuthorizationPrincipal) -> SafeEmployerResponse:
        self.calls.append(("employer", active))
        return SafeEmployerResponse(
            company_name="Horizon Clinic",
            branch_name="Dubai",
            branch_contact_email="dubai@example.test",
            branch_address="Synthetic address",
            work_location_type="mainland",
            free_zone_name="",
            logo_url="",
        )

    async def list_branches(
        self, active: AuthorizationPrincipal, query: object
    ) -> tuple[list[BranchAdminResponse | BranchSafeResponse], str | None]:
        self.calls.append(("branches", query))
        if active.role is AppRole.ADMIN:
            item: BranchAdminResponse | BranchSafeResponse = BranchAdminResponse(
                id=BRANCH_ID,
                name="Dubai",
                mol_employer_id="MOL-001",
                default_bank_routing_code="BANK-A",
                address="Synthetic address",
                contact_email="dubai@example.test",
                default_salary_day=25,
                work_location_type="mainland",
                free_zone_name="",
                logo_url="",
                enable_staffing_rules=True,
                enable_biometric_import=False,
                created_at=NOW,
                updated_at=NOW,
            )
        else:
            item = BranchSafeResponse(
                id=BRANCH_ID,
                name="Dubai",
                address="Synthetic address",
                contact_email="dubai@example.test",
                work_location_type="mainland",
                free_zone_name="",
                logo_url="",
            )
        return [item], None

    async def get_branch(
        self, active: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> BranchAdminResponse:
        self.calls.append(("branch", branch_id))
        assert active.role is AppRole.ADMIN
        items, _cursor = await self.list_branches(active, object())
        item = items[0]
        assert isinstance(item, BranchAdminResponse)
        return item


class RecordingExecutor:
    def __init__(self, service: StubService) -> None:
        self.service = service
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
) -> AsyncGenerator[tuple[AsyncClient, FastAPI, StubService, RecordingExecutor]]:
    from app.main import create_app

    active_principal = principal(role)
    service = StubService()
    executor = RecordingExecutor(service)
    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = executor

    def service_factory(_connection: AsyncConnection) -> StubService:
        return service

    application.state.organization_service_factory = service_factory

    async def verified_claims() -> AccessTokenClaims:
        return claims()

    async def resolved_principal() -> AuthorizationPrincipal:
        return active_principal

    application.dependency_overrides[require_access_token] = verified_claims
    application.dependency_overrides[require_authorization_principal] = resolved_principal
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        yield client, application, service, executor


@pytest.mark.asyncio
async def test_admin_company_and_branch_responses_have_exact_projections() -> None:
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        company = await client.get("/api/v1/company")
        branches = await client.get("/api/v1/branches")
        branch = await client.get(
            f"/api/v1/branches/{BRANCH_ID}",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
        )

    assert company.status_code == branches.status_code == branch.status_code == 200
    assert company.json()["data"]["createdAt"] == "2026-09-09T12:30:45.123Z"
    assert set(company.json()["data"]) == {
        "id",
        "name",
        "sector",
        "nafisQuotaPercent",
        "enableNafis",
        "createdAt",
        "updatedAt",
    }
    assert set(branches.json()["data"][0]) == {
        "id",
        "name",
        "molEmployerId",
        "defaultBankRoutingCode",
        "address",
        "contactEmail",
        "defaultSalaryDay",
        "workLocationType",
        "freeZoneName",
        "logoUrl",
        "enableStaffingRules",
        "enableBiometricImport",
        "createdAt",
        "updatedAt",
    }
    assert branches.json()["page"] == {"limit": 50, "nextCursor": None, "hasMore": False}
    assert branch.json()["data"] == branches.json()["data"][0]
    assert executor.selected == [None, None, BRANCH_ID]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_staff_receive_only_safe_employer_and_own_branch(role: AppRole) -> None:
    async with client_for(role) as (client, _app, _service, executor):
        employer = await client.get("/api/v1/employer")
        branches = await client.get("/api/v1/branches")
        company = await client.get("/api/v1/company")
        detail = await client.get(
            f"/api/v1/branches/{BRANCH_ID}",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
        )

    assert employer.status_code == branches.status_code == 200
    assert set(employer.json()["data"]) == {
        "companyName",
        "branchName",
        "branchContactEmail",
        "branchAddress",
        "workLocationType",
        "freeZoneName",
        "logoUrl",
    }
    assert set(branches.json()["data"][0]) == {
        "id",
        "name",
        "address",
        "contactEmail",
        "workLocationType",
        "freeZoneName",
        "logoUrl",
    }
    assert company.status_code == detail.status_code == 403
    assert executor.selected == [None, None]


@pytest.mark.asyncio
async def test_branch_detail_requires_one_matching_canonical_header() -> None:
    cases: list[tuple[dict[str, str], int, str]] = [
        ({}, 400, "branch_required"),
        ({"X-Workloop-Branch-ID": "not-a-uuid"}, 422, "invalid_branch"),
        ({"X-Workloop-Branch-ID": str(OTHER_BRANCH_ID)}, 404, "resource_not_found"),
    ]
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        for headers, status, code in cases:
            response = await client.get(f"/api/v1/branches/{BRANCH_ID}", headers=headers)
            assert response.status_code == status
            assert response.json()["error"]["code"] == code
        duplicate = await client.get(
            f"/api/v1/branches/{BRANCH_ID}",
            headers=[
                ("X-Workloop-Branch-ID", str(BRANCH_ID)),
                ("X-Workloop-Branch-ID", str(BRANCH_ID)),
            ],
        )

    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "invalid_branch"
    assert executor.selected == []


@pytest.mark.asyncio
async def test_branch_collection_rejects_unknown_duplicate_and_malformed_query_values() -> None:
    paths = [
        "/api/v1/branches?companyId=3afbf0a0-9642-4d44-9884-e9654983eb9b",
        "/api/v1/branches?limit=10&limit=20",
        "/api/v1/branches?limit=01",
        "/api/v1/branches?search=%20",
        "/api/v1/branches?sort=defaultSalaryDay",
        "/api/v1/branches?cursor=not%20opaque",
    ]
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        responses = [await client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [422] * len(paths)
    assert executor.selected == []


@pytest.mark.asyncio
async def test_malformed_branch_path_is_validation_failure_and_does_not_enter_transaction() -> None:
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        malformed = await client.get(
            "/api/v1/branches/NOT-A-UUID",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
        )
        uppercase = await client.get(
            f"/api/v1/branches/{str(BRANCH_ID).upper()}",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
        )

    assert malformed.status_code == uppercase.status_code == 422
    assert executor.selected == []
