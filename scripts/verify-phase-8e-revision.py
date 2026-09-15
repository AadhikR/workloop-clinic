#!/usr/bin/env python3
"""Verify the Phase 8E audit wrapper and request update policy rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "d1e5f8a2c904"
PREDECESSOR = "a83d5e7c1b29"
SIGNATURE = "text,text,uuid,text[],text,jsonb"


def function_row(connection: object, name: str, signature: str = SIGNATURE) -> object:
    return connection.execute(
        text(
            "SELECT pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,"
            "procedure.provolatile,procedure.proconfig::text,procedure.proacl::text,"
            "pg_catalog.pg_get_functiondef(procedure.oid) "
            "FROM pg_catalog.pg_proc AS procedure "
            "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace "
            "WHERE namespace.nspname='public' AND procedure.oid=CAST(:signature AS regprocedure)"
        ),
        {"signature": f"public.{name}({signature})"},
    ).one()


def policy_row(connection: object, name: str, table: str = "leave_requests") -> object:
    return connection.execute(
        text(
            "SELECT policy.polcmd,ARRAY(SELECT role.rolname FROM pg_catalog.pg_roles AS role "
            "WHERE role.oid=ANY(policy.polroles) ORDER BY role.rolname),"
            "pg_catalog.pg_get_expr(policy.polqual,policy.polrelid),"
            "pg_catalog.pg_get_expr(policy.polwithcheck,policy.polrelid) "
            "FROM pg_catalog.pg_policy AS policy "
            "WHERE policy.polrelid=CAST(:table AS regclass) AND policy.polname=:name"
        ),
        {"name": name, "table": f"public.{table}"},
    ).one()


def replay_constraint(connection: object) -> str:
    return str(
        connection.execute(
            text(
                "SELECT pg_catalog.pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint "
                "WHERE conrelid='public.idempotency_records'::regclass "
                "AND conname='ck_idempotency_records_replay_resource'"
            )
        ).scalar_one()
    )


def digest(value: object) -> str:
    normalized = (
        str(value)
        .replace("_append_audit_event_phase8e_prior", "append_audit_event")
        .replace(
            "phase8e_prior_leave_requests_update_runtime", "phase5f_leave_requests_update_runtime"
        )
        .replace(", 'leave_request'::text", "")
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def assert_security(row: object, *, runtime_execute: bool) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == "v"
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert ("workloop_runtime=X" in acl) is runtime_execute
    assert "{=X/" not in acl


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-8e-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        public = function_row(connection, "append_audit_event")
        assert_security(public, runtime_execute=True)
        if sys.argv[1] == "head":
            assert version == HEAD
            predecessor = function_row(connection, "_append_audit_event_phase8e_prior")
            assert_security(predecessor, runtime_execute=False)
            definition = str(public[5]).lower()
            for marker in (
                "leave_request_submitted",
                "leave_request_auto_approved",
                "leave_request_cancelled",
                "_append_audit_event_phase8e_prior",
            ):
                assert marker in definition
            current_policy = policy_row(connection, "phase5f_leave_requests_update_runtime")
            prior_policy = policy_row(connection, "phase8e_prior_leave_requests_update_runtime")
            assert current_policy[0] == prior_policy[0] == "w"
            assert current_policy[1] == ["workloop_runtime"]
            assert prior_policy[1] == ["workloop_migration"]
            assert "Auto-approved by leave type policy" in str(current_policy[3])
            settings_lock = policy_row(
                connection, "phase8e_leave_settings_lock_runtime", "leave_settings"
            )
            type_lock = policy_row(connection, "phase8e_leave_types_lock_runtime", "leave_types")
            assert settings_lock[1] == type_lock[1] == ["workloop_runtime"]
            assert settings_lock[3] == type_lock[3] == "false"
            assert "is_active" in str(type_lock[2])
            constraint = replay_constraint(connection)
            assert "'leave_request'::text" in constraint
            print(
                digest(
                    (
                        predecessor[5],
                        prior_policy[0],
                        prior_policy[2],
                        prior_policy[3],
                        constraint,
                    )
                )
            )
        else:
            assert version == PREDECESSOR
            assert connection.execute(
                text("SELECT to_regprocedure(:signature) IS NULL"),
                {"signature": f"public._append_audit_event_phase8e_prior({SIGNATURE})"},
            ).scalar_one()
            assert connection.execute(
                text(
                    "SELECT count(*)=0 FROM pg_catalog.pg_policy WHERE "
                    "polrelid IN ('public.leave_settings'::regclass,"
                    "'public.leave_types'::regclass) "
                    "AND polname IN ('phase8e_leave_settings_lock_runtime',"
                    "'phase8e_leave_types_lock_runtime')"
                )
            ).scalar_one()
            assert connection.execute(
                text(
                    "SELECT count(*)=0 FROM pg_catalog.pg_policy WHERE "
                    "polrelid='public.leave_requests'::regclass "
                    "AND polname='phase8e_prior_leave_requests_update_runtime'"
                )
            ).scalar_one()
            policy = policy_row(connection, "phase5f_leave_requests_update_runtime")
            assert policy[1] == ["workloop_runtime"]
            constraint = replay_constraint(connection)
            assert "'leave_request'::text" not in constraint
            print(digest((public[5], policy[0], policy[2], policy[3], constraint)))
    engine.dispose()


if __name__ == "__main__":
    main()
