#!/usr/bin/env python3
"""Verify the Phase 10D catalogue and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "f2d4a8c6b901"
PREDECESSOR = "b7d9e1f3a5c6"
AUDIT_ARGS = "text,text,uuid,text[],text,jsonb"
COLUMNS = {
    "source_snapshot",
    "source_digest",
    "calculation_version",
    "source_clock_event_ids",
    "evidence_flags",
    "source_stale",
}
INDEX = "ix_attendance_records_scope_stale"
TRIGGER = "trg_phase10d_clock_events_stale"
FUNCTION = "phase10d_mark_attendance_stale()"


def scalar_set(connection: object, statement: str) -> set[str]:
    return set(connection.execute(text(statement)).scalars())


def audit_digest(connection: object) -> str:
    definition = str(
        connection.scalar(
            text("SELECT pg_get_functiondef(CAST(:signature AS regprocedure))"),
            {"signature": f"public.append_audit_event({AUDIT_ARGS})"},
        )
    )
    return hashlib.sha256(definition.encode()).hexdigest()


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_records'",
    )
    assert columns >= COLUMNS
    indexes = scalar_set(
        connection,
        "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
        "AND tablename='attendance_records'",
    )
    assert INDEX in indexes
    triggers = scalar_set(
        connection,
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal",
    )
    assert TRIGGER in triggers
    assert connection.scalar(
        text("SELECT to_regprocedure('public.phase10d_mark_attendance_stale()') IS NOT NULL")
    )
    constraints = scalar_set(
        connection,
        "SELECT conname FROM pg_constraint WHERE conrelid='public.attendance_records'::regclass",
    )
    assert "ck_attendance_records_phase10d_attendance_derivation" in constraints
    replay = str(
        connection.scalar(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='public.idempotency_records'::regclass "
                "AND conname='ck_idempotency_records_replay_resource'"
            )
        )
    )
    assert "attendance_record" in replay
    return audit_digest(connection)


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_records'",
    )
    assert COLUMNS.isdisjoint(columns)
    indexes = scalar_set(
        connection,
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'",
    )
    assert INDEX not in indexes
    assert connection.scalar(
        text("SELECT to_regprocedure('public.phase10d_mark_attendance_stale()') IS NULL")
    )
    replay = str(
        connection.scalar(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='public.idempotency_records'::regclass "
                "AND conname='ck_idempotency_records_replay_resource'"
            )
        )
    )
    assert "attendance_record" not in replay
    return audit_digest(connection)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10d-revision.py head|predecessor")
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
