#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = (
    Path("/workspace")
    if Path("/workspace").is_dir()
    else Path(__file__).resolve().parents[1]
)


def policy(connection: object, table: str, name: str) -> str:
    return str(
        connection.execute(
            text(
                "SELECT coalesce(qual,'') || ' ' || coalesce(with_check,'') "
                "FROM pg_catalog.pg_policies WHERE schemaname='public' "
                "AND tablename=:table AND policyname=:name"
            ),
            {"table": table, "name": name},
        ).scalar_one()
    ).lower()


def verify_manifest() -> None:
    manifest = json.loads(
        (ROOT / "scripts" / "phase-5h-control-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    controls = manifest["controls"]
    assert [item["id"] for item in controls] == list(range(1, 20))
    assert len({item["name"] for item in controls}) == 19
    for item in controls:
        expected = {"A", "S"} if item["id"] in {10, 17, 18} else {"A", "R"}
        assert set(item["layers"]) == expected
        assert all(item["layers"][layer] for layer in expected)
        assert all(
            ":" in assertion
            for layer in expected
            for assertion in item["layers"][layer]
        )
        for layer in expected:
            for assertion in item["layers"][layer]:
                if assertion.startswith("deferred:"):
                    continue
                source_name, function_name = assertion.split(":", maxsplit=1)
                if source_name.startswith("test_"):
                    source_path = ROOT / "backend" / "tests" / f"{source_name}.py"
                else:
                    source_path = ROOT / "scripts" / f"{source_name}.py"
                assert source_path.is_file(), f"missing control source: {source_path}"
                source = source_path.read_text(encoding="utf-8")
                definition = re.compile(
                    rf"^(?:async\s+)?def\s+{re.escape(function_name)}\s*\(",
                    re.MULTILINE,
                )
                assert definition.search(source), (
                    f"missing control assertion: {source_name}:{function_name}"
                )


def verify_database() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    with engine.connect() as connection:
        assert not connection.execute(
            text(
                "SELECT has_table_privilege('workloop_runtime',"
                "'public.offboarding_tasks','DELETE')"
            )
        ).scalar_one()
        for column in ("id", "created_by_app_user_id"):
            assert not connection.execute(
                text(
                    "SELECT has_column_privilege('workloop_expiry_processing',"
                    "'public.notifications',:column,'SELECT')"
                ),
                {"column": column},
            ).scalar_one()

        appraisal = policy(
            connection,
            "appraisal_sections",
            "phase5g_appraisal_sections_update_runtime",
        )
        assert "reporting_manager_id = workloop_employee_id()" in appraisal
        assert "appraisal.employee_id <> workloop_employee_id()" in appraisal

        notifications = policy(
            connection, "notifications", "phase5g_notifications_select_runtime"
        )
        assert "workloop_branch_id() is not null" in notifications
        expiry = policy(
            connection, "notifications", "phase5g_notifications_insert_expiry"
        )
        for required in (
            "created_by_app_user_id is null",
            "profile.role = 'admin'",
            "account.status = 'active'",
            "pg_input_is_valid",
            "related_entity_type",
            "source.status = 'verified'",
            "employee.active",
            "source.employment_status = 'probation'",
            "source.contract_type = 'limited'",
            "source.expiry_date >= workloop_business_date()",
            "source.expiry_date <= (workloop_business_date() + 60)",
            "source.renewal_date >= workloop_business_date()",
            "workloop_business_date() + 90",
        ):
            assert required in expiry, required

        notification_function = (
            connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_functiondef("
                    "'public.create_workflow_notification(text,text)'::regprocedure)"
                )
            )
            .scalar_one()
            .lower()
        )
        compact_notification_function = notification_function.replace(" ", "")
        for required in (
            "profile_app_user_id=caller.app_user_id",
            "employee_branch_id=public.workloop_branch_id()",
            "request.employee_id<>public.workloop_employee_id()",
            "joinpublic.branches",
        ):
            assert required in compact_notification_function

        audit_function = (
            connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_functiondef("
                    "'public.append_audit_event(text,text,uuid,text[],text,jsonb)'::regprocedure)"
                )
            )
            .scalar_one()
            .lower()
        )
        assert "profile_app_user_id=caller.app_user_id" in audit_function.replace(
            " ", ""
        )
        assert "branch_created" in audit_function and "branch_deleted" in audit_function
        assert "employee_branch_corrected" in audit_function
        assert "raise exception 'audit event denied'" in audit_function
        for signature in (
            "public._append_audit_event_phase5g(text,text,uuid,text[],text,jsonb)",
            "public._create_workflow_notification_phase5g(text,text)",
            "public._admin_execute_shift_swap_phase5g(uuid,uuid)",
            "public._record_advance_repayment_phase5g(uuid,uuid,uuid,numeric,date)",
        ):
            assert not connection.execute(
                text(
                    "SELECT has_function_privilege('workloop_runtime',:signature,'EXECUTE')"
                ),
                {"signature": signature},
            ).scalar_one()
            assert not connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_catalog.aclexplode("
                    "coalesce(proacl,pg_catalog.acldefault('f',proowner))) AS acl "
                    "WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE') "
                    "FROM pg_catalog.pg_proc WHERE oid=CAST(:signature AS regprocedure)"
                ),
                {"signature": signature},
            ).scalar_one()

        constraint = (
            connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint "
                    "WHERE conrelid='public.audit_events'::regclass "
                    "AND conname='ck_audit_events_primary_actor'"
                )
            )
            .scalar_one()
            .lower()
        )
        assert "system_actor_key is not null" in constraint
        audit_select = policy(
            connection, "audit_events", "phase5g_audit_events_select_runtime"
        )
        assert "workloop_business_date() is not null" in audit_select
        audit_expiry = policy(
            connection, "audit_events", "phase5g_audit_events_insert_expiry"
        )
        compact_audit_expiry = audit_expiry.replace(" ", "").replace("\n", "")
        assert (
            "notification.related_entity_type = audit_events.entity_type"
            in audit_expiry
        )
        assert (
            "notification.related_entity_id=(((((audit_events.entity_id)::text||':'::text)"
            "||(audit_events.metadata->>'source_kind'::text))||':'::text)"
            "||(audit_events.metadata->>'threshold_days'::text))"
            in compact_audit_expiry
        )
        assert "notification.recipient_app_user_id" in audit_expiry
        assert "recipient_app_user_id" in audit_expiry
        assert "source_kind" in audit_expiry
        assert (
            "source.expiry_date = ((audit_events.metadata ->> 'source_date'"
            in audit_expiry
        )
        assert "reason = 'expiry notification created'" in audit_expiry

        shift_swap = (
            connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_functiondef("
                    "'public.admin_execute_shift_swap(uuid,uuid)'::regprocedure)"
                )
            )
            .scalar_one()
            .lower()
        )
        assert "from public.employees as employee" in shift_swap
        assert "order by employee.id for update" in shift_swap
        assert "shift_swap_employee_ineligible" in shift_swap
        repayment = (
            connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_functiondef("
                    "'public.record_advance_repayment(uuid,uuid,uuid,numeric,date)'::regprocedure)"
                )
            )
            .scalar_one()
            .lower()
        )
        assert (
            "from public.payroll_runs where id = p_payroll_run_id for update"
            in repayment
        )
        relationship_lock = (
            connection.execute(
                text(
                    "SELECT pg_catalog.pg_get_functiondef("
                    "'public.lock_authorized_employee_relationships(uuid[])'::regprocedure)"
                )
            )
            .scalar_one()
            .lower()
        )
        assert "order by employee.id for update" in relationship_lock
        assert (
            "reporting_manager_id=public.workloop_employee_id()"
            in relationship_lock.replace(" ", "")
        )
        assert connection.execute(
            text(
                "SELECT has_function_privilege('workloop_runtime',"
                "'public.lock_authorized_employee_relationships(uuid[])','EXECUTE')"
            )
        ).scalar_one()
    engine.dispose()


def verify_source_guards() -> None:
    seed = (ROOT / "backend" / "app" / "db" / "seed" / "runner.py").read_text(
        encoding="utf-8"
    )
    assert 'current != "workloop_migration" or session != "workloop_migration"' in seed
    classifier = (
        ROOT / ".github" / "scripts" / "classify-migration-workflow.sh"
    ).read_text(encoding="utf-8")
    for required in (
        "backend/app/repositories/*",
        "backend/app/schemas/*",
        "backend/tests/test_authorization_*",
        "backend/tests/test_scoped_repositories.py",
        "scripts/phase-5g-catalogue.json",
        "scripts/phase-5h-control-manifest.json",
        "scripts/verify-phase-*-security.*",
    ):
        assert required in classifier
    classifier_path = ROOT / ".github" / "scripts" / "classify-migration-workflow.sh"
    for changed_path in (
        "scripts/phase-5h-control-manifest.json",
        "scripts/verify-phase-5h-security.py",
        "backend/tests/test_scoped_repositories.py",
    ):
        result = subprocess.run(
            ["sh", str(classifier_path)],
            input=f"{changed_path}\n",
            text=True,
            capture_output=True,
            check=True,
        )
        assert "database_deep=true" in result.stdout


def verify_control_execution() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend")
    controls = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify-phase-5h-controls.py")],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    expected = {
        *(f"{control_id}A" for control_id in range(1, 19)),
        *(f"{control_id}R" for control_id in range(1, 17) if control_id != 10),
    }
    delivered = set(controls.stdout.rsplit(":", maxsplit=1)[-1].strip().split(","))
    assert delivered == expected
    concurrency = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "verify-phase-5h-manager-concurrency.py"),
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "relationship, shift-swap, and repayment races passed" in concurrency.stdout


def main() -> None:
    verify_manifest()
    verify_source_guards()
    verify_database()
    verify_control_execution()
    print("Phase 5H security corrections and control manifest passed.")


if __name__ == "__main__":
    main()
