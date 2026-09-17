#!/usr/bin/env python3
"""Verify the Phase 9E audit wrapper and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "d7f1b3c5e9a2"
PREDECESSOR = "c5e7a9b1d3f4"
AUDIT_ARGS = "text,text,uuid,text[],text,jsonb"


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


def digest(definition: object) -> str:
    normalized = str(definition).replace("_append_audit_event_phase9e_prior", "append_audit_event")
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
    prior = function_row(connection, f"_append_audit_event_phase9e_prior({AUDIT_ARGS})")
    assert_protected(audit)
    assert_protected(prior, runtime=False)
    assert "payroll_inputs_refreshed" in str(audit[5])
    assert "source_types text[]" in str(audit[5])
    return digest(prior[5])


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    assert absent(connection, f"_append_audit_event_phase9e_prior({AUDIT_ARGS})")
    audit = function_row(connection, f"append_audit_event({AUDIT_ARGS})")
    assert_protected(audit)
    assert "payroll_inputs_refreshed" not in str(audit[5])
    return digest(audit[5])


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-9e-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        value = verify_head(connection) if sys.argv[1] == "head" else verify_predecessor(connection)
        print(value)
    engine.dispose()


if __name__ == "__main__":
    main()
