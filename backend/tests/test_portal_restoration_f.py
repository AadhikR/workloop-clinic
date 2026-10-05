from datetime import UTC, datetime, timedelta, timezone
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.http.pagination import uuid_page
from app.http.schemas import ApiSchema
from app.http.versions import same_instant
from app.models.identity import AppRole
from app.schemas.appraisals import AppraisalAdminReviewRequest, AppraisalManagerReviewRequest
from app.schemas.assets import AssetHistoryResponse
from app.schemas.employment_contract import ContractCurrentResponse
from app.services.assets import AssetService
from app.services.development import CertificationListQuery, DevelopmentService, TrainingListQuery
from app.services.employment_contracts import EmploymentContractService
from app.services.incidents import IncidentListQuery, IncidentService
from app.services.insurance import InsuranceService
from tests.test_organization_api import BRANCH_ID, client_for, principal
from tests.test_portal_restoration_a import ASSET_ID, Connection, history


def test_wire_versions_keep_millisecond_precision_and_require_a_timezone() -> None:
    source = datetime(2026, 10, 5, 10, 0, 0, 123987, UTC)
    wire = datetime(2026, 10, 5, 10, 0, 0, 123000, UTC)
    assert same_instant(source, wire)
    assert same_instant(source, wire.astimezone(timezone(timedelta(hours=4))))
    assert not same_instant(source, wire + timedelta(milliseconds=1))
    assert not same_instant(source, wire.replace(tzinfo=None))
    assert not same_instant(source, wire.isoformat())


def test_complete_admin_review_rejects_duplicate_sections_and_authority_fields() -> None:
    section = {"id": str(ASSET_ID), "rating": "4.0", "comments": "Synthetic review"}
    body = {
        "expectedUpdatedAt": "2026-10-05T10:00:00.123Z",
        "sections": [section],
        "reviewerComments": "Reviewed",
        "developmentPlan": "Continue training",
    }
    assert AppraisalAdminReviewRequest.model_validate(body).sections[0].rating == 4
    for changed in [
        {**body, "sections": [section, section]},
        {**body, "sections": []},
        {**body, "sections": [{**section, "rating": "4.01"}]},
        {**body, "sections": [{**section, "rating": "5.1"}]},
        {**body, "reviewedByAppUserId": str(ASSET_ID)},
        {**body, "sections": [{**section, "appraisalId": str(ASSET_ID)}]},
    ]:
        with pytest.raises(ValidationError):
            AppraisalAdminReviewRequest.model_validate(changed)


def test_uuid_page_uses_extra_row_and_keeps_terminal_page_complete() -> None:
    rows = [AssetHistoryResponse.model_validate(history()) for _ in range(3)]
    result = uuid_page(rows, 2)
    assert len(result.data) == 2
    assert result.page.has_more and result.page.next_cursor == str(rows[1].id)
    terminal = uuid_page(rows[:2], 2)
    assert len(terminal.data) == 2
    assert not terminal.page.has_more and terminal.page.next_cursor is None
    assert not uuid_page([], 2).page.has_more


def test_manager_review_rejects_administrator_and_derived_fields() -> None:
    body = {
        "expectedUpdatedAt": "2026-10-05T10:00:00.123Z",
        "sections": [{"id": str(ASSET_ID), "rating": "4.0", "comments": "Synthetic review"}],
    }
    assert AppraisalManagerReviewRequest.model_validate(body).sections[0].rating == 4
    for key in ["reviewedByAppUserId", "overallRating", "calibratedRating", "reviewerComments"]:
        with pytest.raises(ValidationError):
            AppraisalManagerReviewRequest.model_validate({**body, key: "Synthetic authority"})


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.ADMIN, AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_record_editor_reads_require_administrator_branch_scope(
    role: AppRole, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[object, ...]] = []

    async def current(_self: object, *args: object) -> ContractCurrentResponse:
        calls.append(args)
        return ContractCurrentResponse(
            employee_updated_at=datetime(2026, 10, 5, 10, 0, 0, 123987, UTC),
            current_contract_type="Unlimited",
            current_contract_end_date=None,
            latest_contract_event_id=None,
        )

    async def coverage(_self: object, *args: object) -> None:
        calls.append(args)

    monkeypatch.setattr(EmploymentContractService, "current", current)
    monkeypatch.setattr(InsuranceService, "read_coverage", coverage)
    async with client_for(role) as (client, _app, _service, _executor):
        headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
        contract = await client.get(
            f"/api/v1/employees/{ASSET_ID}/contracts/current", headers=headers
        )
        insurance = await client.get(
            f"/api/v1/insurance/employees/{ASSET_ID}/coverage", headers=headers
        )
        if role is AppRole.ADMIN:
            assert contract.status_code == insurance.status_code == 200
            assert contract.json()["data"] == {
                "employeeUpdatedAt": "2026-10-05T10:00:00.123Z",
                "currentContractType": "Unlimited",
                "currentContractEndDate": None,
                "latestContractEventId": None,
            }
            assert insurance.json()["data"] is None
            assert all(call[1:] == (BRANCH_ID, ASSET_ID) for call in calls)
            assert (
                await client.get(f"/api/v1/employees/{ASSET_ID}/contracts/current")
            ).status_code == 400
        else:
            assert contract.status_code == insurance.status_code == 403
            assert calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "role", "service", "method"),
    [
        ("training-records", AppRole.ADMIN, DevelopmentService, "list_training"),
        ("training-records/self", AppRole.EMPLOYEE, DevelopmentService, "list_training"),
        (
            "training-records/direct-reports?employeeId=",
            AppRole.MANAGER,
            DevelopmentService,
            "list_training",
        ),
        ("certifications", AppRole.ADMIN, DevelopmentService, "list_certifications"),
        ("certifications/self", AppRole.EMPLOYEE, DevelopmentService, "list_certifications"),
        (
            "certifications/direct-reports?employeeId=",
            AppRole.MANAGER,
            DevelopmentService,
            "list_certifications",
        ),
        ("clinical-incidents", AppRole.ADMIN, IncidentService, "list"),
    ],
)
async def test_collection_routes_request_lookahead_and_validate_cursor(
    path: str,
    role: AppRole,
    service: type[object],
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    async def read(_self: object, *args: object, **kwargs: object) -> list[ApiSchema]:
        calls.append(args[2])
        return []

    monkeypatch.setattr(service, method, read)
    if service is DevelopmentService:

        def factory(request: object, connection: AsyncConnection) -> DevelopmentService:
            return DevelopmentService(connection, scanner_definition="test")

        monkeypatch.setattr(
            "app.development_api._service",
            factory,
        )
    parameters = {"limit": "1", "cursor": str(ASSET_ID)}
    if path.endswith("="):
        path = path.split("?", 1)[0]
        parameters["employeeId"] = str(ASSET_ID)
    async with client_for(role) as (client, _app, _service, _executor):
        headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)} if role is AppRole.ADMIN else {}
        response = await client.get(
            f"/api/v1/{path}",
            params=parameters,
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["page"] == {"limit": 1, "nextCursor": None, "hasMore": False}
        query = cast(TrainingListQuery | CertificationListQuery | IncidentListQuery, calls[-1])
        assert query.limit == 2 and query.after_id == ASSET_ID
        response = await client.get(f"/api/v1/{path}", params={"cursor": "bad"}, headers=headers)
        assert response.status_code == 422
        assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["training", "certifications", "incidents", "self_assets"])
async def test_collection_keysets_preserve_scope_and_use_immutable_identity(kind: str) -> None:
    connection = Connection([[]])
    development = DevelopmentService(cast(AsyncConnection, connection), scanner_definition="test")
    actor = principal(AppRole.EMPLOYEE if kind == "self_assets" else AppRole.ADMIN)
    if kind == "training":
        await development.list_training(
            actor,
            BRANCH_ID,
            TrainingListQuery(None, None, None, None, None, 101, ASSET_ID),
            scope="admin",
        )
    elif kind == "certifications":
        await development.list_certifications(
            actor,
            BRANCH_ID,
            CertificationListQuery(None, None, 101, ASSET_ID),
            scope="admin",
        )
    elif kind == "incidents":
        await IncidentService(cast(AsyncConnection, connection)).list(
            actor,
            BRANCH_ID,
            IncidentListQuery(None, None, None, None, None, 101, ASSET_ID),
        )
    else:
        await AssetService(cast(AsyncConnection, connection)).list_self(
            actor,
            BRANCH_ID,
            101,
            ASSET_ID,
        )
    sql, params = connection.calls[-1]
    sql = " ".join(sql.split())
    assert "company_id=:company_id" in sql and "branch_id=:branch_id" in sql
    assert "id>:after_id" in sql and "id ASC LIMIT :limit" in sql
    assert params["after_id"] == ASSET_ID and params["limit"] == 101
