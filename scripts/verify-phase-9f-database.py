#!/usr/bin/env python3
"""Verify Phase 9F database authority, immutability, and self-read scope."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "b8e2c4d6f9a1"
        )
        triggers = set(
            connection.scalars(
                text(
                    "SELECT tgname FROM pg_catalog.pg_trigger WHERE NOT tgisinternal "
                    "AND tgrelid IN ('public.payslips'::regclass,"
                    "'public.payroll_approval_log'::regclass)"
                )
            )
        )
        assert {
            "trg_payslips_immutable",
            "trg_payroll_approval_log_immutable",
        } <= triggers
        payroll_update = connection.scalar(
            text(
                "SELECT has_table_privilege('workloop_runtime','public.payroll_runs','UPDATE')"
            )
        )
        assert payroll_update is False
        locker = connection.execute(
            text(
                "SELECT pg_catalog.pg_get_userbyid(proowner),prosecdef,proacl::text "
                "FROM pg_catalog.pg_proc WHERE oid="
                "'public.lock_payroll_run(uuid)'::regprocedure"
            )
        ).one()
        assert locker[0] == "workloop_migration" and locker[1] is True
        assert "workloop_runtime=X" in str(locker[2]) and "{=X/" not in str(locker[2])
        for table in ("payslips", "payroll_approval_log"):
            assert (
                connection.scalar(
                    text(
                        "SELECT relrowsecurity FROM pg_class WHERE oid=CAST(:oid AS regclass)"
                    ),
                    {"oid": f"public.{table}"},
                )
                is True
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT NOT has_table_privilege('workloop_runtime',:table,'UPDATE') "
                        "AND NOT has_table_privilege('workloop_runtime',:table,'DELETE')"
                    ),
                    {"table": f"public.{table}"},
                )
                is True
            )
        policy = connection.scalar(
            text(
                "SELECT qual FROM pg_catalog.pg_policies WHERE schemaname='public' "
                "AND tablename='payslips' AND policyname='phase5f_payslips_select_runtime'"
            )
        )
        assert "CURRENT_USER" in str(policy) and "SESSION_USER" in str(policy)
        assert "resolve_workloop_principal()" in str(policy)
        assert "workloop_role() = 'employee'::text" in str(policy)
        assert "manager" not in str(policy)
    engine.dispose()
    print("Phase 9F database authority check passed")


if __name__ == "__main__":
    main()
