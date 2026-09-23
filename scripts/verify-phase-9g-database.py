#!/usr/bin/env python3
"""Verify Phase 9G database authority and immutable evidence."""

from __future__ import annotations

import os

from sqlalchemy import create_engine, text


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "f0b2c4d6e8a3"
        )
        for table in (
            "payroll_runs",
            "payroll_entries",
            "compliance_overrides",
            "nafis_reports",
        ):
            assert (
                connection.scalar(
                    text("SELECT relrowsecurity FROM pg_class WHERE oid=CAST(:table AS regclass)"),
                    {"table": f"public.{table}"},
                )
                is True
            )
        for table in ("compliance_overrides", "nafis_reports"):
            assert (
                connection.scalar(
                    text(
                        "SELECT NOT has_table_privilege('workloop_runtime',:table,'INSERT') "
                        "AND NOT has_table_privilege('workloop_runtime',:table,'UPDATE') "
                        "AND NOT has_table_privilege('workloop_runtime',:table,'DELETE')"
                    ),
                    {"table": f"public.{table}"},
                )
                is True
            )
        assert (
            connection.scalar(
                text("SELECT NOT has_table_privilege('workloop_runtime','payroll_runs','UPDATE')")
            )
            is True
        )
        assert (
            connection.scalar(
                text(
                    "SELECT NOT has_table_privilege('workloop_runtime','payroll_entries','UPDATE')"
                )
            )
            is True
        )
        policies = list(
            connection.execute(
                text(
                    "SELECT tablename,cmd,qual,with_check FROM pg_catalog.pg_policies "
                    "WHERE schemaname='public' AND tablename IN "
                    "('compliance_overrides','nafis_reports')"
                )
            )
        )
        assert policies
        combined = " ".join(str(value) for row in policies for value in row)
        assert "workloop_role() = 'admin'::text" in combined
        assert "workloop_branch_id()" in combined
        assert "workloop_role() = 'manager'::text" not in combined
        assert "workloop_role() = 'employee'::text" not in combined
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_constraint WHERE conrelid="
                    "'public.compliance_overrides'::regclass AND conname IN "
                    "('ck_compliance_overrides_rule_code',"
                    "'fk_compliance_overrides_payroll_run_id_payroll_runs',"
                    "'fk_compliance_overrides_payroll_entry_id_payroll_entries')"
                )
            )
            == 3
        )
    engine.dispose()
    print("Phase 9G database authority check passed")


if __name__ == "__main__":
    main()
