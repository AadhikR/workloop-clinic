#!/usr/bin/env python3
"""Verify the Phase 8F protected functions and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "e8f4c7b2a610"
PREDECESSOR = "d1e5f8a2c904"
AUDIT_SIGNATURE = "text,text,uuid,text[],text,jsonb"


def function_row(connection: object, signature: str) -> object:
    return connection.execute(
        text(
            "SELECT pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,"
            "procedure.provolatile,procedure.proconfig::text,procedure.proacl::text,"
            "pg_catalog.pg_get_functiondef(procedure.oid) "
            "FROM pg_catalog.pg_proc AS procedure "
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


def digest(value: object) -> str:
    normalized = str(value).replace("_append_audit_event_phase8f_prior", "append_audit_event")
    return hashlib.sha256(normalized.encode()).hexdigest()


def assert_protected(row: object, volatility: str) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == volatility
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert "workloop_runtime=X" in acl and "{=X/" not in acl


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-8f-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT version_num FROM alembic_version"))
        audit = function_row(connection, f"append_audit_event({AUDIT_SIGNATURE})")
        assert_protected(audit, "v")
        if sys.argv[1] == "head":
            assert version == HEAD
            assert connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE "
                    "table_schema='public' AND table_name='leave_approval_delegates' "
                    "AND column_name='updated_at' AND is_nullable='NO')"
                )
            )
            prior = function_row(
                connection, f"_append_audit_event_phase8f_prior({AUDIT_SIGNATURE})"
            )
            assert prior[0] == "workloop_migration" and "workloop_runtime=X" not in str(prior[4])
            functions = {
                "leave_decision_visibility(uuid)": "s",
                "leave_queue_employee(uuid)": "s",
                "leave_decision_employee_status(uuid)": "s",
                "lock_leave_decision_authority(uuid)": "v",
                "read_leave_audit_projection(uuid)": "s",
                "append_leave_domain_decision_audit(uuid,text,text,text,text)": "v",
            }
            for signature, volatility in functions.items():
                assert_protected(function_row(connection, signature), volatility)
            definition = str(audit[5])
            for marker in (
                "leave_request_manager_approved",
                "leave_request_manager_rejected",
                "leave_request_approved",
                "leave_request_rejected",
                "leave_delegation_created",
                "leave_delegation_updated",
                "leave_delegation_deleted",
            ):
                assert marker in definition
            print(digest(prior[5]))
        else:
            assert version == PREDECESSOR
            assert not connection.scalar(
                text(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE "
                    "table_schema='public' AND table_name='leave_approval_delegates' "
                    "AND column_name='updated_at')"
                )
            )
            for signature in (
                f"_append_audit_event_phase8f_prior({AUDIT_SIGNATURE})",
                "leave_decision_visibility(uuid)",
                "leave_queue_employee(uuid)",
                "leave_decision_employee_status(uuid)",
                "lock_leave_decision_authority(uuid)",
                "read_leave_audit_projection(uuid)",
                "append_leave_domain_decision_audit(uuid,text,text,text,text)",
            ):
                assert absent(connection, signature)
            print(digest(audit[5]))
    engine.dispose()


if __name__ == "__main__":
    main()
