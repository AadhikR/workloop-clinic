import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import AppRole
from app.schemas.employees import EmployeeProfileSaveRequest
from app.services.employees import EmployeeCursorCodec, EmployeeService
from app.services.execution import ServiceExecutionError
from app.services.letter_requests import LetterRequestService
from tests.test_employee_service import BRANCH_ID as EMPLOYEE_BRANCH_ID
from tests.test_employee_service import employee_row
from tests.test_employee_service import principal as employee_principal
from tests.test_organization_api import BRANCH_ID, principal

REQUEST_ID = uuid.UUID("b2000000-0000-4000-8000-000000000091")


@pytest.mark.asyncio
async def test_custom_request_cannot_produce_standard_letter_source() -> None:
    service = LetterRequestService(cast(AsyncConnection, object()))

    async def custom_row(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"status": "completed", "completed_at": object(), "request_kind": "custom"}

    service._get_row = custom_row  # type: ignore[method-assign]
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await service.print_source(principal(AppRole.EMPLOYEE), BRANCH_ID, REQUEST_ID)


def test_manager_is_an_authorized_self_letter_output_role() -> None:
    from app.rendered_output_api import _branch  # pyright: ignore[reportPrivateUsage]

    class Headers:
        def getlist(self, _name: str) -> list[str]:
            return []

    request = cast(Any, SimpleNamespace(headers=Headers()))
    manager = employee_principal(AppRole.MANAGER)
    assert _branch(request, manager) == EMPLOYEE_BRANCH_ID


def test_profile_save_route_is_published_as_an_idempotent_command() -> None:
    from app.main import create_app

    operation = create_app().openapi()["paths"]["/api/v1/employees/{employee_id}/profile-save"]
    assert set(operation) == {"post"}
    assert operation["post"]["operationId"] == "save_employee_profile"


@pytest.mark.asyncio
async def test_profile_save_updates_protected_fields_once_with_history_and_audit() -> None:
    current = employee_row()
    updated: dict[str, Any] = {
        **current,
        "updated_at": datetime(2026, 9, 10, 12, 31, tzinfo=UTC),
    }

    class Repository:
        def __init__(self) -> None:
            self.histories: list[str] = []
            self.updates: list[dict[str, object]] = []
            self.audits: list[str] = []

        async def acquire_relationship_locks(self, _ids: set[uuid.UUID]) -> None:
            return None

        async def assert_employee_exists(self, **_kwargs: object) -> None:
            return None

        async def lock_employee_set(self, **_kwargs: object) -> dict[uuid.UUID, dict[str, object]]:
            return {cast(uuid.UUID, current["id"]): current}

        async def lock_department(self, **_kwargs: object) -> dict[str, object]:
            return {"name": "Operations"}

        async def append_job_history(self, **kwargs: object) -> None:
            self.histories.append(cast(str, kwargs["change_type"]))

        async def update_workflow_employee(self, **kwargs: object) -> dict[str, object]:
            guarded = cast(Any, kwargs["values"])
            values: dict[str, object] = {
                str(key): cast(object, value) for key, value in guarded.items()
            }
            self.updates.append(values)
            updated.update(values)
            return updated

        async def append_employee_audit(self, **kwargs: object) -> None:
            self.audits.append(cast(str, kwargs["action"]))

    repository = Repository()
    service = EmployeeService(cast(AsyncConnection, object()), EmployeeCursorCodec(b"0" * 32))
    service._repository = cast(object, repository)  # type: ignore[assignment]
    expected = "2026-09-10T12:30:45.123Z"
    request = EmployeeProfileSaveRequest.model_validate(
        {
            "expectedUpdatedAt": expected,
            "reason": "Annual profile review",
            "profile": {"expectedUpdatedAt": expected, "name": "Updated Employee"},
            "jobTitle": "Senior Nurse",
            "department": "Operations",
            "reportingManagerId": None,
            "basicSalary": "11000.00",
            "allowance": "300.00",
            "housingAllowance": "1200.00",
            "transportAllowance": "600.00",
            "otherAllowances": "100.00",
            "otherAllowancesLabel": "Clinical allowance",
        }
    )

    result = await service.save_profile(
        employee_principal(AppRole.ADMIN),
        EMPLOYEE_BRANCH_ID,
        cast(uuid.UUID, current["id"]),
        request,
    )

    assert result.name == "Updated Employee"
    assert len(repository.updates) == 1
    assert repository.updates[0]["basic_salary"] == Decimal("11000.00")
    assert repository.histories == ["title_change", "department_change", "salary_change"]
    assert repository.audits == ["employee_manager_changed"]
