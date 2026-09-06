import os
import sys

from sqlalchemy import create_engine, text

PHASES = (
    (
        "b63e4d8a1f20",
        {
            "payroll_runs": {"SELECT", "INSERT", "UPDATE", "DELETE"},
            "payroll_entries": {"SELECT"},
            "payslips": {"SELECT", "INSERT"},
            "payroll_approval_log": {"SELECT", "INSERT"},
            "nafis_reports": {"SELECT", "INSERT", "UPDATE"},
            "salary_advances": {"SELECT", "INSERT", "UPDATE"},
            "advance_repayments": {"SELECT"},
            "expense_claims": {"SELECT", "INSERT", "UPDATE", "DELETE"},
            "compliance_overrides": {"SELECT", "INSERT"},
        },
    ),
    (
        "c74f5e9b2a31",
        {
            "leave_settings": {"SELECT", "INSERT", "UPDATE"},
            "leave_types": {"SELECT", "INSERT", "UPDATE"},
            "public_holidays": {"SELECT", "INSERT", "UPDATE", "DELETE"},
            "leave_requests": {"SELECT", "INSERT", "UPDATE"},
            "leave_audit_log": {"SELECT", "INSERT"},
            "leave_balances": {"SELECT", "INSERT", "UPDATE"},
            "leave_approval_delegates": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        },
    ),
    (
        "d85a6f0c3b42",
        {
            "attendance_settings": {"SELECT", "INSERT", "UPDATE"},
            "shifts": {"SELECT", "INSERT", "UPDATE"},
            "shift_assignments": {"SELECT", "INSERT", "UPDATE"},
            "clock_events": {"SELECT", "INSERT"},
            "attendance_records": {"SELECT", "INSERT", "UPDATE"},
            "attendance_periods": {"SELECT", "INSERT", "UPDATE"},
            "regularisation_requests": {"SELECT", "INSERT", "UPDATE"},
            "attendance_audit_log": {"SELECT", "INSERT"},
            "roster_assignments": {"SELECT", "INSERT", "UPDATE", "DELETE"},
            "shift_swap_requests": {"SELECT", "INSERT", "UPDATE"},
            "biometric_mappings": {"SELECT", "INSERT", "UPDATE", "DELETE"},
        },
    ),
)

BASELINE_GRANTS = {
    "payroll_runs": {"SELECT"},
    "payroll_entries": {"SELECT"},
    "payslips": {"SELECT", "INSERT"},
    "payroll_approval_log": {"SELECT", "INSERT"},
    "nafis_reports": {"SELECT", "INSERT", "UPDATE"},
    "salary_advances": {"SELECT"},
    "advance_repayments": {"SELECT"},
    "expense_claims": {"SELECT", "INSERT", "UPDATE"},
    "compliance_overrides": {"SELECT", "INSERT"},
    "leave_settings": {"SELECT", "INSERT", "UPDATE"},
    "leave_types": {"SELECT", "INSERT", "UPDATE"},
    "public_holidays": {"SELECT", "INSERT", "UPDATE"},
    "leave_requests": {"SELECT", "INSERT", "UPDATE"},
    "leave_audit_log": {"SELECT", "INSERT"},
    "leave_balances": {"SELECT", "INSERT", "UPDATE"},
    "leave_approval_delegates": {"SELECT", "INSERT", "UPDATE"},
    "attendance_settings": {"SELECT", "INSERT", "UPDATE"},
    "shifts": {"SELECT", "INSERT", "UPDATE"},
    "shift_assignments": {"SELECT", "INSERT", "UPDATE"},
    "clock_events": {"SELECT", "INSERT"},
    "attendance_records": {"SELECT", "INSERT", "UPDATE"},
    "attendance_periods": {"SELECT", "INSERT", "UPDATE"},
    "regularisation_requests": {"SELECT", "INSERT", "UPDATE"},
    "attendance_audit_log": {"SELECT", "INSERT"},
    "roster_assignments": {"SELECT"},
    "shift_swap_requests": {"SELECT"},
    "biometric_mappings": {"SELECT", "INSERT", "UPDATE"},
}


def expected_state(revision: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    enabled: dict[str, set[str]] = {}
    grants = {table: set(privileges) for table, privileges in BASELINE_GRANTS.items()}
    if revision == "f52e0a1b9c34":
        return enabled, grants
    for phase_revision, phase_commands in PHASES:
        enabled.update(phase_commands)
        for table, commands in phase_commands.items():
            grants[table] = set(commands)
        if phase_revision == revision:
            return enabled, grants
    raise AssertionError(f"unsupported Phase 5F revision {revision}")


def verify(revision: str) -> None:
    enabled, expected_grants = expected_state(revision)
    all_tables = list(BASELINE_GRANTS)
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            actual_revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert actual_revision == revision

            expected_policies = {
                (
                    table,
                    f"phase5f_{table}_{command.lower()}_runtime",
                    command,
                    "workloop_runtime",
                )
                for table, commands in enabled.items()
                for command in commands
            }
            actual_policies = {
                (row.tablename, row.policyname, row.cmd, row.roles[0])
                for row in connection.execute(
                    text(
                        """
SELECT tablename, policyname, cmd, roles
FROM pg_catalog.pg_policies
WHERE schemaname = 'public' AND policyname LIKE 'phase5f_%'
"""
                    )
                )
            }
            assert actual_policies == expected_policies

            flags = {
                row.relname: (row.relrowsecurity, row.relforcerowsecurity)
                for row in connection.execute(
                    text(
                        """
SELECT object.relname, object.relrowsecurity, object.relforcerowsecurity
FROM pg_catalog.pg_class AS object
JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = object.relnamespace
WHERE namespace.nspname = 'public' AND object.relname = ANY(:tables)
"""
                    ),
                    {"tables": all_tables},
                )
            }
            assert flags == {table: (table in enabled, False) for table in all_tables}

            actual_grants: dict[str, set[str]] = {table: set() for table in all_tables}
            for row in connection.execute(
                text(
                    """
SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'public'
  AND grantee = 'workloop_runtime'
  AND table_name = ANY(:tables)
"""
                ),
                {"tables": all_tables},
            ):
                actual_grants[row.table_name].add(row.privilege_type)
            assert actual_grants == expected_grants

            helper_count = connection.execute(
                text(
                    """
SELECT count(*)
FROM pg_catalog.pg_proc AS procedure
JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
WHERE namespace.nspname = 'public'
  AND procedure.proname = 'can_act_for_delegated_leave'
"""
                )
            ).scalar_one()
            assert helper_count == (
                1 if revision in {"c74f5e9b2a31", "d85a6f0c3b42"} else 0
            )

            definitions = {
                row.proname: row.definition.lower()
                for row in connection.execute(
                    text(
                        """
SELECT procedure.proname,
       pg_catalog.pg_get_functiondef(procedure.oid) AS definition
FROM pg_catalog.pg_proc AS procedure
JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
WHERE namespace.nspname = 'public'
  AND procedure.proname IN (
    'replace_payroll_entries', 'record_advance_repayment',
    'admin_execute_shift_swap'
  )
"""
                    )
                )
            }
            payroll_hardened = revision != "f52e0a1b9c34"
            swap_hardened = revision == "d85a6f0c3b42"
            for name in ("replace_payroll_entries", "record_advance_repayment"):
                assert (
                    "workloop_admin_context_required" in definitions[name]
                ) == payroll_hardened
            assert (
                "workloop_admin_context_required"
                in definitions["admin_execute_shift_swap"]
            ) == swap_hardened

            expiry_access = connection.execute(
                text(
                    """
SELECT count(*)
FROM information_schema.column_privileges
WHERE table_schema = 'public'
  AND grantee = 'workloop_expiry_processing'
  AND table_name = ANY(:tables)
"""
                ),
                {"tables": all_tables},
            ).scalar_one()
            assert expiry_access == 0
    finally:
        engine.dispose()

    print(f"Phase 5F revision {revision} catalog and rollback state passed.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify-phase-5f-revision.py REVISION")
    verify(sys.argv[1])
