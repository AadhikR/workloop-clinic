#!/usr/bin/env python3
"""Verify the Phase 10F catalogue and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "d0f6b8e2a753"
PREDECESSOR = "c9e5a7d1f642"
TABLES = (
    "attendance_period_versions",
    "attendance_period_record_snapshots",
    "attendance_period_audit_log",
)
FUNCTIONS = (
    "public.phase10f_lock_clock_events("
    "uuid,uuid,timestamp with time zone,timestamp with time zone)",
    "public.phase10f_lock_period_evidence(uuid,uuid,uuid)",
)


def scalar_set(connection: object, statement: str) -> set[str]:
    return set(connection.execute(text(statement)).scalars())


def predecessor_digest(connection: object) -> str:
    definition = connection.scalar(
        text("SELECT pg_get_functiondef('public.phase10e_regularisation_limits()'::regprocedure)")
    )
    assert isinstance(definition, str)
    return hashlib.sha256(definition.encode()).hexdigest()


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    assert all(
        connection.scalar(
            text("SELECT to_regclass(:name) IS NOT NULL"), {"name": f"public.{table}"}
        )
        for table in TABLES
    )
    period_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_periods'",
    )
    assert {"version", "current_version_id", "source_version", "updated_at"} <= period_columns
    constraints = scalar_set(
        connection,
        "SELECT conname FROM pg_constraint WHERE conrelid='public.attendance_periods'::regclass",
    )
    assert {
        "ck_attendance_periods_phase10f_period_format",
        "ck_attendance_periods_phase10f_period_state",
    } <= constraints
    triggers = scalar_set(
        connection,
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal",
    )
    assert {
        "trg_phase10f_attendance_record_guard",
        "trg_phase10f_attendance_period_guard",
        "trg_phase10f_period_versions_append_only",
        "trg_phase10f_period_snapshots_append_only",
        "trg_phase10f_period_audit_append_only",
    } <= triggers
    for table in TABLES:
        assert connection.scalar(
            text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                "WHERE oid=CAST(:name AS regclass)"
            ),
            {"name": f"public.{table}"},
        )
        assert connection.scalar(
            text("SELECT has_table_privilege('workloop_runtime',:name,'SELECT,INSERT')"),
            {"name": f"public.{table}"},
        )
        assert not connection.scalar(
            text("SELECT has_table_privilege('workloop_runtime',:name,'UPDATE,DELETE')"),
            {"name": f"public.{table}"},
        )
    for signature in FUNCTIONS:
        assert connection.scalar(
            text("SELECT to_regprocedure(:signature) IS NOT NULL"), {"signature": signature}
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
    assert isinstance(replay, str) and "attendance_period" in replay
    return predecessor_digest(connection)


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    assert all(
        connection.scalar(text("SELECT to_regclass(:name) IS NULL"), {"name": f"public.{table}"})
        for table in TABLES
    )
    period_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_periods'",
    )
    assert not {"version", "current_version_id", "source_version", "updated_at"} & period_columns
    for signature in FUNCTIONS:
        assert connection.scalar(
            text("SELECT to_regprocedure(:signature) IS NULL"), {"signature": signature}
        )
    replay = connection.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert isinstance(replay, str) and "attendance_period" not in replay
    return predecessor_digest(connection)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10f-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            print(
                verify_head(connection) if sys.argv[1] == "head" else verify_predecessor(connection)
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
