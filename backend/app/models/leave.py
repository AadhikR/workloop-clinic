import uuid
from datetime import date, datetime
from datetime import date as date_type
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeaveSettings(Base):
    __tablename__ = "leave_settings"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("branch_id", name="uq_leave_settings_branch_id"),
        CheckConstraint("weekend_definition IN ('fri-sat', 'sat-sun')", name="weekend_definition"),
        CheckConstraint(
            "ramadan_end IS NULL OR ramadan_start IS NULL OR ramadan_end >= ramadan_start",
            name="ramadan_dates",
        ),
        CheckConstraint("approval_chain IN ('1-level', '2-level')", name="approval_chain"),
        Index("ix_leave_settings_company_id_branch_id", "company_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    leave_year_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'calendar'")
    )
    weekend_definition: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'fri-sat'")
    )
    carry_forward_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("true")
    )
    carry_forward_max_days: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("15")
    )
    approval_chain: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'1-level'")
    )
    ramadan_active: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    ramadan_start: Mapped[date | None] = mapped_column(Date(), nullable=True)
    ramadan_end: Mapped[date | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class LeaveType(Base):
    __tablename__ = "leave_types"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_leave_types_id_company_id_branch_id"
        ),
        UniqueConstraint("branch_id", "code", name="uq_leave_types_branch_id_code"),
        CheckConstraint(
            "min_notice_days >= 0 AND annual_entitlement_days >= 0 "
            "AND carry_forward_max_days >= 0 AND min_service_months >= 0",
            name="nonnegative_rules",
        ),
        Index("ix_leave_types_branch_id_active_sort", "branch_id", "is_active", "sort_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(Text(), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    color: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'#6b7280'"))
    is_paid: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("true"))
    is_unlimited: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("true")
    )
    requires_attachment: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    requires_reason: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    min_notice_days: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("0")
    )
    annual_entitlement_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    accrual_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'fixed'")
    )
    day_count_type: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'calendar'")
    )
    auto_approve: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    carry_forward_allowed: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    carry_forward_max_days: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("0")
    )
    gender_restriction: Mapped[str | None] = mapped_column(Text(), nullable=True)
    min_service_months: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("0")
    )
    once_per_career: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    not_deducted_from_annual: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    affects_payroll: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    law_reference: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("true"))
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    probation_eligible: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class PublicHoliday(Base):
    __tablename__ = "public_holidays"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("branch_id", "date", name="uq_public_holidays_branch_id_date"),
        CheckConstraint("year = extract(year FROM date)::integer", name="year"),
        Index("ix_public_holidays_branch_id_date", "branch_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date: Mapped[date_type] = mapped_column(Date(), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    type: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'federal'"))
    year: Mapped[int] = mapped_column(Integer(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["leave_type_id", "company_id", "branch_id"],
            ["leave_types.id", "leave_types.company_id", "leave_types.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["substitute_employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_leave_requests_substitute_employee_id_employees",
            ondelete="SET NULL (substitute_employee_id)",
        ),
        ForeignKeyConstraint(["approved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["manager_approved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"
        ),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_leave_requests_id_company_id_branch_id"
        ),
        CheckConstraint("end_date >= start_date", name="dates"),
        CheckConstraint("days_requested > 0", name="days_requested"),
        CheckConstraint("approval_level_required >= 1", name="approval_level"),
        CheckConstraint(
            "status IN ('Pending', 'ManagerApproved', 'ManagerRejected', 'Approved', "
            "'Rejected', 'Cancelled')",
            name="status",
        ),
        CheckConstraint(
            "(NOT is_half_day AND half_day_period IS NULL) "
            "OR (is_half_day AND half_day_period IN ('AM', 'PM'))",
            name="half_day",
        ),
        CheckConstraint(
            "status <> 'Approved' OR (approved_by_app_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL)",
            name="approved_fields",
        ),
        CheckConstraint(
            "status <> 'ManagerApproved' OR (manager_approved_by_app_user_id IS NOT NULL "
            "AND manager_approved_at IS NOT NULL)",
            name="manager_approved_fields",
        ),
        CheckConstraint(
            "status <> 'Rejected' OR (approved_by_app_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL AND btrim(rejection_reason) <> '')",
            name="rejected_fields",
        ),
        CheckConstraint(
            "status <> 'ManagerRejected' OR (manager_approved_by_app_user_id IS NOT NULL "
            "AND manager_approved_at IS NOT NULL AND btrim(manager_rejection_reason) <> '')",
            name="manager_rejected_fields",
        ),
        Index("ix_leave_requests_employee_id", "employee_id"),
        Index("ix_leave_requests_status", "status"),
        Index("ix_leave_requests_branch_id_start_date", "branch_id", "start_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    end_date: Mapped[date] = mapped_column(Date(), nullable=False)
    is_half_day: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    half_day_period: Mapped[str | None] = mapped_column(Text(), nullable=True)
    days_requested: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'Pending'"))
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    attachment_url: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    rejection_reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    relationship: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    deceased_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    date_of_death: Mapped[date | None] = mapped_column(Date(), nullable=True)
    child_birth_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    child_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    expected_due_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    institution_name: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    exam_dates: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    manager_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manager_approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    manager_rejection_reason: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    substitute_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    approval_level_required: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("1")
    )
    approval_comment: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    warnings: Mapped[list[Any]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'")
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class LeaveAuditLog(Base):
    __tablename__ = "leave_audit_log"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["leave_request_id", "company_id", "branch_id"],
            ["leave_requests.id", "leave_requests.company_id", "leave_requests.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        Index("ix_leave_audit_log_request_id_created_at", "leave_request_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    leave_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    actor_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    old_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    new_status: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class LeaveBalance(Base):
    __tablename__ = "leave_balances"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["leave_type_id", "company_id", "branch_id"],
            ["leave_types.id", "leave_types.company_id", "leave_types.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "employee_id",
            "leave_type_id",
            "leave_year",
            name="uq_leave_balances_employee_id_leave_type_id_leave_year",
        ),
        CheckConstraint(
            "entitled_days >= 0 AND accrued_days >= 0 AND used_days >= 0 AND pending_days >= 0 "
            "AND carried_forward >= 0 AND remaining_days >= 0 AND sick_full_pay_used >= 0 "
            "AND sick_half_pay_used >= 0 AND sick_unpaid_used >= 0",
            name="nonnegative_days",
        ),
        Index("ix_leave_balances_branch_id_year", "branch_id", "leave_year"),
        Index("ix_leave_balances_employee_id", "employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    leave_year: Mapped[int] = mapped_column(Integer(), nullable=False)
    entitled_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    accrued_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    used_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    pending_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    carried_forward: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    remaining_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    sick_full_pay_used: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    sick_half_pay_used: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    sick_unpaid_used: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default=text("0")
    )
    hajj_taken: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class LeaveApprovalDelegate(Base):
    __tablename__ = "leave_approval_delegates"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approver_employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_leave_approval_delegates_approver_employee_id_employees",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["delegate_employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_leave_approval_delegates_delegate_employee_id_employees",
            ondelete="RESTRICT",
        ),
        CheckConstraint("approver_employee_id <> delegate_employee_id", name="distinct"),
        CheckConstraint("to_date >= from_date", name="dates"),
        Index(
            "ix_leave_approval_delegates_approver_dates",
            "approver_employee_id",
            "from_date",
            "to_date",
        ),
        Index(
            "ix_leave_approval_delegates_delegate_dates",
            "delegate_employee_id",
            "from_date",
            "to_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    approver_employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    delegate_employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_date: Mapped[date] = mapped_column(Date(), nullable=False)
    to_date: Mapped[date] = mapped_column(Date(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
