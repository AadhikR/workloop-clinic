#!/usr/bin/env python3
"""Verify the Phase 9G functions and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "f4b8d2e6a901"
PREDECESSOR = "b8e2c4d6f9a1"
AUDIT_ARGS = "text,text,uuid,text[],text,jsonb"
FUNCTIONS = (
    "transition_payroll_wps(uuid,text,text,text,timestamptz,text,text)",
    "transition_wps_entry(uuid,uuid,text,text,timestamptz)",
    "create_wps_compliance_override(uuid,uuid,uuid,text,text)",
    "lock_nafis_sources(date)",
    "replace_nafis_snapshot(uuid,text,integer,integer,numeric,numeric,boolean,jsonb,timestamptz)",
)


def function_row(connection: object, signature: str) -> object:
    return connection.execute(
        text(
            "SELECT pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,"
            "procedure.provolatile,procedure.proconfig::text,procedure.proacl::text,"
            "pg_catalog.pg_get_functiondef(procedure.oid) FROM pg_catalog.pg_proc AS procedure "
            "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace "
            "WHERE namespace.nspname='public' AND procedure.oid=CAST(:signature AS regprocedure)"
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


def digest(definition: object) -> str:
    normalized = str(definition).replace("_append_audit_event_phase9g_prior", "append_audit_event")
    return hashlib.sha256(normalized.encode()).hexdigest()


def assert_protected(row: object, *, runtime: bool = True) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == "v"
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert ("workloop_runtime=X" in acl) is runtime and "{=X/" not in acl


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    audit = function_row(connection, f"append_audit_event({AUDIT_ARGS})")
    prior = function_row(connection, f"_append_audit_event_phase9g_prior({AUDIT_ARGS})")
    assert_protected(audit)
    assert_protected(prior, runtime=False)
    for signature in FUNCTIONS:
        assert_protected(function_row(connection, signature))
    assert "sif_projection_recorded" in str(audit[5])
    assert "FOR UPDATE" in str(function_row(connection, FUNCTIONS[0])[5])
    assert "previous_digest" in str(function_row(connection, FUNCTIONS[0])[5])
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='compliance_overrides' "
                "AND column_name IN ('payroll_run_id','payroll_entry_id','rule_code')"
            )
        )
        == 3
    )
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM pg_catalog.pg_trigger WHERE NOT tgisinternal "
                "AND tgrelid='public.compliance_overrides'::regclass "
                "AND tgname='trg_compliance_overrides_immutable'"
            )
        )
        == 1
    )
    return digest(prior[5])


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    assert absent(connection, f"_append_audit_event_phase9g_prior({AUDIT_ARGS})")
    for signature in FUNCTIONS:
        assert absent(connection, signature)
    assert (
        connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='compliance_overrides' "
                "AND column_name IN ('payroll_run_id','payroll_entry_id','rule_code')"
            )
        )
        == 0
    )
    audit = function_row(connection, f"append_audit_event({AUDIT_ARGS})")
    assert_protected(audit)
    assert "sif_projection_recorded" not in str(audit[5])
    return digest(audit[5])


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-9g-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        value = verify_head(connection) if sys.argv[1] == "head" else verify_predecessor(connection)
        print(value)
    engine.dispose()


if __name__ == "__main__":
    main()
