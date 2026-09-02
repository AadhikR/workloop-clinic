import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmployeeJobHistory(Base):
    __tablename__ = "employee_job_history"
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
        ForeignKeyConstraint(["changed_by_app_user_id"], ["app_users.id"], ondelete="SET NULL"),
        CheckConstraint(
            "change_type IN ('title_change', 'department_change', 'salary_change', "
            "'status_change')",
            name="change_type",
        ),
        Index(
            "ix_employee_job_history_employee_id_changed_at",
            "employee_id",
            text("changed_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    changed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    change_type: Mapped[str] = mapped_column(Text(), nullable=False)
    old_value: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    new_value: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["parent_id", "company_id", "branch_id"],
            ["departments.id", "departments.company_id", "departments.branch_id"],
            ondelete="SET NULL (parent_id)",
        ),
        ForeignKeyConstraint(
            ["head_employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_departments_head_employee_id_employees",
            ondelete="SET NULL (head_employee_id)",
        ),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_departments_id_company_id_branch_id"
        ),
        UniqueConstraint("branch_id", "name", name="uq_departments_branch_id_name"),
        Index("ix_departments_company_id_branch_id", "company_id", "branch_id"),
        Index("ix_departments_parent_id", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    head_employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    color: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'#6366f1'"))
    description: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    sort_order: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class DepartmentStaffingRule(Base):
    __tablename__ = "department_staffing_rules"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "branch_id",
            "department",
            "shift_category",
            name="uq_department_staffing_rules_branch_department_category",
        ),
        CheckConstraint(
            "shift_category IN ('morning', 'afternoon', 'night', 'flexible')",
            name="shift_category",
        ),
        CheckConstraint("min_staff >= 0", name="min_staff"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="effective_dates",
        ),
        Index("ix_department_staffing_rules_branch_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    department: Mapped[str] = mapped_column(Text(), nullable=False)
    shift_category: Mapped[str] = mapped_column(Text(), nullable=False)
    min_staff: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("1"))
    effective_from: Mapped[date | None] = mapped_column(Date(), nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date(), nullable=True)
