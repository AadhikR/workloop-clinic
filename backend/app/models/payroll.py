import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
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
        CheckConstraint(
            "source_snapshot_digest='' OR source_snapshot_digest~'^[0-9a-f]{64}$'",
            name="source_snapshot_digest",
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
    source_snapshot_digest: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
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
        CheckConstraint("jsonb_typeof(source_snapshot)='object'", name="source_snapshot_object"),
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
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB(), nullable=False, server_default=text("'{}'")
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
        UniqueConstraint(
            "id",
            "company_id",
            "branch_id",
            name="uq_expense_claims_id_company_id_branch_id",
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


class ExpenseReceipt(Base):
    __tablename__ = "expense_receipts"
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
            ["created_by_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["expense_claim_id", "company_id", "branch_id"],
            ["expense_claims.id", "expense_claims.company_id", "expense_claims.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("expense_claim_id", name="uq_expense_receipts_expense_claim_id"),
        UniqueConstraint(
            "submission_token_digest", name="uq_expense_receipts_submission_token_digest"
        ),
        CheckConstraint(
            "status IN ('pending','uploading','staged','attached','cleanup_pending','removed')",
            name="status",
        ),
        CheckConstraint("octet_length(submission_token_digest)=32", name="submission_token_digest"),
        CheckConstraint(
            "((file_name IS NULL AND content_type IS NULL AND size_bytes IS NULL "
            "AND sha256 IS NULL AND object_key IS NULL) OR "
            "(file_name IS NOT NULL AND content_type IS NOT NULL AND size_bytes IS NOT NULL "
            "AND sha256 IS NOT NULL AND object_key IS NOT NULL))",
            name="metadata_completeness",
        ),
        CheckConstraint(
            "file_name IS NULL OR octet_length(file_name) BETWEEN 1 AND 180", name="file_name"
        ),
        CheckConstraint(
            "content_type IS NULL OR content_type IN ('application/pdf','image/png','image/jpeg')",
            name="content_type",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes BETWEEN 1 AND 10485760", name="size_bytes"
        ),
        CheckConstraint("sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        CheckConstraint(
            "object_key IS NULL OR (octet_length(object_key) BETWEEN 1 AND 1024 "
            "AND object_key !~ '[[:cntrl:]\\\\]' AND left(object_key,1)<>'/' "
            "AND object_key NOT LIKE '%//%' AND ('/'||object_key||'/') NOT LIKE '%/./%' "
            "AND ('/'||object_key||'/') NOT LIKE '%/../%')",
            name="object_key",
        ),
        CheckConstraint(
            "(status='pending' AND file_name IS NULL AND content_type IS NULL "
            "AND size_bytes IS NULL AND sha256 IS NULL AND object_key IS NULL "
            "AND token_consumed_at IS NULL AND expires_at=created_at+interval '15 minutes' "
            "AND uploaded_at IS NULL AND attached_at IS NULL "
            "AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            "(status='uploading' AND file_name IS NULL AND content_type IS NULL "
            "AND size_bytes IS NULL AND sha256 IS NULL AND object_key IS NULL "
            "AND token_consumed_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND uploaded_at IS NULL AND attached_at IS NULL "
            "AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            "(status='staged' AND file_name IS NOT NULL AND content_type IS NOT NULL "
            "AND size_bytes IS NOT NULL AND sha256 IS NOT NULL AND object_key IS NOT NULL "
            "AND token_consumed_at IS NOT NULL AND uploaded_at IS NOT NULL "
            "AND expires_at=uploaded_at+interval '24 hours' AND expense_claim_id IS NULL "
            "AND attached_at IS NULL AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            "(status='attached' AND file_name IS NOT NULL AND content_type IS NOT NULL "
            "AND size_bytes IS NOT NULL AND sha256 IS NOT NULL AND object_key IS NOT NULL "
            "AND token_consumed_at IS NOT NULL AND uploaded_at IS NOT NULL "
            "AND expires_at IS NULL AND expense_claim_id IS NOT NULL "
            "AND attached_at IS NOT NULL AND cleanup_requested_at IS NULL "
            "AND removed_at IS NULL) OR "
            "(status='cleanup_pending' AND file_name IS NOT NULL "
            "AND content_type IS NOT NULL AND size_bytes IS NOT NULL AND sha256 IS NOT NULL "
            "AND object_key IS NOT NULL AND cleanup_requested_at IS NOT NULL "
            "AND removed_at IS NULL) OR "
            "(status='removed' AND file_name IS NOT NULL AND content_type IS NOT NULL "
            "AND size_bytes IS NOT NULL AND sha256 IS NOT NULL AND object_key IS NOT NULL "
            "AND removed_at IS NOT NULL)",
            name="lifecycle",
        ),
        CheckConstraint(
            "updated_at>=created_at AND (expires_at IS NULL OR expires_at>=created_at) "
            "AND (token_consumed_at IS NULL OR token_consumed_at>=created_at) "
            "AND (uploaded_at IS NULL OR uploaded_at>=created_at) "
            "AND (attached_at IS NULL OR attached_at>=created_at) "
            "AND (cleanup_requested_at IS NULL OR cleanup_requested_at>=created_at) "
            "AND (removed_at IS NULL OR removed_at>=created_at)",
            name="timestamps",
        ),
        Index("ix_expense_receipts_employee_scope", "company_id", "branch_id", "employee_id"),
        Index(
            "ix_expense_receipts_staged_expiry",
            "expires_at",
            "id",
            postgresql_where=text("status='staged'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expense_claim_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    submission_token_digest: Mapped[bytes] = mapped_column(LargeBinary(), nullable=False)
    file_name: Mapped[str | None] = mapped_column(Text(), nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    sha256: Mapped[str | None] = mapped_column(Text(), nullable=True)
    object_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'pending'"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleanup_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("statement_timestamp()")
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
        ForeignKeyConstraint(
            ["payroll_run_id", "company_id", "branch_id"],
            ["payroll_runs.id", "payroll_runs.company_id", "payroll_runs.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["payroll_entry_id"], ["payroll_entries.id"], ondelete="RESTRICT"),
        CheckConstraint("override_type IN ('payroll_sif', 'roster_publish')", name="override_type"),
        CheckConstraint(
            "rule_code IS NULL OR rule_code IN ('visa_expired','emirates_id_expired',"
            "'labour_card_expired','passport_expired','professional_licence_expired',"
            "'leave_conflict','staffing_shortfall')",
            name="rule_code",
        ),
        CheckConstraint(
            "(override_type<>'roster_publish' AND roster_month IS NULL "
            "AND violation_digest IS NULL AND violation_snapshot IS NULL) OR "
            "(override_type='roster_publish' AND branch_id IS NOT NULL "
            "AND payroll_run_id IS NULL AND payroll_entry_id IS NULL "
            "AND rule_code IN ('leave_conflict','staffing_shortfall') "
            "AND roster_month ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$' "
            "AND violation_digest ~ '^sha256:[0-9a-f]{64}$' "
            "AND jsonb_typeof(violation_snapshot)='object' "
            "AND octet_length(btrim(reason)) BETWEEN 10 AND 500)",
            name="phase10g_roster_override",
        ),
        Index("ix_compliance_overrides_company_id_branch_id", "company_id", "branch_id"),
        Index("ix_compliance_overrides_payroll_run_id", "payroll_run_id"),
        Index("ix_compliance_overrides_payroll_entry_id", "payroll_entry_id"),
        Index(
            "uq_compliance_overrides_roster_violation",
            "branch_id",
            "roster_month",
            "violation_digest",
            unique=True,
            postgresql_where=text("override_type='roster_publish'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    override_type: Mapped[str] = mapped_column(Text(), nullable=False)
    employee_ids: Mapped[list[Any] | None] = mapped_column(JSONB(), nullable=True)
    payroll_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payroll_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    rule_code: Mapped[str | None] = mapped_column(Text(), nullable=True)
    roster_month: Mapped[str | None] = mapped_column(Text(), nullable=True)
    violation_digest: Mapped[str | None] = mapped_column(Text(), nullable=True)
    violation_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB(), nullable=True)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    created_by_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
