from __future__ import annotations

from pydantic import Field

from app.http.schemas import ApiSchema


class SifPreviewResponse(ApiSchema):
    filename: str
    source_digest: str
    renderer_version: str
    byte_count: int = Field(gt=0)
    record_count: int = Field(gt=0)
    records: list[dict[str, str | int]] = Field(min_length=1)
