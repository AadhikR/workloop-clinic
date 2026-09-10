from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import field_serializer

from app.http.schemas import ApiSchema

EmploymentStatus = Literal["active", "probation", "on_leave", "terminated"]
ChangeType = Literal["title_change", "department_change", "salary_change", "status_change"]
NullableGender = Literal["male", "female", "other"] | None
NullableMaritalStatus = Literal["single", "married", "divorced", "widowed"] | None
NullableVisaType = (
    Literal[
        "employment_visa",
        "investor_visa",
        "dependent_visa",
        "tourist_temp",
        "exempt",
    ]
    | None
)
WorkLocationType = Literal["mainland", "free_zone"]


def _instant(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("employee timestamps must include a timezone")
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EmployeeAdminListResponse(ApiSchema):
    id: uuid.UUID
    emp_no: str
    name: str
    photo_url: str
    work_email: str
    job_title: str
    department: str
    reporting_manager_id: uuid.UUID | None
    employment_start_date: date | None
    probation_end_date: date | None
    employment_status: EmploymentStatus
    active: bool
    basic_salary: str
    housing_allowance: str
    transport_allowance: str
    other_allowances: str
    bank_name: str
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_updated_at(self, value: datetime) -> str:
        return _instant(value)


class EmployeeAdminDetailResponse(EmployeeAdminListResponse):
    mol_id: str
    bank_routing_code: str
    iban: str
    allowance: str
    personal_email: str
    phone: str
    date_of_birth: date | None
    gender: NullableGender
    marital_status: NullableMaritalStatus
    home_country_address: str
    emergency_contact_name: str
    emergency_contact_relationship: str
    emergency_contact_phone: str
    probation_extended: bool
    termination_date: date | None
    termination_reason: str
    other_allowances_label: str
    bank_account_holder: str
    nationality: str
    visa_type: NullableVisaType
    visa_number: str
    visa_expiry: date | None
    passport_number: str
    passport_expiry: date | None
    emirates_id: str
    emirates_id_expiry: date | None
    labour_card_number: str
    labour_card_expiry: date | None
    sponsoring_entity: str
    work_location_type: WorkLocationType
    free_zone_name: str
    nafis_registration_no: str
    licence_authority: str
    licence_number: str
    licence_expiry: date | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return _instant(value)


class ReportingManagerResponse(ApiSchema):
    id: uuid.UUID
    name: str
    job_title: str


class EmployeeSelfResponse(ApiSchema):
    id: uuid.UUID
    emp_no: str
    name: str
    photo_url: str
    work_email: str
    job_title: str
    department: str
    employment_start_date: date | None
    probation_end_date: date | None
    employment_status: EmploymentStatus
    basic_salary: str
    housing_allowance: str
    transport_allowance: str
    other_allowances: str
    bank_name: str
    mol_id: str
    bank_routing_code: str
    iban: str
    allowance: str
    personal_email: str
    phone: str
    date_of_birth: date | None
    gender: NullableGender
    marital_status: NullableMaritalStatus
    home_country_address: str
    emergency_contact_name: str
    emergency_contact_relationship: str
    emergency_contact_phone: str
    probation_extended: bool
    termination_date: date | None
    termination_reason: str
    other_allowances_label: str
    bank_account_holder: str
    nationality: str
    visa_type: NullableVisaType
    visa_number: str
    visa_expiry: date | None
    passport_number: str
    passport_expiry: date | None
    emirates_id: str
    emirates_id_expiry: date | None
    labour_card_number: str
    labour_card_expiry: date | None
    sponsoring_entity: str
    work_location_type: WorkLocationType
    free_zone_name: str
    nafis_registration_no: str
    licence_authority: str
    licence_number: str
    licence_expiry: date | None
    reporting_manager: ReportingManagerResponse | None


class DirectReportResponse(ApiSchema):
    id: uuid.UUID
    emp_no: str
    name: str
    photo_url: str
    job_title: str
    department: str
    employment_start_date: date | None
    probation_end_date: date | None
    employment_status: EmploymentStatus


class EmployeeJobHistoryResponse(ApiSchema):
    id: uuid.UUID
    employee_id: uuid.UUID
    changed_at: datetime
    changed_by_app_user_id: uuid.UUID | None
    change_type: ChangeType
    old_value: str
    new_value: str
    reason: str

    @field_serializer("changed_at")
    def serialize_changed_at(self, value: datetime) -> str:
        return _instant(value)
