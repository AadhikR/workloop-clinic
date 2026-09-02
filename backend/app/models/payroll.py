import uuid
from datetime import date, datetime
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


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["run_by_app_user_id"], ["app_users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["submitted_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["approved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["rejected_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_payroll_runs_id_company_id_branch_id"
        ),
        UniqueConstraint("branch_id", "period", name="uq_payroll_runs_branch_id_period"),
        CheckConstraint("total_disbursed >= 0", name="total_disbursed"),
        CheckConstraint("employee_count >= 0", name="employee_count"),
        CheckConstraint("status IN ('draft', 'generated')", name="status"),
        CheckConstraint(
            "approval_status IN ('draft', 'pending_approval', 'approved')",
            name="approval_status",
        ),
        CheckConstraint(
            "wps_status IN ('draft', 'sif_generated', 'submitted', 'confirmed', "
            "'partial_rejection', 'failed')",
            name="wps_status",
        ),
        CheckConstraint(
            "approval_status <> 'pending_approval' OR (submitted_by_app_user_id IS NOT NULL "
            "AND submitted_for_approval_at IS NOT NULL)",
            name="submission_fields",
        ),
        CheckConstraint(
            "approval_status <> 'approved' OR (approved_by_app_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL)",
            name="approval_fields",
        ),
        CheckConstraint(
            "(rejected_at IS NULL AND rejected_by_app_user_id IS NULL AND rejection_reason = '') "
            "OR (rejected_at IS NOT NULL AND rejected_by_app_user_id IS NOT NULL "
            "AND btrim(rejection_reason) <> '')",
            name="rejection_fields",
        ),
        CheckConstraint(
            "status <> 'generated' OR (approval_status = 'approved' "
            "AND approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL)",
            name="generated_fields",
        ),
        CheckConstraint(
            "wps_status NOT IN ('submitted', 'confirmed', 'partial_rejection') "
            "OR wps_submitted_at IS NOT NULL",
            name="wps_submitted_at",
        ),
        CheckConstraint(
            "wps_status NOT IN ('confirmed', 'partial_rejection') OR wps_confirmed_at IS NOT NULL",
            name="wps_confirmed_at",
        ),
        Index("ix_payroll_runs_company_id", "company_id"),
        Index("ix_payroll_runs_branch_id", "branch_id"),
        Index("ix_payroll_runs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(Text(), nullable=False)
    payment_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    sequence_no: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    scr_bank_routing_code: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'draft'"))
    run_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    total_disbursed: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    employee_count: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    wps_status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'draft'"))
    wps_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wps_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wps_reference_no: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    approval_status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'draft'")
    )
    submitted_for_approval_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class PayrollEntry(Base):
    __tablename__ = "payroll_entries"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payroll_run_id", "company_id", "branch_id"],
            ["payroll_runs.id", "payroll_runs.company_id", "payroll_runs.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "payroll_run_id",
            "employee_id",
            name="uq_payroll_entries_payroll_run_id_employee_id",
        ),
        CheckConstraint("basic_salary >= 0", name="basic_salary"),
        CheckConstraint("housing_allowance >= 0", name="housing_allowance"),
        CheckConstraint("transport_allowance >= 0", name="transport_allowance"),
        CheckConstraint("allowance >= 0", name="allowance"),
        CheckConstraint("increment >= 0", name="increment"),
        CheckConstraint("bonus >= 0", name="bonus"),
        CheckConstraint("other_pay >= 0", name="other_pay"),
        CheckConstraint("leave_deduction >= 0", name="leave_deduction"),
        CheckConstraint(
            "wps_payment_status IN ('pending', 'paid', 'rejected')", name="wps_payment_status"
        ),
        CheckConstraint(
            "wps_payment_status <> 'rejected' OR btrim(wps_rejection_reason) <> ''",
            name="wps_rejection_reason",
        ),
        Index("ix_payroll_entries_payroll_run_id", "payroll_run_id"),
        Index("ix_payroll_entries_employee_id", "employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    basic_salary: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    housing_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    transport_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    increment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    bonus: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, server_default=text("0"))
    other_pay: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    leave_deduction: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    variable_allowance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    additional_allowances: Mapped[list[Any]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'")
    )
    deductions: Mapped[list[Any]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'[]'")
    )
    excluded: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("false"))
    wps_payment_status: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'pending'")
    )
    wps_rejection_reason: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Payslip(Base):
    __tablename__ = "payslips"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payroll_run_id", "company_id", "branch_id"],
            ["payroll_runs.id", "payroll_runs.company_id", "payroll_runs.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "payroll_run_id", "employee_id", name="uq_payslips_payroll_run_id_employee_id"
        ),
        CheckConstraint("gross_pay >= 0", name="gross_pay"),
        CheckConstraint("net_pay >= 0", name="net_pay"),
        Index("ix_payslips_employee_id_period", "employee_id", text("period DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(Text(), nullable=False)
    payment_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    gross_pay: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    net_pay: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    data_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'")
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class PayrollApprovalLog(Base):
    __tablename__ = "payroll_approval_log"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payroll_run_id", "company_id", "branch_id"],
            ["payroll_runs.id", "payroll_runs.company_id", "payroll_runs.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["performed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint(
            "action IN ('submitted', 'approved', 'rejected', 'recalled')", name="action"
        ),
        Index(
            "ix_payroll_approval_log_payroll_run_id_created_at",
            "payroll_run_id",
            text("created_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    performed_by_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class NafisReport(Base):
    __tablename__ = "nafis_reports"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("branch_id", "period", name="uq_nafis_reports_branch_id_period"),
        CheckConstraint(
            "total_headcount >= 0 AND emirati_count >= 0 AND emirati_count <= total_headcount",
            name="counts",
        ),
        CheckConstraint(
            "ratio_percent BETWEEN 0 AND 100 AND required_percent BETWEEN 0 AND 100",
            name="percentages",
        ),
        Index("ix_nafis_reports_branch_id_period", "branch_id", text("period DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(Text(), nullable=False)
    total_headcount: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("0")
    )
    emirati_count: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    ratio_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    required_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    compliant: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("false"))
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class SalaryAdvance(Base):
    __tablename__ = "salary_advances"
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
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_salary_advances_id_company_id_branch_id"
        ),
        CheckConstraint("amount > 0", name="amount"),
        CheckConstraint("monthly_deduction >= 0", name="monthly_deduction"),
        CheckConstraint("outstanding_balance >= 0", name="outstanding_balance"),
        CheckConstraint("repayment_months > 0", name="repayment_months"),
        CheckConstraint(
            "repayment_start_month = date_trunc('month', repayment_start_month)::date",
            name="repayment_start_month",
        ),
        CheckConstraint("status IN ('pending', 'active', 'settled', 'cancelled')", name="status"),
        CheckConstraint(
            "status <> 'cancelled' OR coalesce(btrim(rejection_reason), '') <> ''",
            name="cancelled_reason",
        ),
        Index("ix_salary_advances_employee_id", "employee_id"),
        Index("ix_salary_advances_status", "status"),
        Index("ix_salary_advances_branch_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    disbursed_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    repayment_start_month: Mapped[date] = mapped_column(
        Date(),
        nullable=False,
        server_default=text("date_trunc('month', CURRENT_DATE)::date"),
    )
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    repayment_months: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("1")
    )
    monthly_deduction: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    outstanding_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'active'"))
    rejection_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AdvanceRepayment(Base):
    __tablename__ = "advance_repayments"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["advance_id", "company_id", "branch_id"],
            ["salary_advances.id", "salary_advances.company_id", "salary_advances.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["payroll_run_id", "company_id", "branch_id"],
            ["payroll_runs.id", "payroll_runs.company_id", "payroll_runs.branch_id"],
            ondelete="SET NULL (payroll_run_id)",
        ),
        UniqueConstraint(
            "advance_id",
            "idempotency_key",
            name="uq_advance_repayments_advance_id_idempotency_key",
        ),
        CheckConstraint("amount > 0", name="amount"),
        Index("ix_advance_repayments_advance_id", "advance_id"),
        Index("ix_advance_repayments_payroll_run_id", "payroll_run_id"),
        Index("ix_advance_repayments_company_id_branch_id", "company_id", "branch_id"),
        Index(
            "uq_advance_repayment_payroll",
            "advance_id",
            "payroll_run_id",
            unique=True,
            postgresql_where=text("payroll_run_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    advance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_date: Mapped[date] = mapped_column(
        Date(), nullable=False, server_default=text("CURRENT_DATE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ExpenseClaim(Base):
    __tablename__ = "expense_claims"
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
            ["payroll_run_id", "company_id", "branch_id"],
            ["payroll_runs.id", "payroll_runs.company_id", "payroll_runs.branch_id"],
            ondelete="SET NULL (payroll_run_id)",
        ),
        ForeignKeyConstraint(["approved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["manager_approved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("amount > 0", name="amount"),
        CheckConstraint(
            "status IN ('pending', 'manager_approved', 'manager_rejected', 'approved', "
            "'paid', 'rejected')",
            name="status",
        ),
        CheckConstraint(
            "status <> 'manager_approved' OR (manager_approved_by_app_user_id IS NOT NULL "
            "AND manager_approved_at IS NOT NULL)",
            name="manager_approved_fields",
        ),
        CheckConstraint(
            "status <> 'manager_rejected' OR (manager_approved_by_app_user_id IS NOT NULL "
            "AND manager_approved_at IS NOT NULL AND btrim(manager_rejection_reason) <> '')",
            name="manager_rejected_fields",
        ),
        CheckConstraint(
            "status NOT IN ('approved', 'paid', 'rejected') OR (approved_by_app_user_id IS NOT "
            "NULL AND approved_at IS NOT NULL)",
            name="hr_decision_fields",
        ),
        CheckConstraint(
            "status <> 'rejected' OR btrim(rejection_reason) <> ''", name="rejection_fields"
        ),
        Index("ix_expense_claims_employee_id", "employee_id"),
        Index("ix_expense_claims_status", "status"),
        Index("ix_expense_claims_branch_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'other'"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date(), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    receipt_url: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'pending'"))
    rejection_reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manager_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manager_approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    manager_rejection_reason: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ComplianceOverride(Base):
    __tablename__ = "compliance_overrides"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="SET NULL (branch_id)",
        ),
        ForeignKeyConstraint(["created_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint("override_type IN ('payroll_sif', 'roster_publish')", name="override_type"),
        Index("ix_compliance_overrides_company_id_branch_id", "company_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    override_type: Mapped[str] = mapped_column(Text(), nullable=False)
    employee_ids: Mapped[list[Any] | None] = mapped_column(JSONB(), nullable=True)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    created_by_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
