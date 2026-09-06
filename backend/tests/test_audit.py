import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from app.db.audit import append_audit_event


@pytest.mark.asyncio
async def test_append_audit_event_uses_callers_transaction() -> None:
    expected_id = uuid.uuid4()
    result = Mock()
    result.scalar_one.return_value = expected_id
    session = AsyncMock()
    session.execute.return_value = result

    actual_id = await append_audit_event(
        session,
        action="incident_closed",
        entity_type="incident_report",
        entity_id=uuid.uuid4(),
        changed_fields=("status", "closed_date"),
        reason="Investigation completed",
        metadata={"transition": "investigating_to_closed"},
    )

    assert actual_id == expected_id
    session.execute.assert_awaited_once()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
