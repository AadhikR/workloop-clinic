"""Add Phase 11G offboarding and immutable final settlements.

Revision ID: c3e5a7b9d1f6
Revises: b2d4f6a8c0e5
Created: 2026-09-23 22:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c3e5a7b9d1f6"
down_revision: str | Sequence[str] | None = "b2d4f6a8c0e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE11F_REPLAY_KINDS = (
    "'branch','employee','department','user_profile','leave_request','expense_claim',"
    "'salary_advance','payroll_run','compliance_override','nafis_snapshot',"
    "'attendance_settings','shift','shift_assignment','clock_event','biometric_mapping',"
    "'attendance_import_batch','attendance_record','regularisation_request',"
    "'attendance_period','roster_assignment','roster_publication_version','shift_swap_request',"
    "'employee_document','insurance_policy','employee_insurance','insurance_dependant',"
    "'employee_contract','asset','asset_assignment','training_record','certification',"
    "'cme_requirement','appraisal_cycle','appraisal','incident_report','letter_request'"
)
PHASE11G_REPLAY_KINDS = PHASE11F_REPLAY_KINDS + ",'offboarding_checklist'"

POLICY_JSON = r"""{"advanceTreatment":"deduct-and-settle-active-outstanding","assetTreatment":"open-assignments-block-and-asset-deduction-zero","capBasicSalaryMonths":24,"dailyBasicDivisor":30,"eligibilityPaidServiceDays":365,"finalSalary":"termination-month-approved-generated-payslip-net-if-unpaid","firstTierGratuityDaysPerYear":21,"firstTierPaidServiceDays":1825,"jurisdiction":"uae-mainland-private-sector","laterTierGratuityDaysPerYear":30,"leaveDailyRate":"basic_salary/30","leaveTypeCode":"ANNUAL","negativeNet":"block","resignationReduction":false,"rounding":"ROUND_HALF_UP_each_component_and_totals_0.01","separationOfDuty":"completer_must_differ_from_initializer","serviceDayConvention":"inclusive-calendar-days-minus-approved-unpaid-leave","workers":"foreign-full-time-standard-gratuity"}"""
POLICY_DIGEST = "sha256:c5ddc71c214b8b9b2d4a1ec77854a2274173b1da33432b2e857b2bcaf024c8b8"

HUMAN_CONTEXT = """
current_user='workloop_runtime' AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND EXISTS (
 SELECT 1 FROM public.resolve_workloop_principal() principal
 WHERE principal.app_user_id=public.workloop_app_user_id()
  AND principal.account_status='active'
  AND principal.profile_company_id=public.workloop_company_id()
  AND principal.role=public.workloop_role()
)
""".strip()


def _task_provenance() -> None:
    op.create_unique_constraint(
        "uq_offboarding_task_templates_id_scope",
        "offboarding_task_templates",
        ["id", "company_id", "branch_id"],
    )
    op.add_column(
        "offboarding_tasks",
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'custom'")),
    )
    op.add_column("offboarding_tasks", sa.Column("template_id", postgresql.UUID(as_uuid=True)))
    op.add_column(
        "offboarding_tasks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
    )
    op.execute(
        """
UPDATE public.offboarding_tasks task SET source='template',template_id=template.id
FROM public.offboarding_task_templates template
WHERE template.company_id=task.company_id AND template.branch_id=task.branch_id
 AND template.task_name=task.task_name
"""
    )
    op.alter_column("offboarding_tasks", "source", server_default=sa.text("'template'"))
    op.create_foreign_key(
        "fk_offboarding_tasks_template_scope",
        "offboarding_tasks",
        "offboarding_task_templates",
        ["template_id", "company_id", "branch_id"],
        ["id", "company_id", "branch_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint("source", "offboarding_tasks", "source IN ('template','custom')")
    op.create_check_constraint(
        "source_template",
        "offboarding_tasks",
        "(source='template' AND template_id IS NOT NULL) OR "
        "(source='custom' AND template_id IS NULL)",
    )
    op.create_index(
        "uq_offboarding_tasks_checklist_template",
        "offboarding_tasks",
        ["checklist_id", "template_id"],
        unique=True,
        postgresql_where=sa.text("template_id IS NOT NULL"),
    )
    op.execute(
        "CREATE TRIGGER trg_offboarding_tasks_set_updated_at BEFORE UPDATE ON "
        "public.offboarding_tasks FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
    )
    op.add_column(
        "offboarding_checklists",
        sa.Column("initialized_by_app_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_offboarding_checklists_initialized_by_app_user_id",
        "offboarding_checklists",
        "app_users",
        ["initialized_by_app_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "offboarding_checklists",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
    )
    op.execute(
        "CREATE TRIGGER trg_offboarding_checklists_set_updated_at BEFORE UPDATE ON "
        "public.offboarding_checklists FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
    )


def _settlement_tables() -> None:
    op.create_table(
        "settlement_policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("jurisdiction_key", sa.Text(), nullable=False),
        sa.Column("semantic_version", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        sa.Column("approval_authority", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.UniqueConstraint(
            "jurisdiction_key", "semantic_version", name="uq_settlement_policy_version"
        ),
        sa.CheckConstraint("jsonb_typeof(policy)='object'", name="policy_object"),
        sa.CheckConstraint("digest~'^sha256:[0-9a-f]{64}$'", name="digest"),
        schema="public",
    )
    op.execute(
        sa.text(
            "INSERT INTO public.settlement_policy_versions(id,jurisdiction_key,semantic_version,"
            "effective_date,policy,digest,approval_authority,approved_at) VALUES("
            "'c3e5a7b9-d1f6-4b18-9b4e-11a700000001',"
            "'uae-mainland-private-sector-foreign-full-time','1.0.0','2022-02-02',"
            "CAST(:policy AS jsonb),:digest,'project_owner_delegated_decision',"
            "'2026-09-23T00:00:00Z')"
        ).bindparams(policy=POLICY_JSON, digest=POLICY_DIGEST)
    )
    op.create_table(
        "final_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("source_digest", sa.Text(), nullable=False),
        sa.Column("source_captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("final_salary", sa.Numeric(14, 2), nullable=False),
        sa.Column("leave_encashment", sa.Numeric(14, 2), nullable=False),
        sa.Column("gratuity", sa.Numeric(14, 2), nullable=False),
        sa.Column("notice_pay", sa.Numeric(14, 2), nullable=False),
        sa.Column("other_earnings", sa.Numeric(14, 2), nullable=False),
        sa.Column("advance_deduction", sa.Numeric(14, 2), nullable=False),
        sa.Column("asset_deduction", sa.Numeric(14, 2), nullable=False),
        sa.Column("notice_deduction", sa.Numeric(14, 2), nullable=False),
        sa.Column("other_deductions", sa.Numeric(14, 2), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_deductions", sa.Numeric(14, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("calculation_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column("completed_by_app_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reviewed_by_app_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["public.companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["public.branches.id", "public.branches.company_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["public.employees.id", "public.employees.company_id", "public.employees.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["checklist_id", "company_id", "branch_id"],
            [
                "public.offboarding_checklists.id",
                "public.offboarding_checklists.company_id",
                "public.offboarding_checklists.branch_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["policy_version_id"], ["public.settlement_policy_versions.id"]),
        sa.ForeignKeyConstraint(["completed_by_app_user_id"], ["public.app_users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_app_user_id"], ["public.app_users.id"]),
        sa.UniqueConstraint("checklist_id", name="uq_final_settlements_checklist_id"),
        sa.UniqueConstraint("id", "company_id", "branch_id", name="uq_final_settlements_id_scope"),
        sa.CheckConstraint("source_digest~'^sha256:[0-9a-f]{64}$'", name="source_digest"),
        sa.CheckConstraint("jsonb_typeof(source_snapshot)='object'", name="source_snapshot_object"),
        sa.CheckConstraint("jsonb_typeof(calculation_breakdown)='object'", name="breakdown_object"),
        sa.CheckConstraint(
            "final_salary>=0 AND leave_encashment>=0 AND gratuity>=0 AND notice_pay>=0 "
            "AND other_earnings>=0 AND advance_deduction>=0 AND asset_deduction>=0 "
            "AND notice_deduction>=0 AND other_deductions>=0 AND gross_amount>=0 "
            "AND total_deductions>=0 AND net_amount>=0",
            name="nonnegative_money",
        ),
        sa.CheckConstraint(
            "gross_amount=final_salary+leave_encashment+gratuity+notice_pay+other_earnings "
            "AND total_deductions=advance_deduction+asset_deduction+notice_deduction+other_deductions "
            "AND net_amount=gross_amount-total_deductions",
            name="exact_totals",
        ),
        sa.CheckConstraint("completed_by_app_user_id=reviewed_by_app_user_id", name="review_actor"),
        schema="public",
    )
    op.create_index(
        "ix_final_settlements_employee_id_completed_at",
        "final_settlements",
        ["employee_id", sa.text("completed_at DESC")],
    )
    op.add_column(
        "offboarding_checklists",
        sa.Column("final_settlement_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_offboarding_checklists_final_settlement_id",
        "offboarding_checklists",
        "final_settlements",
        ["final_settlement_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_offboarding_checklists_final_settlement_id",
        "offboarding_checklists",
        ["final_settlement_id"],
    )


def _security() -> None:
    admin = f"{HUMAN_CONTEXT} AND public.workloop_role()='admin' AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()"
    op.execute("ALTER TABLE public.settlement_policy_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.final_settlements ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY phase11g_settlement_policy_select_runtime ON public.settlement_policy_versions "
        f"FOR SELECT TO workloop_runtime USING ({HUMAN_CONTEXT})"
    )
    op.execute(
        "CREATE POLICY phase11g_final_settlements_select_runtime ON public.final_settlements "
        f"FOR SELECT TO workloop_runtime USING ({admin})"
    )
    op.execute(
        "CREATE POLICY phase11g_final_settlements_insert_runtime ON public.final_settlements "
        f"FOR INSERT TO workloop_runtime WITH CHECK ({admin} "
        "AND completed_by_app_user_id=public.workloop_app_user_id() "
        "AND reviewed_by_app_user_id=public.workloop_app_user_id())"
    )
    op.execute("GRANT SELECT ON TABLE public.settlement_policy_versions TO workloop_runtime")
    op.execute("GRANT SELECT,INSERT ON TABLE public.final_settlements TO workloop_runtime")
    op.execute(
        "REVOKE UPDATE,DELETE ON TABLE public.settlement_policy_versions,public.final_settlements FROM workloop_runtime"
    )
    op.execute("GRANT DELETE ON TABLE public.offboarding_tasks TO workloop_runtime")
    op.execute(
        "CREATE POLICY phase11g_offboarding_tasks_delete_runtime ON public.offboarding_tasks "
        f"FOR DELETE TO workloop_runtime USING ({admin} AND source='custom' AND NOT completed "
        "AND EXISTS (SELECT 1 FROM public.offboarding_checklists checklist "
        "WHERE checklist.id=offboarding_tasks.checklist_id AND checklist.status='in_progress'))"
    )
    op.execute(
        r"""
CREATE FUNCTION public.read_offboarding_payroll_source(p_employee_id uuid,p_period text)
RETURNS TABLE(
 payroll_run_id uuid,payroll_updated_at timestamptz,run_payment_date date,
 payslip_id uuid,net_pay numeric,payslip_payment_date date,issued_at timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp
AS $function$
BEGIN
 IF session_user<>'workloop_runtime' OR public.workloop_actor_kind()<>'human'
  OR public.workloop_actor_key() IS NOT NULL OR public.workloop_business_date() IS NULL
  OR public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
  OR public.workloop_app_user_id() IS NULL OR public.workloop_company_id() IS NULL
  OR public.workloop_branch_id() IS NULL OR p_period!~'^[0-9]{4}-(0[1-9]|1[0-2])$'
  OR NOT EXISTS (SELECT 1 FROM public.resolve_workloop_principal() caller
   WHERE caller.app_user_id=public.workloop_app_user_id() AND caller.account_status='active'
    AND caller.profile_company_id=public.workloop_company_id() AND caller.role='admin') THEN
  RAISE EXCEPTION 'offboarding payroll source denied' USING ERRCODE='42501';
 END IF;
 RETURN QUERY
 SELECT run.id,run.updated_at,run.payment_date,payslip.id,payslip.net_pay,
  payslip.payment_date,payslip.issued_at
 FROM public.payroll_runs run
 JOIN public.payslips payslip ON payslip.payroll_run_id=run.id
  AND payslip.company_id=run.company_id AND payslip.branch_id=run.branch_id
 WHERE run.company_id=public.workloop_company_id()
  AND run.branch_id=public.workloop_branch_id() AND run.period=p_period
  AND run.status='generated' AND run.approval_status='approved'
  AND payslip.employee_id=p_employee_id;
END
$function$;
ALTER FUNCTION public.read_offboarding_payroll_source(uuid,text) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.read_offboarding_payroll_source(uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.read_offboarding_payroll_source(uuid,text) TO workloop_runtime;
"""
    )


def _audit() -> None:
    op.execute(
        """
ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
RENAME TO _append_audit_event_phase11g_prior;
REVOKE ALL ON FUNCTION public._append_audit_event_phase11g_prior(text,text,uuid,text[],text,jsonb)
FROM PUBLIC,workloop_runtime;
"""
    )
    op.execute(
        r"""
CREATE FUNCTION public.append_audit_event(
 p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],
 p_reason text,p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp
AS $function$
DECLARE event_id uuid; source_company uuid; source_branch uuid; source_actor uuid;
 source_record_digest text;
BEGIN
 IF p_action NOT IN ('offboarding_initialized','offboarding_task_added',
  'offboarding_task_completed','offboarding_task_reopened','offboarding_task_deleted',
  'offboarding_visa_changed','final_settlement_completed') THEN
  RETURN public._append_audit_event_phase11g_prior(
   p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
 END IF;
 IF session_user<>'workloop_runtime' OR public.workloop_actor_kind()<>'human'
  OR public.workloop_actor_key() IS NOT NULL OR public.workloop_business_date() IS NULL
  OR public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
  OR public.workloop_app_user_id() IS NULL OR public.workloop_company_id() IS NULL
  OR public.workloop_branch_id() IS NULL OR coalesce(btrim(p_reason),'')=''
  OR jsonb_typeof(coalesce(p_metadata,'{}'::jsonb))<>'object'
  OR NOT EXISTS (SELECT 1 FROM public.resolve_workloop_principal() caller
   WHERE caller.app_user_id=public.workloop_app_user_id() AND caller.account_status='active'
    AND caller.profile_company_id=public.workloop_company_id() AND caller.role='admin') THEN
  RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
 END IF;
 IF p_action='final_settlement_completed' THEN
  SELECT settlement.company_id,settlement.branch_id,settlement.completed_by_app_user_id,
   settlement.source_digest
   INTO source_company,source_branch,source_actor,source_record_digest
  FROM public.final_settlements settlement WHERE settlement.id=p_entity_id;
  IF p_entity_type<>'final_settlement' OR source_company IS DISTINCT FROM public.workloop_company_id()
   OR source_branch IS DISTINCT FROM public.workloop_branch_id()
   OR source_actor IS DISTINCT FROM public.workloop_app_user_id()
   OR p_changed_fields IS DISTINCT FROM ARRAY['source_snapshot','calculation_breakdown','net_amount','completed_by_app_user_id']::text[]
   OR p_metadata IS DISTINCT FROM jsonb_build_object('source_digest',source_record_digest) THEN
   RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
 ELSE
  SELECT company_id,branch_id,initialized_by_app_user_id
   INTO source_company,source_branch,source_actor
  FROM public.offboarding_checklists WHERE id=p_entity_id;
  IF p_entity_type<>'offboarding_checklist'
   OR source_company IS DISTINCT FROM public.workloop_company_id()
   OR source_branch IS DISTINCT FROM public.workloop_branch_id()
   OR p_metadata IS DISTINCT FROM '{}'::jsonb
   OR (p_action='offboarding_initialized' AND
    (source_actor IS DISTINCT FROM public.workloop_app_user_id()
     OR p_changed_fields IS DISTINCT FROM ARRAY['initialized_by_app_user_id','status']::text[]))
   OR (p_action LIKE 'offboarding_task_%' AND p_changed_fields IS DISTINCT FROM ARRAY['tasks']::text[])
   OR (p_action='offboarding_visa_changed' AND p_changed_fields IS DISTINCT FROM ARRAY['visa_cancellation_status','visa_cancellation_date']::text[]) THEN
   RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
 END IF;
 INSERT INTO public.audit_events(
  company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
  initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
 VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
  public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
  p_changed_fields,p_reason,coalesce(p_metadata,'{}'::jsonb)) RETURNING id INTO event_id;
 RETURN event_id;
END
$function$;
ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) TO workloop_runtime;
"""
    )


def _idempotency() -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        f"(replay_resource_kind IN ({PHASE11G_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )


def upgrade() -> None:
    _task_provenance()
    _settlement_tables()
    _security()
    _audit()
    _idempotency()


def downgrade() -> None:
    op.execute(
        """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM public.final_settlements)
  OR EXISTS (SELECT 1 FROM public.idempotency_records WHERE replay_resource_kind='offboarding_checklist')
  OR EXISTS (SELECT 1 FROM public.audit_events WHERE action IN (
   'offboarding_initialized','offboarding_task_added','offboarding_task_completed',
   'offboarding_task_reopened','offboarding_task_deleted','offboarding_visa_changed',
   'final_settlement_completed'))
 THEN RAISE EXCEPTION 'phase11g_data_requires_preservation'; END IF;
END $$;
"""
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        f"(replay_resource_kind IN ({PHASE11F_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
    op.execute("DROP FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase11g_prior(text,text,uuid,text[],text,jsonb) "
        "RENAME TO append_audit_event"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "TO workloop_runtime"
    )
    op.execute("DROP FUNCTION public.read_offboarding_payroll_source(uuid,text)")
    op.execute("DROP POLICY phase11g_offboarding_tasks_delete_runtime ON public.offboarding_tasks")
    op.execute("REVOKE DELETE ON TABLE public.offboarding_tasks FROM workloop_runtime")
    op.execute("REVOKE SELECT,INSERT ON TABLE public.final_settlements FROM workloop_runtime")
    op.execute("REVOKE SELECT ON TABLE public.settlement_policy_versions FROM workloop_runtime")
    op.drop_constraint(
        "uq_offboarding_checklists_final_settlement_id", "offboarding_checklists", type_="unique"
    )
    op.drop_constraint(
        "fk_offboarding_checklists_final_settlement_id",
        "offboarding_checklists",
        type_="foreignkey",
    )
    op.drop_column("offboarding_checklists", "final_settlement_id")
    op.drop_table("final_settlements")
    op.drop_table("settlement_policy_versions")
    op.execute(
        "DROP TRIGGER trg_offboarding_checklists_set_updated_at ON public.offboarding_checklists"
    )
    op.drop_column("offboarding_checklists", "updated_at")
    op.drop_constraint(
        "fk_offboarding_checklists_initialized_by_app_user_id",
        "offboarding_checklists",
        type_="foreignkey",
    )
    op.drop_column("offboarding_checklists", "initialized_by_app_user_id")
    op.execute("DROP TRIGGER trg_offboarding_tasks_set_updated_at ON public.offboarding_tasks")
    op.drop_index("uq_offboarding_tasks_checklist_template", table_name="offboarding_tasks")
    op.drop_constraint("source_template", "offboarding_tasks", type_="check")
    op.drop_constraint("source", "offboarding_tasks", type_="check")
    op.drop_constraint(
        "fk_offboarding_tasks_template_scope", "offboarding_tasks", type_="foreignkey"
    )
    op.drop_column("offboarding_tasks", "updated_at")
    op.drop_column("offboarding_tasks", "template_id")
    op.drop_column("offboarding_tasks", "source")
    op.drop_constraint(
        "uq_offboarding_task_templates_id_scope", "offboarding_task_templates", type_="unique"
    )
