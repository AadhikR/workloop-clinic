import logging
import uuid
from collections.abc import Sequence
from typing import Annotated, cast

import pytest
from fastapi import Depends, FastAPI, Request, Response, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.auth.dependencies import (
    AdminSelectedBranch,
    AuthenticatedAuthorizationPrincipal,
    EmployeeSelfIdentity,
    ManagerIdentity,
    TenantScope,
    require_access_token,
    require_admin_principal,
    require_authorization_principal,
    require_roles,
)
from app.models.identity import AccountStatus, AppRole
from tests.test_application_user import (
    StubConnection,
    StubEngine,
    fixture_resolution,
)


def principal(role: AppRole) -> AuthorizationPrincipal:
    is_staff = role in {AppRole.MANAGER, AppRole.EMPLOYEE}
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=uuid.uuid4(),
        employee_id=uuid.uuid4() if is_staff else None,
        branch_id=uuid.uuid4() if is_staff else None,
    )


def dependency_app(
    active_principal: AuthorizationPrincipal,
    *,
    branch_rows: Sequence[tuple[object, ...]] | None = None,
    failure: Exception | None = None,
) -> tuple[FastAPI, StubEngine]:
    application = FastAPI()
    connection = StubConnection(branch_rows or [], failure=failure)
    engine = StubEngine(connection)
    application.state.application_user_resolver = ApplicationUserResolver(
        engine=cast(AsyncEngine, engine),
        issuer="https://seed.workloop.test",
        timeout_seconds=1,
    )

    async def resolved_principal() -> AuthorizationPrincipal:
        return active_principal

    application.dependency_overrides[require_authorization_principal] = resolved_principal

    async def tenant_route(_company_id: TenantScope) -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def self_route(_employee_id: EmployeeSelfIdentity) -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def manager_route(_manager_id: ManagerIdentity) -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def admin_route(
        _principal: Annotated[AuthorizationPrincipal, Depends(require_admin_principal)],
    ) -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def branch_route(_branch_id: AdminSelectedBranch) -> Response:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    async def caller_input_route(
        request: Request,
        _company_id: TenantScope,
    ) -> Response:
        await request.body()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    application.add_api_route("/tenant", tenant_route, methods=["GET"])
    application.add_api_route("/self", self_route, methods=["GET"])
    application.add_api_route("/manager", manager_route, methods=["GET"])
    application.add_api_route("/admin", admin_route, methods=["GET"])
    application.add_api_route("/branch", branch_route, methods=["GET"])
    application.add_api_route("/caller-input", caller_input_route, methods=["POST"])
    return application, engine


@pytest.mark.asyncio
async def test_role_tenant_self_and_manager_dependencies_use_only_principal() -> None:
    manager = principal(AppRole.MANAGER)
    application, _ = dependency_app(manager)

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        tenant = await client.get("/tenant")
        employee_self = await client.get("/self")
        manager_scope = await client.get("/manager")
        admin = await client.get("/admin")

    assert tenant.status_code == employee_self.status_code == manager_scope.status_code == 204
    assert admin.status_code == 403
    assert admin.json() == {
        "detail": {"code": "operation_not_permitted", "message": "Operation not permitted"}
    }


@pytest.mark.asyncio
async def test_composed_dependencies_share_one_principal_lookup() -> None:
    row, expected = fixture_resolution("aisha.manager@horizon.test")
    engine = StubEngine(StubConnection([row]))
    resolver = ApplicationUserResolver(
        engine=cast(AsyncEngine, engine),
        issuer="https://seed.workloop.test",
        timeout_seconds=1,
    )
    application = FastAPI()
    application.state.application_user_resolver = resolver

    async def verified_claims() -> AccessTokenClaims:
        return AccessTokenClaims(
            issuer="https://seed.workloop.test",
            subject="aisha.manager@horizon.test",
            audience=("workloop-api",),
            expires_at=1,
            issued_at=1,
            not_before=None,
        )

    async def composed_route(
        resolved: AuthenticatedAuthorizationPrincipal,
        company_id: TenantScope,
        employee_id: EmployeeSelfIdentity,
        manager_id: ManagerIdentity,
    ) -> Response:
        assert resolved == expected
        assert company_id == expected.company_id
        assert employee_id == manager_id == expected.employee_id
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    application.dependency_overrides[require_access_token] = verified_claims
    application.add_api_route("/composed", composed_route, methods=["GET"])

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get("/composed")

    assert response.status_code == 204
    assert engine.connect_count == 1
    assert len(engine.connection.statements) == 1


@pytest.mark.asyncio
async def test_admin_has_tenant_scope_but_no_employee_or_manager_identity() -> None:
    admin = principal(AppRole.ADMIN)
    application, _ = dependency_app(admin)

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        tenant = await client.get("/tenant")
        employee_self = await client.get("/self")
        manager_scope = await client.get("/manager")

    assert tenant.status_code == 204
    assert employee_self.status_code == manager_scope.status_code == 403
    assert admin.employee_id is None
    assert admin.branch_id is None


@pytest.mark.asyncio
async def test_employee_has_self_identity_but_not_manager_identity() -> None:
    employee = principal(AppRole.EMPLOYEE)
    application, _ = dependency_app(employee)

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        employee_self = await client.get("/self")
        manager_scope = await client.get("/manager")

    assert employee_self.status_code == 204
    assert manager_scope.status_code == 403


def test_role_dependency_rejects_empty_and_unapproved_sets() -> None:
    with pytest.raises(ValueError):
        require_roles()
    with pytest.raises(ValueError):
        require_roles(cast(AppRole, "owner"))


@pytest.mark.asyncio
async def test_admin_branch_selection_is_company_scoped_and_temporary() -> None:
    admin = principal(AppRole.ADMIN)
    selected_branch = uuid.uuid4()
    application, engine = dependency_app(admin, branch_rows=[(selected_branch,)])

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/branch", headers={"X-Workloop-Branch-ID": str(selected_branch)}
        )

    assert response.status_code == 204
    assert admin.employee_id is None
    assert admin.branch_id is None
    assert engine.connect_count == 1
    statement = engine.connection.statements[0]
    assert set(statement.compile().params.values()) >= {admin.company_id, selected_branch}
    sql = str(statement).lower()
    assert "branches.id" in sql
    assert "branches.company_id" in sql


@pytest.mark.parametrize(
    ("headers", "expected_status", "expected_code"),
    [
        (None, 400, "branch_required"),
        ({"X-Workloop-Branch-ID": "not-a-uuid"}, 422, "invalid_branch"),
        ({"X-Workloop-Branch-ID": " "}, 422, "invalid_branch"),
    ],
    ids=["missing", "malformed", "blank"],
)
@pytest.mark.asyncio
async def test_branch_selector_returns_approved_input_errors(
    headers: dict[str, str] | None,
    expected_status: int,
    expected_code: str,
) -> None:
    application, engine = dependency_app(principal(AppRole.ADMIN))

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get("/branch", headers=headers)

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    assert engine.connect_count == 0


@pytest.mark.asyncio
async def test_duplicate_branch_selector_is_invalid() -> None:
    branch_id = str(uuid.uuid4())
    application, engine = dependency_app(principal(AppRole.ADMIN))

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/branch",
            headers=[
                ("X-Workloop-Branch-ID", branch_id),
                ("X-Workloop-Branch-ID", branch_id),
            ],
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_branch"
    assert engine.connect_count == 0


@pytest.mark.asyncio
async def test_missing_and_cross_company_branch_use_same_safe_404() -> None:
    selected_branch = uuid.uuid4()
    for rows in ([], [(uuid.uuid4(),)]):
        application, _ = dependency_app(principal(AppRole.ADMIN), branch_rows=rows)
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/branch", headers={"X-Workloop-Branch-ID": str(selected_branch)}
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": {"code": "resource_not_found", "message": "Resource not found"}
        }
        assert str(selected_branch) not in response.text


@pytest.mark.asyncio
async def test_manager_and_employee_cannot_select_another_branch() -> None:
    selected_branch = uuid.uuid4()
    for role in (AppRole.MANAGER, AppRole.EMPLOYEE):
        active_principal = principal(role)
        application, engine = dependency_app(active_principal, branch_rows=[(selected_branch,)])
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/branch", headers={"X-Workloop-Branch-ID": str(selected_branch)}
            )

        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "operation_not_permitted"
        assert engine.connect_count == 0


@pytest.mark.asyncio
async def test_caller_fields_cannot_change_admin_business_scope() -> None:
    admin = principal(AppRole.ADMIN)
    application, _ = dependency_app(admin)
    untrusted = str(uuid.uuid4())

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.post(
            f"/caller-input?company_id={untrusted}&employee_id={untrusted}&role=manager",
            headers={
                "X-Company-ID": untrusted,
                "X-Employee-ID": untrusted,
                "X-Role": "employee",
                "X-Email": "attacker@example.test",
            },
            json={
                "company_id": untrusted,
                "employee_id": untrusted,
                "branch_id": untrusted,
                "role": "manager",
            },
        )

    assert response.status_code == 204
    assert admin.company_id != uuid.UUID(untrusted)
    assert admin.role is AppRole.ADMIN
    assert admin.employee_id is None
    assert admin.branch_id is None


@pytest.mark.asyncio
async def test_branch_lookup_failure_returns_safe_503_without_detail_leak(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_detail = "database-branch-detail"
    selected_branch = uuid.uuid4()
    application, _ = dependency_app(
        principal(AppRole.ADMIN), failure=RuntimeError(sensitive_detail)
    )
    caplog.set_level(logging.DEBUG)

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        response = await client.get(
            "/branch", headers={"X-Workloop-Branch-ID": str(selected_branch)}
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "application_account_lookup_unavailable"
    assert sensitive_detail not in response.text + caplog.text
    assert str(selected_branch) not in response.text + caplog.text
