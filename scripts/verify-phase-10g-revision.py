#!/usr/bin/env python3
"""Verify the Phase 10G catalogue and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "a1c3e5f7b902"
PREDECESSOR = "d0f6b8e2a753"
OVERRIDE_FUNCTION = "public.create_roster_compliance_override(uuid,text,text,text,text,jsonb)"


def scalar_set(connection: object, statement: str) -> set[str]:
    return set(connection.execute(text(statement)).scalars())


def predecessor_digest(connection: object) -> str:
    definition = connection.scalar(
        text(
            "SELECT pg_get_functiondef("
            "'public.phase10f_lock_period_evidence(uuid,uuid,uuid)'::regprocedure)"
        )
    )
    assert isinstance(definition, str)
    return hashlib.sha256(definition.encode()).hexdigest()


def constraint_definition(connection: object, table: str, name: str) -> str:
    definition = connection.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid=CAST(:table AS regclass) AND conname=:name"
        ),
        {"table": f"public.{table}", "name": name},
    )
    assert isinstance(definition, str)
    return definition


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    roster_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='roster_assignments'",
    )
    assert "version" in roster_columns
    override_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='compliance_overrides'",
    )
    assert {"roster_month", "violation_digest", "violation_snapshot"} <= override_columns
    rule_codes = constraint_definition(
        connection, "compliance_overrides", "ck_compliance_overrides_rule_code"
    )
    assert "leave_conflict" in rule_codes and "staffing_shortfall" in rule_codes
    assert "roster_publish" in constraint_definition(
        connection, "compliance_overrides", "ck_compliance_overrides_phase10g_roster_override"
    )
    indexes = scalar_set(
        connection,
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'",
    )
    assert {
        "ix_roster_assignments_scope_date_employee",
        "uq_compliance_overrides_roster_violation",
    } <= indexes
    triggers = scalar_set(
        connection,
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal",
    )
    assert "trg_phase10g_roster_draft_guard" in triggers
    assert connection.scalar(
        text("SELECT to_regprocedure(:signature) IS NOT NULL"),
        {"signature": OVERRIDE_FUNCTION},
    )
    assert connection.scalar(
        text("SELECT has_function_privilege('workloop_runtime',:signature,'EXECUTE')"),
        {"signature": OVERRIDE_FUNCTION},
    )
    assert not connection.scalar(
        text("SELECT has_function_privilege('public',:signature,'EXECUTE')"),
        {"signature": OVERRIDE_FUNCTION},
    )
    replay = constraint_definition(
        connection, "idempotency_records", "ck_idempotency_records_replay_resource"
    )
    assert "roster_assignment" in replay
    return predecessor_digest(connection)


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    roster_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='roster_assignments'",
    )
    assert "version" not in roster_columns
    override_columns = scalar_set(
        connection,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='compliance_overrides'",
    )
    assert not {"roster_month", "violation_digest", "violation_snapshot"} & override_columns
    assert "staffing_shortfall" not in constraint_definition(
        connection, "compliance_overrides", "ck_compliance_overrides_rule_code"
    )
    indexes = scalar_set(
        connection,
        "SELECT indexname FROM pg_indexes WHERE schemaname='public'",
    )
    assert "ix_roster_assignments_scope_date_employee" not in indexes
    assert "uq_compliance_overrides_roster_violation" not in indexes
    triggers = scalar_set(
        connection,
        "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal",
    )
    assert "trg_phase10g_roster_draft_guard" not in triggers
    assert connection.scalar(
        text("SELECT to_regprocedure(:signature) IS NULL"),
        {"signature": OVERRIDE_FUNCTION},
    )
    replay = constraint_definition(
        connection, "idempotency_records", "ck_idempotency_records_replay_resource"
    )
    assert "roster_assignment" not in replay
    assert "attendance_period" in replay
    return predecessor_digest(connection)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10g-revision.py head|predecessor")
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
