#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

ROOT = (
    Path("/workspace")
    if Path("/workspace").is_dir()
    else Path(__file__).resolve().parents[1]
)
sys.path.insert(0, str(ROOT / "backend"))

from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, validate
from app.db.seed.runner import clean as clean_seed

NAFIS_ID = uuid.UUID("d6f8a0c2-e4b7-4a12-8f00-000000000001")
FILTER_DIGEST = "sha256:" + "a" * 64
SOURCE_DIGEST = "sha256:" + "b" * 64
SIGNATURE = "append_phase12_output_audit(text,text,uuid,text,text,text,text,integer,bigint,text)"


def context(connection: object, *, app_user: uuid.UUID, branch: uuid.UUID) -> None:
    connection.execute(
        text(
            """
SELECT set_config('workloop.identity_issuer',:issuer,true),
 set_config('workloop.identity_subject',:subject,true),
 set_config('workloop.app_user_id',:app_user,true),
 set_config('workloop.role','admin',true),
 set_config('workloop.company_id',:company,true),
 set_config('workloop.employee_id','',true),
 set_config('workloop.branch_id',:branch,true),
 set_config('workloop.actor_kind','human',true),
 set_config('workloop.actor_key','',true),
 set_config('workloop.business_date','2026-09-25',true)
"""
        ),
        {
            "issuer": seed.SEED_ISSUER,
            "subject": "hr.admin@horizon.test",
            "app_user": str(app_user),
            "company": str(seed.COMPANY_ID[seed.HORIZON]),
            "branch": str(branch),
        },
    )


def invoke(
    runtime: object,
    values: dict[str, object],
    *,
    app_user: uuid.UUID | None = None,
    branch: uuid.UUID | None = None,
) -> uuid.UUID:
    with runtime.begin() as connection:
        context(
            connection,
            app_user=app_user or seed.ADMIN_APP_USER[seed.HORIZON],
            branch=branch or seed.BRANCH_DXB,
        )
        value = connection.scalar(
            text(
                "SELECT public.append_phase12_output_audit("
                ":action,:entity_type,:entity_id,:format,:filter_digest,:source_digest,"
                ":renderer_version,:row_count,:byte_count,:result)"
            ),
            values,
        )
        return uuid.UUID(str(value))


def denied(
    runtime: object, values: dict[str, object], **context_values: object
) -> None:
    try:
        invoke(runtime, values, **context_values)
    except DBAPIError as error:
        assert getattr(error.orig, "sqlstate", None) in {"42501", "23502", "22P02"}
    else:
        raise AssertionError("invalid output audit was accepted")


def verify() -> None:
    migration = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    runtime = create_engine(os.environ["DATABASE_URL"])
    rows = build_rows()
    company = seed.COMPANY_ID[seed.HORIZON]
    branch = seed.BRANCH_DXB
    actions = (
        "report_csv_exported",
        "attendance_csv_exported",
        "roster_csv_exported",
        "leave_balance_csv_exported",
        "employee_csv_exported",
        "nafis_csv_exported",
        "sif_previewed",
        "sif_exported",
    )
    try:
        with migration.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "d6f8a0c2e4b7"
            )
            clean_seed(connection, rows)
            apply_rows(connection, rows)
            validate(connection, rows)
            connection.execute(
                text(
                    """
INSERT INTO public.nafis_reports(
 id,company_id,branch_id,period,total_headcount,emirati_count,
 ratio_percent,required_percent,compliant,snapshot,generated_at
) VALUES (
 :id,:company,:branch,'2026-12',0,0,0,2,false,
 '{"employees":[],"qualifyingWageTotal":"0.00","sourceVersion":"synthetic"}'::jsonb,
 '2026-09-25T08:00:00Z'
)
"""
                ),
                {"id": NAFIS_ID, "company": company, "branch": branch},
            )
            attendance_period = connection.scalar(
                text(
                    "SELECT id FROM public.attendance_periods WHERE company_id=:company "
                    "AND branch_id=:branch ORDER BY period,id LIMIT 1"
                ),
                {"company": company, "branch": branch},
            )
            payroll_run = connection.scalar(
                text(
                    "SELECT id FROM public.payroll_runs WHERE company_id=:company "
                    "AND branch_id=:branch AND status='generated' AND approval_status='approved' "
                    "ORDER BY period,id LIMIT 1"
                ),
                {"company": company, "branch": branch},
            )
            assert attendance_period is not None and payroll_run is not None
            properties = (
                connection.execute(
                    text(
                        """
SELECT owner.rolname AS owner,procedure.prosecdef,
 procedure.proconfig,has_function_privilege('workloop_runtime',procedure.oid,'EXECUTE') runtime_executes,
 EXISTS (
  SELECT 1 FROM pg_catalog.aclexplode(procedure.proacl) permission
  WHERE permission.grantee=0 AND permission.privilege_type='EXECUTE'
 ) public_executes
FROM pg_proc procedure
JOIN pg_namespace namespace ON namespace.oid=procedure.pronamespace
JOIN pg_roles owner ON owner.oid=procedure.proowner
WHERE namespace.nspname='public' AND procedure.oid=CAST(:signature AS regprocedure)
"""
                    ),
                    {"signature": f"public.{SIGNATURE}"},
                )
                .mappings()
                .one()
            )
            assert properties["owner"] == "workloop_migration"
            assert properties["prosecdef"] is True
            assert properties["proconfig"] == ["search_path=pg_catalog, public"]
            assert properties["runtime_executes"] is True
            assert properties["public_executes"] is False
            assert not connection.scalar(
                text(
                    "SELECT has_table_privilege('workloop_runtime','public.audit_events','INSERT')"
                )
            )

        base = {
            "filter_digest": FILTER_DIGEST,
            "source_digest": SOURCE_DIGEST,
            "renderer_version": "phase12f-test-v1",
            "row_count": 1,
            "byte_count": 10,
            "result": "succeeded",
        }
        tuples = (
            ("report_csv_exported", "report", branch, "csv"),
            ("attendance_csv_exported", "attendance_period", attendance_period, "csv"),
            ("roster_csv_exported", "roster_month", branch, "csv"),
            ("leave_balance_csv_exported", "leave_balance_year", branch, "csv"),
            ("employee_csv_exported", "employee_export", branch, "csv"),
            ("nafis_csv_exported", "nafis_report", NAFIS_ID, "csv"),
            ("sif_previewed", "payroll_run", payroll_run, "sif_preview"),
            ("sif_exported", "payroll_run", payroll_run, "sif"),
        )
        audit_ids = []
        for action, entity_type, entity_id, format_name in tuples:
            audit_ids.append(
                invoke(
                    runtime,
                    {
                        **base,
                        "action": action,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "format": format_name,
                    },
                )
            )

        valid = {
            **base,
            "action": "report_csv_exported",
            "entity_type": "report",
            "entity_id": branch,
            "format": "csv",
        }
        for changes in (
            {"action": "report_pdf_exported"},
            {"entity_type": "payroll_run"},
            {"format": "pdf"},
            {"result": "streamed"},
            {"filter_digest": "bad"},
            {"source_digest": "sha256:" + "G" * 64},
            {"renderer_version": "has space"},
            {"row_count": -1},
            {"byte_count": 0},
            {"entity_id": seed.BRANCH_AUH},
        ):
            denied(runtime, {**valid, **changes})
        denied(runtime, valid, branch=uuid.UUID("d6f8a0c2-e4b7-4a12-8f00-000000000099"))
        denied(runtime, valid, app_user=seed.ADMIN_APP_USER[seed.CEDAR])

        try:
            with runtime.begin() as connection:
                context(
                    connection,
                    app_user=seed.ADMIN_APP_USER[seed.HORIZON],
                    branch=branch,
                )
                connection.execute(
                    text(
                        "INSERT INTO public.audit_events(company_id,branch_id,actor_kind,"
                        "actor_app_user_id,action,entity_type,entity_id,changed_fields,reason) "
                        "VALUES(:company,:branch,'human',:actor,'forged','report',:branch,"
                        "ARRAY['output'],'forged')"
                    ),
                    {
                        "company": company,
                        "branch": branch,
                        "actor": seed.ADMIN_APP_USER[seed.HORIZON],
                    },
                )
        except DBAPIError as error:
            assert getattr(error.orig, "sqlstate", None) == "42501"
        else:
            raise AssertionError("runtime inserted directly into audit_events")

        with migration.begin() as connection:
            audit = (
                connection.execute(
                    text(
                        "SELECT action,entity_type,changed_fields,reason,metadata,actor_app_user_id,"
                        "initiated_by_app_user_id FROM public.audit_events WHERE id=ANY(:ids)"
                    ),
                    {"ids": audit_ids},
                )
                .mappings()
                .all()
            )
            assert len(audit) == 8
            for item in audit:
                assert item["action"] in actions
                assert item["changed_fields"] == ["output"]
                assert item["reason"] == "Phase 12 output delivery"
                assert item["actor_app_user_id"] == seed.ADMIN_APP_USER[seed.HORIZON]
                assert (
                    item["initiated_by_app_user_id"]
                    == seed.ADMIN_APP_USER[seed.HORIZON]
                )
                assert set(item["metadata"]) == {
                    "format",
                    "filterDigest",
                    "sourceDigest",
                    "rendererVersion",
                    "rowCount",
                    "byteCount",
                    "result",
                }
                forbidden = str(item["metadata"]).lower()
                for marker in (
                    "filename",
                    "iban",
                    "employee",
                    "salary",
                    "bytes",
                    "letter",
                ):
                    assert marker not in forbidden
    finally:
        with migration.begin() as connection:
            connection.execute(
                text("DELETE FROM public.audit_events WHERE action=ANY(:actions)"),
                {"actions": list(actions)},
            )
            connection.execute(
                text("DELETE FROM public.nafis_reports WHERE id=:id"), {"id": NAFIS_ID}
            )
            clean_seed(connection, rows)
        runtime.dispose()
        migration.dispose()

    print("Phase 12F output audit database verification passed")


if __name__ == "__main__":
    verify()
