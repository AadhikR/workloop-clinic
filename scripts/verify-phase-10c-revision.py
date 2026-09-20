#!/usr/bin/env python3
"""Verify the Phase 10C catalogue and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "b7d9e1f3a5c6"
PREDECESSOR = "a6c8e0f2b4d7"
AUDIT_ARGS = "text,text,uuid,text[],text,jsonb"
TABLES = {"attendance_import_batches", "attendance_import_row_outcomes"}
INDEXES = {
    "ix_attendance_import_batches_scope_created",
    "ix_biometric_mappings_scope_badge",
    "ix_clock_events_scope_employee_time",
    "uq_clock_events_method_minute",
    "uq_clock_events_fingerprint",
}
TRIGGERS = {
    "trg_phase10c_clock_events_append_only",
    "trg_phase10c_import_batches_append_only",
    "trg_phase10c_import_outcomes_append_only",
}


def scalar_set(connection: object, statement: str) -> set[str]:
    return set(connection.execute(text(statement)).scalars())


def function_definition(connection: object, signature: str) -> str:
    return str(
        connection.scalar(
            text(
                "SELECT pg_catalog.pg_get_functiondef(CAST(:signature AS regprocedure))"
            ),
            {"signature": f"public.{signature}"},
        )
    )


def digest(definition: str) -> str:
    normalized = definition.replace(
        "_append_audit_event_phase10c", "append_audit_event"
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    tables = scalar_set(
        connection,
        "SELECT tablename FROM pg_tables WHERE schemaname='public'",
    )
    assert TABLES <= tables
    indexes = scalar_set(
        connection,
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'",
    )
    assert INDEXES <= indexes
    triggers = scalar_set(
        connection,
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal",
    )
    assert TRIGGERS <= triggers
    columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='clock_events'",
    )
    assert {
        "event_fingerprint",
        "import_batch_id",
        "import_row_number",
        "source_badge_no",
        "source_device_name",
    } <= columns
    outcome_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='attendance_import_row_outcomes'",
    )
    assert {"company_id", "branch_id"} <= outcome_columns
    constraints = scalar_set(
        connection,
        "SELECT conname FROM pg_constraint WHERE connamespace='public'::regnamespace",
    )
    assert {
        "uq_attendance_import_batches_id_scope",
        "uq_clock_events_id_scope",
        "fk_clock_events_import_batch_scope",
    } <= constraints
    for table_name in TABLES:
        owner, rls = connection.execute(
            text(
                "SELECT pg_catalog.pg_get_userbyid(relowner),relrowsecurity "
                "FROM pg_class WHERE oid=CAST(:table AS regclass)"
            ),
            {"table": f"public.{table_name}"},
        ).one()
        assert owner == "workloop_migration" and rls is True
        privileges = scalar_set(
            connection,
            "SELECT privilege_type FROM information_schema.role_table_grants "
            f"WHERE table_schema='public' AND table_name='{table_name}' "
            "AND grantee='workloop_runtime'",
        )
        assert privileges == {"INSERT", "SELECT"}
    replay = str(
        connection.scalar(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='public.idempotency_records'::regclass "
                "AND conname='ck_idempotency_records_replay_resource'"
            )
        )
    )
    for resource in ("clock_event", "biometric_mapping", "attendance_import_batch"):
        assert resource in replay
    current = function_definition(connection, f"append_audit_event({AUDIT_ARGS})")
    for action in (
        "attendance_manual_event_created",
        "biometric_mapping_replaced",
        "biometric_mapping_deleted",
        "attendance_biometric_batch_imported",
    ):
        assert action in current
    prior = function_definition(
        connection, f"_append_audit_event_phase10c({AUDIT_ARGS})"
    )
    return digest(prior)


def verify_predecessor(connection: object) -> str:
    assert (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        == PREDECESSOR
    )
    tables = scalar_set(
        connection,
        "SELECT tablename FROM pg_tables WHERE schemaname='public'",
    )
    assert TABLES.isdisjoint(tables)
    indexes = scalar_set(
        connection,
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'",
    )
    assert INDEXES.isdisjoint(indexes)
    assert connection.scalar(
        text(
            "SELECT to_regprocedure('public._append_audit_event_phase10c"
            "(text,text,uuid,text[],text,jsonb)') IS NULL"
        )
    )
    definition = function_definition(connection, f"append_audit_event({AUDIT_ARGS})")
    assert "attendance_manual_event_created" not in definition
    return digest(definition)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10c-revision.py head|predecessor")
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
