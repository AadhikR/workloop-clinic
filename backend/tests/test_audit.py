import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from app.db.audit import append_audit_event


@pytest.mark.asyncio
async def test_append_audit_event_uses_callers_transaction() -> None:
    expected_id = uuid.uuid4()
    result = Mock()
    result.scalar_one.return_value = expected_id
    connection = AsyncMock()
    connection.execute.return_value = result

    actual_id = await append_audit_event(
        connection,
        action="incident_closed",
        entity_type="incident_report",
        entity_id=uuid.uuid4(),
        changed_fields=("status", "closed_date"),
        reason="Investigation completed",
        metadata={"transition": "investigating_to_closed"},
    )

    assert actual_id == expected_id
    connection.execute.assert_awaited_once()
    connection.commit.assert_not_awaited()
    connection.rollback.assert_not_awaited()
