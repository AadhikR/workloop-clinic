#!/usr/bin/env python3
"""Verify the Phase 10E catalogue and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "c9e5a7d1f642"
PREDECESSOR = "f2d4a8c6b901"


def scalar_set(connection: object, statement: str) -> set[str]:
    return set(connection.execute(text(statement)).scalars())


def constraint_names(connection: object, table: str) -> set[str]:
    return scalar_set(
        connection,
        "SELECT conname FROM pg_constraint "
        f"WHERE conrelid='public.{table}'::regclass",
    )


def index_definition(connection: object, name: str) -> str:
    result = connection.scalar(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname='public' AND indexname=:name"
        ),
        {"name": name},
    )
    assert isinstance(result, str)
    return result


def predecessor_digest(connection: object) -> str:
    definition = connection.scalar(
        text(
            "SELECT pg_get_functiondef("
            "'public.phase10d_mark_attendance_stale()'::regprocedure)"
        )
    )
    assert isinstance(definition, str)
    return hashlib.sha256(definition.encode()).hexdigest()


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='regularisation_requests'",
    )
    assert "version" in columns
    record_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_records'",
    )
    assert {
        "resolved_at",
        "resolution_source_digest",
        "overtime_approved_at",
        "overtime_approval_source_digest",
    } <= record_columns
    regularisation_constraints = constraint_names(connection, "regularisation_requests")
    assert {
        "ck_regularisation_requests_phase10e_regularisation_version",
        "ck_regularisation_requests_phase10e_regularisation_reason",
        "ck_regularisation_requests_phase10e_regularisation_span",
    } <= regularisation_constraints
    assert "ck_regularisation_requests_phase10e_decision_state" in regularisation_constraints
    assert {
        "ck_attendance_records_phase10e_attendance_resolution_evidence",
        "ck_attendance_records_phase10e_overtime_approval_evidence",
    } <= constraint_names(connection, "attendance_records")
    assert "ck_clock_events_phase10e_clock_event_supersession" in constraint_names(
        connection, "clock_events"
    )
    assert (
        "ck_attendance_audit_log_phase10e_attendance_audit_action"
        in constraint_names(connection, "attendance_audit_log")
    )
    assert "superseded_by IS NULL" in index_definition(
        connection, "uq_clock_events_method_minute"
    )
    assert "status = 'Pending'::text" in index_definition(
        connection, "uq_regularisation_requests_pending_employee_date"
    )
    triggers = scalar_set(
        connection,
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal",
    )
    assert "trg_phase10e_attendance_audit_append_only" in triggers
    for signature in (
        "public.phase10e_regularisation_limits()",
        "public.phase10e_prepare_regularisation_approval(uuid,integer)",
    ):
        assert connection.scalar(
            text("SELECT to_regprocedure(:signature) IS NOT NULL"),
            {"signature": signature},
        )
        assert connection.scalar(
            text(
                "SELECT prosecdef FROM pg_proc WHERE oid=to_regprocedure(:signature)"
            ),
            {"signature": signature},
        )
        assert connection.scalar(
            text(
                "SELECT pg_get_userbyid(proowner)='workloop_migration' "
                "FROM pg_proc WHERE oid=to_regprocedure(:signature)"
            ),
            {"signature": signature},
        )
        assert connection.scalar(
            text("SELECT has_function_privilege('workloop_runtime',:signature,'EXECUTE')"),
            {"signature": signature},
        )
        assert not connection.scalar(
            text("SELECT has_function_privilege('public',:signature,'EXECUTE')"),
            {"signature": signature},
        )
    replay = connection.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert isinstance(replay, str) and "regularisation_request" in replay
    return predecessor_digest(connection)


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='regularisation_requests'",
    )
    assert "version" not in columns
    record_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_records'",
    )
    assert not {
        "resolved_at",
        "resolution_source_digest",
        "overtime_approved_at",
        "overtime_approval_source_digest",
    } & record_columns
    assert {
        "ck_regularisation_requests_decision_fields",
        "ck_regularisation_requests_rejection_fields",
    } <= constraint_names(connection, "regularisation_requests")
    assert not any(
        "phase10e" in name
        for table in (
            "regularisation_requests",
            "attendance_records",
            "attendance_audit_log",
            "clock_events",
        )
        for name in constraint_names(connection, table)
    )
    assert "superseded_by IS NULL" not in index_definition(
        connection, "uq_clock_events_method_minute"
    )
    assert connection.scalar(
        text(
            "SELECT to_regclass("
            "'public.uq_regularisation_requests_pending_employee_date') IS NULL"
        )
    )
    for signature in (
        "public.phase10e_regularisation_limits()",
        "public.phase10e_prepare_regularisation_approval(uuid,integer)",
    ):
        assert connection.scalar(
            text("SELECT to_regprocedure(:signature) IS NULL"),
            {"signature": signature},
        )
    assert "trg_phase10e_attendance_audit_append_only" not in scalar_set(
        connection, "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
    )
    replay = connection.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert isinstance(replay, str) and "regularisation_request" not in replay
    return predecessor_digest(connection)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10e-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            print(
                verify_head(connection)
                if sys.argv[1] == "head"
                else verify_predecessor(connection)
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
