from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy.sql.elements import TextClause

from app.repositories.notifications import NotificationRepository


class Result:
    def mappings(self) -> Result:
        return self

    def __iter__(self) -> Iterator[object]:
        return iter(())


class Connection:
    def __init__(self) -> None:
        self.statement: TextClause | None = None

    async def execute(self, statement: TextClause, _parameters: object) -> Result:
        self.statement = statement
        return Result()


@pytest.mark.asyncio
@pytest.mark.parametrize("include_tenant", [False, True])
async def test_notification_cursor_qualifies_columns_without_changing_bind_names(
    include_tenant: bool,
) -> None:
    connection = Connection()
    repository = NotificationRepository(connection)  # type: ignore[arg-type]

    await repository.list(
        company_id=uuid.uuid4(),
        branch_id=uuid.uuid4(),
        recipient_id=uuid.uuid4(),
        include_tenant=include_tenant,
        cursor_id=None,
        limit=41,
    )

    assert connection.statement is not None
    assert set(connection.statement.compile().params) == {
        "branch_id",
        "company_id",
        "cursor_id",
        "limit",
        "recipient_id",
    }
    assert "anchor.branch_id=:branch_id" in str(connection.statement)
