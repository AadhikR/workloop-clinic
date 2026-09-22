from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
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


class RosterMonth(Base):
    __tablename__ = "roster_months"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["current_version_id"],
            ["roster_publication_versions.id"],
            name="fk_roster_months_current_version_id_roster_publication_versions",
            ondelete="RESTRICT",
            use_alter=True,
        ),
        ForeignKeyConstraint(["published_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint("branch_id", "period", name="uq_roster_months_branch_id_period"),
        CheckConstraint("status IN ('draft','published')", name="status"),
        CheckConstraint("period ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$'", name="period"),
        CheckConstraint(
            "(status='draft' AND version=0 AND current_version_id IS NULL AND "
            "source_version IS NULL AND published_at IS NULL AND "
            "published_by_app_user_id IS NULL) OR "
            "(status='published' AND version>=1 AND current_version_id IS NOT NULL AND "
            "source_version ~ '^sha256:[0-9a-f]{64}$' AND published_at IS NOT NULL AND "
            "published_by_app_user_id IS NOT NULL)",
            name="state",
        ),
        Index("ix_roster_months_scope_period", "company_id", "branch_id", "period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'draft'"))
    version: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_version: Mapped[str | None] = mapped_column(Text(), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RosterPublicationVersion(Base):
    __tablename__ = "roster_publication_versions"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["roster_month_id"], ["roster_months.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["prior_version_id"], ["roster_publication_versions.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "roster_month_id", "version", name="uq_roster_publication_versions_month_version"
        ),
        UniqueConstraint("source_version", name="uq_roster_publication_versions_source_version"),
        CheckConstraint("period ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$'", name="period"),
        CheckConstraint("version >= 1 AND record_count >= 1", name="counts"),
        CheckConstraint(
            "kind IN ('publication','actual_hours','overtime_approval','swap')", name="kind"
        ),
        CheckConstraint(
            "source_version ~ '^sha256:[0-9a-f]{64}$' AND "
            "affected_row_digest ~ '^sha256:[0-9a-f]{64}$'",
            name="digests",
        ),
        CheckConstraint(
            "jsonb_typeof(source_payload)='object' AND source_canonical::jsonb=source_payload",
            name="payload",
        ),
        CheckConstraint(
            "(version=1 AND prior_version_id IS NULL AND kind='publication') OR "
            "(version>1 AND prior_version_id IS NOT NULL AND kind<>'publication' AND "
            "octet_length(btrim(reason)) BETWEEN 3 AND 500)",
            name="transition",
        ),
        Index(
            "ix_roster_publication_versions_scope_period_version",
            "company_id",
            "branch_id",
            "period",
            "version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    roster_month_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prior_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    period: Mapped[str] = mapped_column(Text(), nullable=False)
    version: Mapped[int] = mapped_column(Integer(), nullable=False)
    kind: Mapped[str] = mapped_column(Text(), nullable=False)
    source_version: Mapped[str] = mapped_column(Text(), nullable=False)
    source_canonical: Mapped[str] = mapped_column(Text(), nullable=False)
    source_payload: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False)
    affected_row_digest: Mapped[str] = mapped_column(Text(), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    actor_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RosterActualHoursEvidence(Base):
    __tablename__ = "roster_actual_hours_evidence"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["roster_month_id"], ["roster_months.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["source_assignment_id"], ["roster_assignments.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["prior_evidence_id"], ["roster_actual_hours_evidence.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint("actual_hours BETWEEN 0 AND 24", name="hours"),
        CheckConstraint("octet_length(btrim(reason)) BETWEEN 3 AND 500", name="reason"),
        Index(
            "ix_roster_actual_hours_scope_assignment",
            "company_id",
            "branch_id",
            "roster_month_id",
            "source_assignment_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    roster_month_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prior_evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    evidence_source: Mapped[str] = mapped_column(Text(), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    actor_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RosterOvertimeApproval(Base):
    __tablename__ = "roster_overtime_approvals"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["roster_month_id"], ["roster_months.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["source_assignment_id"], ["roster_assignments.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["actual_evidence_id"], ["roster_actual_hours_evidence.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        CheckConstraint(
            "overtime_hours > 0 AND overtime_amount >= 0 AND attendance_overlap_hours=0",
            name="amounts",
        ),
        CheckConstraint("salary_source_version <> ''", name="salary_source"),
        CheckConstraint("octet_length(btrim(reason)) BETWEEN 3 AND 500", name="reason"),
        Index(
            "ix_roster_overtime_scope_assignment",
            "company_id",
            "branch_id",
            "roster_month_id",
            "source_assignment_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    roster_month_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actual_evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    overtime_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    attendance_overlap_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    attendance_source_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("ARRAY[]::uuid[]")
    )
    salary_source_version: Mapped[str] = mapped_column(Text(), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    actor_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RosterPublicationMembership(Base):
    __tablename__ = "roster_publication_memberships"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["publication_version_id"], ["roster_publication_versions.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["source_assignment_id"], ["roster_assignments.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shift_id", "company_id", "branch_id"],
            ["shifts.id", "shifts.company_id", "shifts.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actual_evidence_id"], ["roster_actual_hours_evidence.id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["overtime_approval_id"], ["roster_overtime_approvals.id"], ondelete="RESTRICT"
        ),
        UniqueConstraint(
            "publication_version_id",
            "source_assignment_id",
            name="uq_roster_publication_memberships_version_assignment",
        ),
        CheckConstraint(
            "planned_hours BETWEEN 0.25 AND 24 AND "
            "(actual_hours IS NULL OR actual_hours BETWEEN 0 AND 24) AND "
            "overtime_hours >= 0 AND overtime_amount >= 0 AND attendance_overlap_hours >= 0",
            name="hours",
        ),
        CheckConstraint(
            "(actual_evidence_id IS NULL AND actual_hours IS NULL AND "
            "overtime_approval_id IS NULL AND overtime_hours=0 AND overtime_amount=0) OR "
            "(actual_evidence_id IS NOT NULL AND actual_hours IS NOT NULL AND "
            "((overtime_approval_id IS NULL AND overtime_hours=0 AND overtime_amount=0) OR "
            "(actual_hours>planned_hours AND overtime_approval_id IS NOT NULL AND "
            "overtime_hours=actual_hours-planned_hours AND attendance_overlap_hours=0)))",
            name="evidence",
        ),
        Index(
            "ix_roster_publication_memberships_version_employee",
            "publication_version_id",
            "employee_id",
            "date",
            "source_assignment_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    publication_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_assignment_version: Mapped[int] = mapped_column(Integer(), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_name: Mapped[str] = mapped_column(Text(), nullable=False)
    department: Mapped[str] = mapped_column(Text(), nullable=False)
    shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    shift_name: Mapped[str] = mapped_column(Text(), nullable=False)
    shift_code: Mapped[str | None] = mapped_column(Text(), nullable=True)
    shift_category: Mapped[str] = mapped_column(Text(), nullable=False)
    date: Mapped[date] = mapped_column(Date(), nullable=False)
    planned_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    notes: Mapped[str] = mapped_column(Text(), nullable=False)
    actual_evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    overtime_approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    overtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    overtime_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, server_default=text("0")
    )
    attendance_overlap_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    attendance_source_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, server_default=text("ARRAY[]::uuid[]")
    )
    salary_source_version: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_payload: Mapped[dict[str, object]] = mapped_column(JSONB(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
