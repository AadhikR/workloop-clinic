import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Text

_APPEND_AUDIT_EVENT = text(
    """
    SELECT public.append_audit_event(
      :action, :entity_type, :entity_id, :changed_fields, :reason, :metadata
    )
    """
).bindparams(
    bindparam("changed_fields", type_=ARRAY(Text())),
    bindparam("metadata", type_=JSONB()),
)


async def append_audit_event(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changed_fields: Sequence[str],
    reason: str,
    metadata: Mapping[str, object] | None = None,
) -> uuid.UUID:
    result = await session.execute(
        _APPEND_AUDIT_EVENT,
        {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "changed_fields": list(changed_fields),
            "reason": reason,
            "metadata": dict(metadata or {}),
        },
    )
    return result.scalar_one()
