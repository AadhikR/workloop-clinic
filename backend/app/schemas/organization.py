from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

INSTANT_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
PERCENT_PATTERN = r"^(?:0|[1-9]\d?|100)\.\d{2}$"


def _serialize_instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("organization timestamps must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class TimestampedOrganizationSchema(ApiSchema):
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return _serialize_instant(value)


class CompanyAdminResponse(TimestampedOrganizationSchema):
    id: uuid.UUID
    name: str
    sector: str
    nafis_quota_percent: str
    enable_nafis: bool


class SafeEmployerResponse(ApiSchema):
    company_name: str
    branch_name: str
    branch_contact_email: str
    branch_address: str
    work_location_type: Literal["mainland", "free_zone"]
    free_zone_name: str
    logo_url: str


class BranchSafeResponse(ApiSchema):
    id: uuid.UUID
    name: str
    address: str
    contact_email: str
    work_location_type: Literal["mainland", "free_zone"]
    free_zone_name: str
    logo_url: str


class BranchAdminResponse(TimestampedOrganizationSchema):
    id: uuid.UUID
    name: str
    mol_employer_id: str
    default_bank_routing_code: str
    address: str
    contact_email: str
    default_salary_day: int | None
    work_location_type: Literal["mainland", "free_zone"]
    free_zone_name: str
    logo_url: str
    enable_staffing_rules: bool
    enable_biometric_import: bool


class ExpectedUpdatedAt(StrictRequestSchema):
    expected_updated_at: datetime

    @field_validator("expected_updated_at", mode="before")
    @classmethod
    def validate_expected_updated_at(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if re.fullmatch(INSTANT_PATTERN, value) is None:
            raise ValueError("invalid instant")
        return value


class CompanyUpdateRequest(ExpectedUpdatedAt):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    sector: str | None = Field(default=None, max_length=200)
    nafis_quota_percent: Decimal | None = Field(default=None, ge=0, le=100)
    enable_nafis: bool | None = None

    @field_validator("name", "sector")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @field_validator("nafis_quota_percent", mode="before")
    @classmethod
    def validate_percent(cls, value: object) -> object:
        if value is not None and (
            not isinstance(value, str) or re.fullmatch(PERCENT_PATTERN, value) is None
        ):
            raise ValueError("invalid percentage")
        return value

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        mutable = {"name", "sector", "nafis_quota_percent", "enable_nafis"}
        supplied = self.model_fields_set & mutable
        if not supplied or any(getattr(self, field) is None for field in supplied):
            raise ValueError("company patch requires non-null writable fields")
        if "name" in supplied and not self.name:
            raise ValueError("company name must not be blank")
        return self

    def changes(self) -> dict[str, object]:
        return {
            field: getattr(self, field)
            for field in self.model_fields_set
            if field != "expected_updated_at"
        }


class BranchFields(StrictRequestSchema):
    name: str = Field(min_length=1, max_length=200)
    mol_employer_id: str = Field(default="", max_length=200)
    default_bank_routing_code: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=2_000)
    contact_email: str = Field(default="", max_length=320)
    default_salary_day: int | None = Field(default=25, ge=1, le=31)
    work_location_type: Literal["mainland", "free_zone"] = "mainland"
    free_zone_name: str = Field(default="", max_length=200)
    logo_url: str = Field(default="", max_length=2_048)
    enable_staffing_rules: bool = True
    enable_biometric_import: bool = True

    @field_validator(
        "name",
        "mol_employer_id",
        "default_bank_routing_code",
        "address",
        "contact_email",
        "free_zone_name",
        "logo_url",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_normalized_name(self) -> Self:
        if not self.name:
            raise ValueError("branch name must not be blank")
        return self


class BranchCreateRequest(BranchFields):
    def values(self) -> dict[str, object]:
        values = self.model_dump(by_alias=False)
        values["work_location_type"] = (
            "Mainland" if self.work_location_type == "mainland" else "Free Zone"
        )
        return values


class BranchUpdateRequest(ExpectedUpdatedAt):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    mol_employer_id: str | None = Field(default=None, max_length=200)
    default_bank_routing_code: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=2_000)
    contact_email: str | None = Field(default=None, max_length=320)
    default_salary_day: int | None = Field(default=None, ge=1, le=31)
    work_location_type: Literal["mainland", "free_zone"] | None = None
    free_zone_name: str | None = Field(default=None, max_length=200)
    logo_url: str | None = Field(default=None, max_length=2_048)
    enable_staffing_rules: bool | None = None
    enable_biometric_import: bool | None = None

    @field_validator(
        "name",
        "mol_employer_id",
        "default_bank_routing_code",
        "address",
        "contact_email",
        "free_zone_name",
        "logo_url",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        supplied = self.model_fields_set - {"expected_updated_at"}
        clearable = {"default_salary_day"}
        if not supplied or any(
            getattr(self, field) is None for field in supplied if field not in clearable
        ):
            raise ValueError("branch patch requires writable fields")
        if "name" in supplied and not self.name:
            raise ValueError("branch name must not be blank")
        return self

    def changes(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for field in self.model_fields_set - {"expected_updated_at"}:
            value = getattr(self, field)
            if field == "work_location_type":
                value = "Mainland" if value == "mainland" else "Free Zone"
            values[field] = value
        return values
