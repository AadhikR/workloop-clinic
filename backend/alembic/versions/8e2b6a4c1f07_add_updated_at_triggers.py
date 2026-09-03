"""Add canonical updated_at trigger helper and the 19 named triggers.

Revision ID: 8e2b6a4c1f07
Revises: 7d3e5a1f6c54
Created: 2026-09-03 00:00:00.000000

Phase 4D, part 1 of 3. Creates the single canonical timestamp helper
``set_updated_at`` from the approved Phase 4A catalogue and the 19 canonical
``BEFORE UPDATE`` triggers it backs, one per table that carries ``updated_at``.
The helper uses ``clock_timestamp()`` so ``updated_at`` advances even when the
row is modified more than once inside a single transaction. Four triggers are
new Phase 4A decisions (branches, roster_assignments, shift_swap_requests,
appraisals); the four legacy duplicate triggers are not recreated. No grant,
function execution privilege, or business table is added here.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8e2b6a4c1f07"
down_revision: str | Sequence[str] | None = "7d3e5a1f6c54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (trigger name, table) exactly as named in the Phase 4A catalogue.
TRIGGERS: tuple[tuple[str, str], ...] = (
    ("trg_companies_set_updated_at", "companies"),
    ("trg_branches_set_updated_at", "branches"),
    ("trg_employees_set_updated_at", "employees"),
    ("trg_payroll_runs_set_updated_at", "payroll_runs"),
    ("trg_payroll_entries_set_updated_at", "payroll_entries"),
    ("trg_salary_advances_set_updated_at", "salary_advances"),
    ("trg_leave_settings_set_updated_at", "leave_settings"),
    ("trg_leave_types_set_updated_at", "leave_types"),
    ("trg_leave_requests_set_updated_at", "leave_requests"),
    ("trg_leave_balances_set_updated_at", "leave_balances"),
    ("trg_attendance_settings_set_updated_at", "attendance_settings"),
    ("trg_shifts_set_updated_at", "shifts"),
    ("trg_attendance_records_set_updated_at", "attendance_records"),
    ("trg_roster_assignments_set_updated_at", "roster_assignments"),
    ("trg_shift_swap_requests_set_updated_at", "shift_swap_requests"),
    ("trg_expense_claims_set_updated_at", "expense_claims"),
    ("trg_appraisals_set_updated_at", "appraisals"),
    ("trg_cme_requirements_set_updated_at", "cme_requirements"),
    ("trg_incident_reports_set_updated_at", "incident_reports"),
)


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO public
        AS $$
        BEGIN
          NEW.updated_at = clock_timestamp();
          RETURN NEW;
        END;
        $$;
        """
    )
    # The helper is internal and only ever reached through a trigger. Revoke the
    # default PUBLIC execute privilege so no role can call it directly.
    op.execute("REVOKE EXECUTE ON FUNCTION set_updated_at() FROM PUBLIC")

    for trigger_name, table in TRIGGERS:
        op.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )


def downgrade() -> None:
    for trigger_name, table in TRIGGERS:
        op.execute(f"DROP TRIGGER {trigger_name} ON {table}")
    op.execute("DROP FUNCTION set_updated_at()")
