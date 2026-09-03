"""Add least-privilege runtime grants for the Phase 4B/4C business schema.

Revision ID: a0d4e6f8c92b
Revises: 9f3c7b5d2a18
Created: 2026-09-03 00:00:00.000000

Phase 4D, part 3 of 3. Grants ``workloop_runtime`` an explicit, per-table,
least-privilege privilege set on the 50 business tables added in Phase 4B and
4C, following the pattern set by ``f41c9a7b23d1``. There is no
``GRANT ... ON ALL TABLES``, no ``PUBLIC`` grant, no default privilege, and no
grant to any Supabase-era browser or service role. No ``DELETE`` or
``TRUNCATE`` is granted anywhere: the only delete path in the schema is inside
``replace_payroll_entries``, which runs SECURITY DEFINER, and every other
purge is deferred to a Phase 5 endpoint-specific review.

The four identity tables (``companies``, ``employees``, ``app_users``,
``user_profiles``) keep the Phase 3 read-only ``SELECT`` grant unchanged;
identity writes wait for the Phase 5 permission matrix.

Grant classes:
- SELECT only: rows the runtime reads but only ever writes through a definer
  function (``advance_repayments``, written solely by ``record_advance_repayment``).
- SELECT, INSERT: append-only history, audit, log, and issued-snapshot tables
  that are created and read but never updated in place.
- SELECT, INSERT, UPDATE: operational tables whose rows are created, read, and
  mutated by the application.

Execute grants: the three retained business functions to ``workloop_runtime``.
``set_updated_at`` is a trigger helper and takes no execute grant.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a0d4e6f8c92b"
down_revision: str | Sequence[str] | None = "9f3c7b5d2a18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Written only through the SECURITY DEFINER record_advance_repayment function.
SELECT_ONLY: tuple[str, ...] = ("advance_repayments",)

# Append-only history, audit, log, and issued-snapshot tables.
SELECT_INSERT: tuple[str, ...] = (
    "employee_job_history",
    "payslips",
    "payroll_approval_log",
    "compliance_overrides",
    "leave_audit_log",
    "clock_events",
    "attendance_audit_log",
    "employee_contracts",
)

# Operational tables: created, read, and mutated by the application.
SELECT_INSERT_UPDATE: tuple[str, ...] = (
    "branches",
    "departments",
    "department_staffing_rules",
    "payroll_runs",
    "payroll_entries",
    "nafis_reports",
    "salary_advances",
    "expense_claims",
    "leave_settings",
    "leave_types",
    "public_holidays",
    "leave_requests",
    "leave_balances",
    "leave_approval_delegates",
    "attendance_settings",
    "shifts",
    "shift_assignments",
    "attendance_records",
    "attendance_periods",
    "regularisation_requests",
    "roster_assignments",
    "shift_swap_requests",
    "biometric_mappings",
    "employee_documents",
    "insurance_policies",
    "employee_insurance",
    "insurance_dependants",
    "notifications",
    "offboarding_checklists",
    "offboarding_tasks",
    "offboarding_task_templates",
    "assets",
    "asset_assignments",
    "training_records",
    "certifications",
    "appraisal_cycles",
    "appraisals",
    "appraisal_sections",
    "cme_requirements",
    "incident_reports",
    "letter_requests",
)

FUNCTION_SIGNATURES: tuple[str, ...] = (
    "replace_payroll_entries(uuid, jsonb)",
    "record_advance_repayment(uuid, uuid, uuid, numeric, date)",
    "admin_execute_shift_swap(uuid, uuid)",
)

# Guard: the three classes must cover exactly the 50 business tables, disjointly.
_ALL = SELECT_ONLY + SELECT_INSERT + SELECT_INSERT_UPDATE
assert len(_ALL) == 50, f"expected 50 business tables, got {len(_ALL)}"
assert len(set(_ALL)) == 50, "business table classes overlap"


def upgrade() -> None:
    for table in SELECT_ONLY:
        op.execute(f"GRANT SELECT ON TABLE {table} TO workloop_runtime")
    for table in SELECT_INSERT:
        op.execute(f"GRANT SELECT, INSERT ON TABLE {table} TO workloop_runtime")
    for table in SELECT_INSERT_UPDATE:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO workloop_runtime")
    for signature in FUNCTION_SIGNATURES:
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO workloop_runtime")


def downgrade() -> None:
    for signature in FUNCTION_SIGNATURES:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM workloop_runtime")
    for table in SELECT_INSERT_UPDATE:
        op.execute(f"REVOKE SELECT, INSERT, UPDATE ON TABLE {table} FROM workloop_runtime")
    for table in SELECT_INSERT:
        op.execute(f"REVOKE SELECT, INSERT ON TABLE {table} FROM workloop_runtime")
    for table in SELECT_ONLY:
        op.execute(f"REVOKE SELECT ON TABLE {table} FROM workloop_runtime")
