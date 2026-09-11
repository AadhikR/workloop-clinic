import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from typing import cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.auth.dependencies import require_access_token, require_authorization_principal
from app.models.identity import AccountStatus, AppRole
from app.schemas.employees import (
    DirectReportResponse,
    EmployeeAdminDetailResponse,
    EmployeeAdminListResponse,
    EmployeeImportResponse,
    EmployeeImportResult,
    EmployeeJobHistoryResponse,
    EmployeeSelfResponse,
)
from app.services.idempotency import IdempotentResponse
from tests.test_http_boundary import make_settings

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
EMPLOYEE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c3")
MANAGER_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c4")
HISTORY_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c5")
NOW = datetime(2026, 9, 10, 12, 30, 45, 123000, tzinfo=UTC)


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
        employee_id=MANAGER_ID if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


def list_employee() -> EmployeeAdminListResponse:
    return EmployeeAdminListResponse(
        id=EMPLOYEE_ID,
        emp_no="E-001",
        name="Synthetic Employee",
        photo_url="",
        work_email="employee@example.test",
        job_title="Nurse",
        department="Clinical",
        reporting_manager_id=MANAGER_ID,
        employment_start_date=date(2025, 1, 2),
        probation_end_date=None,
        employment_status="active",
        active=True,
        basic_salary="10000.00",
        housing_allowance="1000.00",
        transport_allowance="500.00",
        other_allowances="0.00",
        bank_name="Synthetic Bank",
        updated_at=NOW,
    )


def employee_detail() -> EmployeeAdminDetailResponse:
    return EmployeeAdminDetailResponse(
        **list_employee().model_dump(),
        mol_id="MOL-001",
        bank_routing_code="BANK-A",
        iban="AE000000000000000000001",
        allowance="250.00",
        personal_email="personal@example.test",
        phone="+971500000001",
        date_of_birth=date(1990, 1, 1),
        gender="female",
        marital_status="single",
        home_country_address="Synthetic address",
        emergency_contact_name="Synthetic Contact",
        emergency_contact_relationship="Sibling",
        emergency_contact_phone="+971500000002",
        probation_extended=False,
        termination_date=None,
        termination_reason="",
        other_allowances_label="",
        bank_account_holder="Synthetic Employee",
        nationality="Synthetic",
        visa_type="employment_visa",
        visa_number="VISA-001",
        visa_expiry=None,
        passport_number="P-001",
        passport_expiry=None,
        emirates_id="784-0000-0000000-1",
        emirates_id_expiry=None,
        labour_card_number="LC-001",
        labour_card_expiry=None,
        sponsoring_entity="Horizon Clinic",
        work_location_type="mainland",
        free_zone_name="",
        nafis_registration_no="",
        licence_authority="DHA",
        licence_number="LIC-001",
        licence_expiry=None,
        created_at=NOW,
    )


def employee_self() -> EmployeeSelfResponse:
    values = employee_detail().model_dump(by_alias=False)
    for field in ("reporting_manager_id", "active", "created_at", "updated_at"):
        values.pop(field)
    values["reporting_manager"] = {
        "id": MANAGER_ID,
        "name": "Synthetic Manager",
        "job_title": "Manager",
    }
    return EmployeeSelfResponse(**values)


def history() -> EmployeeJobHistoryResponse:
    return EmployeeJobHistoryResponse(
        id=HISTORY_ID,
        employee_id=EMPLOYEE_ID,
        changed_at=NOW,
        changed_by_app_user_id=None,
        change_type="title_change",
        old_value="Assistant nurse",
        new_value="Nurse",
        reason="Synthetic promotion",
    )


class StubService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    async def list_employees(
        self, active: AuthorizationPrincipal, branch_id: uuid.UUID, query: object
    ) -> tuple[list[EmployeeAdminListResponse], str | None]:
        self.calls.append(("list", (active, branch_id, query)))
        return [list_employee()], None

    async def get_employee(
        self, active: AuthorizationPrincipal, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> EmployeeAdminDetailResponse:
        self.calls.append(("detail", (active, branch_id, employee_id)))
        return employee_detail()

    async def create_employee(
        self, active: AuthorizationPrincipal, branch_id: uuid.UUID, request: object
    ) -> EmployeeAdminDetailResponse:
        self.calls.append(("create", (active, branch_id, request)))
        return employee_detail()

    async def authorize_employee_replay(
        self,
        active: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        assert active.role is AppRole.ADMIN
        assert (branch_id, kind, resource_id) == (BRANCH_ID, "employee", EMPLOYEE_ID)

    async def update_employee(
        self,
        active: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: object,
    ) -> EmployeeAdminDetailResponse:
        self.calls.append(("update", (active, branch_id, employee_id, request)))
        return employee_detail()

    async def import_employees(
        self, active: AuthorizationPrincipal, branch_id: uuid.UUID, request: object
    ) -> EmployeeImportResponse:
        self.calls.append(("import", (active, branch_id, request)))
        return EmployeeImportResponse(
            created_count=1,
            rows=[EmployeeImportResult(row_number=2, employee_id=EMPLOYEE_ID)],
        )

    async def authorize_import_replay(
        self,
        active: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        assert active.role is AppRole.ADMIN
        assert (branch_id, kind, resource_id) == (BRANCH_ID, "tenant", None)

    async def get_self(self, active: AuthorizationPrincipal) -> EmployeeSelfResponse:
        self.calls.append(("self", active))
        return employee_self()

    async def list_direct_reports(
        self, active: AuthorizationPrincipal, query: object
    ) -> tuple[list[DirectReportResponse], str | None]:
        self.calls.append(("reports", (active, query)))
        item = list_employee()
        return [
            DirectReportResponse(
                id=item.id,
                emp_no=item.emp_no,
                name=item.name,
                photo_url=item.photo_url,
                job_title=item.job_title,
                department=item.department,
                employment_start_date=item.employment_start_date,
                probation_end_date=item.probation_end_date,
                employment_status=item.employment_status,
            )
        ], None

    async def list_job_history(
        self,
        active: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: object,
        *,
        path_employee_id: uuid.UUID | None = None,
    ) -> tuple[list[EmployeeJobHistoryResponse], str | None]:
        self.calls.append(("history", (active, branch_id, query, path_employee_id)))
        return [history()], None


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


class ImmediateIdempotency:
    async def execute(self, **values: object) -> IdempotentResponse:
        mutation = cast(Callable[[], Awaitable[IdempotentResponse]], values["mutation"])
        return await mutation()


@asynccontextmanager
async def client_for(
    role: AppRole,
) -> AsyncGenerator[tuple[AsyncClient, FastAPI, StubService, RecordingExecutor]]:
    from app.main import create_app

    active_principal = principal(role)
    service = StubService()
    executor = RecordingExecutor()
    application = create_app(settings=make_settings(api_request_timeout_seconds=1))
    application.state.authorized_service_executor = executor

    def service_factory(_connection: AsyncConnection) -> StubService:
        return service

    application.state.employee_service_factory = service_factory

    def idempotency_factory(_connection: AsyncConnection) -> ImmediateIdempotency:
        return ImmediateIdempotency()

    application.state.idempotency_coordinator_factory = idempotency_factory

    async def verified_claims() -> AccessTokenClaims:
        return claims()

    async def resolved_principal() -> AuthorizationPrincipal:
        return active_principal

    application.dependency_overrides[require_access_token] = verified_claims
    application.dependency_overrides[require_authorization_principal] = resolved_principal
    async with AsyncClient(
        transport=ASGITransport(app=application, raise_app_exceptions=True),
        base_url="http://testserver",
    ) as client:
        yield client, application, service, executor


@pytest.mark.asyncio
async def test_admin_employee_reads_have_exact_camel_case_projections() -> None:
    header = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    async with client_for(AppRole.ADMIN) as (client, _app, service, executor):
        listing = await client.get("/api/v1/employees", headers=header)
        detail = await client.get(f"/api/v1/employees/{EMPLOYEE_ID}", headers=header)
        one_history = await client.get(
            f"/api/v1/employees/{EMPLOYEE_ID}/job-history", headers=header
        )
        branch_history = await client.get("/api/v1/employee-job-history", headers=header)

    assert listing.status_code == detail.status_code == 200
    assert one_history.status_code == branch_history.status_code == 200
    assert set(listing.json()["data"][0]) == set(
        list_employee().model_dump(mode="json", by_alias=True)
    )
    assert set(detail.json()["data"]) == set(
        employee_detail().model_dump(mode="json", by_alias=True)
    )
    assert set(one_history.json()["data"][0]) == set(
        history().model_dump(mode="json", by_alias=True)
    )
    assert one_history.headers["cache-control"] == "no-store"
    assert (
        len(
            {
                response.headers["x-correlation-id"]
                for response in (listing, detail, one_history, branch_history)
            }
        )
        == 4
    )
    assert [call[0] for call in service.calls] == ["list", "detail", "history", "history"]
    assert executor.selected == [BRANCH_ID, BRANCH_ID, BRANCH_ID, BRANCH_ID]


@pytest.mark.asyncio
async def test_staff_self_and_manager_projection_do_not_expose_sensitive_fields() -> None:
    async with client_for(AppRole.MANAGER) as (client, _app, _service, executor):
        self_response = await client.get("/api/v1/employees/self")
        reports = await client.get("/api/v1/employees/direct-reports")

    assert self_response.status_code == reports.status_code == 200
    self_data = self_response.json()["data"]
    assert "basicSalary" in self_data
    assert "active" not in self_data
    assert "reportingManagerId" not in self_data
    report = reports.json()["data"][0]
    assert set(report) == set(
        DirectReportResponse(
            id=EMPLOYEE_ID,
            emp_no="E-001",
            name="Synthetic Employee",
            photo_url="",
            job_title="Nurse",
            department="Clinical",
            employment_start_date=date(2025, 1, 2),
            probation_end_date=None,
            employment_status="active",
        ).model_dump(mode="json", by_alias=True)
    )
    assert not {"basicSalary", "workEmail", "phone", "emiratesId"} & set(report)
    assert executor.selected == [None, None]


@pytest.mark.asyncio
async def test_employee_cannot_read_admin_or_manager_collections() -> None:
    header = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    async with client_for(AppRole.EMPLOYEE) as (client, _app, _service, _executor):
        responses = [
            await client.get("/api/v1/employees", headers=header),
            await client.get("/api/v1/employees/direct-reports"),
            await client.get("/api/v1/employee-job-history", headers=header),
            await client.get("/api/v1/employees/self", headers=header),
        ]

    assert [(response.status_code, response.json()["error"]["code"]) for response in responses] == [
        (403, "operation_not_permitted"),
        (403, "operation_not_permitted"),
        (403, "operation_not_permitted"),
        (403, "operation_not_permitted"),
    ]


@pytest.mark.asyncio
async def test_employee_queries_reject_unknown_duplicates_and_invalid_values() -> None:
    header = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    async with client_for(AppRole.ADMIN) as (client, _app, _service, _executor):
        responses = [
            await client.get("/api/v1/employees?companyId=guessed", headers=header),
            await client.get("/api/v1/employees?active=true&active=false", headers=header),
            await client.get("/api/v1/employees?employmentStatus=Active", headers=header),
            await client.get("/api/v1/employee-job-history?changedFrom=2026-09-10", headers=header),
            await client.get("/api/v1/employees/self?employeeId=guessed"),
            await client.get(f"/api/v1/employees/{EMPLOYEE_ID}?expand=all", headers=header),
        ]

    assert all(response.status_code == 422 for response in responses)
    assert all(response.json()["error"]["code"] == "validation_failed" for response in responses)


@pytest.mark.asyncio
async def test_admin_can_create_edit_and_import_employees() -> None:
    header = {
        "X-Workloop-Branch-ID": str(BRANCH_ID),
        "Idempotency-Key": "7f000000-0000-4000-8000-000000000002",
    }
    create_body = {
        "name": "Synthetic Employee",
        "molId": "10003048635715",
        "department": "Clinical",
    }
    import_row = {
        "rowNumber": 2,
        "empNo": "E-001",
        "name": "Synthetic Employee",
        "molId": "10003048635715",
        "bankName": "Synthetic Bank",
        "bankRoutingCode": "123456789",
        "iban": "AE000000000000000000001",
        "basicSalary": "10000.00",
        "allowance": "250.00",
    }
    async with client_for(AppRole.ADMIN) as (client, _app, service, executor):
        created = await client.post("/api/v1/employees", headers=header, json=create_body)
        updated = await client.patch(
            f"/api/v1/employees/{EMPLOYEE_ID}",
            headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            json={"name": "Edited Employee", "expectedUpdatedAt": "2026-09-10T12:30:45.123Z"},
        )
        imported = await client.post(
            "/api/v1/employee-imports", headers=header, json={"rows": [import_row]}
        )

    assert created.status_code == imported.status_code == 201
    assert created.headers["location"] == f"/api/v1/employees/{EMPLOYEE_ID}"
    assert updated.status_code == 200
    assert imported.json()["data"] == {
        "createdCount": 1,
        "rows": [{"rowNumber": 2, "employeeId": str(EMPLOYEE_ID)}],
    }
    assert [name for name, _value in service.calls if name in {"create", "update", "import"}] == [
        "create",
        "update",
        "import",
    ]
    assert executor.selected == [BRANCH_ID, BRANCH_ID, BRANCH_ID]


@pytest.mark.asyncio
async def test_employee_mutations_reject_missing_keys_unknown_fields_and_large_batches() -> None:
    header = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
    row = {
        "rowNumber": 2,
        "empNo": "E-001",
        "name": "Synthetic Employee",
        "molId": "10003048635715",
        "bankName": "",
        "bankRoutingCode": "",
        "iban": "",
        "basicSalary": "0.00",
        "allowance": "0.00",
    }
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        missing_key = await client.post(
            "/api/v1/employees",
            headers=header,
            json={
                "name": "Synthetic Employee",
                "molId": "10003048635715",
                "department": "Clinical",
            },
        )
        forbidden_edit = await client.patch(
            f"/api/v1/employees/{EMPLOYEE_ID}",
            headers=header,
            json={"jobTitle": "Director", "expectedUpdatedAt": "2026-09-10T12:30:45.123Z"},
        )
        too_many = await client.post(
            "/api/v1/employee-imports",
            headers={**header, "Idempotency-Key": "7f000000-0000-4000-8000-000000000005"},
            json={"rows": [{**row, "rowNumber": index + 1} for index in range(501)]},
        )
        invalid_row = await client.post(
            "/api/v1/employee-imports",
            headers={**header, "Idempotency-Key": "7f000000-0000-4000-8000-000000000006"},
            json={"rows": [{**row, "molId": "invalid"}]},
        )
        oversized = await client.post(
            "/api/v1/employee-imports",
            headers={
                **header,
                "Idempotency-Key": "7f000000-0000-4000-8000-000000000007",
                "Content-Type": "application/json",
                "Content-Length": "1048577",
            },
            content=b"{}",
        )

    assert (missing_key.status_code, missing_key.json()["error"]["code"]) == (
        400,
        "idempotency_key_required",
    )
    assert forbidden_edit.status_code == too_many.status_code == 422
    assert all(
        response.json()["error"]["code"] == "validation_failed"
        for response in (forbidden_edit, too_many)
    )
    assert invalid_row.status_code == 422
    assert invalid_row.json()["error"]["details"] == [
        {
            "path": "body.rows[0].molId",
            "code": "invalid_format",
            "message": "Value has an invalid format",
        }
    ]
    assert (oversized.status_code, oversized.json()["error"]["code"]) == (
        413,
        "request_too_large",
    )
    assert executor.selected == []


def test_openapi_publishes_the_authorized_employee_routes() -> None:
    from app.main import create_app

    schema = create_app(settings=make_settings()).openapi()
    expected = {
        "/api/v1/employees",
        "/api/v1/employees/{employee_id}",
        "/api/v1/employees/self",
        "/api/v1/employees/direct-reports",
        "/api/v1/employees/{employee_id}/job-history",
        "/api/v1/employee-job-history",
    }
    assert expected <= set(schema["paths"])
    assert set(schema["paths"]["/api/v1/employees"]) == {"get", "post"}
    assert set(schema["paths"]["/api/v1/employees/{employee_id}"]) == {"get", "patch"}
    for path in expected - {
        "/api/v1/employees",
        "/api/v1/employees/{employee_id}",
    }:
        assert set(schema["paths"][path]) == {"get"}
    assert set(schema["paths"]["/api/v1/employee-imports"]) == {"post"}
