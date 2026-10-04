from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import AppRole
from app.schemas.organization import BranchUpdateRequest
from app.services.execution import ServiceExecutionError
from app.services.organization import OrganizationService
from tests.test_organization_api import BRANCH_ID, OTHER_BRANCH_ID, client_for
from tests.test_organization_service import RecordingConnection, cursor_codec, principal


def test_routing_command_requires_unique_complete_source_versions() -> None:
    from app.schemas.routing import RoutingChangeRequest

    value = {
        "expectedUpdatedAt": "2026-10-05T08:00:00.000Z",
        "routingCode": "123456789",
        "drafts": [
            {
                "id": "d4000000-0000-4000-8000-000000000001",
                "expectedUpdatedAt": "2026-10-05T08:00:00.000Z",
                "sourceDigest": "a" * 64,
            }
        ],
    }
    assert RoutingChangeRequest.model_validate(value).routing_code == "123456789"
    with pytest.raises(ValidationError):
        RoutingChangeRequest.model_validate({**value, "drafts": value["drafts"] * 2})
    with pytest.raises(ValidationError):
        RoutingChangeRequest.model_validate({**value, "routingCode": "bad"})


def test_routing_authority_locks_and_checks_before_writing() -> None:
    source = next(Path("alembic/versions").glob("f1a3c5e7b9d2*")).read_text()
    assert source.index("FOR UPDATE;") < source.index("UPDATE public.branches")
    assert "draft set changed" in source
    assert "source_snapshot_digest" in source
    assert "approval_status<>'draft'" in source
    assert "payroll_routing_changed" in source
    assert "REVOKE ALL" in source


def test_routing_command_has_scoped_preview_and_idempotent_write() -> None:
    from app.main import create_app

    paths = create_app().openapi()["paths"]
    command = paths["/api/v1/branches/{branch_id}/payroll-routing"]
    assert command["post"]["operationId"] == "change_branch_payroll_routing"
    assert command["get"]["operationId"] == "read_branch_payroll_routing"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_staff_cannot_read_or_write_routing(role: AppRole) -> None:
    async with client_for(role) as (client, _app, _service, executor):
        path = f"/api/v1/branches/{BRANCH_ID}/payroll-routing"
        headers = {"X-Workloop-Branch-ID": str(BRANCH_ID)}
        read = await client.get(path, headers=headers)
        write = await client.post(
            path,
            headers={**headers, "Origin": "http://localhost:5173"},
            json={
                "expectedUpdatedAt": "2026-10-05T08:00:00.000Z",
                "routingCode": "123456789",
                "drafts": [],
            },
        )
    assert read.status_code == write.status_code == 403
    assert executor.selected == []


@pytest.mark.asyncio
async def test_routing_requires_matching_selected_branch_before_execution() -> None:
    async with client_for(AppRole.ADMIN) as (client, _app, _service, executor):
        result = await client.get(
            f"/api/v1/branches/{BRANCH_ID}/payroll-routing",
            headers={"X-Workloop-Branch-ID": str(OTHER_BRANCH_ID)},
        )
    assert result.status_code == 404
    assert executor.selected == []


@pytest.mark.asyncio
async def test_ordinary_branch_update_cannot_bypass_routing_command() -> None:
    connection = RecordingConnection([])
    service = OrganizationService(cast(AsyncConnection, connection), cursor_codec())
    body = BranchUpdateRequest.model_validate(
        {"expectedUpdatedAt": "2026-10-05T08:00:00.000Z", "defaultBankRoutingCode": "123456789"}
    )
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await service.update_branch(principal(AppRole.ADMIN), BRANCH_ID, body)
    assert connection.statements == []
