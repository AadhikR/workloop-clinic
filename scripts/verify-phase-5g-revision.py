
import hashlib
import json
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
    "2c4d6e8f0a1b": (
        69,
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

EXPECTED_CATALOGUE_HASH = {
    "d85a6f0c3b42": "6925b2b73c77d1aa52f983a6d5388282d32d7ad64a798d50c32e412e30f5c804",
    "e96f7a1b4c53": "10c752c1bdc93d735a58b452ead7e017cf3cfd42268d9eb6847ced0307e73ed6",
    "f07a8b2c5d64": "73e2180f02fb010b54cc9d647d275e25d35626a0277ee6c1b8975432a804c2b7",
    "0a18c3d6e75f": "90b2f6396c460d70de135bf57cbc7de637bb2f462f6c0804b3dac2b7a1b603a6",
    "1b29d4e7f860": "0c91b337ce6b38c7d7a2db64c9a8b8d1587102dc0ca1b0dcd68915cd2f9a98a7",
    "2c4d6e8f0a1b": "bd6a3b73296d847c951bb7bc3d360b5e85e7c13538ec7347ef74344f16f583e2",
}


CATALOGUE_QUERIES = (
    "SELECT tablename,policyname,permissive,cmd,roles::text,coalesce(qual,''),coalesce(with_check,'') FROM pg_catalog.pg_policies WHERE schemaname='public' ORDER BY 1,2",
    "SELECT table_name,grantee,privilege_type,is_grantable FROM information_schema.table_privileges WHERE table_schema='public' AND grantee IN ('workloop_runtime','workloop_expiry_processing') ORDER BY 1,2,3,4",
    "SELECT table_name,column_name,grantee,privilege_type,is_grantable FROM information_schema.column_privileges WHERE table_schema='public' AND grantee IN ('workloop_runtime','workloop_expiry_processing') ORDER BY 1,2,3,4,5",
    "SELECT routine_name,grantee,privilege_type,is_grantable FROM information_schema.routine_privileges WHERE specific_schema='public' AND grantee IN ('workloop_runtime','workloop_expiry_processing','PUBLIC') ORDER BY 1,2,3,4",
    "SELECT object.relname,object.relrowsecurity,object.relforcerowsecurity FROM pg_catalog.pg_class AS object JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=object.relnamespace WHERE namespace.nspname='public' AND object.relkind='r' ORDER BY 1",
    "SELECT procedure.proname,pg_catalog.pg_get_function_identity_arguments(procedure.oid),pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,procedure.provolatile,procedure.proconfig::text,procedure.proacl::text,pg_catalog.pg_get_functiondef(procedure.oid) FROM pg_catalog.pg_proc AS procedure JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace WHERE namespace.nspname='public' ORDER BY 1,2",
    "SELECT object.relname,con.conname,pg_catalog.pg_get_constraintdef(con.oid,true) FROM pg_catalog.pg_constraint AS con JOIN pg_catalog.pg_class AS object ON object.oid=con.conrelid JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=object.relnamespace WHERE namespace.nspname='public' ORDER BY 1,2",
    "SELECT tablename,indexname,indexdef FROM pg_catalog.pg_indexes WHERE schemaname='public' ORDER BY 1,2",
    "SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,coalesce(column_default,'') FROM information_schema.columns WHERE table_schema='public' ORDER BY 1,3",
)


def exact_catalogue_hash(connection: object) -> str:
    payload = [connection.execute(text(query)).all() for query in CATALOGUE_QUERIES]
    payload[5] = [
        (
            *row[:-1],
            "\n".join(
                line.rstrip() for line in str(row[-1]).splitlines() if line.strip()
            ),
        )
        for row in payload[5]
    ]
    encoded = json.dumps(payload, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


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
                    "SELECT proname FROM pg_catalog.pg_proc AS procedure JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=procedure.pronamespace WHERE namespace.nspname='public' AND proname IN ('create_workflow_notification','append_audit_event','lock_authorized_employee_relationships')"
                )
            ).scalars()
        )
        expected_functions = set()
        if notification_function:
            expected_functions.add("create_workflow_notification")
        if audit_table:
            expected_functions.add("append_audit_event")
        if revision == "2c4d6e8f0a1b":
            expected_functions.add("lock_authorized_employee_relationships")
        assert functions == expected_functions
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_policies WHERE schemaname='public' AND tablename IN ('nafis_reports','compliance_overrides') AND policyname LIKE 'phase5f_%'"
                )
            ).scalar_one()
            == 5
        )
        actual_hash = exact_catalogue_hash(connection)
        if len(sys.argv) == 3 and sys.argv[2] == "--print-hash":
            print(f'{revision} {actual_hash}')
            return
        expected_hash = EXPECTED_CATALOGUE_HASH[revision]
        assert actual_hash == expected_hash
    engine.dispose()
    print(f"Phase 5G revision {revision} catalog and rollback state passed.")


if __name__ == "__main__":
    main()
