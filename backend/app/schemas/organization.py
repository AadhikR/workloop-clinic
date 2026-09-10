from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import field_serializer

from app.http.schemas import ApiSchema


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
