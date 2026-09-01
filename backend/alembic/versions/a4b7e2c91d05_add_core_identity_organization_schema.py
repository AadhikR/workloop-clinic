"""Add core identity and organization schema.

Revision ID: a4b7e2c91d05
Revises: f41c9a7b23d1
Created: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a4b7e2c91d05"
down_revision: str | Sequence[str] | None = "f41c9a7b23d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies", sa.Column("name", sa.Text(), server_default=sa.text("''"), nullable=False)
    )
    op.add_column(
        "companies", sa.Column("sector", sa.Text(), server_default=sa.text("''"), nullable=False)
    )
    op.add_column(
        "companies",
        sa.Column(
            "nafis_quota_percent", sa.Numeric(5, 2), server_default=sa.text("2.00"), nullable=False
        ),
    )
    op.add_column(
        "companies",
        sa.Column("enable_nafis", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "companies",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "nafis_quota_percent", "companies", "nafis_quota_percent BETWEEN 0 AND 100"
    )
    op.create_index("ix_companies_name", "companies", ["name"])

    op.create_table(
        "branches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("mol_employer_id", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "default_bank_routing_code", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("address", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("contact_email", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("default_salary_day", sa.Integer(), server_default=sa.text("25"), nullable=True),
        sa.Column(
            "work_location_type", sa.Text(), server_default=sa.text("'Mainland'"), nullable=False
        ),
        sa.Column("free_zone_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("logo_url", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("enable_staffing_rules", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "enable_biometric_import", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "default_salary_day IS NULL OR default_salary_day BETWEEN 1 AND 31",
            name="default_salary_day",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_branches_company_id_companies",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "company_id", name="uq_branches_id_company_id"),
        sa.UniqueConstraint("company_id", "name", name="uq_branches_company_id_name"),
    )
    op.create_index("ix_branches_company_id", "branches", ["company_id"])

    employee_columns = (
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("emp_no", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("mol_id", sa.Text(), nullable=False),
        sa.Column("bank_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("bank_routing_code", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("iban", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("basic_salary", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("allowance", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("personal_email", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("work_email", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("phone", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("marital_status", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("home_country_address", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("photo_url", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "emergency_contact_name", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "emergency_contact_relationship",
            sa.Text(),
            server_default=sa.text("''"),
            nullable=False,
        ),
        sa.Column(
            "emergency_contact_phone", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("job_title", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("department", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("reporting_manager_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("employment_start_date", sa.Date(), nullable=True),
        sa.Column("probation_end_date", sa.Date(), nullable=True),
        sa.Column("probation_extended", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "contract_type", sa.Text(), server_default=sa.text("'Unlimited'"), nullable=False
        ),
        sa.Column("contract_end_date", sa.Date(), nullable=True),
        sa.Column(
            "employment_status", sa.Text(), server_default=sa.text("'Active'"), nullable=False
        ),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("termination_reason", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "housing_allowance", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "transport_allowance", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "other_allowances", sa.Numeric(12, 2), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "other_allowances_label", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column("bank_account_holder", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("nationality", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("visa_type", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("visa_number", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("visa_expiry", sa.Date(), nullable=True),
        sa.Column("passport_number", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("passport_expiry", sa.Date(), nullable=True),
        sa.Column("emirates_id", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("emirates_id_expiry", sa.Date(), nullable=True),
        sa.Column("labour_card_number", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("labour_card_expiry", sa.Date(), nullable=True),
        sa.Column("sponsoring_entity", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "work_location_type", sa.Text(), server_default=sa.text("'Mainland'"), nullable=False
        ),
        sa.Column("free_zone_name", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("nafis_registration_no", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("shift_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("licence_authority", sa.Text(), server_default=sa.text("'None'"), nullable=False),
        sa.Column("licence_number", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("licence_expiry", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    for column in employee_columns:
        op.add_column("employees", column)

    op.create_unique_constraint(
        "uq_employees_id_company_id_branch_id", "employees", ["id", "company_id", "branch_id"]
    )
    op.create_foreign_key(
        "fk_employees_branch_id_branches",
        "employees",
        "branches",
        ["branch_id", "company_id"],
        ["id", "company_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_employees_reporting_manager_id_employees",
        "employees",
        "employees",
        ["reporting_manager_id", "company_id", "branch_id"],
        ["id", "company_id", "branch_id"],
        ondelete="SET NULL (reporting_manager_id)",
    )
    for column in (
        "basic_salary",
        "allowance",
        "housing_allowance",
        "transport_allowance",
        "other_allowances",
    ):
        op.create_check_constraint(column, "employees", f"{column} >= 0")
    op.create_check_constraint(
        "employment_status",
        "employees",
        "employment_status IN ('Active', 'Probation', 'On Leave', 'Terminated')",
    )
    op.create_check_constraint(
        "contract_type", "employees", "contract_type IN ('Limited', 'Unlimited')"
    )
    op.create_check_constraint(
        "visa_type",
        "employees",
        "visa_type IN ('', 'Employment Visa', 'Investor Visa', 'Dependent Visa', "
        "'Tourist (Temp)', 'Exempt')",
    )
    op.create_index("ix_employees_company_id", "employees", ["company_id"])
    op.create_index("ix_employees_branch_id", "employees", ["branch_id"])
    op.create_index("ix_employees_active", "employees", ["active"])
    op.create_index("ix_employees_reporting_manager_id", "employees", ["reporting_manager_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_employees_work_email_nonempty ON employees "
        "(company_id, lower(btrim(work_email))) WHERE btrim(work_email) <> ''"
    )

    op.create_unique_constraint(
        "uq_user_profiles_app_user_id_company_id", "user_profiles", ["app_user_id", "company_id"]
    )
    op.create_index("ix_user_profiles_company_id", "user_profiles", ["company_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_user_profiles_employee_id ON user_profiles "
        "(employee_id) WHERE employee_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX uq_user_profiles_employee_id")
    op.execute("DROP INDEX IF EXISTS ix_user_profiles_company_id")
    op.drop_constraint("uq_user_profiles_app_user_id_company_id", "user_profiles", type_="unique")
    op.execute("DROP INDEX uq_employees_work_email_nonempty")
    for index in (
        "ix_employees_reporting_manager_id",
        "ix_employees_active",
        "ix_employees_branch_id",
        "ix_employees_company_id",
    ):
        op.drop_index(index, table_name="employees")
    for constraint in (
        "visa_type",
        "contract_type",
        "employment_status",
        "other_allowances",
        "transport_allowance",
        "housing_allowance",
        "allowance",
        "basic_salary",
    ):
        op.drop_constraint(op.f(f"ck_employees_{constraint}"), "employees", type_="check")
    op.drop_constraint(
        "fk_employees_reporting_manager_id_employees", "employees", type_="foreignkey"
    )
    op.drop_constraint("fk_employees_branch_id_branches", "employees", type_="foreignkey")
    op.drop_constraint("uq_employees_id_company_id_branch_id", "employees", type_="unique")
    for column in reversed(
        (
            "branch_id",
            "emp_no",
            "name",
            "mol_id",
            "bank_name",
            "bank_routing_code",
            "iban",
            "basic_salary",
            "allowance",
            "active",
            "personal_email",
            "work_email",
            "phone",
            "date_of_birth",
            "gender",
            "marital_status",
            "home_country_address",
            "photo_url",
            "emergency_contact_name",
            "emergency_contact_relationship",
            "emergency_contact_phone",
            "job_title",
            "department",
            "reporting_manager_id",
            "employment_start_date",
            "probation_end_date",
            "probation_extended",
            "contract_type",
            "contract_end_date",
            "employment_status",
            "termination_date",
            "termination_reason",
            "housing_allowance",
            "transport_allowance",
            "other_allowances",
            "other_allowances_label",
            "bank_account_holder",
            "nationality",
            "visa_type",
            "visa_number",
            "visa_expiry",
            "passport_number",
            "passport_expiry",
            "emirates_id",
            "emirates_id_expiry",
            "labour_card_number",
            "labour_card_expiry",
            "sponsoring_entity",
            "work_location_type",
            "free_zone_name",
            "nafis_registration_no",
            "shift_id",
            "licence_authority",
            "licence_number",
            "licence_expiry",
            "created_at",
            "updated_at",
        )
    ):
        op.drop_column("employees", column)
    op.drop_index("ix_branches_company_id", table_name="branches")
    op.drop_table("branches")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_constraint(op.f("ck_companies_nafis_quota_percent"), "companies", type_="check")
    for column in (
        "updated_at",
        "created_at",
        "enable_nafis",
        "nafis_quota_percent",
        "sector",
        "name",
    ):
        op.drop_column("companies", column)
