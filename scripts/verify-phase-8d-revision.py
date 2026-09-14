#!/usr/bin/env python3
"""Verify the Phase 8D audit wrapper and exact predecessor state."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "a83d5e7c1b29"
PREDECESSOR = "4d8a7c2e9f31"
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


def normalized_hash(definition: str) -> str:
    canonical = definition.replace("_append_audit_event_phase8d_prior", "append_audit_event")
    canonical = "\n".join(line.rstrip() for line in canonical.splitlines() if line.strip())
    return hashlib.sha256(canonical.encode()).hexdigest()


def assert_security(row: object, *, runtime_execute: bool) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == "v"
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert ("workloop_runtime=X" in acl) is runtime_execute
    assert "{=X/" not in acl


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-8d-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        public = function_row(connection, "append_audit_event")
        assert_security(public, runtime_execute=True)
        if sys.argv[1] == "head":
            assert version == HEAD
            assert connection.execute(
                text("SELECT to_regclass('public.leave_attachments') IS NOT NULL")
            ).scalar_one()
            predecessor = function_row(connection, "_append_audit_event_phase8d_prior")
            assert_security(predecessor, runtime_execute=False)
            definition = str(public[5]).lower()
            for marker in (
                "leave_attachment_uploaded",
                "leave_attachment_cleanup_requested",
                "_append_audit_event_phase8d_prior",
            ):
                assert marker in definition
            print(normalized_hash(str(predecessor[5])))
        else:
            assert version == PREDECESSOR
            assert connection.execute(
                text("SELECT to_regclass('public.leave_attachments') IS NULL")
            ).scalar_one()
            assert connection.execute(
                text("SELECT to_regprocedure(:signature) IS NULL"),
                {"signature": f"public._append_audit_event_phase8d_prior({SIGNATURE})"},
            ).scalar_one()
            print(normalized_hash(str(public[5])))
    engine.dispose()


if __name__ == "__main__":
    main()
