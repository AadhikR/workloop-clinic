#!/usr/bin/env python3
"""Verify the Phase 10I catalogue and exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "c6e8a1b3d927"
PREDECESSOR = "b4d7f9a2c816"
STAFF_SUBMIT = "public.staff_submit_shift_swap(uuid,date,date,text,text)"
PARTICIPANT_NAME = "public.shift_swap_participant_name(uuid,uuid)"
ADMIN_EXECUTE = "public.admin_execute_shift_swap(uuid,uuid)"
RETAINED_ADMIN = "public._admin_execute_shift_swap_phase10h(uuid,uuid)"
COLUMNS = {
    "contract_version",
    "expected_roster_source_version",
    "source_publication_version_id",
    "requester_assignment_id",
    "target_assignment_id",
    "expected_requester_assignment_version",
    "expected_target_assignment_version",
    "approved_publication_version_id",
    "decided_at",
    "decided_by_app_user_id",
    "version",
}


def function_body_digest(connection: object, signature: str) -> str:
    body = connection.scalar(
        text("SELECT prosrc FROM pg_proc WHERE oid=to_regprocedure(:signature)"),
        {"signature": signature},
    )
    assert isinstance(body, str)
    return hashlib.sha256(body.encode()).hexdigest()


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
    assert connection.scalar(text("SELECT to_regclass('public.shift_swap_history') IS NOT NULL"))
    columns = set(
        connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='shift_swap_requests'"
            )
        ).scalars()
    )
    assert columns >= COLUMNS
    for signature in (STAFF_SUBMIT, PARTICIPANT_NAME, ADMIN_EXECUTE):
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
    assert not connection.scalar(
        text("SELECT has_table_privilege('workloop_runtime','shift_swap_requests','INSERT')")
    )
    assert connection.scalar(
        text(
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
            "WHERE oid='public.shift_swap_history'::regclass"
        )
    )
    assert "shift_swap_request" in replay_definition(connection)
    return function_body_digest(connection, RETAINED_ADMIN)


def verify_predecessor(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    assert connection.scalar(text("SELECT to_regclass('public.shift_swap_history') IS NULL"))
    columns = set(
        connection.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='shift_swap_requests'"
            )
        ).scalars()
    )
    assert not COLUMNS & columns
    for signature in (STAFF_SUBMIT, PARTICIPANT_NAME, RETAINED_ADMIN):
        assert connection.scalar(
            text("SELECT to_regprocedure(:signature) IS NULL"), {"signature": signature}
        )
    assert connection.scalar(
        text("SELECT to_regprocedure(:signature) IS NOT NULL"), {"signature": ADMIN_EXECUTE}
    )
    assert connection.scalar(
        text("SELECT has_table_privilege('workloop_runtime','shift_swap_requests','INSERT')")
    )
    assert "shift_swap_request" not in replay_definition(connection)
    return function_body_digest(connection, ADMIN_EXECUTE)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10i-revision.py head|predecessor")
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
