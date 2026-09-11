import uuid
from datetime import UTC, date, datetime
from typing import cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.repositories.departments import DepartmentRepository
from app.schemas.departments import (
    DepartmentCreateRequest,
    DepartmentDeleteRequest,
    DepartmentSnapshot,
    DepartmentUpdateRequest,
    StaffingRuleCreateRequest,
    StaffingRuleSnapshot,
    StaffingRuleUpdateRequest,
)
from app.services.departments import DepartmentService, validate_department_hierarchy
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError

COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
DEPARTMENT_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698d1")
PARENT_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698d2")
EMPLOYEE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698e1")
RULE_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698f1")
NOW = datetime(2026, 9, 11, 8, tzinfo=UTC)


def principal(role: AppRole = AppRole.ADMIN) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=None,
        branch_id=None,
    )


def department_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": DEPARTMENT_ID,
        "name": "Clinical",
        "parent_id": None,
        "head_employee_id": None,
        "color": "#6366f1",
        "description": "Patient care",
        "sort_order": 1,
        "created_at": NOW,
    }
    row.update(changes)
    return row


def snapshot(**changes: object) -> DepartmentSnapshot:
    values: dict[str, object] = {
        "name": "Clinical",
        "parentId": None,
        "headEmployeeId": None,
        "color": "#6366f1",
        "description": "Patient care",
        "sortOrder": 1,
    }
    values.update(changes)
    return DepartmentSnapshot.model_validate(values)


class FakeRepository:
    def __init__(self) -> None:
        self.hierarchy: list[dict[str, object]] = [department_row()]
        self.head: dict[str, object] = {
            "id": EMPLOYEE_ID,
            "active": True,
            "employment_status": "Active",
        }
        self.rename: tuple[str, str] | None = None
        self.deleted = True
        self.rule: dict[str, object] = {
            "id": RULE_ID,
            "department": "Clinical",
            "shift_category": "morning",
            "min_staff": 2,
            "effective_from": date(2026, 9, 1),
            "effective_to": None,
        }

    async def lock_hierarchy(
        self, _company_id: uuid.UUID, _branch_id: uuid.UUID
    ) -> list[dict[str, object]]:
        return self.hierarchy

    async def fetch_head(self, *_values: object) -> dict[str, object]:
        return self.head

    async def create_department(self, **values: object) -> dict[str, object]:
        return department_row(**cast(dict[str, object], values["values"]))

    async def update_department(self, **values: object) -> dict[str, object]:
        return department_row(**cast(dict[str, object], values["changes"]))

    async def rename_dependents(self, **values: object) -> None:
        self.rename = cast(str, values["old_name"]), cast(str, values["new_name"])

    async def delete_guarded_department(self, **_values: object) -> bool:
        return self.deleted

    async def fetch_staffing_rule(self, *_values: object, **_options: object) -> dict[str, object]:
        return self.rule

    async def create_staffing_rule(self, **values: object) -> dict[str, object]:
        row: dict[str, object] = {"id": RULE_ID, **cast(dict[str, object], values["values"])}
        return row

    async def update_staffing_rule(self, **values: object) -> dict[str, object]:
        row: dict[str, object] = {
            **self.rule,
            **cast(dict[str, object], values["changes"]),
        }
        return row

    async def delete_staffing_rule(self, **_values: object) -> None:
        return None


def service() -> tuple[DepartmentService, FakeRepository]:
    repository = FakeRepository()
    active = DepartmentService(
        cast(AsyncConnection, object()),
        EmployeeCursorCodec(b"0" * 32),
        cast(DepartmentRepository, repository),
    )
    return active, repository


def test_hierarchy_rejects_cycles_and_more_than_twenty_levels() -> None:
    with pytest.raises(ServiceExecutionError, match="department_conflict"):
        validate_department_hierarchy(
            [
                {"id": DEPARTMENT_ID, "parent_id": PARENT_ID},
                {"id": PARENT_ID, "parent_id": DEPARTMENT_ID},
            ]
        )
    chain = [
        {"id": uuid.UUID(int=index + 1), "parent_id": uuid.UUID(int=index) if index else None}
        for index in range(21)
    ]
    with pytest.raises(ServiceExecutionError, match="department_conflict"):
        validate_department_hierarchy(chain)


@pytest.mark.asyncio
async def test_department_create_checks_parent_head_and_exact_name() -> None:
    active, repository = service()
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await active.create_department(
            principal(),
            BRANCH_ID,
            DepartmentCreateRequest.model_validate({"name": "Support", "parentId": PARENT_ID}),
        )
    with pytest.raises(ServiceExecutionError, match="department_conflict"):
        await active.create_department(
            principal(), BRANCH_ID, DepartmentCreateRequest(name="Clinical")
        )
    repository.head["active"] = False
    with pytest.raises(ServiceExecutionError, match="department_conflict"):
        await active.create_department(
            principal(),
            BRANCH_ID,
            DepartmentCreateRequest.model_validate(
                {"name": "Support", "headEmployeeId": EMPLOYEE_ID}
            ),
        )


@pytest.mark.asyncio
async def test_department_rename_uses_snapshot_and_cascade() -> None:
    active, repository = service()
    request = DepartmentUpdateRequest(expected=snapshot(), name="Care")
    updated = await active.update_department(principal(), BRANCH_ID, DEPARTMENT_ID, request)
    assert updated.name == "Care"
    assert repository.rename == ("Clinical", "Care")

    stale = DepartmentUpdateRequest(expected=snapshot(description="old"), color="#ffffff")
    with pytest.raises(ServiceExecutionError, match="state_conflict"):
        await active.update_department(principal(), BRANCH_ID, DEPARTMENT_ID, stale)


@pytest.mark.asyncio
async def test_department_delete_guards_head_and_retained_use() -> None:
    active, repository = service()
    repository.hierarchy = [department_row(head_employee_id=EMPLOYEE_ID)]
    request = DepartmentDeleteRequest(expected=snapshot(headEmployeeId=EMPLOYEE_ID))
    with pytest.raises(ServiceExecutionError, match="department_conflict"):
        await active.delete_department(principal(), BRANCH_ID, DEPARTMENT_ID, request)

    repository.hierarchy = [department_row()]
    repository.deleted = False
    with pytest.raises(ServiceExecutionError, match="department_conflict"):
        await active.delete_department(
            principal(), BRANCH_ID, DEPARTMENT_ID, DepartmentDeleteRequest(expected=snapshot())
        )


@pytest.mark.asyncio
async def test_staffing_rule_checks_department_snapshot_and_dates() -> None:
    active, _repository = service()
    created = await active.create_staffing_rule(
        principal(),
        BRANCH_ID,
        StaffingRuleCreateRequest.model_validate(
            {"department": "Clinical", "shiftCategory": "morning", "minStaff": 2}
        ),
    )
    assert created.min_staff == 2

    expected = StaffingRuleSnapshot.model_validate(
        {
            "department": "Clinical",
            "shiftCategory": "morning",
            "minStaff": 2,
            "effectiveFrom": date(2026, 9, 1),
            "effectiveTo": None,
        }
    )
    updated = await active.update_staffing_rule(
        principal(),
        BRANCH_ID,
        RULE_ID,
        StaffingRuleUpdateRequest.model_validate({"expected": expected, "minStaff": 3}),
    )
    assert updated.min_staff == 3
    with pytest.raises(ValidationError):
        StaffingRuleCreateRequest.model_validate(
            {
                "department": "Clinical",
                "shiftCategory": "morning",
                "minStaff": 2,
                "effectiveFrom": date(2026, 9, 2),
                "effectiveTo": date(2026, 9, 1),
            }
        )
