#!/usr/bin/env python3
"""Verify the Phase 7G audit wrapper and exact predecessor state."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "8f6b2d1a4c70"
PREDECESSOR = "7d4a9c2e6b10"
SIGNATURE = "text,text,uuid,text[],text,jsonb"


def function_row(connection: object, name: str) -> object:
    return connection.execute(
        text(
            "SELECT pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,"
            "procedure.provolatile,procedure.proconfig::text,procedure.proacl::text,"
            "pg_catalog.pg_get_functiondef(procedure.oid) "
            "FROM pg_catalog.pg_proc AS procedure "
            "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace "
            "WHERE namespace.nspname='public' AND procedure.oid=CAST(:signature AS regprocedure)"
        ),
        {"signature": f"public.{name}({SIGNATURE})"},
    ).one()


def normalized_hash(connection: object, definition: str) -> str:
    canonical = definition.replace("_append_audit_event_phase7g_prior", "append_audit_event")
    canonical = "\n".join(line.rstrip() for line in canonical.splitlines() if line.strip())
    phase5e_policies = connection.execute(
        text(
            "SELECT policyname,permissive,roles::text,cmd,qual,with_check "
            "FROM pg_catalog.pg_policies WHERE schemaname='public' "
            "AND policyname IN ('phase5e_user_profiles_select_runtime',"
            "'phase5e_user_profiles_update_runtime','phase5e_user_profiles_select_expiry') "
            "ORDER BY policyname"
        )
    ).all()
    assert len(phase5e_policies) == 3
    policy_state = "\n".join(
        "|".join("" if value is None else str(value) for value in row)
        for row in phase5e_policies
    )
    return hashlib.sha256(f"{canonical}\n{policy_state}".encode()).hexdigest()


def assert_security(row: object, *, runtime_execute: bool) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == "v"
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert ("workloop_runtime=X" in acl) is runtime_execute
    assert "{=X/" not in acl


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-7g-revision.py head|predecessor")
    mode = sys.argv[1]
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        policies = set(
            connection.execute(
                text(
                    "SELECT policyname FROM pg_catalog.pg_policies "
                    "WHERE schemaname='public' AND policyname LIKE 'phase7g_%'"
                )
            ).scalars()
        )
        if mode == "head":
            assert version == HEAD
            assert policies == {
                "phase7g_user_profiles_select_branch_runtime",
                "phase7g_user_profiles_update_role_branch_runtime",
            }
            phase7g_policies = connection.execute(
                text(
                    "SELECT policyname,permissive,roles::text,cmd,qual,with_check "
                    "FROM pg_catalog.pg_policies WHERE schemaname='public' "
                    "AND policyname LIKE 'phase7g_%' ORDER BY policyname"
                )
            ).all()
            assert len(phase7g_policies) == 2
            for row in phase7g_policies:
                assert row[1:4] == ("PERMISSIVE", "{workloop_runtime}", "SELECT") or row[
                    1:4
                ] == ("PERMISSIVE", "{workloop_runtime}", "UPDATE")
                expression = f"{row[4] or ''} {row[5] or ''}".lower().replace(" ", "")
                for required in (
                    "workloop_actor_kind()='human'",
                    "caller.account_status='active'",
                    "caller.role='admin'",
                    "workloop_branch_id()isnotnull",
                    "target_employee.branch_id=workloop_branch_id()",
                ):
                    assert required in expression
                if row[3] == "UPDATE":
                    assert row[4] == row[5]
                    for required in (
                        "app_user_id<>workloop_app_user_id()",
                        "is_scoped_active_app_user(app_user_id)",
                        "eligible_employee.active",
                        "eligible_employee.employment_status=any",
                    ):
                        assert required in expression
            public = function_row(connection, "append_audit_event")
            predecessor = function_row(connection, "_append_audit_event_phase7g_prior")
            assert_security(public, runtime_execute=True)
            assert_security(predecessor, runtime_execute=False)
            definition = str(public[5]).lower()
            for required in (
                "employee_manager_changed",
                "employee_probation_confirmed",
                "employee_probation_extended",
                "employee_probation_terminated",
                "employee_archived",
                "employee_portal_role_changed",
                "_append_audit_event_phase7g_prior",
            ):
                assert required in definition
            print(normalized_hash(connection, str(predecessor[5])))
        else:
            assert version == PREDECESSOR
            assert not policies
            assert connection.execute(
                text("SELECT to_regprocedure(:signature) IS NULL"),
                {"signature": f"public._append_audit_event_phase7g_prior({SIGNATURE})"},
            ).scalar_one()
            public = function_row(connection, "append_audit_event")
            assert_security(public, runtime_execute=True)
            print(normalized_hash(connection, str(public[5])))
    engine.dispose()


if __name__ == "__main__":
    main()
