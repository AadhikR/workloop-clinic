from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class StrictRequestSchema(ApiSchema):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=False,
        serialize_by_alias=True,
    )


class Page(ApiSchema):
    limit: int = Field(ge=1, le=100)
    next_cursor: str | None
    has_more: bool


class DataResponse[DataType](ApiSchema):
    data: DataType


class CollectionResponse[DataType](ApiSchema):
    data: list[DataType]
    page: Page
