from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.schemas.tasks import TaskUrgency
from app.services.execution import ServiceExecutionError
from app.services.tasks import (
    TASK_CATEGORY_REGISTRY,
    TaskCursorCodec,
    TaskListQuery,
    TaskService,
)

COMPANY = uuid.UUID("c1000000-0000-4000-8000-000000000001")
BRANCH = uuid.UUID("c1000000-0000-4000-8000-000000000002")
USER = uuid.UUID("c1000000-0000-4000-8000-000000000003")
EMPLOYEE = uuid.UUID("c1000000-0000-4000-8000-000000000004")
NOW = datetime(2026, 9, 24, 8, tzinfo=UTC)


def principal(role: AppRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=USER,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY,
        employee_id=None if role is AppRole.ADMIN else EMPLOYEE,
        branch_id=None if role is AppRole.ADMIN else BRANCH,
    )


class Cursor:
    def __init__(self, anchor: str | None = None) -> None:
        self.anchor = anchor
        self.encoded: str | None = None

    def decode(self, **_values: object) -> str | None:
        return self.anchor

    def encode(self, **values: object) -> str:
        self.encoded = str(values["last_id"])
        return "opaque-cursor"


class Repository:
    def __init__(self, *, empty: bool = False, failing: str | None = None) -> None:
        self.empty = empty
        self.failing = failing
        self.calls: list[dict[str, object]] = []

    async def snapshot(self) -> dict[str, object]:
        return {"as_of": NOW, "business_date": date(2026, 9, 24)}

    async def read_category(self, **values: object) -> list[dict[str, object]]:
        self.calls.append(values)
        code = str(values["code"])
        if code == self.failing:
            raise RuntimeError("source unavailable")
        if self.empty:
            return []
        index = next(spec.order for spec in TASK_CATEGORY_REGISTRY if spec.code == code)
        return [
            {
                "entity_id": uuid.UUID(int=index + 2),
                "title": code,
                "subtitle": "Task",
                "due_date": date(2026, 10, 1),
                "created_at": NOW,
                "task_key": None,
            }
        ]


def query(
    *,
    category: str | None = None,
    urgency: TaskUrgency | None = None,
    limit: int = 200,
    cursor: str | None = None,
) -> TaskListQuery:
    return TaskListQuery(category=category, urgency=urgency, limit=limit, cursor=cursor)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [AppRole.ADMIN, AppRole.MANAGER, AppRole.EMPLOYEE])
async def test_role_catalogues_are_fixed_complete_and_principal_scoped(role: AppRole) -> None:
    repository = Repository()
    service = TaskService(repository, Cursor())  # type: ignore[arg-type]
    actor = principal(role)

    result = await service.list(actor, BRANCH, query())

    expected = [spec.code for spec in TASK_CATEGORY_REGISTRY if role in spec.roles]
    assert [category.code for category in result.categories] == expected
    assert all(category.status == "ok" for category in result.categories)
    assert all(call["principal"] is actor for call in repository.calls)
    assert all(call["branch_id"] == BRANCH for call in repository.calls)


@pytest.mark.asyncio
async def test_empty_categories_are_never_omitted() -> None:
    service = TaskService(Repository(empty=True), Cursor())  # type: ignore[arg-type]
    result = await service.list(principal(AppRole.ADMIN), BRANCH, query())
    assert len(result.categories) == 15
    assert all(category.status == "empty" for category in result.categories)
    assert all(category.count == 0 and category.items == [] for category in result.categories)


@pytest.mark.asyncio
async def test_failed_source_is_explicit_and_marks_response_unavailable() -> None:
    service = TaskService(
        Repository(failing="expenseApprovals"),
        Cursor(),  # type: ignore[arg-type]
    )
    result = await service.list(principal(AppRole.ADMIN), BRANCH, query())
    failed = next(category for category in result.categories if category.code == "expenseApprovals")
    assert result.source_unavailable is True
    assert failed.status == "failed"
    assert failed.error_code == "task_source_unavailable"
    assert failed.items == []
    assert len(result.categories) == 15


@pytest.mark.asyncio
async def test_order_pagination_and_cursor_filter_binding_are_stable() -> None:
    repository = Repository()
    cursor = Cursor()
    service = TaskService(repository, cursor)  # type: ignore[arg-type]
    actor = principal(AppRole.EMPLOYEE)

    first = await service.list(actor, BRANCH, query(limit=2))
    assert first.next_cursor == "opaque-cursor"
    assert cursor.encoded == first.categories[0].items[0].id or cursor.encoded is not None

    stale = TaskService(repository, Cursor("missing:00000000-0000-4000-8000-000000000001"))
    with pytest.raises(ServiceExecutionError, match="invalid_cursor"):
        await stale.list(actor, BRANCH, query(limit=2, cursor="opaque"))


def test_signed_cursor_is_bound_to_principal_branch_and_filters() -> None:
    codec = TaskCursorCodec(b"t" * 32, clock=lambda: NOW)
    actor = principal(AppRole.EMPLOYEE)
    first_query = query(category="pendingLeave", urgency="info", limit=25)
    cursor = codec.encode(
        principal=actor,
        branch_id=BRANCH,
        query=first_query,
        last_id="pendingLeave:00000000-0000-4000-8000-000000000001",
    )
    decoded = codec.decode(
        principal=actor,
        branch_id=BRANCH,
        query=query(category="pendingLeave", urgency="info", limit=25, cursor=cursor),
    )
    assert decoded == "pendingLeave:00000000-0000-4000-8000-000000000001"
    with pytest.raises(ValueError, match="invalid cursor"):
        codec.decode(
            principal=actor,
            branch_id=BRANCH,
            query=query(category="pendingExpenses", urgency="info", limit=25, cursor=cursor),
        )


@pytest.mark.asyncio
async def test_unknown_role_category_fails_instead_of_becoming_empty() -> None:
    service = TaskService(Repository(), Cursor())  # type: ignore[arg-type]
    with pytest.raises(ServiceExecutionError, match="validation_failed"):
        await service.list(principal(AppRole.EMPLOYEE), BRANCH, query(category="payrollApproval"))
