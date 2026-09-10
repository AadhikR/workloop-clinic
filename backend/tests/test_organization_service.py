import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.repositories.organization import OrganizationRepository
from app.schemas.organization import BranchCreateRequest
from app.services.execution import ServiceExecutionError
from app.services.organization import (
    BranchCursorCodec,
    BranchListQuery,
    OrganizationService,
    normalize_search,
)

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
NOW = datetime(2026, 9, 9, 12, 30, 45, 123000, tzinfo=UTC)


def cursor_codec(now: datetime = NOW) -> BranchCursorCodec:
    return BranchCursorCodec(b"0" * 32, clock=lambda: now)


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


class MappingResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> "MappingResult":
        return self

    def one_or_none(self) -> dict[str, Any] | None:
        assert len(self.rows) <= 1
        return self.rows[0] if self.rows else None

    def one(self) -> dict[str, Any]:
        assert len(self.rows) == 1
        return self.rows[0]

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def scalar_one_or_none(self) -> object | None:
        assert len(self.rows) <= 1
        if not self.rows:
            return None
        assert len(self.rows[0]) == 1
        return next(iter(self.rows[0].values()))


class RecordingConnection:
    def __init__(self, results: list[list[dict[str, Any]]]) -> None:
        self.results = results
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> MappingResult:
        self.statements.append(statement)
        return MappingResult(self.results.pop(0))


def company_row() -> dict[str, Any]:
    return {
        "id": COMPANY_ID,
        "name": "Horizon Clinic",
        "sector": "Healthcare",
        "nafis_quota_percent": Decimal("2.00"),
        "enable_nafis": True,
        "created_at": NOW,
        "updated_at": NOW,
    }


def branch_row(identifier: uuid.UUID = BRANCH_ID) -> dict[str, Any]:
    return {
        "id": identifier,
        "name": "Dubai",
        "mol_employer_id": "MOL-001",
        "default_bank_routing_code": "BANK-A",
        "address": "Synthetic address",
        "contact_email": "dubai@example.test",
        "default_salary_day": None,
        "work_location_type": "Mainland",
        "free_zone_name": "",
        "logo_url": "",
        "enable_staffing_rules": True,
        "enable_biometric_import": False,
        "created_at": NOW,
        "updated_at": NOW,
    }


def test_branch_create_values_use_database_column_names() -> None:
    values = BranchCreateRequest.model_validate({"name": "Dubai Annex"}).values()

    assert "mol_employer_id" in values
    assert "molEmployerId" not in values
    assert values["work_location_type"] == "Mainland"


@pytest.mark.asyncio
async def test_repository_compares_versions_at_the_public_millisecond_precision() -> None:
    stored = NOW.replace(microsecond=123789)
    connection = RecordingConnection([[{"updated_at": stored}], [company_row()]])
    repository = OrganizationRepository(cast(AsyncConnection, connection))

    updated = await repository.update_company(
        company_id=COMPANY_ID,
        expected_updated_at=NOW,
        changes={"name": "Horizon Clinic"},
    )

    assert updated["id"] == COMPANY_ID
    stale_connection = RecordingConnection([[{"updated_at": stored}]])
    stale_repository = OrganizationRepository(cast(AsyncConnection, stale_connection))
    with pytest.raises(ValueError, match="state conflict"):
        await stale_repository.update_company(
            company_id=COMPANY_ID,
            expected_updated_at=NOW.replace(microsecond=124000),
            changes={"name": "Horizon Clinic"},
        )


@pytest.mark.asyncio
async def test_repository_repeats_tenant_and_branch_scope_in_every_statement() -> None:
    connection = RecordingConnection([[company_row()], [branch_row()], [branch_row()]])
    repository = OrganizationRepository(cast(AsyncConnection, connection))

    await repository.fetch_company(COMPANY_ID)
    await repository.fetch_branch(COMPANY_ID, BRANCH_ID)
    await repository.fetch_branches(
        company_id=COMPANY_ID,
        branch_id=BRANCH_ID,
        admin_projection=False,
        search="Dubai",
        sort=(("createdAt", True), ("name", False)),
        after=None,
        limit=50,
    )

    compiled = [
        str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        for statement in connection.statements
    ]
    assert "companies.id = '3afbf0a0-9642-4d44-9884-e9654983eb9b'" in compiled[0]
    assert "branches.company_id = '3afbf0a0-9642-4d44-9884-e9654983eb9b'" in compiled[1]
    assert "branches.id = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'" in compiled[1]
    assert "branches.company_id = '3afbf0a0-9642-4d44-9884-e9654983eb9b'" in compiled[2]
    assert "branches.id = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'" in compiled[2]
    assert "ORDER BY branches.created_at DESC, branches.name ASC, branches.id ASC" in compiled[2]
    assert "LIMIT 51" in compiled[2]
    assert " OFFSET " not in compiled[2]


@pytest.mark.asyncio
async def test_service_maps_admin_and_staff_projections_without_field_leakage() -> None:
    admin_connection = RecordingConnection([[company_row()], [branch_row()]])
    admin_service = OrganizationService(cast(AsyncConnection, admin_connection), cursor_codec())
    admin = principal(AppRole.ADMIN)
    company = await admin_service.get_company(admin)
    branches, cursor = await admin_service.list_branches(
        admin,
        BranchListQuery(limit=50, search=None, sort=(("name", False),), cursor=None),
    )

    assert company.nafis_quota_percent == "2.00"
    assert set(company.model_dump(by_alias=True)) == {
        "id",
        "name",
        "sector",
        "nafisQuotaPercent",
        "enableNafis",
        "createdAt",
        "updatedAt",
    }
    assert cursor is None
    assert "molEmployerId" in branches[0].model_dump(by_alias=True)

    employer_row = {
        "company_name": "Horizon Clinic",
        "branch_name": "Dubai",
        "branch_contact_email": "dubai@example.test",
        "branch_address": "Synthetic address",
        "work_location_type": "Mainland",
        "free_zone_name": "",
        "logo_url": "",
    }
    staff_connection = RecordingConnection([[employer_row], [branch_row()]])
    staff_service = OrganizationService(cast(AsyncConnection, staff_connection), cursor_codec())
    employee = principal(AppRole.EMPLOYEE)
    employer = await staff_service.get_employer(employee)
    safe_branches, _ = await staff_service.list_branches(
        employee,
        BranchListQuery(limit=50, search=None, sort=(("name", False),), cursor=None),
    )
    assert employer.company_name == "Horizon Clinic"
    assert set(safe_branches[0].model_dump(by_alias=True)) == {
        "id",
        "name",
        "address",
        "contactEmail",
        "workLocationType",
        "freeZoneName",
        "logoUrl",
    }


def test_branch_cursor_is_authenticated_and_scope_bound() -> None:
    codec = cursor_codec()
    admin = principal(AppRole.ADMIN)
    query = BranchListQuery(
        limit=1,
        search=normalize_search("  Du\u0301bai  "),
        sort=(("name", False),),
        cursor=None,
    )
    cursor = codec.encode(admin, query, cast(Any, branch_row()))
    resumed = BranchListQuery(
        limit=1,
        search=query.search,
        sort=query.sort,
        cursor=cursor,
    )
    assert codec.decode(admin, resumed) == BRANCH_ID
    assert "Dubai" not in cursor
    assert len(cursor) <= 512

    for changed in [
        BranchListQuery(limit=1, search="other", sort=query.sort, cursor=cursor),
        BranchListQuery(limit=1, search=query.search, sort=(("name", True),), cursor=cursor),
    ]:
        with pytest.raises(ValueError):
            codec.decode(admin, changed)
    with pytest.raises(ValueError):
        codec.decode(principal(AppRole.ADMIN), resumed)

    tampered = BranchListQuery(
        limit=1,
        search=query.search,
        sort=query.sort,
        cursor=(
            f"{cursor[: len(cursor) // 2]}"
            f"{'A' if cursor[len(cursor) // 2] != 'A' else 'B'}"
            f"{cursor[len(cursor) // 2 + 1 :]}"
        ),
    )
    with pytest.raises(ValueError):
        codec.decode(admin, tampered)

    expired_codec = cursor_codec(NOW + timedelta(minutes=16))
    with pytest.raises(ValueError):
        expired_codec.decode(admin, resumed)

    largest_filter = BranchListQuery(
        limit=100,
        search="𐍈" * 100,
        sort=(("createdAt", True), ("name", False)),
        cursor=None,
    )
    assert len(codec.encode(admin, largest_filter, cast(Any, branch_row()))) <= 512


@pytest.mark.asyncio
async def test_repository_uses_cursor_position_for_stable_pagination() -> None:
    connection = RecordingConnection([[branch_row()], [branch_row()]])
    repository = OrganizationRepository(cast(AsyncConnection, connection))
    position = await repository.fetch_branch_position(
        company_id=COMPANY_ID,
        branch_id=BRANCH_ID,
        cursor_branch_id=BRANCH_ID,
        sort=(("createdAt", True), ("name", False)),
    )
    await repository.fetch_branches(
        company_id=COMPANY_ID,
        branch_id=None,
        admin_projection=True,
        search=None,
        sort=(("createdAt", True), ("name", False)),
        after=(NOW, "Dubai", BRANCH_ID),
        limit=50,
    )

    assert position == (NOW, "Dubai", BRANCH_ID)
    position_query = str(
        connection.statements[0].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    page_query = str(
        connection.statements[1].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "branches.company_id = '3afbf0a0-9642-4d44-9884-e9654983eb9b'" in position_query
    assert position_query.count("branches.id = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'") == 2
    assert "branches.created_at < '2026-09-09 12:30:45.123000+00:00'" in page_query
    assert "branches.name > 'Dubai'" in page_query
    assert "branches.id > 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'" in page_query


@pytest.mark.asyncio
async def test_service_returns_generic_not_found_for_inaccessible_company() -> None:
    service = OrganizationService(cast(AsyncConnection, RecordingConnection([[]])), cursor_codec())
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await service.get_company(principal(AppRole.ADMIN))
