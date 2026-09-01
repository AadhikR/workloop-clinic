import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def enum_values(enum_type: type[enum.Enum]) -> list[str]:
    return [str(item.value) for item in enum_type]


class AccountStatus(enum.StrEnum):
    PENDING_IDENTITY = "pending_identity"
    ACTIVE = "active"
    DISABLED = "disabled"


class AppRole(enum.StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint("nafis_quota_percent BETWEEN 0 AND 100", name="nafis_quota_percent"),
        Index("ix_companies_name", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    sector: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    nafis_quota_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("2.00")
    )
    enable_nafis: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    branches: Mapped[list["Branch"]] = relationship(back_populates="company")
    employees: Mapped[list["Employee"]] = relationship(back_populates="company")
    user_profiles: Mapped[list["UserProfile"]] = relationship(back_populates="company")


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint(
            "default_salary_day IS NULL OR default_salary_day BETWEEN 1 AND 31",
            name="default_salary_day",
        ),
        UniqueConstraint("id", "company_id", name="uq_branches_id_company_id"),
        UniqueConstraint("company_id", "name", name="uq_branches_company_id_name"),
        Index("ix_branches_company_id", "company_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    mol_employer_id: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    default_bank_routing_code: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    address: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    contact_email: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    default_salary_day: Mapped[int | None] = mapped_column(
        Integer(), nullable=True, server_default=text("25")
    )
    work_location_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'Mainland'")
    )
    free_zone_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    logo_url: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    enable_staffing_rules: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("true")
    )
    enable_biometric_import: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    company: Mapped[Company] = relationship(back_populates="branches")
    employees: Mapped[list["Employee"]] = relationship(back_populates="branch")


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("id", "company_id", name="uq_employees_id_company_id"),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_employees_id_company_id_branch_id"
        ),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_employees_branch_id_branches",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reporting_manager_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_employees_reporting_manager_id_employees",
            ondelete="SET NULL (reporting_manager_id)",
        ),
        CheckConstraint("basic_salary >= 0", name="basic_salary"),
        CheckConstraint("allowance >= 0", name="allowance"),
        CheckConstraint("housing_allowance >= 0", name="housing_allowance"),
        CheckConstraint("transport_allowance >= 0", name="transport_allowance"),
        CheckConstraint("other_allowances >= 0", name="other_allowances"),
        CheckConstraint(
            "employment_status IN ('Active', 'Probation', 'On Leave', 'Terminated')",
            name="employment_status",
        ),
        CheckConstraint("contract_type IN ('Limited', 'Unlimited')", name="contract_type"),
        CheckConstraint(
            "visa_type IN ('', 'Employment Visa', 'Investor Visa', 'Dependent Visa', "
            "'Tourist (Temp)', 'Exempt')",
            name="visa_type",
        ),
        Index("ix_employees_company_id", "company_id"),
        Index("ix_employees_branch_id", "branch_id"),
        Index("ix_employees_active", "active"),
        Index("ix_employees_reporting_manager_id", "reporting_manager_id"),
        Index(
            "uq_employees_work_email_nonempty",
            "company_id",
            text("lower(btrim(work_email))"),
            unique=True,
            postgresql_where=text("btrim(work_email) <> ''"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    emp_no: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    mol_id: Mapped[str] = mapped_column(Text(), nullable=False)
    bank_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    bank_routing_code: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    iban: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    basic_salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("true"))
    personal_email: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    work_email: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    phone: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    date_of_birth: Mapped[date | None] = mapped_column(Date(), nullable=True)
    gender: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    marital_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    home_country_address: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    photo_url: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    emergency_contact_name: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    emergency_contact_relationship: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    emergency_contact_phone: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    job_title: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    department: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    employment_start_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    probation_end_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    probation_extended: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    contract_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'Unlimited'")
    )
    contract_end_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    employment_status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'Active'")
    )
    termination_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    termination_reason: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    housing_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    transport_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    other_allowances: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    other_allowances_label: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    bank_account_holder: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    nationality: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    visa_type: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    visa_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    visa_expiry: Mapped[date | None] = mapped_column(Date(), nullable=True)
    passport_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    passport_expiry: Mapped[date | None] = mapped_column(Date(), nullable=True)
    emirates_id: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    emirates_id_expiry: Mapped[date | None] = mapped_column(Date(), nullable=True)
    labour_card_number: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    labour_card_expiry: Mapped[date | None] = mapped_column(Date(), nullable=True)
    sponsoring_entity: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    work_location_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'Mainland'")
    )
    free_zone_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    nafis_registration_no: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    licence_authority: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'None'")
    )
    licence_number: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    licence_expiry: Mapped[date | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    company: Mapped[Company] = relationship(back_populates="employees")
    branch: Mapped[Branch] = relationship(back_populates="employees")
    user_profiles: Mapped[list["UserProfile"]] = relationship(back_populates="employee")


class AppUser(Base):
    __tablename__ = "app_users"
    __table_args__ = (UniqueConstraint("identity_issuer", "identity_subject"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_issuer: Mapped[str] = mapped_column(Text(), nullable=False)
    identity_subject: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(AccountStatus, name="account_status", values_callable=enum_values),
        nullable=False,
        server_default=text("'pending_identity'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    user_profile: Mapped["UserProfile | None"] = relationship(back_populates="app_user")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_id", "company_id"],
            ["employees.id", "employees.company_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(role = 'admin' AND employee_id IS NULL) OR "
            "(role IN ('manager', 'employee') AND employee_id IS NOT NULL)",
            name="role_employee_link",
        ),
        UniqueConstraint(
            "app_user_id", "company_id", name="uq_user_profiles_app_user_id_company_id"
        ),
        Index("ix_user_profiles_company_id", "company_id"),
        Index(
            "uq_user_profiles_employee_id",
            "employee_id",
            unique=True,
            postgresql_where=text("employee_id IS NOT NULL"),
        ),
    )

    app_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_users.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    role: Mapped[AppRole] = mapped_column(
        Enum(AppRole, name="app_role", values_callable=enum_values),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    app_user: Mapped[AppUser] = relationship(back_populates="user_profile")
    company: Mapped[Company] = relationship(back_populates="user_profiles")
    employee: Mapped[Employee | None] = relationship(back_populates="user_profiles")
