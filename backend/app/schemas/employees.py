from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, field_serializer, field_validator, model_validator

from app.http.schemas import ApiSchema, StrictRequestSchema

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
InitialEmploymentStatus = Literal["active", "probation", "on_leave"]
MONEY_PATTERN = r"^(?:0|[1-9]\d{0,9})\.\d{2}$"
INSTANT_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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


def _stored_enum(value: str | None, mapping: dict[str, str]) -> str:
    return "" if value is None else mapping[value]


def _mapped_employee_values(values: dict[str, object]) -> dict[str, object]:
    mappings = {
        "employment_status": {
            "active": "Active",
            "probation": "Probation",
            "on_leave": "On Leave",
        },
        "gender": {"male": "Male", "female": "Female", "other": "Other"},
        "marital_status": {
            "single": "Single",
            "married": "Married",
            "divorced": "Divorced",
            "widowed": "Widowed",
        },
        "visa_type": {
            "employment_visa": "Employment Visa",
            "investor_visa": "Investor Visa",
            "dependent_visa": "Dependent Visa",
            "tourist_temp": "Tourist (Temp)",
            "exempt": "Exempt",
        },
        "work_location_type": {"mainland": "Mainland", "free_zone": "Free Zone"},
    }
    for field, mapping in mappings.items():
        if field in values:
            values[field] = _stored_enum(values[field], mapping)  # type: ignore[arg-type]
    return values


class EmployeeCreateRequest(StrictRequestSchema):
    emp_no: str = Field(default="", max_length=200)
    name: str = Field(min_length=1, max_length=200)
    photo_url: str = Field(default="", max_length=2_048)
    work_email: str = Field(default="", max_length=254)
    job_title: str = Field(default="", max_length=200)
    department: str = Field(min_length=1, max_length=200)
    reporting_manager_id: uuid.UUID | None = None
    employment_start_date: date | None = None
    probation_end_date: date | None = None
    employment_status: InitialEmploymentStatus = "active"
    basic_salary: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("9999999999.99"))
    housing_allowance: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("9999999999.99"))
    transport_allowance: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("9999999999.99"))
    other_allowances: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("9999999999.99"))
    bank_name: str = Field(default="", max_length=200)
    mol_id: str = Field(min_length=1, max_length=200)
    bank_routing_code: str = Field(default="", max_length=200)
    iban: str = Field(default="", max_length=200)
    allowance: Decimal = Field(default=Decimal("0.00"), ge=0, le=Decimal("9999999999.99"))
    personal_email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=100)
    date_of_birth: date | None = None
    gender: NullableGender = None
    marital_status: NullableMaritalStatus = None
    home_country_address: str = Field(default="", max_length=2_000)
    emergency_contact_name: str = Field(default="", max_length=200)
    emergency_contact_relationship: str = Field(default="", max_length=200)
    emergency_contact_phone: str = Field(default="", max_length=100)
    probation_extended: bool = False
    other_allowances_label: str = Field(default="", max_length=200)
    bank_account_holder: str = Field(default="", max_length=200)
    nationality: str = Field(default="", max_length=200)
    visa_type: NullableVisaType = None
    visa_number: str = Field(default="", max_length=200)
    visa_expiry: date | None = None
    passport_number: str = Field(default="", max_length=200)
    passport_expiry: date | None = None
    emirates_id: str = Field(default="", max_length=200)
    emirates_id_expiry: date | None = None
    labour_card_number: str = Field(default="", max_length=200)
    labour_card_expiry: date | None = None
    sponsoring_entity: str = Field(default="", max_length=200)
    work_location_type: WorkLocationType = "mainland"
    free_zone_name: str = Field(default="", max_length=200)
    nafis_registration_no: str = Field(default="", max_length=200)
    licence_authority: str = Field(default="None", max_length=200)
    licence_number: str = Field(default="", max_length=200)
    licence_expiry: date | None = None

    @field_validator(
        "emp_no",
        "name",
        "photo_url",
        "work_email",
        "job_title",
        "department",
        "bank_name",
        "mol_id",
        "bank_routing_code",
        "iban",
        "personal_email",
        "phone",
        "home_country_address",
        "emergency_contact_name",
        "emergency_contact_relationship",
        "emergency_contact_phone",
        "other_allowances_label",
        "bank_account_holder",
        "nationality",
        "visa_number",
        "passport_number",
        "emirates_id",
        "labour_card_number",
        "sponsoring_entity",
        "free_zone_name",
        "nafis_registration_no",
        "licence_authority",
        "licence_number",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("work_email")
    @classmethod
    def validate_work_email(cls, value: str) -> str:
        if value and EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("invalid email")
        return value.lower()

    @field_validator("personal_email")
    @classmethod
    def validate_personal_email(cls, value: str) -> str:
        if value and EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("invalid email")
        return value

    @field_validator("mol_id")
    @classmethod
    def validate_mol_id(cls, value: str) -> str:
        if re.fullmatch(r"\d{10,15}", value) is None:
            raise ValueError("invalid MOL ID")
        return value

    @field_validator("bank_routing_code")
    @classmethod
    def validate_bank_routing_code(cls, value: str) -> str:
        if value and re.fullmatch(r"\d{9}", value) is None:
            raise ValueError("invalid bank routing code")
        return value

    @field_validator("iban")
    @classmethod
    def validate_iban(cls, value: str) -> str:
        if value and re.fullmatch(r"AE\d{21}", value) is None:
            raise ValueError("invalid IBAN")
        return value

    @field_validator(
        "basic_salary",
        "housing_allowance",
        "transport_allowance",
        "other_allowances",
        "allowance",
        mode="before",
    )
    @classmethod
    def validate_money(cls, value: object) -> object:
        if not isinstance(value, str) or re.fullmatch(MONEY_PATTERN, value) is None:
            raise ValueError("invalid money")
        return value

    @model_validator(mode="after")
    def validate_required_relationships(self) -> Self:
        if not self.name or not self.mol_id or not self.department:
            raise ValueError("employee name, MOL ID, and department are required")
        return self

    def values(self) -> dict[str, object]:
        return _mapped_employee_values(self.model_dump(by_alias=False))


class EmployeeUpdateRequest(StrictRequestSchema):
    expected_updated_at: datetime
    emp_no: str | None = Field(default=None, max_length=200)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    photo_url: str | None = Field(default=None, max_length=2_048)
    mol_id: str | None = Field(default=None, min_length=1, max_length=200)
    bank_name: str | None = Field(default=None, max_length=200)
    bank_routing_code: str | None = Field(default=None, max_length=200)
    bank_account_holder: str | None = Field(default=None, max_length=200)
    iban: str | None = Field(default=None, max_length=200)
    personal_email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = None
    gender: NullableGender = None
    marital_status: NullableMaritalStatus = None
    home_country_address: str | None = Field(default=None, max_length=2_000)
    emergency_contact_name: str | None = Field(default=None, max_length=200)
    emergency_contact_relationship: str | None = Field(default=None, max_length=200)
    emergency_contact_phone: str | None = Field(default=None, max_length=100)
    employment_start_date: date | None = None
    nationality: str | None = Field(default=None, max_length=200)
    visa_type: NullableVisaType = None
    visa_number: str | None = Field(default=None, max_length=200)
    visa_expiry: date | None = None
    passport_number: str | None = Field(default=None, max_length=200)
    passport_expiry: date | None = None
    emirates_id: str | None = Field(default=None, max_length=200)
    emirates_id_expiry: date | None = None
    labour_card_number: str | None = Field(default=None, max_length=200)
    labour_card_expiry: date | None = None
    sponsoring_entity: str | None = Field(default=None, max_length=200)
    work_location_type: WorkLocationType | None = None
    free_zone_name: str | None = Field(default=None, max_length=200)
    nafis_registration_no: str | None = Field(default=None, max_length=200)
    licence_authority: str | None = Field(default=None, max_length=200)
    licence_number: str | None = Field(default=None, max_length=200)
    licence_expiry: date | None = None

    @field_validator("expected_updated_at", mode="before")
    @classmethod
    def validate_expected_updated_at(cls, value: object) -> object:
        if isinstance(value, str) and re.fullmatch(INSTANT_PATTERN, value) is None:
            raise ValueError("invalid instant")
        return value

    @field_validator(
        "emp_no",
        "name",
        "photo_url",
        "mol_id",
        "bank_name",
        "bank_routing_code",
        "bank_account_holder",
        "iban",
        "personal_email",
        "phone",
        "home_country_address",
        "emergency_contact_name",
        "emergency_contact_relationship",
        "emergency_contact_phone",
        "nationality",
        "visa_number",
        "passport_number",
        "emirates_id",
        "labour_card_number",
        "sponsoring_entity",
        "free_zone_name",
        "nafis_registration_no",
        "licence_authority",
        "licence_number",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @field_validator("personal_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value and EMAIL_PATTERN.fullmatch(value) is None:
            raise ValueError("invalid email")
        return value

    @field_validator("mol_id")
    @classmethod
    def validate_mol_id(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"\d{10,15}", value) is None:
            raise ValueError("invalid MOL ID")
        return value

    @field_validator("bank_routing_code")
    @classmethod
    def validate_bank_routing_code(cls, value: str | None) -> str | None:
        if value and re.fullmatch(r"\d{9}", value) is None:
            raise ValueError("invalid bank routing code")
        return value

    @field_validator("iban")
    @classmethod
    def validate_iban(cls, value: str | None) -> str | None:
        if value and re.fullmatch(r"AE\d{21}", value) is None:
            raise ValueError("invalid IBAN")
        return value

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        supplied = self.model_fields_set - {"expected_updated_at"}
        nullable = {
            "date_of_birth",
            "gender",
            "marital_status",
            "employment_start_date",
            "visa_type",
            "visa_expiry",
            "passport_expiry",
            "emirates_id_expiry",
            "labour_card_expiry",
            "licence_expiry",
        }
        if not supplied or any(getattr(self, field) is None for field in supplied - nullable):
            raise ValueError("employee patch requires writable fields")
        if "name" in supplied and not self.name:
            raise ValueError("employee name must not be blank")
        if "mol_id" in supplied and not self.mol_id:
            raise ValueError("MOL ID must not be blank")
        return self

    def changes(self) -> dict[str, object]:
        values = {
            field: getattr(self, field) for field in self.model_fields_set - {"expected_updated_at"}
        }
        return _mapped_employee_values(values)


class EmployeeImportRow(StrictRequestSchema):
    row_number: int = Field(ge=1, le=1_000_000)
    emp_no: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    mol_id: str = Field(pattern=r"^\d{10,15}$")
    bank_name: str = Field(max_length=200)
    bank_routing_code: str = Field(pattern=r"^(?:|\d{9})$")
    iban: str = Field(pattern=r"^(?:|AE\d{21})$")
    basic_salary: Decimal = Field(ge=0, le=Decimal("9999999999.99"))
    allowance: Decimal = Field(ge=0, le=Decimal("9999999999.99"))

    @field_validator("emp_no", "name", "mol_id", "bank_name", "bank_routing_code", "iban")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("basic_salary", "allowance", mode="before")
    @classmethod
    def validate_money(cls, value: object) -> object:
        if not isinstance(value, str) or re.fullmatch(MONEY_PATTERN, value) is None:
            raise ValueError("invalid money")
        return value

    def values(self) -> dict[str, object]:
        return self.model_dump(by_alias=False, exclude={"row_number"})


class EmployeeImportRequest(StrictRequestSchema):
    rows: list[EmployeeImportRow] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_row_numbers(self) -> Self:
        numbers = [row.row_number for row in self.rows]
        if len(numbers) != len(set(numbers)):
            raise ValueError("import row numbers must be unique")
        return self


class EmployeeImportResult(ApiSchema):
    row_number: int
    employee_id: uuid.UUID


class EmployeeImportResponse(ApiSchema):
    created_count: int
    rows: list[EmployeeImportResult]
