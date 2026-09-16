#!/usr/bin/env python3
"""Verify the Phase 9B receipt schema and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "a1c3e5f7b9d2"
PREDECESSOR = "e8f4c7b2a610"
AUDIT_SIGNATURE = "text,text,uuid,text[],text,jsonb"
PHASE9B_AUDIT_SIGNATURE = f"_append_audit_event_phase9c_prior({AUDIT_SIGNATURE})"


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
    normalized = str(value).replace("_append_audit_event_phase9b_prior", "append_audit_event")
    return hashlib.sha256(normalized.encode()).hexdigest()


def assert_protected(row: object) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == "v"
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert "workloop_runtime=X" in acl and "{=X/" not in acl


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    table = connection.execute(
        text(
            "SELECT pg_catalog.pg_get_userbyid(class.relowner),class.relrowsecurity,"
            "class.relforcerowsecurity FROM pg_catalog.pg_class AS class "
            "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=class.relnamespace "
            "WHERE namespace.nspname='public' AND class.relname='expense_receipts'"
        )
    ).one()
    assert table == ("workloop_migration", True, True)
    constraints = set(
        connection.execute(
            text(
                "SELECT conname FROM pg_catalog.pg_constraint "
                "WHERE conrelid='public.expense_receipts'::regclass"
            )
        ).scalars()
    )
    assert {
        "pk_expense_receipts",
        "ck_expense_receipts_lifecycle",
        "ck_expense_receipts_metadata_completeness",
        "fk_expense_receipts_expense_claim_id_expense_claims",
        "uq_expense_receipts_expense_claim_id",
        "uq_expense_receipts_submission_token_digest",
    } <= constraints
    indexes = set(
        connection.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND tablename='expense_receipts'"
            )
        ).scalars()
    )
    assert {
        "ix_expense_receipts_employee_scope",
        "ix_expense_receipts_staged_expiry",
    } <= indexes
    policies = set(
        connection.execute(
            text(
                "SELECT policyname FROM pg_policies "
                "WHERE schemaname='public' AND tablename='expense_receipts'"
            )
        ).scalars()
    )
    assert policies == {
        "expense_receipts_migration_all",
        "expense_receipts_runtime_select",
        "expense_receipts_runtime_insert",
        "expense_receipts_runtime_update",
    }
    replay_constraint = connection.scalar(
        text(
            "SELECT pg_catalog.pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert "expense_claim" in str(replay_constraint)
    grants = connection.execute(
        text(
            "SELECT privilege_type,column_name FROM information_schema.column_privileges "
            "WHERE table_schema='public' AND table_name='expense_receipts' "
            "AND grantee='workloop_runtime'"
        )
    ).all()
    assert grants and not any(privilege == "DELETE" for privilege, _ in grants)
    audit = function_row(connection, f"append_audit_event({AUDIT_SIGNATURE})")
    assert_protected(audit)
    phase9b_audit = function_row(connection, PHASE9B_AUDIT_SIGNATURE)
    assert phase9b_audit[0] == "workloop_migration"
    assert phase9b_audit[1] is True and phase9b_audit[2] == "v"
    assert phase9b_audit[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    assert "workloop_runtime=X" not in str(phase9b_audit[4])
    definition = str(phase9b_audit[5])
    assert "expense_receipt_uploaded" in definition
    assert "expense_receipt_cleanup_requested" in definition
    prior = function_row(connection, f"_append_audit_event_phase9b_prior({AUDIT_SIGNATURE})")
    assert prior[0] == "workloop_migration" and "workloop_runtime=X" not in str(prior[4])
    assert_protected(function_row(connection, "lock_expense_claim(uuid)"))
    assert_protected(function_row(connection, "lock_expense_direct_report(uuid)"))
    return digest(prior[5])


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    assert connection.scalar(text("SELECT to_regclass('public.expense_receipts') IS NULL"))
    assert not connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_constraint "
            "WHERE conrelid='public.expense_claims'::regclass "
            "AND conname='uq_expense_claims_id_company_id_branch_id')"
        )
    )
    assert absent(connection, f"_append_audit_event_phase9b_prior({AUDIT_SIGNATURE})")
    assert absent(connection, "lock_expense_claim(uuid)")
    assert absent(connection, "lock_expense_direct_report(uuid)")
    replay_constraint = connection.scalar(
        text(
            "SELECT pg_catalog.pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert "expense_claim" not in str(replay_constraint) and "leave_request" in str(
        replay_constraint
    )
    audit = function_row(connection, f"append_audit_event({AUDIT_SIGNATURE})")
    assert_protected(audit)
    return digest(audit[5])


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-9b-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        value = verify_head(connection) if sys.argv[1] == "head" else verify_predecessor(connection)
        print(value)
    engine.dispose()


if __name__ == "__main__":
    main()
