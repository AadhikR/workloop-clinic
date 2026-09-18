#!/usr/bin/env python3
"""Verify the Phase 9H replay-resource constraint and predecessor."""

from __future__ import annotations

import os
import re
import sys

from sqlalchemy import create_engine, text

HEAD = "f4b8d2e6a901"
PREDECESSOR = "e3a7c9d1f5b2"
PHASE_9G_RESOURCES = {
    "branch",
    "department",
    "employee",
    "expense_claim",
    "leave_request",
    "payroll_run",
    "salary_advance",
    "tenant",
    "user_profile",
}
PHASE_9H_RESOURCES = PHASE_9G_RESOURCES | {"compliance_override", "nafis_snapshot"}


def replay_constraint(connection: object) -> str:
    definition = connection.scalar(
        text(
            "SELECT pg_catalog.pg_get_constraintdef(oid) "
            "FROM pg_catalog.pg_constraint "
            "WHERE conrelid='public.idempotency_records'::regclass "
            "AND conname='ck_idempotency_records_replay_resource'"
        )
    )
    assert isinstance(definition, str)
    assert "replay_resource_id IS NOT NULL" in definition
    assert "replay_resource_id IS NULL" in definition
    return definition


def verify(connection: object, *, revision: str, resources: set[str]) -> None:
    assert (
        connection.scalar(text("SELECT version_num FROM alembic_version")) == revision
    )
    definition = replay_constraint(connection)
    assert set(re.findall(r"'([a-z_]+)'::text", definition)) == resources


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-9h-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        if sys.argv[1] == "head":
            verify(connection, revision=HEAD, resources=PHASE_9H_RESOURCES)
        else:
            verify(connection, revision=PREDECESSOR, resources=PHASE_9G_RESOURCES)
    engine.dispose()
    print(f"Phase 9H {sys.argv[1]} replay-resource constraint passed")


if __name__ == "__main__":
    main()
