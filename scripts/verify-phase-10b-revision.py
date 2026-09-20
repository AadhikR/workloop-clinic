#!/usr/bin/env python3
"""Verify the Phase 10B schema and its exact predecessor rollback."""

from __future__ import annotations

import hashlib
import os
import sys

from sqlalchemy import create_engine, text

HEAD = "a6c8e0f2b4d7"
PREDECESSOR = "f4b8d2e6a901"
AUDIT_ARGS = "text,text,uuid,text[],text,jsonb"
PHASE10B_CONSTRAINTS = {
    "ck_attendance_settings_phase10b_attendance_settings_bounds",
    "ck_attendance_settings_phase10b_attendance_settings_days",
    "ck_attendance_settings_phase10b_attendance_settings_secret",
    "ck_shifts_phase10b_shifts_bounds",
    "ck_shifts_phase10b_shifts_shape",
    "ck_shifts_phase10b_shifts_text",
    "shift_assignments_no_overlap",
}


def function_row(connection: object, signature: str) -> object:
    return connection.execute(
        text(
            "SELECT pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,"
            "procedure.provolatile,procedure.proconfig::text,procedure.proacl::text,"
            "pg_catalog.pg_get_functiondef(procedure.oid) "
            "FROM pg_catalog.pg_proc AS procedure "
            "JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace "
            "WHERE namespace.nspname='public' "
            "AND procedure.oid=CAST(:signature AS regprocedure)"
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


def digest(definition: object) -> str:
    normalized = str(definition).replace(
        "_append_audit_event_phase10a", "append_audit_event"
    )
    return hashlib.sha256(normalized.encode()).hexdigest()


def assert_protected(row: object, *, runtime: bool = True) -> None:
    assert row[0] == "workloop_migration"
    assert row[1] is True and row[2] == "v"
    assert row[3] == '{"search_path=pg_catalog, public, pg_temp"}'
    acl = str(row[4])
    assert ("workloop_runtime=X" in acl) is runtime
    assert "{=X/" not in acl


def constraint_names(connection: object) -> set[str]:
    return set(
        connection.execute(
            text(
                "SELECT conname FROM pg_catalog.pg_constraint "
                "WHERE conrelid IN "
                "('public.attendance_settings'::regclass,'public.shifts'::regclass,"
                "'public.shift_assignments'::regclass)"
            )
        ).scalars()
    )


def column_default(connection: object, table: str, column: str) -> str:
    value = connection.scalar(
        text(
            "SELECT pg_catalog.pg_get_expr(attribute.adbin,attribute.adrelid) "
            "FROM pg_catalog.pg_attrdef attribute "
            "JOIN pg_catalog.pg_attribute column_value "
            "ON column_value.attrelid=attribute.adrelid "
            "AND column_value.attnum=attribute.adnum "
            "WHERE attribute.adrelid=CAST(:table AS regclass) "
            "AND column_value.attname=:column"
        ),
        {"table": f"public.{table}", "column": column},
    )
    return str(value)


def verify_head(connection: object) -> str:
    assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
    assert connection.scalar(
        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='btree_gist')")
    )
    assert PHASE10B_CONSTRAINTS <= constraint_names(connection)
    assert "Sun" in column_default(connection, "attendance_settings", "working_days")
    assert "#6366F1" in column_default(connection, "shifts", "color")

    column = connection.execute(
        text(
            "SELECT is_nullable,column_default FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='shift_assignments' "
            "AND column_name='updated_at'"
        )
    ).one()
    assert column[0] == "NO" and "now()" in str(column[1])
    assert connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE schemaname='public' "
            "AND tablename='shift_assignments' "
            "AND indexname='ix_shift_assignments_scope_employee_effective' "
            "AND indexdef LIKE '%effective_from DESC%')"
        )
    )
    assert connection.scalar(
        text(
            "SELECT EXISTS(SELECT 1 FROM pg_trigger "
            "WHERE tgrelid='public.shift_assignments'::regclass "
            "AND tgname='trg_shift_assignments_set_updated_at' AND NOT tgisinternal)"
        )
    )

    replay = str(
        connection.scalar(
            text(
                "SELECT pg_catalog.pg_get_constraintdef(oid) "
                "FROM pg_catalog.pg_constraint "
                "WHERE conrelid='public.idempotency_records'::regclass "
                "AND conname='ck_idempotency_records_replay_resource'"
            )
        )
    )
    for resource in ("attendance_settings", "shift", "shift_assignment"):
        assert resource in replay

    for table_name in ("attendance_settings", "shifts", "shift_assignments"):
        table = connection.execute(
            text(
                "SELECT pg_catalog.pg_get_userbyid(class.relowner),class.relrowsecurity,"
                "class.relforcerowsecurity FROM pg_catalog.pg_class AS class "
                "WHERE class.oid=CAST(:table AS regclass)"
            ),
            {"table": f"public.{table_name}"},
        ).one()
        assert table == ("workloop_migration", True, False)
        privileges = set(
            connection.execute(
                text(
                    "SELECT privilege_type FROM information_schema.role_table_grants "
                    "WHERE table_schema='public' AND table_name=:table "
                    "AND grantee='workloop_runtime'"
                ),
                {"table": table_name},
            ).scalars()
        )
        assert {"SELECT", "INSERT", "UPDATE"} <= privileges
        assert "DELETE" not in privileges

    current = function_row(connection, f"append_audit_event({AUDIT_ARGS})")
    prior = function_row(connection, f"_append_audit_event_phase10a({AUDIT_ARGS})")
    assert_protected(current)
    assert_protected(prior, runtime=False)
    definition = str(current[5])
    for action in (
        "attendance_settings_changed",
        "shift_created",
        "shift_changed",
        "shift_deactivated",
        "shift_assigned",
    ):
        assert action in definition
    return digest(prior[5])


def verify_predecessor(connection: object) -> str:
    assert (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        == PREDECESSOR
    )
    assert PHASE10B_CONSTRAINTS.isdisjoint(constraint_names(connection))
    assert connection.scalar(
        text(
            "SELECT NOT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='shift_assignments' "
            "AND column_name='updated_at')"
        )
    )
    assert connection.scalar(
        text(
            "SELECT NOT EXISTS(SELECT 1 FROM pg_indexes WHERE schemaname='public' "
            "AND indexname='ix_shift_assignments_scope_employee_effective')"
        )
    )
    assert absent(connection, f"_append_audit_event_phase10a({AUDIT_ARGS})")
    replay = str(
        connection.scalar(
            text(
                "SELECT pg_catalog.pg_get_constraintdef(oid) "
                "FROM pg_catalog.pg_constraint "
                "WHERE conrelid='public.idempotency_records'::regclass "
                "AND conname='ck_idempotency_records_replay_resource'"
            )
        )
    )
    for resource in ("attendance_settings", "shift_assignment"):
        assert resource not in replay
    assert "Sun" not in column_default(
        connection, "attendance_settings", "working_days"
    )
    assert "#6366f1" in column_default(connection, "shifts", "color")
    audit = function_row(connection, f"append_audit_event({AUDIT_ARGS})")
    assert_protected(audit)
    assert "attendance_settings_changed" not in str(audit[5])
    return digest(audit[5])


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"head", "predecessor"}:
        raise SystemExit("usage: verify-phase-10b-revision.py head|predecessor")
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    try:
        with engine.connect() as connection:
            value = (
                verify_head(connection)
                if sys.argv[1] == "head"
                else verify_predecessor(connection)
            )
            print(value)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
