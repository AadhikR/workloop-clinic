"""Add people and organization schema.

Revision ID: 3f9a1c7b2e10
Revises: a4b7e2c91d05
Created: 2026-09-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "3f9a1c7b2e10"
down_revision: str | Sequence[str] | None = "a4b7e2c91d05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_job_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("changed_by_app_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("new_value", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.CheckConstraint(
            "change_type IN ('title_change', 'department_change', 'salary_change', "
            "'status_change')",
            name="change_type",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_employee_job_history_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_employee_job_history_branch_id_branches",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_employee_job_history_employee_id_employees",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_app_user_id"],
            ["app_users.id"],
            name="fk_employee_job_history_changed_by_app_user_id_app_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_employee_job_history"),
    )
    op.create_index(
        "ix_employee_job_history_employee_id_changed_at",
        "employee_job_history",
        ["employee_id", sa.text("changed_at DESC")],
    )

    op.create_table(
        "departments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("head_employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("color", sa.Text(), server_default=sa.text("'#6366f1'"), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_departments_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_departments_branch_id_branches",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id", "company_id", "branch_id"],
            ["departments.id", "departments.company_id", "departments.branch_id"],
            name="fk_departments_parent_id_departments",
            ondelete="SET NULL (parent_id)",
        ),
        sa.ForeignKeyConstraint(
            ["head_employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_departments_head_employee_id_employees",
            ondelete="SET NULL (head_employee_id)",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_departments"),
        sa.UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_departments_id_company_id_branch_id"
        ),
        sa.UniqueConstraint("branch_id", "name", name="uq_departments_branch_id_name"),
    )
    op.create_index(
        "ix_departments_company_id_branch_id", "departments", ["company_id", "branch_id"]
    )
    op.create_index("ix_departments_parent_id", "departments", ["parent_id"])

    op.create_table(
        "department_staffing_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("shift_category", sa.Text(), nullable=False),
        sa.Column("min_staff", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "shift_category IN ('morning', 'afternoon', 'night', 'flexible')",
            name="shift_category",
        ),
        sa.CheckConstraint("min_staff >= 0", name="min_staff"),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="effective_dates",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_department_staffing_rules_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_department_staffing_rules_branch_id_branches",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_department_staffing_rules"),
        sa.UniqueConstraint(
            "branch_id",
            "department",
            "shift_category",
            name="uq_department_staffing_rules_branch_department_category",
        ),
    )
    op.create_index(
        "ix_department_staffing_rules_branch_id", "department_staffing_rules", ["branch_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_department_staffing_rules_branch_id", table_name="department_staffing_rules")
    op.drop_table("department_staffing_rules")
    op.drop_index("ix_departments_parent_id", table_name="departments")
    op.drop_index("ix_departments_company_id_branch_id", table_name="departments")
    op.drop_table("departments")
    op.drop_index(
        "ix_employee_job_history_employee_id_changed_at", table_name="employee_job_history"
    )
    op.drop_table("employee_job_history")
