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

NAFIS_ID = uuid.UUID("e8a1c3f5-b7d9-4a12-8f00-000000000001")
SETTLEMENT_ID = uuid.UUID("e8a1c3f5-b7d9-4a12-8f00-000000000002")
FILTER_DIGEST = "sha256:" + "a" * 64
SOURCE_DIGEST = "sha256:" + "b" * 64
SIGNATURE = "append_phase12_output_audit(text,text,uuid,text,text,text,text,integer,bigint,text)"


def context(
    connection: object,
    *,
    app_user: uuid.UUID,
    subject: str,
    role: str,
    branch: uuid.UUID,
    employee: uuid.UUID | None = None,
) -> None:
    connection.execute(
        text(
            """
SELECT set_config('workloop.identity_issuer',:issuer,true),
 set_config('workloop.identity_subject',:subject,true),
 set_config('workloop.app_user_id',:app_user,true),
 set_config('workloop.role',:role,true),
 set_config('workloop.company_id',:company,true),
 set_config('workloop.employee_id',:employee,true),
 set_config('workloop.branch_id',:branch,true),
 set_config('workloop.actor_kind','human',true),
 set_config('workloop.actor_key','',true),
 set_config('workloop.business_date','2026-09-25',true)
"""
        ),
        {
            "issuer": seed.SEED_ISSUER,
            "subject": subject,
            "app_user": str(app_user),
            "role": role,
            "company": str(seed.COMPANY_ID[seed.HORIZON]),
            "employee": "" if employee is None else str(employee),
            "branch": str(branch),
        },
    )


def invoke(
    runtime: object, values: dict[str, object], actor: dict[str, object]
) -> uuid.UUID:
    with runtime.begin() as connection:
        context(connection, **actor)
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
    runtime: object, values: dict[str, object], actor: dict[str, object]
) -> None:
    try:
        invoke(runtime, values, actor)
    except DBAPIError as error:
        assert getattr(error.orig, "sqlstate", None) in {"42501", "23502", "22P02"}
    else:
        raise AssertionError("invalid Part 12G output audit was accepted")


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
        "report_pdf_exported",
        "payslip_pdf_exported",
        "payslip_zip_exported",
        "letter_pdf_exported",
        "offboarding_letter_pdf_exported",
        "final_settlement_pdf_exported",
    )
    try:
        with migration.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "e8a1c3f5b7d9"
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
            payslip = (
                connection.execute(
                    text(
                        "SELECT slip.id,slip.employee_id,user_account.id app_user_id,"
                        "user_account.identity_subject FROM public.payslips slip "
                        "JOIN public.user_profiles profile ON profile.employee_id=slip.employee_id "
                        "JOIN public.app_users user_account ON user_account.id=profile.app_user_id "
                        "WHERE slip.company_id=:company AND slip.branch_id=:branch "
                        "ORDER BY slip.id LIMIT 1"
                    ),
                    {"company": company, "branch": branch},
                )
                .mappings()
                .one()
            )
            manager = (
                connection.execute(
                    text(
                        "SELECT user_account.id app_user_id,user_account.identity_subject,"
                        "profile.employee_id FROM public.user_profiles profile "
                        "JOIN public.app_users user_account ON user_account.id=profile.app_user_id "
                        "JOIN public.employees employee ON employee.id=profile.employee_id "
                        "WHERE profile.company_id=:company AND profile.role='manager' "
                        "AND employee.branch_id=:branch ORDER BY user_account.id LIMIT 1"
                    ),
                    {"company": company, "branch": branch},
                )
                .mappings()
                .one()
            )
            letter = (
                connection.execute(
                    text(
                        "SELECT request.id,request.employee_id,user_account.id app_user_id,"
                        "user_account.identity_subject FROM public.letter_requests request "
                        "JOIN public.user_profiles profile "
                        "ON profile.employee_id=request.employee_id "
                        "JOIN public.app_users user_account ON user_account.id=profile.app_user_id "
                        "WHERE request.company_id=:company AND request.branch_id=:branch "
                        "AND request.status='completed' ORDER BY request.id LIMIT 1"
                    ),
                    {"company": company, "branch": branch},
                )
                .mappings()
                .one()
            )
            checklist = (
                connection.execute(
                    text(
                        "SELECT id,employee_id FROM public.offboarding_checklists "
                        "WHERE company_id=:company AND branch_id=:branch AND status='completed' "
                        "ORDER BY id LIMIT 1"
                    ),
                    {"company": company, "branch": branch},
                )
                .mappings()
                .one()
            )
            policy = connection.scalar(
                text(
                    "SELECT id FROM public.settlement_policy_versions "
                    "ORDER BY effective_date,id LIMIT 1"
                )
            )
            assert attendance_period and payroll_run and policy
            connection.execute(
                text(
                    """
INSERT INTO public.final_settlements(
 id,company_id,branch_id,employee_id,checklist_id,policy_version_id,
 source_snapshot,source_digest,source_captured_at,final_salary,leave_encashment,
 gratuity,notice_pay,other_earnings,advance_deduction,asset_deduction,
 notice_deduction,other_deductions,gross_amount,total_deductions,net_amount,
 calculation_breakdown,completed_by_app_user_id,reviewed_by_app_user_id,completed_at
) VALUES (
 :id,:company,:branch,:employee,:checklist,:policy,
 jsonb_build_object('policy',jsonb_build_object('version','1.0.0','digest',CAST(:digest AS text))),
 :digest,'2026-09-25T08:00:00Z',1000,200,3000,0,0,100,0,0,0,4200,100,4100,
 '{"serviceDays":"1000","gratuityDays":"50","leaveDays":"5"}'::jsonb,
 :admin,:admin,'2026-09-25T08:00:00Z'
)
"""
                ),
                {
                    "id": SETTLEMENT_ID,
                    "company": company,
                    "branch": branch,
                    "employee": checklist["employee_id"],
                    "checklist": checklist["id"],
                    "policy": policy,
                    "digest": SOURCE_DIGEST,
                    "admin": seed.ADMIN_APP_USER[seed.HORIZON],
                },
            )
            connection.execute(
                text(
                    "UPDATE public.offboarding_checklists SET final_settlement_id=:settlement "
                    "WHERE id=:checklist"
                ),
                {"settlement": SETTLEMENT_ID, "checklist": checklist["id"]},
            )
            properties = (
                connection.execute(
                    text(
                        """
SELECT owner.rolname AS owner,procedure.prosecdef,procedure.proconfig,
 has_function_privilege('workloop_runtime',procedure.oid,'EXECUTE') runtime_executes,
 EXISTS (SELECT 1 FROM pg_catalog.aclexplode(procedure.proacl) permission
         WHERE permission.grantee=0 AND permission.privilege_type='EXECUTE') public_executes
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

        admin_actor = {
            "app_user": seed.ADMIN_APP_USER[seed.HORIZON],
            "subject": "hr.admin@horizon.test",
            "role": "admin",
            "branch": branch,
            "employee": None,
        }
        payslip_actor = {
            "app_user": payslip["app_user_id"],
            "subject": payslip["identity_subject"],
            "role": "employee",
            "branch": branch,
            "employee": payslip["employee_id"],
        }
        manager_actor = {
            "app_user": manager["app_user_id"],
            "subject": manager["identity_subject"],
            "role": "manager",
            "branch": branch,
            "employee": manager["employee_id"],
        }
        letter_actor = {
            "app_user": letter["app_user_id"],
            "subject": letter["identity_subject"],
            "role": "employee",
            "branch": branch,
            "employee": letter["employee_id"],
        }
        for actor, expected in (
            (admin_actor, 1),
            (payslip_actor, 1),
            (manager_actor, 0),
        ):
            with runtime.begin() as connection:
                context(connection, **actor)
                visible = connection.scalar(
                    text("SELECT count(*) FROM public.payslips WHERE id=:id"),
                    {"id": payslip["id"]},
                )
                assert visible == expected
        base = {
            "filter_digest": FILTER_DIGEST,
            "source_digest": SOURCE_DIGEST,
            "renderer_version": "phase12g-test-v1",
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
            ("report_pdf_exported", "report", branch, "pdf"),
            ("payslip_pdf_exported", "payslip", payslip["id"], "pdf"),
            ("payslip_zip_exported", "payroll_run", payroll_run, "zip"),
            ("letter_pdf_exported", "letter_request", letter["id"], "pdf"),
            (
                "offboarding_letter_pdf_exported",
                "offboarding_checklist",
                checklist["id"],
                "pdf",
            ),
            ("final_settlement_pdf_exported", "final_settlement", SETTLEMENT_ID, "pdf"),
        )
        audit_ids = [
            invoke(
                runtime,
                {
                    **base,
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "format": format_name,
                },
                admin_actor,
            )
            for action, entity_type, entity_id, format_name in tuples
        ]
        audit_ids.append(
            invoke(
                runtime,
                {
                    **base,
                    "action": "payslip_pdf_exported",
                    "entity_type": "payslip",
                    "entity_id": payslip["id"],
                    "format": "pdf",
                },
                payslip_actor,
            )
        )
        audit_ids.append(
            invoke(
                runtime,
                {
                    **base,
                    "action": "letter_pdf_exported",
                    "entity_type": "letter_request",
                    "entity_id": letter["id"],
                    "format": "pdf",
                },
                letter_actor,
            )
        )

        valid = {
            **base,
            "action": "report_pdf_exported",
            "entity_type": "report",
            "entity_id": branch,
            "format": "pdf",
        }
        for changes in (
            {"action": "unknown_pdf_exported"},
            {"entity_type": "payroll_run"},
            {"format": "zip"},
            {"result": "streamed"},
            {"filter_digest": "bad"},
            {"source_digest": "sha256:" + "G" * 64},
            {"renderer_version": "has space"},
            {"row_count": -1},
            {"byte_count": 0},
            {"entity_id": seed.BRANCH_AUH},
        ):
            denied(runtime, {**valid, **changes}, admin_actor)
        denied(
            runtime,
            {
                **base,
                "action": "payslip_pdf_exported",
                "entity_type": "payslip",
                "entity_id": payslip["id"],
                "format": "pdf",
            },
            letter_actor,
        )
        denied(
            runtime,
            {
                **base,
                "action": "letter_pdf_exported",
                "entity_type": "letter_request",
                "entity_id": letter["id"],
                "format": "pdf",
            },
            payslip_actor,
        )

        try:
            with runtime.begin() as connection:
                context(connection, **admin_actor)
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
                        "SELECT action,changed_fields,reason,metadata FROM public.audit_events "
                        "WHERE id=ANY(:ids)"
                    ),
                    {"ids": audit_ids},
                )
                .mappings()
                .all()
            )
            assert len(audit) == 16
            for item in audit:
                assert item["action"] in actions
                assert item["changed_fields"] == ["output"]
                assert item["reason"] == "Phase 12 output delivery"
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
                    "lettertext",
                    "bytes",
                ):
                    assert marker not in forbidden
    finally:
        with migration.begin() as connection:
            connection.execute(
                text("DELETE FROM public.audit_events WHERE action=ANY(:actions)"),
                {"actions": list(actions)},
            )
            connection.execute(
                text(
                    "UPDATE public.offboarding_checklists SET final_settlement_id=NULL "
                    "WHERE final_settlement_id=:id"
                ),
                {"id": SETTLEMENT_ID},
            )
            connection.execute(
                text("DELETE FROM public.final_settlements WHERE id=:id"),
                {"id": SETTLEMENT_ID},
            )
            connection.execute(
                text("DELETE FROM public.nafis_reports WHERE id=:id"), {"id": NAFIS_ID}
            )
            clean_seed(connection, rows)
        runtime.dispose()
        migration.dispose()

    print("Phase 12G output audit database verification passed")


if __name__ == "__main__":
    verify()
