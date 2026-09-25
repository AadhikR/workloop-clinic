from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_APPEND_OUTPUT_AUDIT = text(
    """
    SELECT public.append_phase12_output_audit(
      :action, :entity_type, :entity_id, :format, :filter_digest,
      :source_digest, :renderer_version, :row_count, :byte_count, :result
    )
    """
)


async def append_output_audit(
    connection: AsyncConnection,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    format: str,
    filter_digest: str,
    source_digest: str,
    renderer_version: str,
    row_count: int,
    byte_count: int,
    result: str = "succeeded",
) -> uuid.UUID:
    value = await connection.scalar(
        _APPEND_OUTPUT_AUDIT,
        {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "format": format,
            "filter_digest": filter_digest,
            "source_digest": source_digest,
            "renderer_version": renderer_version,
            "row_count": row_count,
            "byte_count": byte_count,
            "result": result,
        },
    )
    if not isinstance(value, uuid.UUID):
        raise RuntimeError("output audit did not return an identifier")
    return value
