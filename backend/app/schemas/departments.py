from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema


def _instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("department timestamps must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class DepartmentResponse(ApiSchema):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    head_employee_id: uuid.UUID | None
    color: str
    description: str
    sort_order: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return _instant(value)


class DepartmentSnapshot(StrictRequestSchema):
    name: str
    parent_id: uuid.UUID | None
    head_employee_id: uuid.UUID | None
    color: str
    description: str
    sort_order: int


class DepartmentFields(StrictRequestSchema):
    name: str = Field(min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    head_employee_id: uuid.UUID | None = None
    color: str = Field(default="#6366f1", max_length=100)
    description: str = Field(default="", max_length=2_000)
    sort_order: int = Field(default=0, ge=-2_147_483_648, le=2_147_483_647)

    @field_validator("name", "color", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_name(self) -> Self:
        if not self.name:
            raise ValueError("department name must not be blank")
        return self

    def values(self) -> dict[str, object]:
        return self.model_dump(by_alias=False)


class DepartmentCreateRequest(DepartmentFields):
    pass


class DepartmentUpdateRequest(StrictRequestSchema):
    expected: DepartmentSnapshot
    name: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: uuid.UUID | None = None
    head_employee_id: uuid.UUID | None = None
    color: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2_000)
    sort_order: int | None = Field(default=None, ge=-2_147_483_648, le=2_147_483_647)

    @field_validator("name", "color", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        supplied = self.model_fields_set - {"expected"}
        nullable = {"parent_id", "head_employee_id"}
        if not supplied or any(getattr(self, field) is None for field in supplied - nullable):
            raise ValueError("department patch requires writable fields")
        if "name" in supplied and not self.name:
            raise ValueError("department name must not be blank")
        return self

    def changes(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.model_fields_set - {"expected"}}


class DepartmentDeleteRequest(StrictRequestSchema):
    expected: DepartmentSnapshot


class StaffingRuleResponse(ApiSchema):
    id: uuid.UUID
    department: str
    shift_category: Literal["morning", "afternoon", "night", "flexible"]
    min_staff: int
    effective_from: date | None
    effective_to: date | None


class StaffingRuleSnapshot(StrictRequestSchema):
    department: str
    shift_category: Literal["morning", "afternoon", "night", "flexible"]
    min_staff: int
    effective_from: date | None
    effective_to: date | None


class StaffingRuleFields(StrictRequestSchema):
    department: str = Field(min_length=1, max_length=200)
    shift_category: Literal["morning", "afternoon", "night", "flexible"]
    min_staff: int = Field(ge=0, le=2_147_483_647)
    effective_from: date | None = None
    effective_to: date | None = None

    @field_validator("department")
    @classmethod
    def normalize_department(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        if not self.department:
            raise ValueError("department must not be blank")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError("effective date range is invalid")
        return self

    def values(self) -> dict[str, object]:
        return self.model_dump(by_alias=False)


class StaffingRuleCreateRequest(StaffingRuleFields):
    pass


class StaffingRuleUpdateRequest(StrictRequestSchema):
    expected: StaffingRuleSnapshot
    department: str | None = Field(default=None, min_length=1, max_length=200)
    shift_category: Literal["morning", "afternoon", "night", "flexible"] | None = None
    min_staff: int | None = Field(default=None, ge=0, le=2_147_483_647)
    effective_from: date | None = None
    effective_to: date | None = None

    @field_validator("department")
    @classmethod
    def normalize_department(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        supplied = self.model_fields_set - {"expected"}
        nullable = {"effective_from", "effective_to"}
        if not supplied or any(getattr(self, field) is None for field in supplied - nullable):
            raise ValueError("staffing rule patch requires writable fields")
        if "department" in supplied and not self.department:
            raise ValueError("department must not be blank")
        values = self.expected.model_dump(by_alias=False)
        values.update(self.changes())
        start = values["effective_from"]
        end = values["effective_to"]
        if isinstance(start, date) and isinstance(end, date) and end < start:
            raise ValueError("effective date range is invalid")
        return self

    def changes(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.model_fields_set - {"expected"}}


class StaffingRuleDeleteRequest(StrictRequestSchema):
    expected: StaffingRuleSnapshot
