import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from app.asset_api import list_assets
from app.models.identity import AppRole
from app.schemas.assets import AssetAssignRequest, AssetHistoryResponse, AssetReturnRequest
from app.schemas.development import CertificationUpdateRequest
from app.services.assets import AssetListQuery, AssetService
from app.services.development import DevelopmentService
from app.services.execution import ServiceExecutionError
from tests.test_organization_api import BRANCH_ID, COMPANY_ID, NOW, client_for, principal

EMPLOYEE_ID = uuid.UUID("b2000000-0000-4000-8000-000000000003")
ASSET_ID = uuid.UUID("b2000000-0000-4000-8000-000000000020")
ASSIGNMENT_ID = uuid.UUID("b2000000-0000-4000-8000-000000000021")


class Result:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def mappings(self) -> "Result":
        return self

    def all(self) -> list[Any]:
        return self.rows

    def one_or_none(self) -> Any:
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self) -> Any:
        return self.rows[0] if self.rows else None

    def scalar_one(self) -> Any:
        return self.rows[0]


class Connection:
    def __init__(self, rows: list[list[Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute(self, sql: object, params: dict[str, object] | None = None) -> Result:
        self.calls.append((str(sql), params or {}))
        return Result(self.rows.pop(0))


def history() -> dict[str, object]:
    return {
        "id": ASSIGNMENT_ID,
        "asset_id": ASSET_ID,
        "employee_id": EMPLOYEE_ID,
        "employee_name": "Alex Morgan",
        "asset_name": "Clinic laptop",
        "asset_code": "IT-001",
        "status": "assigned",
        "assigned_date": date(2026, 9, 1),
        "return_date": None,
        "condition_at_handover": "good",
        "condition_at_return": None,
        "notes": "",
        "created_at": NOW,
    }


@pytest.mark.asyncio
async def test_history_query_scopes_employee_and_asset_joins_and_keyset() -> None:
    connection = Connection([[history()]])
    result = await AssetService(cast(AsyncConnection, connection)).list_history(
        principal(AppRole.ADMIN), BRANCH_ID, ASSET_ID, 2, date(2026, 9, 2), ASSIGNMENT_ID
    )
    sql, params = connection.calls[0]
    assert "asset.company_id=assignment.company_id" in sql
    assert "employee.branch_id=assignment.branch_id" in sql
    assert "(assignment.assigned_date,assignment.id)<(:after_date,:after_id)" in sql
    assert params == {
        "company_id": COMPANY_ID,
        "branch_id": BRANCH_ID,
        "asset_id": ASSET_ID,
        "limit": 2,
        "after_date": date(2026, 9, 2),
        "after_id": ASSIGNMENT_ID,
    }
    assert result[0].employee_name == "Alex Morgan"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_history_and_cme_services_reject_staff_before_query(role: AppRole) -> None:
    connection = Connection([])
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await AssetService(cast(AsyncConnection, connection)).list_history(
            principal(role), BRANCH_ID, None, 100
        )
    development = DevelopmentService(
        cast(AsyncConnection, connection), scanner_definition="test", object_key_hmac_key=b"x" * 32
    )
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await development.branch_cme(principal(role), BRANCH_ID, 2026, 100, None)
    assert not connection.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_branch_history_and_cme_routes_deny_staff(role: AppRole) -> None:
    async with client_for(role) as (client, _app, _service, executor):
        for path in ("/api/v1/assets/assignments", "/api/v1/cme/summary?year=2026"):
            response = await client.get(path, headers={"X-Workloop-Branch-ID": str(BRANCH_ID)})
            assert response.status_code == 403
        assert not executor.selected


@pytest.mark.asyncio
async def test_history_route_requires_branch_and_valid_cursor() -> None:
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        missing = await client.get("/api/v1/assets/assignments")
        assert missing.status_code == 400
        for cursor in ("not-a-cursor", f"20260901:{ASSIGNMENT_ID}", "2026-09-01:bad-id"):
            response = await client.get(
                "/api/v1/assets/assignments",
                params={"cursor": cursor},
                headers={"X-Workloop-Branch-ID": str(BRANCH_ID)},
            )
            assert response.status_code == 422
        assert not executor.selected


@pytest.mark.asyncio
async def test_history_route_returns_real_has_more_and_next_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [AssetHistoryResponse.model_validate(history())] * 2

    async def history_list(self: AssetService, *args: object) -> list[AssetHistoryResponse]:
        assert args[3] == 2
        return rows

    monkeypatch.setattr(AssetService, "list_history", history_list)
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        response = await client.get(
            "/api/v1/assets/assignments?limit=1", headers={"X-Workloop-Branch-ID": str(BRANCH_ID)}
        )
        assert response.status_code == 200
        assert response.json()["page"] == {
            "limit": 1,
            "hasMore": True,
            "nextCursor": f"2026-09-01:{ASSIGNMENT_ID}",
        }
        assert len(response.json()["data"]) == 1
        assert executor.selected == [BRANCH_ID]


@pytest.mark.asyncio
async def test_asset_inventory_query_applies_cursor_without_truncation() -> None:
    connection = Connection([[]])
    await AssetService(cast(AsyncConnection, connection)).list(
        principal(AppRole.ADMIN), BRANCH_ID, AssetListQuery(None, None, None, 101, ASSET_ID)
    )
    sql, params = connection.calls[0]
    assert "id>:after_id" in sql and "ORDER BY id ASC" in sql
    assert params["after_id"] == ASSET_ID and params["limit"] == 101
    assert "cursor" in list_assets.__annotations__


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["assign", "return_future", "return_before_assignment"])
async def test_custody_dates_reject_invalid_dates_before_writing(kind: str) -> None:
    locked = SimpleNamespace(
        id=ASSET_ID, status="available" if kind == "assign" else "assigned", updated_at=NOW
    )
    assignment = SimpleNamespace(id=ASSIGNMENT_ID, assigned_date=date(2026, 9, 1))
    connection = Connection(
        [[locked], [EMPLOYEE_ID if kind == "assign" else assignment], [date(2026, 9, 9)]]
    )
    service = AssetService(cast(AsyncConnection, connection))
    with pytest.raises(
        ServiceExecutionError,
        match="validation_failed" if kind != "return_before_assignment" else "state_conflict",
    ):
        if kind == "assign":
            await service.assign(
                principal(AppRole.ADMIN),
                BRANCH_ID,
                ASSET_ID,
                AssetAssignRequest(
                    employee_id=EMPLOYEE_ID,
                    assigned_date=date(2026, 9, 10),
                    expected_updated_at=NOW,
                ),
            )
        else:
            await service.return_asset(
                principal(AppRole.ADMIN),
                BRANCH_ID,
                ASSET_ID,
                AssetReturnRequest(
                    return_date=date(2026, 9, 10) if kind == "return_future" else date(2026, 8, 31),
                    condition_at_return="good",
                    expected_updated_at=NOW,
                ),
            )
    assert not any(
        sql.lstrip().startswith(("UPDATE", "INSERT")) for sql, _params in connection.calls
    )


@pytest.mark.asyncio
async def test_cme_aggregate_preserves_scans_scope_and_authoritative_values() -> None:
    row = {
        "employee_id": EMPLOYEE_ID,
        "employee_name": "Alex Morgan",
        "department": "Clinical",
        "requirement_id": None,
        "required_hours": None,
        "notes": None,
        "created_at": None,
        "updated_at": None,
        "achieved": Decimal("12.50"),
        "in_progress": Decimal("4.25"),
    }
    connection = Connection([[row]])
    result = await DevelopmentService(
        cast(AsyncConnection, connection), scanner_definition="test", object_key_hmac_key=b"x" * 32
    ).branch_cme(principal(AppRole.ADMIN), BRANCH_ID, 2026, 101, EMPLOYEE_ID)
    sql, params = connection.calls[0]
    assert "file_security_scan_allows_download" in sql
    assert "record.status='completed' AND record.passed" in sql
    assert "record.company_id=employee.company_id" in sql
    assert params["company_id"] == COMPANY_ID and params["branch_id"] == BRANCH_ID
    assert result[0].model_dump(mode="json", by_alias=True)["achievedHours"] == "12.5"
    assert result[0].requirement is None


def test_certification_edit_cannot_change_scope_review_or_evidence_fields() -> None:
    values = {
        "certificationName": "Updated title",
        "issuingBody": "Synthetic issuer",
        "expectedUpdatedAt": NOW,
    }
    assert CertificationUpdateRequest.model_validate(values).certification_name == "Updated title"
    for key in ("employeeId", "status", "reviewedAt", "storagePath", "companyId"):
        with pytest.raises(ValueError):
            CertificationUpdateRequest.model_validate({**values, key: "forged"})


@pytest.mark.asyncio
async def test_assignment_date_cannot_overlap_retained_custody() -> None:
    locked = SimpleNamespace(id=ASSET_ID, status="available", updated_at=NOW)
    connection = Connection([[locked], [EMPLOYEE_ID], [date(2026, 9, 9)], [date(2026, 9, 8)]])
    with pytest.raises(ServiceExecutionError, match="state_conflict"):
        await AssetService(cast(AsyncConnection, connection)).assign(
            principal(AppRole.ADMIN),
            BRANCH_ID,
            ASSET_ID,
            AssetAssignRequest(
                employee_id=EMPLOYEE_ID, assigned_date=date(2026, 9, 7), expected_updated_at=NOW
            ),
        )
    assert len(connection.calls) == 4


def certification_row() -> dict[str, object]:
    return {
        "id": ASSIGNMENT_ID,
        "employee_id": EMPLOYEE_ID,
        "certification_name": "Basic life support",
        "issuing_body": "Synthetic issuer",
        "certificate_no": "BLS001",
        "issued_date": None,
        "expiry_date": None,
        "notes": "",
        "status": "verified",
        "has_evidence": False,
        "file_name": None,
        "content_type": None,
        "reviewed_at": NOW,
        "created_at": NOW,
        "updated_at": NOW,
    }


@pytest.mark.asyncio
async def test_certification_edit_locks_scopes_audits_and_resubmits() -> None:
    updated = {
        **certification_row(),
        "status": "pending_review",
        "reviewed_at": None,
        "certification_name": "Advanced life support",
    }
    connection = Connection(
        [
            [certification_row()],
            [EMPLOYEE_ID],
            [],
            [ASSIGNMENT_ID],
            [updated],
            [EMPLOYEE_ID],
        ]
    )
    response = await DevelopmentService(
        cast(AsyncConnection, connection), scanner_definition="test", object_key_hmac_key=b"x" * 32
    ).update_certification(
        principal(AppRole.ADMIN),
        BRANCH_ID,
        ASSIGNMENT_ID,
        CertificationUpdateRequest(
            certification_name="Advanced life support",
            issuing_body="Synthetic issuer",
            expected_updated_at=NOW,
        ),
        scope="admin",
    )
    assert response.status == "pending_review" and response.reviewed_at is None
    assert "FOR UPDATE" in connection.calls[0][0]
    assert "company_id=:company_id AND branch_id=:branch_id" in connection.calls[2][0]
    assert "status='pending_review',reviewed_at=NULL" in connection.calls[2][0]
    assert connection.calls[3][1]["action"] == "certification_submitted"
    assert connection.calls[3][1]["reason"] == "Certification edited and resubmitted for review"


@pytest.mark.asyncio
async def test_certification_edit_denies_employee_access_to_another_employee() -> None:
    connection = Connection([[certification_row()]])
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await DevelopmentService(
            cast(AsyncConnection, connection),
            scanner_definition="test",
            object_key_hmac_key=b"x" * 32,
        ).update_certification(
            principal(AppRole.EMPLOYEE),
            BRANCH_ID,
            ASSIGNMENT_ID,
            CertificationUpdateRequest(
                certification_name="Changed", issuing_body="Issuer", expected_updated_at=NOW
            ),
            scope="staff",
        )
    assert len(connection.calls) == 1
