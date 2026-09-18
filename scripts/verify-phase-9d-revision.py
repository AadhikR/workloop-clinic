#!/usr/bin/env python3
"""Verify the Phase 9D payroll functions and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "f4b8d2e6a901"
PREDECESSOR = "a1c3e5f7b9d2"
AUDIT_ARGS = "text,text,uuid,text[],text,jsonb"
REPLACE_ARGS = "uuid,jsonb"


def function_row(connection: object, signature: str) -> object:
    return connection.execute(
        text(
            "SELECT pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,"
            "procedure.provolatile,procedure.proconfig::text,procedure.proacl::text,"
            "pg_catalog.pg_get_functiondef(procedure.oid) FROM pg_catalog.pg_proc AS procedure "
            "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace "
            "WHERE namespace.nspname='public' "
            "AND procedure.oid=CAST(:signature AS regprocedure)"
        ),
        {"signature": f"public.{signature}"},
    ).one()


def absent(connection: object, signature: str) -> bool:
    return bool(
        connection.scalar(
            text("SELECT to_regprocedure(:signature) IS NULL"),
            {"signature": f"public.{signature}"},
        )
    )


def digest(audit: object, replace: object) -> str:
    normalized = (
        str(audit).replace("_append_audit_event_phase9d_prior", "append_audit_event")
        + "\n"
        + str(replace).replace(
            "_replace_payroll_entries_phase9d_prior", "replace_payroll_entries"
        )
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def assert_protected(row: object, *, runtime: bool = True) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == "v"
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert ("workloop_runtime=X" in acl) is runtime and "{=X/" not in acl


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    assert connection.scalar(
        text(
            "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' "
            "AND ((table_name='payroll_entries' AND column_name='source_snapshot') "
            "OR (table_name='payroll_runs' AND column_name='source_snapshot_digest'))"
        )
    ) == 2
    replay = connection.scalar(
        text(
            "SELECT pg_catalog.pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert "payroll_run" in str(replay)
    current_audit = function_row(connection, f"append_audit_event({AUDIT_ARGS})")
    audit = function_row(connection, f"_append_audit_event_phase9f_prior({AUDIT_ARGS})")
    replace = function_row(connection, f"replace_payroll_entries({REPLACE_ARGS})")
    assert_protected(current_audit)
    assert_protected(audit, runtime=False)
    assert_protected(replace)
    assert "payroll_inputs_refreshed" in str(audit[5])
    assert "source_snapshot_digest" in str(replace[5])
    phase9d_audit = function_row(
        connection, f"_append_audit_event_phase9e_prior({AUDIT_ARGS})"
    )
    assert_protected(phase9d_audit, runtime=False)
    assert "payroll_entries_replaced" in str(phase9d_audit[5])
    prior_audit = function_row(connection, f"_append_audit_event_phase9d_prior({AUDIT_ARGS})")
    prior_replace = function_row(
        connection, f"_replace_payroll_entries_phase9d_prior({REPLACE_ARGS})"
    )
    assert_protected(prior_audit, runtime=False)
    assert_protected(prior_replace, runtime=False)
    return digest(prior_audit[5], prior_replace[5])


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    assert absent(connection, f"_append_audit_event_phase9e_prior({AUDIT_ARGS})")
    assert absent(connection, f"_append_audit_event_phase9d_prior({AUDIT_ARGS})")
    assert absent(connection, f"_replace_payroll_entries_phase9d_prior({REPLACE_ARGS})")
    assert connection.scalar(
        text(
            "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' "
            "AND ((table_name='payroll_entries' AND column_name='source_snapshot') "
            "OR (table_name='payroll_runs' AND column_name='source_snapshot_digest'))"
        )
    ) == 0
    audit = function_row(connection, f"append_audit_event({AUDIT_ARGS})")
    replace = function_row(connection, f"replace_payroll_entries({REPLACE_ARGS})")
    assert_protected(audit)
    assert_protected(replace)
    return digest(audit[5], replace[5])


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-9d-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        value = verify_head(connection) if sys.argv[1] == "head" else verify_predecessor(connection)
        print(value)
    engine.dispose()


if __name__ == "__main__":
    main()
