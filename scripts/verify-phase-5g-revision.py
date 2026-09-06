# ruff: noqa: E501

import os
import sys

from sqlalchemy import create_engine, text

EXPECTED = {
    "d85a6f0c3b42": (0, set(), False, False),
    "e96f7a1b4c53": (
        22,
        {
            "employee_documents",
            "insurance_policies",
            "employee_insurance",
            "insurance_dependants",
            "notifications",
        },
        True,
        False,
    ),
    "f07a8b2c5d64": (
        39,
        {
            "employee_documents",
            "insurance_policies",
            "employee_insurance",
            "insurance_dependants",
            "notifications",
            "employee_contracts",
            "offboarding_checklists",
            "offboarding_tasks",
            "offboarding_task_templates",
            "assets",
            "asset_assignments",
        },
        True,
        False,
    ),
    "0a18c3d6e75f": (
        68,
        {
            "employee_documents",
            "insurance_policies",
            "employee_insurance",
            "insurance_dependants",
            "notifications",
            "employee_contracts",
            "offboarding_checklists",
            "offboarding_tasks",
            "offboarding_task_templates",
            "assets",
            "asset_assignments",
            "training_records",
            "certifications",
            "appraisal_cycles",
            "appraisals",
            "appraisal_sections",
            "cme_requirements",
            "incident_reports",
            "letter_requests",
        },
        True,
        False,
    ),
    "1b29d4e7f860": (
        70,
        {
            "employee_documents",
            "insurance_policies",
            "employee_insurance",
            "insurance_dependants",
            "notifications",
            "employee_contracts",
            "offboarding_checklists",
            "offboarding_tasks",
            "offboarding_task_templates",
            "assets",
            "asset_assignments",
            "training_records",
            "certifications",
            "appraisal_cycles",
            "appraisals",
            "appraisal_sections",
            "cme_requirements",
            "incident_reports",
            "letter_requests",
            "audit_events",
        },
        True,
        True,
    ),
}


def main() -> None:
    revision = sys.argv[1]
    expected_count, expected_tables, notification_function, audit_table = EXPECTED[revision]
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == revision
        )
        rows = connection.execute(
            text(
                "SELECT tablename,policyname FROM pg_catalog.pg_policies WHERE schemaname='public' AND policyname LIKE 'phase5g_%'"
            )
        ).all()
        assert len(rows) == expected_count
        assert {row[0] for row in rows} == expected_tables
        table_exists = connection.execute(
            text("SELECT to_regclass('public.audit_events') IS NOT NULL")
        ).scalar_one()
        assert table_exists is audit_table
        functions = set(
            connection.execute(
                text(
                    "SELECT proname FROM pg_catalog.pg_proc AS procedure JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace WHERE namespace.nspname='public' AND proname IN ('create_workflow_notification','append_audit_event')"
                )
            ).scalars()
        )
        expected_functions = set()
        if notification_function:
            expected_functions.add("create_workflow_notification")
        if audit_table:
            expected_functions.add("append_audit_event")
        assert functions == expected_functions
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname='public' AND tablename IN ('nafis_reports','compliance_overrides') AND policyname LIKE 'phase5f_%'"
                )
            ).scalar_one()
            == 5
        )
    engine.dispose()
    print(f"Phase 5G revision {revision} catalog and rollback state passed.")


if __name__ == "__main__":
    main()
