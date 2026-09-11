import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.repositories.employees import EmployeeRepository
from app.services.employees import (
    DirectReportQuery,
    EmployeeCursorCodec,
    EmployeeListQuery,
    EmployeeService,
    JobHistoryQuery,
)

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
EMPLOYEE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c3")
MANAGER_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c4")
NOW = datetime(2026, 9, 10, 12, 30, 45, 123000, tzinfo=UTC)


def principal(role: AppRole, *, app_user_id: uuid.UUID | None = None) -> AuthorizationPrincipal:
    staff = role is not AppRole.ADMIN
    return AuthorizationPrincipal(
        app_user_id=app_user_id or uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=MANAGER_ID if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


def employee_row() -> dict[str, Any]:
    return {
        "id": EMPLOYEE_ID,
        "emp_no": "E-001",
        "name": "Synthetic Employee",
        "photo_url": "",
        "work_email": "employee@example.test",
        "job_title": "Nurse",
        "department": "Clinical",
        "reporting_manager_id": MANAGER_ID,
        "employment_start_date": None,
        "probation_end_date": date(2026, 12, 1),
        "employment_status": "Active",
        "active": True,
        "basic_salary": Decimal("10000.00"),
        "housing_allowance": Decimal("1000.00"),
        "transport_allowance": Decimal("500.00"),
        "other_allowances": Decimal("0.00"),
        "bank_name": "Synthetic Bank",
        "updated_at": NOW,
        "mol_id": "MOL-001",
        "bank_routing_code": "BANK-A",
        "iban": "AE000000000000000000001",
        "allowance": Decimal("250.00"),
        "personal_email": "personal@example.test",
        "phone": "+971500000001",
        "date_of_birth": date(1990, 1, 1),
        "gender": "Female",
        "marital_status": "Single",
        "home_country_address": "Synthetic address",
        "emergency_contact_name": "Synthetic Contact",
        "emergency_contact_relationship": "Sibling",
        "emergency_contact_phone": "+971500000002",
        "probation_extended": False,
        "termination_date": None,
        "termination_reason": "",
        "other_allowances_label": "",
        "bank_account_holder": "Synthetic Employee",
        "nationality": "Synthetic",
        "visa_type": "Employment Visa",
        "visa_number": "VISA-001",
        "visa_expiry": None,
        "passport_number": "P-001",
        "passport_expiry": None,
        "emirates_id": "784-0000-0000000-1",
        "emirates_id_expiry": None,
        "labour_card_number": "LC-001",
        "labour_card_expiry": None,
        "sponsoring_entity": "Horizon Clinic",
        "work_location_type": "Mainland",
        "free_zone_name": "",
        "nafis_registration_no": "",
        "licence_authority": "DHA",
        "licence_number": "LIC-001",
        "licence_expiry": None,
        "created_at": NOW,
        "manager_id": MANAGER_ID,
        "manager_name": "Synthetic Manager",
        "manager_job_title": "Manager",
    }


class MappingResult:
    def __init__(self, rows: list[dict[str, Any] | tuple[object, ...]]) -> None:
        self.rows = rows

    def mappings(self) -> "MappingResult":
        return self

    def all(self) -> list[Any]:
        return self.rows

    def one_or_none(self) -> Any | None:
        assert len(self.rows) <= 1
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self) -> object | None:
        assert len(self.rows) <= 1
        if not self.rows:
            return None
        row = self.rows[0]
        return next(iter(row.values())) if isinstance(row, dict) else row[0]


class RecordingConnection:
    def __init__(self, results: list[list[dict[str, Any] | tuple[object, ...]]]) -> None:
        self.results = results
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> MappingResult:
        self.statements.append(statement)
        return MappingResult(self.results.pop(0))


def list_query(**changes: object) -> EmployeeListQuery:
    values: dict[str, object] = {
        "limit": 50,
        "search": None,
        "employment_status": None,
        "department": None,
        "active": None,
        "reporting_manager_id": None,
        "sort": (("name", False),),
        "cursor": None,
    }
    values.update(changes)
    return EmployeeListQuery(**values)  # pyright: ignore[reportArgumentType]


@pytest.mark.asyncio
async def test_admin_repository_scopes_filters_sorts_and_pages_on_the_server() -> None:
    connection = RecordingConnection([[employee_row()]])
    repository = EmployeeRepository(cast(AsyncConnection, connection))
    await repository.fetch_employees(
        company_id=COMPANY_ID,
        branch_id=BRANCH_ID,
        search="needle",
        employment_status="Active",
        department="Clinical",
        active=True,
        reporting_manager_id="null",
        sort=(("employmentStartDate", True), ("name", False)),
        after=None,
        limit=50,
    )

    query = str(
        connection.statements[0].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "employees.company_id = '3afbf0a0-9642-4d44-9884-e9654983eb9b'" in query
    assert "employees.branch_id = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'" in query
    assert "employees.mol_id ILIKE" in query
    assert "needle" in query
    assert "ESCAPE '\\\\'" in query
    assert "employees.reporting_manager_id IS NULL" in query
    assert "coalesce(employees.employment_start_date, '0001-01-01') DESC" in query
    assert "employees.id ASC" in query
    assert "LIMIT 51" in query
    assert " OFFSET " not in query


@pytest.mark.asyncio
async def test_service_maps_exact_admin_self_and_manager_projections() -> None:
    codec = EmployeeCursorCodec(b"0" * 32, clock=lambda: NOW)
    admin_connection = RecordingConnection([[employee_row()]])
    admin_service = EmployeeService(cast(AsyncConnection, admin_connection), codec)
    admin_items, _ = await admin_service.list_employees(
        principal(AppRole.ADMIN), BRANCH_ID, list_query()
    )
    assert admin_items[0].basic_salary == "10000.00"
    assert set(admin_items[0].model_dump(by_alias=True)) == {
        "id",
        "empNo",
        "name",
        "photoUrl",
        "workEmail",
        "jobTitle",
        "department",
        "reportingManagerId",
        "employmentStartDate",
        "probationEndDate",
        "employmentStatus",
        "active",
        "basicSalary",
        "housingAllowance",
        "transportAllowance",
        "otherAllowances",
        "bankName",
        "updatedAt",
    }

    self_service = EmployeeService(
        cast(
            AsyncConnection,
            RecordingConnection(
                [
                    [employee_row()],
                    [{"id": MANAGER_ID, "name": "Synthetic Manager", "job_title": "Manager"}],
                ]
            ),
        ),
        codec,
    )
    self_projection = await self_service.get_self(principal(AppRole.EMPLOYEE))
    self_fields = set(self_projection.model_dump(by_alias=True))
    assert {"basicSalary", "iban", "emiratesId", "reportingManager"} <= self_fields
    assert "updatedAt" in self_fields
    assert not {"active", "reportingManagerId", "createdAt"} & self_fields
    assert self_projection.reporting_manager is not None
    assert self_projection.reporting_manager.id == MANAGER_ID

    report_row = {
        key: employee_row()[key]
        for key in (
            "id",
            "emp_no",
            "name",
            "photo_url",
            "job_title",
            "department",
            "employment_start_date",
            "probation_end_date",
            "employment_status",
        )
    }
    manager_service = EmployeeService(
        cast(AsyncConnection, RecordingConnection([[report_row]])), codec
    )
    reports, _ = await manager_service.list_direct_reports(
        principal(AppRole.MANAGER),
        DirectReportQuery(
            limit=50,
            search=None,
            employment_status=None,
            sort=(("name", False),),
            cursor=None,
        ),
    )
    assert set(reports[0].model_dump(by_alias=True)) == {
        "id",
        "empNo",
        "name",
        "photoUrl",
        "jobTitle",
        "department",
        "employmentStartDate",
        "probationEndDate",
        "employmentStatus",
    }


def test_employee_cursor_is_authenticated_and_bound_to_role_branch_route_and_filters() -> None:
    codec = EmployeeCursorCodec(b"0" * 32, clock=lambda: NOW)
    admin = principal(AppRole.ADMIN)
    query = list_query(search="Nurse")
    cursor = codec.encode(
        principal=admin,
        branch_id=BRANCH_ID,
        operation_id="list_employees",
        query=query,
        last_id=EMPLOYEE_ID,
    )
    resumed = list_query(search="Nurse", cursor=cursor)
    assert (
        codec.decode(
            principal=admin,
            branch_id=BRANCH_ID,
            operation_id="list_employees",
            query=resumed,
            cursor=cursor,
        )
        == EMPLOYEE_ID
    )
    assert "Nurse" not in cursor
    assert len(cursor) <= 512

    changed = list_query(search="Other", cursor=cursor)
    with pytest.raises(ValueError):
        codec.decode(
            principal=admin,
            branch_id=BRANCH_ID,
            operation_id="list_employees",
            query=changed,
            cursor=cursor,
        )
    with pytest.raises(ValueError):
        codec.decode(
            principal=principal(AppRole.ADMIN),
            branch_id=BRANCH_ID,
            operation_id="list_employees",
            query=resumed,
            cursor=cursor,
        )
    with pytest.raises(ValueError):
        codec.decode(
            principal=admin,
            branch_id=uuid.uuid4(),
            operation_id="list_employees",
            query=resumed,
            cursor=cursor,
        )
    expired = EmployeeCursorCodec(b"0" * 32, clock=lambda: NOW + timedelta(minutes=16))
    with pytest.raises(ValueError):
        expired.decode(
            principal=admin,
            branch_id=BRANCH_ID,
            operation_id="list_employees",
            query=resumed,
            cursor=cursor,
        )


@pytest.mark.asyncio
async def test_job_history_is_branch_scoped_and_uses_stable_descending_order() -> None:
    history_id = uuid.uuid4()
    history_row = {
        "id": history_id,
        "employee_id": EMPLOYEE_ID,
        "changed_at": NOW,
        "changed_by_app_user_id": None,
        "change_type": "salary_change",
        "old_value": "9000.00",
        "new_value": "10000.00",
        "reason": "Synthetic adjustment",
    }
    connection = RecordingConnection([[history_row]])
    service = EmployeeService(
        cast(AsyncConnection, connection), EmployeeCursorCodec(b"0" * 32, clock=lambda: NOW)
    )
    items, cursor = await service.list_job_history(
        principal(AppRole.ADMIN),
        BRANCH_ID,
        JobHistoryQuery(
            limit=50,
            employee_id=EMPLOYEE_ID,
            change_type="salary_change",
            changed_from=NOW - timedelta(days=1),
            changed_to=NOW + timedelta(days=1),
            descending=True,
            cursor=None,
        ),
    )
    assert cursor is None
    assert items[0].changed_at == NOW
    query = str(
        connection.statements[0].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "employee_job_history.company_id = '3afbf0a0-9642-4d44-9884-e9654983eb9b'" in query
    assert "employee_job_history.branch_id = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'" in query
    assert "ORDER BY employee_job_history.changed_at DESC, employee_job_history.id ASC" in query
