import uuid
from datetime import UTC, datetime
from typing import Self

from pydantic import Field, field_serializer, model_validator

from app.http.schemas import ApiSchema
from app.schemas.organization import BranchAdminResponse, ExpectedUpdatedAt


class RoutingDraft(ExpectedUpdatedAt):
    id: uuid.UUID
    source_digest: str = Field(pattern=r"^(?:[0-9a-f]{64})?$", max_length=64)

    @field_serializer("expected_updated_at")
    def serialize_version(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class RoutingChangeRequest(ExpectedUpdatedAt):
    routing_code: str = Field(pattern=r"^[0-9]{9}$")
    drafts: list[RoutingDraft] = Field(max_length=1000)

    @model_validator(mode="after")
    def unique_drafts(self) -> Self:
        if len({item.id for item in self.drafts}) != len(self.drafts):
            raise ValueError("duplicate draft")
        return self


class RoutingSnapshot(ApiSchema):
    branch: BranchAdminResponse
    drafts: list[RoutingDraft]


class RoutingChangeResponse(ApiSchema):
    branch: BranchAdminResponse
    changed_runs: list[RoutingDraft]
