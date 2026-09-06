import json
import os
import runpy
from pathlib import Path
from typing import Any

import psycopg
from sqlalchemy import create_engine, text

BASE = runpy.run_path(str(Path(__file__).with_name("verify-phase-5e-rls.py")))
c = BASE["c"]
build_rows = BASE["build_rows"]
apply_rows = BASE["apply_rows"]
clean = BASE["clean"]
validate = BASE["validate"]
connect_as = BASE["connect_as"]
human_context = BASE["human_context"]
job_context = BASE["job_context"]
principal_for = BASE["principal_for"]
scalar = BASE["scalar"]

CATALOGUE = json.loads(Path(__file__).with_name("phase-5g-catalogue.json").read_text())
TABLES = tuple(CATALOGUE["tables"])
BUSINESS_TABLES = tuple(table for table in TABLES if table != "audit_events")

COMMANDS = {
    "employee_documents": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "insurance_policies": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "employee_insurance": {"SELECT", "INSERT", "UPDATE"},
    "insurance_dependants": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "notifications": {"SELECT", "UPDATE"},
    "employee_contracts": {"SELECT", "INSERT"},
    "offboarding_checklists": {"SELECT", "INSERT", "UPDATE"},
    "offboarding_tasks": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "offboarding_task_templates": {"SELECT"},
    "assets": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "asset_assignments": {"SELECT", "INSERT", "UPDATE"},
    "training_records": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "certifications": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "appraisal_cycles": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "appraisals": {"SELECT", "INSERT", "UPDATE"},
    "appraisal_sections": {"SELECT", "INSERT", "UPDATE"},
    "cme_requirements": {"SELECT", "INSERT", "UPDATE", "DELETE"},
    "incident_reports": {"SELECT", "INSERT", "UPDATE"},
    "letter_requests": {"SELECT", "INSERT", "UPDATE"},
}
EXPIRY_TABLES = {
    "employee_documents",
    "insurance_policies",
    "employee_insurance",
    "notifications",
    "certifications",
}
RUNTIME_TABLE_GRANTS = {table: set(commands) for table, commands in COMMANDS.items()}
RUNTIME_TABLE_GRANTS["audit_events"] = {"SELECT"}
RUNTIME_TABLE_GRANTS["notifications"] = {"SELECT"}
EXPIRY_COLUMNS = {
    ("employee_documents", "SELECT"): {
        "id",
        "company_id",
        "branch_id",
        "employee_id",
        "document_type",
        "expiry_date",
        "status",
    },
    ("insurance_policies", "SELECT"): {
        "id",
        "company_id",
        "branch_id",
        "insurer_name",
        "tier_name",
        "renewal_date",
    },
    ("employee_insurance", "SELECT"): {
        "id",
        "company_id",
        "branch_id",
        "employee_id",
        "policy_id",
        "expiry_date",
        "tier_name",
    },
    ("certifications", "SELECT"): {
        "id",
        "company_id",
        "branch_id",
        "employee_id",
        "certification_name",
        "issuing_body",
        "expiry_date",
        "status",
    },
    ("notifications", "SELECT"): {
        "company_id",
        "branch_id",
        "recipient_app_user_id",
        "type",
        "related_entity_type",
        "related_entity_id",
    },
    ("notifications", "INSERT"): {
        "company_id",
        "branch_id",
        "created_by_app_user_id",
        "recipient_app_user_id",
        "type",
        "title",
        "body",
        "related_entity_type",
        "related_entity_id",
    },
    ("audit_events", "INSERT"): {
        "company_id",
        "branch_id",
        "actor_kind",
        "system_actor_key",
        "action",
        "entity_type",
        "entity_id",
        "changed_fields",
        "reason",
        "metadata",
    },
}


def expected_policies() -> set[tuple[str, str, str, str]]:
    expected = {
        (
            table,
            f"phase5g_{table}_{command.lower()}_runtime",
            command,
            "workloop_runtime",
        )
        for table, commands in COMMANDS.items()
        for command in commands
    }
    for table in EXPIRY_TABLES:
        expected.add(
            (
                table,
                f"phase5g_{table}_select_expiry",
                "SELECT",
                "workloop_expiry_processing",
            )
        )
    expected.add(
        (
            "notifications",
            "phase5g_notifications_insert_expiry",
            "INSERT",
            "workloop_expiry_processing",
        )
    )
    expected.add(
        (
            "audit_events",
            "phase5g_audit_events_select_runtime",
            "SELECT",
            "workloop_runtime",
        )
    )
    expected.add(
        (
            "audit_events",
            "phase5g_audit_events_insert_expiry",
            "INSERT",
            "workloop_expiry_processing",
        )
    )
    return expected


def verify_catalog(engine: Any) -> None:
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "1b29d4e7f860"
        )
        tables = set(
            connection.execute(
                text(
                    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"
                )
            ).scalars()
        )
        assert len(tables) == CATALOGUE["schema_table_count"]
        assert "audit_events" in tables

        policies = {
            (row.tablename, row.policyname, row.cmd, row.roles[0])
            for row in connection.execute(
                text(
                    "SELECT tablename,policyname,cmd,roles FROM pg_catalog.pg_policies WHERE schemaname='public' AND policyname LIKE 'phase5g_%'"
                )
            )
        }
        assert policies == expected_policies()
        assert len(policies) == 70
        for row in connection.execute(
            text(
                "SELECT cmd,permissive,qual,with_check FROM pg_catalog.pg_policies WHERE schemaname='public' AND policyname LIKE 'phase5g_%'"
            )
        ).mappings():
            assert row["permissive"] == "PERMISSIVE"
            if row["cmd"] in {"SELECT", "DELETE"}:
                assert row["qual"] and row["with_check"] is None
            elif row["cmd"] == "INSERT":
                assert row["qual"] is None and row["with_check"]
            else:
                assert row["qual"] and row["with_check"]
            expression = f"{row['qual'] or ''} {row['with_check'] or ''}".lower()
            assert "workloop_actor_kind" in expression
            assert "auth." not in expression and "storage." not in expression

        actual_runtime_grants = {table: set() for table in TABLES}
        for row in connection.execute(
            text(
                """
SELECT table_name,privilege_type FROM information_schema.role_table_grants
WHERE table_schema='public' AND grantee='workloop_runtime'
  AND table_name = ANY(:tables)
"""
            ),
            {"tables": list(TABLES)},
        ):
            actual_runtime_grants[row.table_name].add(row.privilege_type)
        assert actual_runtime_grants == RUNTIME_TABLE_GRANTS
        runtime_notification_updates = set(
            connection.execute(
                text(
                    """
SELECT column_name FROM information_schema.column_privileges
WHERE table_schema='public' AND table_name='notifications'
  AND grantee='workloop_runtime' AND privilege_type='UPDATE'
"""
                )
            ).scalars()
        )
        assert runtime_notification_updates == {"read_at"}

        actual_expiry_columns: dict[tuple[str, str], set[str]] = {}
        for row in connection.execute(
            text(
                """
SELECT table_name,privilege_type,column_name
FROM information_schema.column_privileges
WHERE table_schema='public' AND grantee='workloop_expiry_processing'
  AND table_name = ANY(:tables)
"""
            ),
            {"tables": list(TABLES)},
        ):
            actual_expiry_columns.setdefault(
                (row.table_name, row.privilege_type), set()
            ).add(row.column_name)
        assert actual_expiry_columns == EXPIRY_COLUMNS

        legacy = set(CATALOGUE["legacy_policies_must_be_absent"])
        present_legacy = set(
            connection.execute(
                text(
                    "SELECT policyname FROM pg_catalog.pg_policies WHERE policyname = ANY(:names)"
                ),
                {"names": list(legacy)},
            ).scalars()
        )
        assert not present_legacy
        non_phase5_policies = connection.execute(
            text(
                """
SELECT count(*) FROM pg_catalog.pg_policies
WHERE schemaname='public' AND policyname NOT LIKE 'phase5%'
"""
            )
        ).scalar_one()
        assert non_phase5_policies == 0

        flags = {
            row[0]: row[1]
            for row in connection.execute(
                text(
                    "SELECT object.relname,object.relrowsecurity FROM pg_catalog.pg_class AS object JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid=object.relnamespace WHERE namespace.nspname='public' AND object.relkind='r'"
                )
            )
        }
        assert all(flags[table] for table in TABLES)
        assert sum(1 for enabled in flags.values() if enabled) == 55

        for function_name in ("create_workflow_notification", "append_audit_event"):
            row = connection.execute(
                text("""
SELECT pg_catalog.pg_get_userbyid(procedure.proowner),procedure.prosecdef,procedure.provolatile,
 procedure.proconfig,procedure.proacl,pg_catalog.pg_get_functiondef(procedure.oid),
 pg_catalog.pg_get_function_identity_arguments(procedure.oid)
FROM pg_catalog.pg_proc AS procedure JOIN pg_catalog.pg_namespace AS namespace
 ON namespace.oid=procedure.pronamespace
WHERE namespace.nspname='public' AND procedure.proname=:name
"""),
                {"name": function_name},
            ).one()
            assert row[0] == "workloop_migration" and row[1] and row[2] == "v"
            assert row[3] == ["search_path=pg_catalog, public, pg_temp"]
            acl = str(row[4])
            assert "workloop_runtime=X" in acl and "{=X/" not in acl
            definition = row[5].lower()
            assert (
                "session_user" in definition
                and "resolve_workloop_principal" in definition
            )
            expected_arguments = {
                "create_workflow_notification": "p_type text, p_related_entity_id text",
                "append_audit_event": (
                    "p_action text, p_entity_type text, p_entity_id uuid, "
                    "p_changed_fields text[], p_reason text, p_metadata jsonb"
                ),
            }
            assert row[6] == expected_arguments[function_name]

        shift_swap_definition = connection.execute(
            text(
                """
SELECT pg_catalog.pg_get_functiondef(
  'public.admin_execute_shift_swap(uuid,uuid)'::regprocedure
)
"""
            )
        ).scalar_one()
        assert "public.append_audit_event(" in shift_swap_definition

        constraints = set(
            connection.execute(
                text(
                    "SELECT conname FROM pg_catalog.pg_constraint WHERE conrelid='public.audit_events'::regclass"
                )
            ).scalars()
        )
        assert {
            "ck_audit_events_actor_kind",
            "ck_audit_events_primary_actor",
            "fk_audit_events_actor_profile",
            "fk_audit_events_initiator_profile",
        } <= constraints


def verify_scopes(runtime: psycopg.Connection[Any]) -> None:
    with human_context(
        runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
    ) as cursor:
        for table in BUSINESS_TABLES:
            cursor.execute(f"SELECT company_id,branch_id FROM {table}")
            for company_id, branch_id in cursor.fetchall():
                assert company_id == c.COMPANY_ID[c.HORIZON]
                assert branch_id == c.BRANCH_DXB or (
                    table == "notifications" and branch_id is None
                )

    ravi = principal_for("ravi.employee@horizon.test")
    with human_context(runtime, "ravi.employee@horizon.test") as cursor:
        for table in (
            "employee_documents",
            "employee_insurance",
            "asset_assignments",
            "training_records",
            "certifications",
            "appraisals",
            "letter_requests",
        ):
            cursor.execute(f"SELECT employee_id FROM {table}")
            assert all(row[0] == ravi.employee_id for row in cursor.fetchall())
        for table in (
            "insurance_dependants",
            "employee_contracts",
            "offboarding_checklists",
            "incident_reports",
            "cme_requirements",
        ):
            assert scalar(cursor, f"SELECT count(*) FROM {table}") == 0

    with runtime.transaction(), runtime.cursor() as cursor:
        assert scalar(cursor, "SELECT count(*) FROM employee_documents") == 0
        assert scalar(cursor, "SELECT count(*) FROM certifications") == 0


def verify_notification_helper(runtime: psycopg.Connection[Any], engine: Any) -> None:
    with engine.connect() as connection:
        payslip_id = connection.execute(
            text(
                "SELECT id FROM payslips WHERE company_id=:company AND branch_id=:branch LIMIT 1"
            ),
            {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
        ).scalar_one()
        employee_id = connection.execute(
            text("SELECT employee_id FROM payslips WHERE id=:id"), {"id": payslip_id}
        ).scalar_one()
        recipient_id = connection.execute(
            text("SELECT app_user_id FROM user_profiles WHERE employee_id=:employee"),
            {"employee": employee_id},
        ).scalar_one()
    with human_context(
        runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
    ) as cursor:
        notification_id = scalar(
            cursor,
            "SELECT public.create_workflow_notification('payslip_available', %s)",
            (str(payslip_id),),
        )
    with engine.connect() as connection:
        created = connection.execute(
            text(
                "SELECT recipient_app_user_id,type,branch_id FROM notifications WHERE id=:id"
            ),
            {"id": notification_id},
        ).one()
        assert tuple(created) == (recipient_id, "payslip_available", c.BRANCH_DXB)
        before = connection.execute(
            text("SELECT count(*) FROM notifications")
        ).scalar_one()
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT public.create_workflow_notification('unknown', %s)",
                (str(payslip_id),),
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("unknown notification producer was accepted")
    with engine.connect() as connection:
        after = connection.execute(
            text("SELECT count(*) FROM notifications")
        ).scalar_one()
    assert after == before


def verify_audit(
    runtime: psycopg.Connection[Any], expiry: psycopg.Connection[Any], engine: Any
) -> None:
    with engine.connect() as connection:
        incident_id = connection.execute(
            text(
                "SELECT id FROM incident_reports WHERE company_id=:company AND branch_id=:branch AND status='closed' LIMIT 1"
            ),
            {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
        ).scalar_one()
        open_incident_id = connection.execute(
            text(
                "SELECT id FROM incident_reports WHERE company_id=:company AND branch_id=:branch AND status='open' LIMIT 1"
            ),
            {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
        ).scalar_one()
        original_status = connection.execute(
            text("SELECT status FROM incident_reports WHERE id=:id"),
            {"id": incident_id},
        ).scalar_one()
        original_closed_by = connection.execute(
            text("SELECT closed_by_app_user_id FROM incident_reports WHERE id=:id"),
            {"id": incident_id},
        ).scalar_one()
    with human_context(
        runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
    ) as cursor:
        event_id = scalar(
            cursor,
            "SELECT public.append_audit_event('incident_closed','incident_report',%s,ARRAY['status','closed_date']::text[],'Investigation completed','{\"transition\":\"investigating_to_closed\"}'::jsonb)",
            (incident_id,),
        )
        cursor.execute(
            "SELECT actor_kind,actor_app_user_id,company_id,branch_id FROM audit_events WHERE id=%s",
            (event_id,),
        )
        row = cursor.fetchone()
        assert (
            row[0] == "human"
            and row[1] == principal_for("hr.admin@horizon.test").app_user_id
        )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE incident_reports SET closed_by_app_user_id=:actor WHERE id=:id"
            ),
            {
                "actor": principal_for("aisha.manager@horizon.test").app_user_id,
                "id": incident_id,
            },
        )
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT public.append_audit_event('incident_closed','incident_report',%s,ARRAY['status']::text[],'Wrong actor','{\"transition\":\"investigating_to_closed\"}'::jsonb)",
                (incident_id,),
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("an audit action attributed to another actor was accepted")
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE incident_reports SET closed_by_app_user_id=:actor WHERE id=:id"
                ),
                {"actor": original_closed_by, "id": incident_id},
            )
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "SELECT public.append_audit_event('incident_closed','incident_report',%s,ARRAY['status']::text[],'False closure','{\"transition\":\"open_to_closed\"}'::jsonb)",
                (open_incident_id,),
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError(
            "an audit action inconsistent with source state was accepted"
        )
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "INSERT INTO audit_events(company_id,actor_kind,actor_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata) VALUES (%s,'human',%s,'x','x',%s,ARRAY[]::text[],'x','{}')",
                (
                    c.COMPANY_ID[c.HORIZON],
                    principal_for("hr.admin@horizon.test").app_user_id,
                    incident_id,
                ),
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("runtime received direct audit insert")

    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "UPDATE incident_reports SET status='investigating' WHERE id=%s",
                (incident_id,),
            )
            cursor.execute(
                "SELECT public.append_audit_event('unknown','incident_report',%s,ARRAY['status']::text[],'x','{}')",
                (incident_id,),
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("unknown audit action was accepted")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM incident_reports WHERE id=:id"),
                {"id": incident_id},
            ).scalar_one()
            == original_status
        )

    with human_context(runtime, "ravi.employee@horizon.test") as cursor:
        assert scalar(cursor, "SELECT count(*) FROM audit_events") == 0
    try:
        with human_context(
            runtime, "hr.admin@horizon.test", branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute("UPDATE audit_events SET reason='changed'")
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("audit update was accepted")

    notification_id = None
    with engine.connect() as connection:
        notification_id = connection.execute(
            text(
                "SELECT id FROM notifications WHERE company_id=:company AND branch_id=:branch LIMIT 1"
            ),
            {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
        ).scalar_one()
    with job_context(
        expiry, company_id=c.COMPANY_ID[c.HORIZON], branch_id=c.BRANCH_DXB
    ) as cursor:
        cursor.execute(
            "INSERT INTO audit_events(company_id,branch_id,actor_kind,system_actor_key,action,entity_type,entity_id,changed_fields,reason,metadata) VALUES (%s,%s,'scheduled_job','expiry_processing','expiry_notification_created','notification',%s,ARRAY['type']::text[],'Expiry alert created','{}')",
            (c.COMPANY_ID[c.HORIZON], c.BRANCH_DXB, notification_id),
        )


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    runtime = connect_as("workloop_runtime")
    expiry = connect_as("workloop_expiry_processing")
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_events"))
            connection.execute(
                text(
                    "DELETE FROM notifications WHERE type='payslip_available' AND created_by_app_user_id=:actor"
                ),
                {"actor": principal_for("hr.admin@horizon.test").app_user_id},
            )
            apply_rows(connection, rows)
            validate(connection, rows)
        verify_catalog(engine)
        verify_scopes(runtime)
        verify_notification_helper(runtime, engine)
        verify_audit(runtime, expiry, engine)
    finally:
        runtime.close()
        expiry.close()
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM audit_events"))
            connection.execute(
                text(
                    "DELETE FROM notifications WHERE type='payslip_available' AND created_by_app_user_id=:actor"
                ),
                {"actor": principal_for("hr.admin@horizon.test").app_user_id},
            )
            clean(connection, rows)
        engine.dispose()
    print("Phase 5G remaining-domain RLS and audit checks passed.")


if __name__ == "__main__":
    main()
