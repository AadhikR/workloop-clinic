#!/usr/bin/env python3
"""Verify the Phase 10H catalogue and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "b4d7f9a2c816"
PREDECESSOR = "a1c3e5f7b902"
TABLES = {
    "roster_months",
    "roster_publication_versions",
    "roster_publication_memberships",
    "roster_actual_hours_evidence",
    "roster_overtime_approvals",
}
FUNCTIONS = {
    "public.phase10h_publish_assignments(uuid[],integer[])",
    "public.phase10h_lock_roster_overrides(text)",
    "public.phase10h_colleague_schedule(date)",
}


def scalar_set(connection: object, statement: str) -> set[str]:
    return set(connection.execute(text(statement)).scalars())


def predecessor_digest(connection: object) -> str:
    definition = connection.scalar(
        text(
            "SELECT pg_get_functiondef("
            "'public.create_roster_compliance_override(uuid,text,text,text,text,jsonb)'"
            "::regprocedure)"
        )
    )
    assert isinstance(definition, str)
    return hashlib.sha256(definition.encode()).hexdigest()


def replay_definition(connection: object) -> str:
    value = connection.scalar(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert isinstance(value, str)
    return value


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    tables = scalar_set(
        connection,
        "SELECT tablename FROM pg_tables WHERE schemaname='public' "
        "AND tablename LIKE 'roster_%'",
    )
    assert tables >= TABLES
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
    forced = set(
        connection.execute(
            text(
                "SELECT relname FROM pg_class WHERE relname=ANY(:tables) "
                "AND relrowsecurity AND relforcerowsecurity"
            ),
            {"tables": sorted(TABLES)},
        ).scalars()
    )
    assert forced == TABLES
    triggers = scalar_set(
        connection, "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
    )
    for table in TABLES - {"roster_months"}:
        assert f"trg_phase10h_{table}_append_only" in triggers
    assert "roster_publication_version" in replay_definition(connection)
    return predecessor_digest(connection)


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    tables = scalar_set(
        connection, "SELECT tablename FROM pg_tables WHERE schemaname='public'"
    )
    assert not TABLES & tables
    for signature in FUNCTIONS:
        assert connection.scalar(
            text("SELECT to_regprocedure(:signature) IS NULL"), {"signature": signature}
        )
    assert "roster_publication_version" not in replay_definition(connection)
    assert "roster_assignment" in replay_definition(connection)
    return predecessor_digest(connection)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10h-revision.py head|predecessor")
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
