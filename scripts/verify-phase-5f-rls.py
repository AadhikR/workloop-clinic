import json
import os
import runpy
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from sqlalchemy import create_engine, text

BASE = runpy.run_path(str(Path(__file__).with_name("verify-phase-5e-rls.py")))
c = BASE["c"]
build_rows = BASE["build_rows"]
apply_rows = BASE["apply_rows"]
clean = BASE["clean"]
validate = BASE["validate"]
connect_as = BASE["connect_as"]
human_context = BASE["human_context"]
job_context = BASE["job_context"]
principal_for = BASE["principal_for"]
row_values = BASE["row_values"]
scalar = BASE["scalar"]
set_value = BASE["set_value"]

SECOND_ADMIN_ID = uuid.UUID("f5f00000-0000-4000-8000-000000000001")
SECOND_ADMIN_SUBJECT = "phase5f.second-admin@horizon.test"


COMMANDS = {
    "payroll_runs": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "payroll_entries": {"SELECT"},
    "payslips": {"SELECT", "INSERT"},
    "payroll_approval_log": {"SELECT", "INSERT"},
    "nafis_reports": {"SELECT", "INSERT", "UPDATE"},
    "salary_advances": {"SELECT", "INSERT", "UPDATE"},
    "advance_repayments": {"SELECT"},
    "expense_claims": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "compliance_overrides": {"SELECT", "INSERT"},
    "leave_settings": {"SELECT", "INSERT", "UPDATE"},
    "leave_types": {"SELECT", "INSERT", "UPDATE"},
    "public_holidays": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "leave_requests": {"SELECT", "INSERT", "UPDATE"},
    "leave_audit_log": {"SELECT", "INSERT"},
    "leave_balances": {"SELECT", "INSERT", "UPDATE"},
    "leave_approval_delegates": {"SELECT", "INSERT", "UPDATE", "DELETE"},
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
}

GRANTS = {table: set(commands) for table, commands in COMMANDS.items()}


def expected_policies() -> set[tuple[str, str, str, str]]:
    return {
        (
            table,
            f"phase5f_{table}_{command.lower()}_runtime",
            command,
            "workloop_runtime",
        )
        for table, commands in COMMANDS.items()
        for command in commands
    }


def first_row(table: str, **matches: object) -> dict[str, object]:
    for row in build_rows():
        if row.table == table and all(
            row.values.get(key) == value for key, value in matches.items()
        ):
            return row.values
    raise AssertionError(f"missing synthetic {table} row")


@contextmanager
def second_admin_context(
    connection: psycopg.Connection[Any], *, branch_id: uuid.UUID
) -> Iterator[psycopg.Cursor[Any]]:
    with connection.transaction(), connection.cursor() as cursor:
        for key, value in {
            "workloop.identity_issuer": c.SEED_ISSUER,
            "workloop.identity_subject": SECOND_ADMIN_SUBJECT,
            "workloop.app_user_id": SECOND_ADMIN_ID,
            "workloop.role": "admin",
            "workloop.company_id": c.COMPANY_ID[c.HORIZON],
            "workloop.employee_id": None,
            "workloop.branch_id": branch_id,
            "workloop.actor_kind": "human",
            "workloop.actor_key": None,
            "workloop.business_date": date(2026, 9, 6),
        }.items():
            set_value(cursor, key, value)
        yield cursor


@contextmanager
def rollback_human_context(
    connection: psycopg.Connection[Any],
    subject: str,
    *,
    branch_id: uuid.UUID | None = None,
) -> Iterator[psycopg.Cursor[Any]]:
    principal = principal_for(subject)
    selected_branch = (
        branch_id if principal.role.value == "admin" else principal.branch_id
    )
    with connection.transaction(force_rollback=True), connection.cursor() as cursor:
        for key, value in {
            "workloop.identity_issuer": c.SEED_ISSUER,
            "workloop.identity_subject": subject,
            "workloop.app_user_id": principal.app_user_id,
            "workloop.role": principal.role.value,
            "workloop.company_id": principal.company_id,
            "workloop.employee_id": principal.employee_id,
            "workloop.branch_id": selected_branch,
            "workloop.actor_kind": "human",
            "workloop.actor_key": None,
            "workloop.business_date": date(2026, 9, 6),
        }.items():
            set_value(cursor, key, value)
        yield cursor


def verify_catalog(engine: Any) -> None:
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
        assert revision == "d85a6f0c3b42"

        policies = {
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
        assert policies == expected_policies()
        assert len(policies) == 77

        policy_rows = connection.execute(
            text(
                """
SELECT tablename, cmd, permissive, roles, qual, with_check
FROM pg_catalog.pg_policies
WHERE schemaname = 'public' AND policyname LIKE 'phase5f_%'
"""
            )
        ).mappings()
        for row in policy_rows:
            assert row["permissive"] == "PERMISSIVE"
            assert row["roles"] == ["workloop_runtime"]
            if row["cmd"] == "SELECT" or row["cmd"] == "DELETE":
                assert row["qual"] and row["with_check"] is None
            elif row["cmd"] == "INSERT":
                assert row["qual"] is None and row["with_check"]
            else:
                assert row["qual"] and row["with_check"]
            expression = f"{row['qual'] or ''} {row['with_check'] or ''}".lower()
            assert "workloop_actor_kind" in expression
            assert "resolve_workloop_principal" in expression
            assert "auth." not in expression and "storage." not in expression

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
                {"tables": list(COMMANDS)},
            )
        }
        assert flags == {table: (True, False) for table in COMMANDS}

        actual_grants: dict[str, set[str]] = {table: set() for table in COMMANDS}
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
            {"tables": list(COMMANDS)},
        ):
            actual_grants[row.table_name].add(row.privilege_type)
        assert actual_grants == GRANTS

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
            {"tables": list(COMMANDS)},
        ).scalar_one()
        assert expiry_access == 0

        function_rows = {
            row.proname: row
            for row in connection.execute(
                text(
                    """
SELECT procedure.proname,
       pg_catalog.pg_get_userbyid(procedure.proowner) AS owner,
       procedure.prosecdef,
       procedure.provolatile,
       procedure.proconfig,
       pg_catalog.pg_get_functiondef(procedure.oid) AS definition,
       procedure.proacl
FROM pg_catalog.pg_proc AS procedure
JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
WHERE namespace.nspname = 'public'
  AND procedure.proname IN (
    'replace_payroll_entries', 'record_advance_repayment',
    'admin_execute_shift_swap', 'can_act_for_delegated_leave'
  )
"""
                )
            )
        }
        assert set(function_rows) == {
            "replace_payroll_entries",
            "record_advance_repayment",
            "admin_execute_shift_swap",
            "can_act_for_delegated_leave",
        }
        for name, row in function_rows.items():
            assert row.owner == "workloop_migration"
            assert row.prosecdef
            assert row.proconfig == ["search_path=pg_catalog, public, pg_temp"]
            definition = row.definition.lower()
            assert "session_user" in definition
            assert "workloop_actor_kind" in definition
            assert "resolve_workloop_principal" in definition
            acl = str(row.proacl)
            assert "workloop_runtime=X" in acl
            assert "{=X/" not in acl and ",=X/" not in acl
            assert "workloop_expiry_processing" not in acl
            if name == "can_act_for_delegated_leave":
                assert row.provolatile == "s"
                assert (
                    "between delegation.from_date and delegation.to_date" in definition
                )
            else:
                assert row.provolatile == "v"

        protected_roles = connection.execute(
            text(
                """
SELECT count(*)
FROM pg_catalog.pg_roles
WHERE rolname IN ('workloop_runtime', 'workloop_expiry_processing')
  AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
"""
            )
        ).scalar_one()
        assert protected_roles == 0


def _assert_scoped_rows(
    cursor: psycopg.Cursor[Any], table: str, company_id: uuid.UUID, branch_id: uuid.UUID
) -> None:
    cursor.execute(f"SELECT company_id, branch_id FROM {table}")
    for company, branch in cursor.fetchall():
        assert company == company_id and branch == branch_id


def verify_admin_scope(runtime: psycopg.Connection[Any]) -> None:
    admin = principal_for("hr.admin@horizon.test")
    branch_tables = tuple(
        table for table in COMMANDS if table != "compliance_overrides"
    )
    with human_context(
        runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
    ) as cursor:
        for table in branch_tables:
            _assert_scoped_rows(cursor, table, admin.company_id, c.BRANCH_DXB)
        assert scalar(cursor, "SELECT count(*) FROM payroll_runs") > 0
        assert scalar(cursor, "SELECT count(*) FROM leave_requests") > 0
        assert scalar(cursor, "SELECT count(*) FROM attendance_records") > 0

    with human_context(
        runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_AUH
    ) as cursor:
        for table in branch_tables:
            _assert_scoped_rows(cursor, table, admin.company_id, c.BRANCH_AUH)
        assert scalar(cursor, "SELECT count(*) FROM payroll_runs") > 0

    with human_context(runtime, "hr.admin@horizon.test") as cursor:
        assert scalar(cursor, "SELECT count(*) FROM payroll_runs") == 0
        assert scalar(cursor, "SELECT count(*) FROM compliance_overrides") == 0


def verify_staff_scope(runtime: psycopg.Connection[Any]) -> None:
    ravi = principal_for("ravi.employee@horizon.test")
    aisha = principal_for("aisha.manager@horizon.test")
    fatima = principal_for("fatima.employee@horizon.test")

    with human_context(runtime, "ravi.employee@horizon.test") as cursor:
        for table in (
            "payslips",
            "salary_advances",
            "expense_claims",
            "leave_requests",
            "leave_balances",
            "clock_events",
            "attendance_records",
            "regularisation_requests",
            "roster_assignments",
        ):
            cursor.execute(f"SELECT DISTINCT employee_id FROM {table}")
            assert all(row[0] == ravi.employee_id for row in cursor.fetchall())
        cursor.execute(
            """
SELECT advance.employee_id
FROM advance_repayments AS repayment
JOIN salary_advances AS advance ON advance.id = repayment.advance_id
"""
        )
        assert all(row[0] == ravi.employee_id for row in cursor.fetchall())
        cursor.execute(
            "SELECT requester_employee_id, target_employee_id FROM shift_swap_requests"
        )
        assert all(ravi.employee_id in row for row in cursor.fetchall())
        for table in ("leave_settings", "leave_types", "public_holidays", "shifts"):
            _assert_scoped_rows(cursor, table, ravi.company_id, ravi.branch_id)
        for table in (
            "payroll_runs",
            "payroll_entries",
            "payroll_approval_log",
            "attendance_settings",
            "shift_assignments",
            "attendance_periods",
            "attendance_audit_log",
            "biometric_mappings",
        ):
            assert scalar(cursor, f"SELECT count(*) FROM {table}") == 0

    with human_context(runtime, "aisha.manager@horizon.test") as cursor:
        for table in ("expense_claims", "leave_requests", "leave_balances"):
            cursor.execute(f"SELECT DISTINCT employee_id FROM {table}")
            visible = {row[0] for row in cursor.fetchall()}
            cursor.execute(
                "SELECT id FROM employees WHERE reporting_manager_id = %s",
                (aisha.employee_id,),
            )
            reports = {row[0] for row in cursor.fetchall()}
            assert visible <= reports | {aisha.employee_id}

    target = row_values("employees", emp_no="H-DXB-002")["id"]
    with human_context(
        runtime,
        "fatima.employee@horizon.test",
        overrides={"workloop.business_date": date(2026, 8, 15)},
    ) as cursor:
        assert scalar(cursor, "SELECT can_act_for_delegated_leave(%s)", (target,))
        assert scalar(
            cursor,
            "SELECT count(*) FROM leave_requests WHERE employee_id = %s",
            (target,),
        )

    for business_date in (date(2026, 6, 30), date(2026, 9, 6)):
        with human_context(
            runtime,
            "fatima.employee@horizon.test",
            overrides={"workloop.business_date": business_date},
        ) as cursor:
            assert not scalar(
                cursor, "SELECT can_act_for_delegated_leave(%s)", (target,)
            )
    with human_context(
        runtime,
        "fatima.employee@horizon.test",
        overrides={"workloop.business_date": date(2026, 8, 15)},
    ) as cursor:
        assert not scalar(
            cursor,
            "SELECT can_act_for_delegated_leave(%s)",
            (fatima.employee_id,),
        )
        assert not scalar(
            cursor,
            "SELECT can_act_for_delegated_leave(%s)",
            (uuid.uuid4(),),
        )


def verify_missing_and_job_context(
    runtime: psycopg.Connection[Any], expiry: psycopg.Connection[Any]
) -> None:
    for overrides in (
        {"workloop.app_user_id": None},
        {"workloop.company_id": "malformed"},
        {"workloop.branch_id": uuid.uuid4()},
        {"workloop.identity_subject": "guessed"},
    ):
        with human_context(
            runtime,
            "ravi.employee@horizon.test",
            overrides=overrides,
        ) as cursor:
            for table in ("payslips", "leave_requests", "attendance_records"):
                assert scalar(cursor, f"SELECT count(*) FROM {table}") == 0

    with runtime.transaction(), runtime.cursor() as cursor:
        for table in ("payroll_runs", "leave_requests", "attendance_records"):
            assert scalar(cursor, f"SELECT count(*) FROM {table}") == 0

    for table in COMMANDS:
        try:
            with job_context(
                expiry,
                company_id=c.COMPANY_ID[c.HORIZON],
                branch_id=c.BRANCH_DXB,
            ) as cursor:
                cursor.execute(f"SELECT count(*) FROM {table}")
        except psycopg.errors.InsufficientPrivilege:
            continue
        raise AssertionError(f"expiry processing read {table}")


def verify_immutable_and_protected(
    runtime: psycopg.Connection[Any], engine: Any
) -> None:
    immutable = (
        "payslips",
        "payroll_approval_log",
        "advance_repayments",
        "compliance_overrides",
        "leave_audit_log",
        "clock_events",
        "attendance_audit_log",
    )
    for table in immutable:
        for command in ("UPDATE", "DELETE"):
            try:
                with human_context(
                    runtime,
                    "hr.admin@horizon.test",
                    branch_id=c.BRANCH_DXB,
                ) as cursor:
                    cursor.execute(
                        f"{command} FROM {table}"
                        if command == "DELETE"
                        else f"UPDATE {table} SET id = id"
                    )
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError(f"{table} accepted {command}")

    run = first_row("payroll_runs", company_id=c.COMPANY_ID[c.CEDAR])
    with engine.connect() as connection:
        before = connection.execute(
            text("SELECT count(*) FROM payroll_entries WHERE payroll_run_id = :id"),
            {"id": run["id"]},
        ).scalar_one()
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT replace_payroll_entries(%s, '[]'::jsonb)", (run["id"],)
            )
    except psycopg.errors.RaiseException:
        pass
    else:
        raise AssertionError("payroll replacement crossed tenants")
    with engine.connect() as connection:
        after = connection.execute(
            text("SELECT count(*) FROM payroll_entries WHERE payroll_run_id = :id"),
            {"id": run["id"]},
        ).scalar_one()
    assert before == after

    advance = first_row("salary_advances", company_id=c.COMPANY_ID[c.CEDAR])
    state_sql = text(
        "SELECT outstanding_balance, status FROM salary_advances WHERE id = :id"
    )
    with engine.connect() as connection:
        before_advance = connection.execute(state_sql, {"id": advance["id"]}).one()
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT record_advance_repayment(%s, NULL, %s, 1, %s)",
                (advance["id"], uuid.uuid4(), date(2026, 9, 6)),
            )
    except psycopg.errors.RaiseException:
        pass
    else:
        raise AssertionError("advance repayment crossed tenants")
    with engine.connect() as connection:
        assert (
            connection.execute(state_sql, {"id": advance["id"]}).one() == before_advance
        )

    swap = first_row("shift_swap_requests", company_id=c.COMPANY_ID[c.CEDAR])
    with engine.connect() as connection:
        before_swap = connection.execute(
            text("SELECT status FROM shift_swap_requests WHERE id = :id"),
            {"id": swap["id"]},
        ).scalar_one()
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT admin_execute_shift_swap(%s, %s)",
                (swap["id"], c.ADMIN_APP_USER[c.HORIZON]),
            )
    except psycopg.errors.RaiseException:
        pass
    else:
        raise AssertionError("shift swap crossed tenants")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM shift_swap_requests WHERE id = :id"),
                {"id": swap["id"]},
            ).scalar_one()
            == before_swap
        )


def verify_protected_finance_success(
    runtime: psycopg.Connection[Any], engine: Any
) -> None:
    ravi = principal_for("ravi.employee@horizon.test")
    run = first_row(
        "payroll_runs",
        company_id=c.COMPANY_ID[c.HORIZON],
        branch_id=c.BRANCH_DXB,
        status="draft",
        approval_status="draft",
    )
    entries_sql = text(
        """
SELECT COALESCE(jsonb_agg(to_jsonb(entry) ORDER BY entry.id), '[]'::jsonb)
FROM payroll_entries AS entry WHERE payroll_run_id = :id
"""
    )
    with engine.connect() as connection:
        entries_before = connection.execute(entries_sql, {"id": run["id"]}).scalar_one()

    payload = json.dumps(
        [
            {
                "employee_id": str(ravi.employee_id),
                "basic_salary": 1234,
                "housing_allowance": 200,
                "deductions": [],
            }
        ]
    )
    with rollback_human_context(
        runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
    ) as cursor:
        cursor.execute(
            "SELECT replace_payroll_entries(%s, %s::jsonb)", (run["id"], payload)
        )
        assert (
            scalar(
                cursor,
                "SELECT count(*) FROM payroll_entries WHERE payroll_run_id = %s",
                (run["id"],),
            )
            == 1
        )
        assert (
            scalar(
                cursor,
                "SELECT basic_salary FROM payroll_entries WHERE payroll_run_id = %s",
                (run["id"],),
            )
            == 1234
        )

    with engine.connect() as connection:
        assert (
            connection.execute(entries_sql, {"id": run["id"]}).scalar_one()
            == entries_before
        )

    advance = first_row(
        "salary_advances",
        company_id=c.COMPANY_ID[c.HORIZON],
        branch_id=c.BRANCH_DXB,
        status="active",
    )
    repayment_key = uuid.uuid4()
    advance_sql = text(
        "SELECT outstanding_balance, status FROM salary_advances WHERE id = :id"
    )
    with engine.connect() as connection:
        advance_before = connection.execute(advance_sql, {"id": advance["id"]}).one()

    with rollback_human_context(
        runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
    ) as cursor:
        first_result = scalar(
            cursor,
            "SELECT record_advance_repayment(%s, NULL, %s, 1, %s)",
            (advance["id"], repayment_key, date(2026, 9, 6)),
        )
        assert first_result["alreadyRecorded"] is False
        assert (
            scalar(
                cursor,
                "SELECT count(*) FROM advance_repayments WHERE idempotency_key = %s",
                (repayment_key,),
            )
            == 1
        )
        second_result = scalar(
            cursor,
            "SELECT record_advance_repayment(%s, NULL, %s, 1, %s)",
            (advance["id"], repayment_key, date(2026, 9, 6)),
        )
        assert second_result["alreadyRecorded"] is True
        assert second_result["repaymentId"] == first_result["repaymentId"]

    with engine.connect() as connection:
        assert (
            connection.execute(advance_sql, {"id": advance["id"]}).one()
            == advance_before
        )
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM advance_repayments "
                    "WHERE idempotency_key = :key"
                ),
                {"key": repayment_key},
            ).scalar_one()
            == 0
        )


def verify_payroll_separation(runtime: psycopg.Connection[Any], engine: Any) -> None:
    run = first_row(
        "payroll_runs",
        company_id=c.COMPANY_ID[c.HORIZON],
        branch_id=c.BRANCH_DXB,
        approval_status="draft",
    )
    run_id = run["id"]
    first_admin = c.ADMIN_APP_USER[c.HORIZON]
    with engine.begin() as connection:
        original = connection.execute(
            text(
                """
SELECT run_by_app_user_id, approval_status,
       submitted_by_app_user_id, submitted_for_approval_at,
       approved_by_app_user_id, approved_at
FROM payroll_runs WHERE id = :id
"""
            ),
            {"id": run_id},
        ).one()
        connection.execute(
            text(
                """
UPDATE payroll_runs
SET run_by_app_user_id = :actor,
    approval_status = 'pending_approval',
    submitted_by_app_user_id = :actor,
    submitted_for_approval_at = now()
WHERE id = :id
"""
            ),
            {"actor": first_admin, "id": run_id},
        )

    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                """
UPDATE payroll_runs
SET approval_status = 'approved',
    approved_by_app_user_id = %s,
    approved_at = now()
WHERE id = %s
""",
                (first_admin, run_id),
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("the payroll submitter approved the same run")

    with second_admin_context(runtime, branch_id=c.BRANCH_DXB) as cursor:
        cursor.execute(
            """
UPDATE payroll_runs
SET approval_status = 'approved',
    approved_by_app_user_id = %s,
    approved_at = now()
WHERE id = %s
""",
            (SECOND_ADMIN_ID, run_id),
        )
        assert cursor.rowcount == 1

    with engine.begin() as connection:
        approved_by = connection.execute(
            text("SELECT approved_by_app_user_id FROM payroll_runs WHERE id = :id"),
            {"id": run_id},
        ).scalar_one()
        assert approved_by == SECOND_ADMIN_ID
        connection.execute(
            text(
                """
UPDATE payroll_runs
SET run_by_app_user_id = :run_by,
    approval_status = :approval_status,
    submitted_by_app_user_id = :submitted_by,
    submitted_for_approval_at = :submitted_at,
    approved_by_app_user_id = :approved_by,
    approved_at = :approved_at
WHERE id = :id
"""
            ),
            {
                "run_by": original.run_by_app_user_id,
                "approval_status": original.approval_status,
                "submitted_by": original.submitted_by_app_user_id,
                "submitted_at": original.submitted_for_approval_at,
                "approved_by": original.approved_by_app_user_id,
                "approved_at": original.approved_at,
                "id": run_id,
            },
        )


def verify_self_approval_denials(runtime: psycopg.Connection[Any], engine: Any) -> None:
    ravi = principal_for("ravi.employee@horizon.test")
    pending_leave = row_values(
        "leave_requests", employee_id=ravi.employee_id, status="Pending"
    )
    with engine.connect() as connection:
        before_leave = connection.execute(
            text("SELECT status FROM leave_requests WHERE id = :id"),
            {"id": pending_leave["id"]},
        ).scalar_one()
    try:
        with human_context(runtime, "ravi.employee@horizon.test") as cursor:
            cursor.execute(
                """
UPDATE leave_requests
SET status = 'Approved', approved_by_app_user_id = %s,
    approved_at = now(), approval_comment = 'forbidden self approval'
WHERE id = %s
""",
                (ravi.app_user_id, pending_leave["id"]),
            )
            assert cursor.rowcount == 0
    except psycopg.errors.InsufficientPrivilege:
        pass
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM leave_requests WHERE id = :id"),
                {"id": pending_leave["id"]},
            ).scalar_one()
            == before_leave
        )

    active_advance = row_values(
        "salary_advances", employee_id=ravi.employee_id, status="active"
    )
    with engine.connect() as connection:
        before_advance = connection.execute(
            text("SELECT status FROM salary_advances WHERE id = :id"),
            {"id": active_advance["id"]},
        ).scalar_one()
    with human_context(runtime, "ravi.employee@horizon.test") as cursor:
        cursor.execute(
            "UPDATE salary_advances SET status = 'cancelled', "
            "rejection_reason = 'forbidden' WHERE id = %s",
            (active_advance["id"],),
        )
        assert cursor.rowcount == 0
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM salary_advances WHERE id = :id"),
                {"id": active_advance["id"]},
            ).scalar_one()
            == before_advance
        )

    maria = principal_for("maria.employee@horizon.test")
    pending_expense = row_values(
        "expense_claims", employee_id=maria.employee_id, status="pending"
    )
    with human_context(runtime, "maria.employee@horizon.test") as cursor:
        cursor.execute(
            """
UPDATE expense_claims
SET status = 'manager_approved',
    manager_approved_by_app_user_id = %s,
    manager_approved_at = now()
WHERE id = %s
""",
            (maria.app_user_id, pending_expense["id"]),
        )
        assert cursor.rowcount == 0

    pending_regularisation = row_values(
        "regularisation_requests", employee_id=ravi.employee_id, status="Pending"
    )
    with human_context(runtime, "ravi.employee@horizon.test") as cursor:
        cursor.execute(
            """
UPDATE regularisation_requests
SET status = 'Approved', approved_by_app_user_id = %s, approved_at = now()
WHERE id = %s
""",
            (ravi.app_user_id, pending_regularisation["id"]),
        )
        assert cursor.rowcount == 0


def verify_protected_shift_swap(runtime: psycopg.Connection[Any], engine: Any) -> None:
    ravi = principal_for("ravi.employee@horizon.test")
    fatima = principal_for("fatima.employee@horizon.test")
    shift = first_row(
        "shifts",
        company_id=c.COMPANY_ID[c.HORIZON],
        branch_id=c.BRANCH_DXB,
    )
    first_roster_id = uuid.uuid4()
    second_roster_id = uuid.uuid4()
    swap_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                """
INSERT INTO roster_assignments (
  id, company_id, branch_id, employee_id, shift_id, date, published
) VALUES
  (:first_id, :company, :branch, :first_employee, :shift, '2027-01-04', true),
  (:second_id, :company, :branch, :second_employee, :shift, '2027-01-05', true)
"""
            ),
            {
                "first_id": first_roster_id,
                "second_id": second_roster_id,
                "company": c.COMPANY_ID[c.HORIZON],
                "branch": c.BRANCH_DXB,
                "first_employee": ravi.employee_id,
                "second_employee": fatima.employee_id,
                "shift": shift["id"],
            },
        )
        connection.execute(
            text(
                """
INSERT INTO shift_swap_requests (
  id, company_id, branch_id, requester_employee_id, target_employee_id,
  requester_date, target_date, status
) VALUES (
  :id, :company, :branch, :requester, :target,
  '2027-01-04', '2027-01-05', 'pending'
)
"""
            ),
            {
                "id": swap_id,
                "company": c.COMPANY_ID[c.HORIZON],
                "branch": c.BRANCH_DXB,
                "requester": ravi.employee_id,
                "target": fatima.employee_id,
            },
        )

    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "UPDATE roster_assignments SET notes = 'forbidden' WHERE id = %s",
                (first_roster_id,),
            )
            assert cursor.rowcount == 0

        try:
            with second_admin_context(runtime, branch_id=c.BRANCH_DXB) as cursor:
                cursor.execute(
                    "SELECT admin_execute_shift_swap(%s, %s)",
                    (swap_id, c.ADMIN_APP_USER[c.HORIZON]),
                )
        except psycopg.errors.RaiseException:
            pass
        else:
            raise AssertionError("shift swap accepted a forged actor")

        with engine.connect() as connection:
            before = (
                connection.execute(
                    text(
                        """
SELECT employee_id FROM roster_assignments
WHERE id IN (:first, :second) ORDER BY id
"""
                    ),
                    {"first": first_roster_id, "second": second_roster_id},
                )
                .scalars()
                .all()
            )
            assert set(before) == {ravi.employee_id, fatima.employee_id}
            assert (
                connection.execute(
                    text("SELECT status FROM shift_swap_requests WHERE id = :id"),
                    {"id": swap_id},
                ).scalar_one()
                == "pending"
            )

        with second_admin_context(runtime, branch_id=c.BRANCH_DXB) as cursor:
            assert scalar(
                cursor,
                "SELECT admin_execute_shift_swap(%s, %s)",
                (swap_id, SECOND_ADMIN_ID),
            )

        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT employee_id FROM roster_assignments WHERE id = :id"),
                    {"id": first_roster_id},
                ).scalar_one()
                == fatima.employee_id
            )
            result = connection.execute(
                text(
                    """
SELECT status, admin_approved_by_app_user_id
FROM shift_swap_requests WHERE id = :id
"""
                ),
                {"id": swap_id},
            ).one()
            assert result == ("approved", SECOND_ADMIN_ID)
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM shift_swap_requests WHERE id = :id"), {"id": swap_id}
            )
            connection.execute(
                text("DELETE FROM roster_assignments WHERE id IN (:first, :second)"),
                {"first": first_roster_id, "second": second_roster_id},
            )


def main() -> None:
    migration_url = os.environ["MIGRATION_DATABASE_URL"]
    rows = build_rows()
    engine = create_engine(migration_url)
    runtime = connect_as("workloop_runtime")
    expiry = connect_as("workloop_expiry_processing")
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            connection.execute(
                text("DELETE FROM user_profiles WHERE app_user_id = :id"),
                {"id": SECOND_ADMIN_ID},
            )
            connection.execute(
                text("DELETE FROM app_users WHERE id = :id"),
                {"id": SECOND_ADMIN_ID},
            )
            connection.execute(
                text(
                    """
INSERT INTO app_users (id, identity_issuer, identity_subject, status)
VALUES (:id, :issuer, :subject, 'active')
"""
                ),
                {
                    "id": SECOND_ADMIN_ID,
                    "issuer": c.SEED_ISSUER,
                    "subject": SECOND_ADMIN_SUBJECT,
                },
            )
            connection.execute(
                text(
                    """
INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
VALUES (:id, :company, NULL, 'admin')
"""
                ),
                {"id": SECOND_ADMIN_ID, "company": c.COMPANY_ID[c.HORIZON]},
            )
        verify_catalog(engine)
        verify_admin_scope(runtime)
        verify_staff_scope(runtime)
        verify_missing_and_job_context(runtime, expiry)
        verify_immutable_and_protected(runtime, engine)
        verify_protected_finance_success(runtime, engine)
        verify_payroll_separation(runtime, engine)
        verify_self_approval_denials(runtime, engine)
        verify_protected_shift_swap(runtime, engine)
    finally:
        runtime.close()
        expiry.close()
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM user_profiles WHERE app_user_id = :id"),
                {"id": SECOND_ADMIN_ID},
            )
            connection.execute(
                text("DELETE FROM app_users WHERE id = :id"),
                {"id": SECOND_ADMIN_ID},
            )
            clean(connection, rows)
        engine.dispose()

    print("Phase 5F payroll, leave, attendance, and roster RLS checks passed.")


if __name__ == "__main__":
    main()
