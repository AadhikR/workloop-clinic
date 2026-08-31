"""Add minimal identity schema.

Revision ID: f41c9a7b23d1
Revises:
Created: 2026-08-31 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f41c9a7b23d1"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

app_role = postgresql.ENUM("admin", "manager", "employee", name="app_role", create_type=False)
account_status = postgresql.ENUM(
    "pending_identity", "active", "disabled", name="account_status", create_type=False
)


def upgrade() -> None:
    app_role.create(op.get_bind(), checkfirst=False)
    account_status.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "company_id", name="uq_employees_id_company_id"),
    )
    op.create_table(
        "app_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_issuer", sa.Text(), nullable=False),
        sa.Column("identity_subject", sa.Text(), nullable=False),
        sa.Column(
            "status",
            account_status,
            server_default=sa.text("'pending_identity'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity_issuer", "identity_subject"),
    )
    op.create_table(
        "user_profiles",
        sa.Column("app_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", app_role, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role = 'admin' AND employee_id IS NULL) OR "
            "(role IN ('manager', 'employee') AND employee_id IS NOT NULL)",
            name="role_employee_link",
        ),
        sa.ForeignKeyConstraint(["app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id"],
            ["employees.id", "employees.company_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("app_user_id"),
    )

    op.execute("GRANT USAGE ON SCHEMA public TO workloop_runtime")
    op.execute(
        "GRANT SELECT ON TABLE companies, employees, app_users, user_profiles TO workloop_runtime"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT ON TABLE companies, employees, app_users, user_profiles "
        "FROM workloop_runtime"
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM workloop_runtime")
    op.drop_table("user_profiles")
    op.drop_table("app_users")
    op.drop_table("employees")
    op.drop_table("companies")
    account_status.drop(op.get_bind(), checkfirst=False)
    app_role.drop(op.get_bind(), checkfirst=False)
