"""Add Phase 9G WPS, compliance, and Nafis authority.

Revision ID: e3a7c9d1f5b2
Revises: b8e2c4d6f9a1
Created: 2026-09-17 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e3a7c9d1f5b2"
down_revision: str | Sequence[str] | None = "b8e2c4d6f9a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
AUDIT_PRIOR_SIGNATURE = "public._append_audit_event_phase9g_prior(text,text,uuid,text[],text,jsonb)"
RUN_TRANSITION_SIGNATURE = (
    "public.transition_payroll_wps(uuid,text,text,text,timestamp with time zone,text,text)"
)
ENTRY_TRANSITION_SIGNATURE = (
    "public.transition_wps_entry(uuid,uuid,text,text,timestamp with time zone)"
)
OVERRIDE_SIGNATURE = "public.create_wps_compliance_override(uuid,uuid,uuid,text,text)"
NAFIS_SIGNATURE = (
    "public.replace_nafis_snapshot(uuid,text,integer,integer,numeric,numeric,boolean,jsonb,"
    "timestamp with time zone)"
)
NAFIS_LOCK_SIGNATURE = "public.lock_nafis_sources(date)"

ADMIN_CONTEXT = """
session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
AND public.workloop_role()='admin'
AND public.workloop_employee_id() IS NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() AS principal
  WHERE principal.app_user_id=public.workloop_app_user_id()
    AND principal.account_status='active' AND principal.role='admin'
    AND principal.profile_company_id=public.workloop_company_id()
    AND principal.company_id=principal.profile_company_id
    AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL
    AND principal.branch_id IS NULL)
AND EXISTS (
  SELECT 1 FROM public.branches AS branch
  WHERE branch.id=public.workloop_branch_id()
    AND branch.company_id=public.workloop_company_id())
""".strip()


def _schema() -> None:
    op.add_column("compliance_overrides", sa.Column("payroll_run_id", sa.UUID(), nullable=True))
    op.add_column("compliance_overrides", sa.Column("payroll_entry_id", sa.UUID(), nullable=True))
    op.add_column("compliance_overrides", sa.Column("rule_code", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_compliance_overrides_payroll_run_id_payroll_runs"),
        "compliance_overrides",
        "payroll_runs",
        ["payroll_run_id", "company_id", "branch_id"],
        ["id", "company_id", "branch_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_compliance_overrides_payroll_entry_id_payroll_entries"),
        "compliance_overrides",
        "payroll_entries",
        ["payroll_entry_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_compliance_overrides_rule_code"),
        "compliance_overrides",
        "rule_code IS NULL OR rule_code IN ('visa_expired','emirates_id_expired',"
        "'labour_card_expired','passport_expired','professional_licence_expired')",
    )
    op.create_index(
        "ix_compliance_overrides_payroll_run_id",
        "compliance_overrides",
        ["payroll_run_id"],
    )
    op.create_index(
        "ix_compliance_overrides_payroll_entry_id",
        "compliance_overrides",
        ["payroll_entry_id"],
    )
    op.execute(
        "CREATE TRIGGER trg_compliance_overrides_immutable BEFORE UPDATE OR DELETE "
        "ON public.compliance_overrides FOR EACH ROW EXECUTE FUNCTION "
        "public.reject_immutable_payroll_evidence_mutation()"
    )
    op.execute("REVOKE INSERT, UPDATE, DELETE ON public.compliance_overrides FROM workloop_runtime")
    op.execute("REVOKE INSERT, UPDATE, DELETE ON public.nafis_reports FROM workloop_runtime")


def _run_transition() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.transition_payroll_wps(
  p_run_id uuid,p_action text,p_reference_number text,p_reason text,
  p_expected_updated_at timestamptz,p_projection_digest text,p_projection_mode text)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE run public.payroll_runs%ROWTYPE; previous_digest text;
BEGIN
  IF NOT ({ADMIN_CONTEXT})
     OR p_action NOT IN ('sif_generated','submit','confirm','fail') THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
  SELECT item.* INTO run FROM public.payroll_runs AS item WHERE item.id=p_run_id FOR UPDATE;
  IF NOT FOUND OR run.company_id<>public.workloop_company_id()
     OR run.branch_id<>public.workloop_branch_id() THEN
    RAISE EXCEPTION 'payroll_run_not_found';
  END IF;
  IF run.status<>'generated' OR run.approval_status<>'approved'
     OR p_expected_updated_at IS NULL
     OR pg_catalog.date_trunc('milliseconds',run.updated_at)
        <>pg_catalog.date_trunc('milliseconds',p_expected_updated_at)
     OR run.wps_status='confirmed' THEN
    RAISE EXCEPTION 'stale_financial_state';
  END IF;
  IF p_action='sif_generated' THEN
    IF p_projection_digest!~'^[0-9a-f]{{64}}$'
       OR p_projection_mode NOT IN ('full','rejected') THEN
      RAISE EXCEPTION 'invalid_sif_projection';
    END IF;
    IF p_projection_mode='full' THEN
      IF run.wps_status<>'draft' THEN RAISE EXCEPTION 'stale_financial_state'; END IF;
    ELSE
      IF run.wps_status<>'partial_rejection'
         OR NOT EXISTS (SELECT 1 FROM public.payroll_entries
                        WHERE payroll_run_id=run.id AND wps_payment_status='rejected') THEN
        RAISE EXCEPTION 'stale_financial_state';
      END IF;
      SELECT event.metadata->>'digest' INTO previous_digest
      FROM public.audit_events AS event
      WHERE event.entity_type='payroll_run' AND event.entity_id=run.id
        AND event.action='sif_projection_recorded'
      ORDER BY event.occurred_at DESC,event.id DESC LIMIT 1;
      IF previous_digest=p_projection_digest THEN RAISE EXCEPTION 'stale_financial_state'; END IF;
      UPDATE public.payroll_entries SET wps_payment_status='pending',wps_rejection_reason='',
        updated_at=statement_timestamp()
      WHERE payroll_run_id=run.id AND wps_payment_status='rejected';
    END IF;
    UPDATE public.payroll_runs SET wps_status='sif_generated',updated_at=statement_timestamp()
    WHERE id=run.id;
  ELSIF p_action='submit' THEN
    IF run.wps_status<>'sif_generated'
       OR COALESCE(pg_catalog.btrim(p_reference_number),'')=''
       OR pg_catalog.char_length(pg_catalog.btrim(p_reference_number))>100 THEN
      RAISE EXCEPTION 'stale_financial_state';
    END IF;
    UPDATE public.payroll_runs SET wps_status='submitted',
      wps_submitted_at=statement_timestamp(),
      wps_reference_no=pg_catalog.btrim(p_reference_number),updated_at=statement_timestamp()
    WHERE id=run.id;
  ELSIF p_action='confirm' THEN
    IF run.wps_status NOT IN ('submitted','partial_rejection')
       OR EXISTS (SELECT 1 FROM public.payroll_entries
                  WHERE payroll_run_id=run.id AND NOT excluded
                    AND wps_payment_status<>'paid') THEN
      RAISE EXCEPTION 'stale_financial_state';
    END IF;
    UPDATE public.payroll_runs SET wps_status='confirmed',
      wps_confirmed_at=statement_timestamp(),updated_at=statement_timestamp()
    WHERE id=run.id;
  ELSE
    IF COALESCE(pg_catalog.btrim(p_reason),'')=''
       OR pg_catalog.char_length(pg_catalog.btrim(p_reason))>500 THEN
      RAISE EXCEPTION 'stale_financial_state';
    END IF;
    UPDATE public.payroll_runs SET wps_status='failed',updated_at=statement_timestamp()
    WHERE id=run.id;
  END IF;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {RUN_TRANSITION_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {RUN_TRANSITION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {RUN_TRANSITION_SIGNATURE} TO workloop_runtime")


def _entry_transition() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.transition_wps_entry(
  p_run_id uuid,p_entry_id uuid,p_action text,p_reason text,p_expected_updated_at timestamptz)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE run public.payroll_runs%ROWTYPE; entry public.payroll_entries%ROWTYPE;
BEGIN
  IF NOT ({ADMIN_CONTEXT}) OR p_action NOT IN ('paid','reject') THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
  SELECT item.* INTO run FROM public.payroll_runs AS item WHERE item.id=p_run_id FOR UPDATE;
  IF NOT FOUND OR run.company_id<>public.workloop_company_id()
     OR run.branch_id<>public.workloop_branch_id() THEN
    RAISE EXCEPTION 'payroll_run_not_found';
  END IF;
  IF run.status<>'generated' OR run.approval_status<>'approved'
     OR run.wps_status NOT IN ('submitted','partial_rejection') THEN
    RAISE EXCEPTION 'stale_financial_state';
  END IF;
  SELECT item.* INTO entry FROM public.payroll_entries AS item
  WHERE item.id=p_entry_id AND item.payroll_run_id=run.id FOR UPDATE;
  IF NOT FOUND OR entry.company_id<>run.company_id OR entry.branch_id<>run.branch_id
     OR entry.excluded OR entry.wps_payment_status<>'pending'
     OR pg_catalog.date_trunc('milliseconds',entry.updated_at)
        <>pg_catalog.date_trunc('milliseconds',p_expected_updated_at) THEN
    RAISE EXCEPTION 'stale_financial_state';
  END IF;
  IF p_action='paid' THEN
    UPDATE public.payroll_entries SET wps_payment_status='paid',wps_rejection_reason='',
      updated_at=statement_timestamp() WHERE id=entry.id;
  ELSE
    IF COALESCE(pg_catalog.btrim(p_reason),'')=''
       OR pg_catalog.char_length(pg_catalog.btrim(p_reason))>500 THEN
      RAISE EXCEPTION 'stale_financial_state';
    END IF;
    UPDATE public.payroll_entries SET wps_payment_status='rejected',
      wps_rejection_reason=pg_catalog.btrim(p_reason),updated_at=statement_timestamp()
    WHERE id=entry.id;
    UPDATE public.payroll_runs SET wps_status='partial_rejection',
      wps_confirmed_at=COALESCE(wps_confirmed_at,statement_timestamp()) WHERE id=run.id;
  END IF;
  UPDATE public.payroll_runs SET updated_at=statement_timestamp() WHERE id=run.id;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {ENTRY_TRANSITION_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {ENTRY_TRANSITION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ENTRY_TRANSITION_SIGNATURE} TO workloop_runtime")


def _override_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.create_wps_compliance_override(
  p_override_id uuid,p_run_id uuid,p_entry_id uuid,p_rule_code text,p_reason text)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE run public.payroll_runs%ROWTYPE;
BEGIN
  IF NOT ({ADMIN_CONTEXT}) OR p_override_id IS NULL
     OR p_rule_code NOT IN ('visa_expired','emirates_id_expired','labour_card_expired',
       'passport_expired','professional_licence_expired')
     OR COALESCE(pg_catalog.btrim(p_reason),'')=''
     OR pg_catalog.char_length(pg_catalog.btrim(p_reason))>500 THEN
    RAISE EXCEPTION 'compliance_override_denied';
  END IF;
  SELECT item.* INTO run FROM public.payroll_runs AS item WHERE item.id=p_run_id FOR SHARE;
  IF NOT FOUND OR run.company_id<>public.workloop_company_id()
     OR run.branch_id<>public.workloop_branch_id()
     OR run.status<>'generated' OR run.approval_status<>'approved'
     OR (p_entry_id IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM public.payroll_entries AS entry
       WHERE entry.id=p_entry_id AND entry.payroll_run_id=run.id
         AND entry.company_id=run.company_id AND entry.branch_id=run.branch_id)) THEN
    RAISE EXCEPTION 'compliance_override_denied';
  END IF;
  INSERT INTO public.compliance_overrides(
    id,company_id,branch_id,override_type,employee_ids,reason,created_by_app_user_id,
    payroll_run_id,payroll_entry_id,rule_code)
  VALUES(p_override_id,run.company_id,run.branch_id,'payroll_sif',NULL,
    pg_catalog.btrim(p_reason),public.workloop_app_user_id(),run.id,p_entry_id,p_rule_code);
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {OVERRIDE_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {OVERRIDE_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {OVERRIDE_SIGNATURE} TO workloop_runtime")


def _nafis_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.lock_nafis_sources(p_period_end date)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF NOT ({ADMIN_CONTEXT}) OR p_period_end IS NULL THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
  PERFORM 1 FROM public.companies
  WHERE id=public.workloop_company_id() FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'nafis_source_not_found'; END IF;
  PERFORM 1 FROM public.branches
  WHERE id=public.workloop_branch_id() AND company_id=public.workloop_company_id() FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'nafis_source_not_found'; END IF;
  PERFORM id FROM public.employees
  WHERE company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
    AND (employment_start_date IS NULL OR employment_start_date<=p_period_end)
    AND (termination_date IS NULL OR termination_date>=p_period_end)
    AND employment_status IN ('Active','Probation','On Leave','Terminated')
  ORDER BY id FOR SHARE;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {NAFIS_LOCK_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {NAFIS_LOCK_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {NAFIS_LOCK_SIGNATURE} TO workloop_runtime")
    op.execute(
        f"""
CREATE FUNCTION public.replace_nafis_snapshot(
  p_snapshot_id uuid,p_period text,p_total_headcount integer,p_emirati_count integer,
  p_ratio_percent numeric,p_required_percent numeric,p_compliant boolean,p_snapshot jsonb,
  p_expected_generated_at timestamptz)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE existing public.nafis_reports%ROWTYPE; result_id uuid;
BEGIN
  IF NOT ({ADMIN_CONTEXT}) OR p_snapshot_id IS NULL
     OR p_period!~'^[0-9]{{4}}-(0[1-9]|1[0-2])$'
     OR p_total_headcount<0 OR p_emirati_count<0 OR p_emirati_count>p_total_headcount
     OR p_ratio_percent<0 OR p_ratio_percent>100 OR pg_catalog.scale(p_ratio_percent)>2
     OR p_required_percent<0 OR p_required_percent>100
     OR pg_catalog.scale(p_required_percent)>2 OR p_compliant IS NULL
     OR p_compliant IS DISTINCT FROM (p_ratio_percent>=p_required_percent)
     OR pg_catalog.jsonb_typeof(p_snapshot) IS DISTINCT FROM 'object'
     OR COALESCE(p_snapshot->>'sourceVersion','')!~'^[0-9a-f]{{64}}$'
     OR pg_catalog.jsonb_typeof(p_snapshot->'employees') IS DISTINCT FROM 'array'
     OR pg_catalog.jsonb_array_length(p_snapshot->'employees')<>p_emirati_count THEN
    RAISE EXCEPTION 'nafis_snapshot_denied';
  END IF;
  SELECT report.* INTO existing FROM public.nafis_reports AS report
  WHERE report.company_id=public.workloop_company_id()
    AND report.branch_id=public.workloop_branch_id() AND report.period=p_period FOR UPDATE;
  IF FOUND THEN
    IF p_expected_generated_at IS NULL
       OR pg_catalog.date_trunc('milliseconds',existing.generated_at)
          <>pg_catalog.date_trunc('milliseconds',p_expected_generated_at) THEN
      RAISE EXCEPTION 'stale_financial_state';
    END IF;
    UPDATE public.nafis_reports SET total_headcount=p_total_headcount,
      emirati_count=p_emirati_count,ratio_percent=p_ratio_percent,
      required_percent=p_required_percent,compliant=p_compliant,snapshot=p_snapshot,
      generated_at=statement_timestamp() WHERE id=existing.id RETURNING id INTO result_id;
  ELSE
    IF p_expected_generated_at IS NOT NULL THEN RAISE EXCEPTION 'stale_financial_state'; END IF;
    INSERT INTO public.nafis_reports(
      id,company_id,branch_id,period,total_headcount,emirati_count,ratio_percent,
      required_percent,compliant,snapshot,generated_at)
    VALUES(p_snapshot_id,public.workloop_company_id(),public.workloop_branch_id(),p_period,
      p_total_headcount,p_emirati_count,p_ratio_percent,p_required_percent,p_compliant,p_snapshot,
      statement_timestamp()) RETURNING id INTO result_id;
  END IF;
  RETURN result_id;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {NAFIS_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {NAFIS_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {NAFIS_SIGNATURE} TO workloop_runtime")


def _audit_wrapper() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase9g_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(
        f"""
CREATE FUNCTION public.append_audit_event(
  p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],
  p_reason text,p_metadata jsonb)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE event_id uuid; run public.payroll_runs%ROWTYPE; entry public.payroll_entries%ROWTYPE;
  override_row public.compliance_overrides%ROWTYPE; report public.nafis_reports%ROWTYPE;
BEGIN
  IF p_action NOT IN ('payroll_wps_changed','wps_entry_paid','wps_entry_rejected',
      'sif_projection_recorded','compliance_override_created','nafis_snapshot_replaced') THEN
    RETURN public._append_audit_event_phase9g_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF NOT ({ADMIN_CONTEXT}) OR COALESCE(pg_catalog.btrim(p_reason),'')=''
     OR pg_catalog.jsonb_typeof(p_metadata) IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action IN ('payroll_wps_changed','sif_projection_recorded') THEN
    SELECT item.* INTO run FROM public.payroll_runs AS item WHERE item.id=p_entity_id
      AND item.company_id=public.workloop_company_id()
      AND item.branch_id=public.workloop_branch_id();
    IF NOT FOUND OR p_entity_type<>'payroll_run' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
    IF p_action='payroll_wps_changed' THEN
      IF p_changed_fields IS DISTINCT FROM ARRAY['wps_status','wps_submitted_at',
          'wps_confirmed_at','wps_reference_no']::text[] OR p_metadata<>'{{}}'::jsonb
         OR run.status<>'generated' OR run.wps_status='draft' THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSE
      IF p_changed_fields IS DISTINCT FROM ARRAY['wps_status','updated_at']::text[]
         OR run.wps_status<>'sif_generated'
         OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata))<>4
         OR p_metadata->>'mode' NOT IN ('full','rejected')
         OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'row_count','integer')
         OR (p_metadata->>'row_count')::integer<1
         OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'integer_total','bigint')
         OR COALESCE(p_metadata->>'digest','')!~'^[0-9a-f]{{64}}$' THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    END IF;
  ELSIF p_action IN ('wps_entry_paid','wps_entry_rejected') THEN
    SELECT item.* INTO entry FROM public.payroll_entries AS item WHERE item.id=p_entity_id
      AND item.company_id=public.workloop_company_id()
      AND item.branch_id=public.workloop_branch_id();
    IF NOT FOUND OR p_entity_type<>'payroll_entry'
       OR p_changed_fields IS DISTINCT FROM ARRAY[
         'wps_payment_status','wps_rejection_reason']::text[]
       OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata))>1
       OR (p_metadata?'corrected_projection_digest'
           AND COALESCE(p_metadata->>'corrected_projection_digest','')!~'^[0-9a-f]{{64}}$')
       OR (p_action='wps_entry_paid' AND (
         entry.wps_payment_status<>'paid' OR entry.wps_rejection_reason<>''))
       OR (p_action='wps_entry_rejected' AND (
         entry.wps_payment_status<>'rejected' OR entry.wps_rejection_reason<>p_reason)) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='compliance_override_created' THEN
    SELECT item.* INTO override_row FROM public.compliance_overrides AS item
    WHERE item.id=p_entity_id AND item.company_id=public.workloop_company_id()
      AND item.branch_id=public.workloop_branch_id();
    IF NOT FOUND OR p_entity_type<>'compliance_override'
       OR p_changed_fields IS DISTINCT FROM ARRAY['rule_code','reason']::text[]
       OR p_metadata<>'{{}}'::jsonb
       OR override_row.created_by_app_user_id<>public.workloop_app_user_id()
       OR override_row.reason<>p_reason OR override_row.rule_code IS NULL
       OR override_row.payroll_run_id IS NULL THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    SELECT item.* INTO report FROM public.nafis_reports AS item WHERE item.id=p_entity_id
      AND item.company_id=public.workloop_company_id()
      AND item.branch_id=public.workloop_branch_id();
    IF NOT FOUND OR p_entity_type<>'nafis_report'
       OR p_changed_fields IS DISTINCT FROM ARRAY['total_headcount','emirati_count',
         'ratio_percent','required_percent','compliant','snapshot','generated_at']::text[]
       OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata))<>2
       OR p_metadata->>'period'<>report.period
       OR COALESCE(p_metadata->>'source_digest','')!~'^[0-9a-f]{{64}}$' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
    p_changed_fields,p_reason,p_metadata) RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def upgrade() -> None:
    _schema()
    _run_transition()
    _entry_transition()
    _override_function()
    _nafis_function()
    _audit_wrapper()


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM public.audit_events WHERE action IN (
    'payroll_wps_changed','wps_entry_paid','wps_entry_rejected','sif_projection_recorded',
    'compliance_override_created','nafis_snapshot_replaced')) THEN
    RAISE EXCEPTION 'cannot downgrade Phase 9G while WPS or Nafis evidence exists';
  END IF;
END
$block$
"""
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase9g_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    for signature in (
        NAFIS_SIGNATURE,
        OVERRIDE_SIGNATURE,
        ENTRY_TRANSITION_SIGNATURE,
        RUN_TRANSITION_SIGNATURE,
    ):
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM workloop_runtime")
        op.execute(f"DROP FUNCTION {signature}")
    op.execute(f"DROP FUNCTION IF EXISTS {NAFIS_LOCK_SIGNATURE}")
    op.execute("DROP TRIGGER trg_compliance_overrides_immutable ON public.compliance_overrides")
    op.execute("GRANT INSERT ON public.compliance_overrides TO workloop_runtime")
    op.execute("GRANT INSERT, UPDATE ON public.nafis_reports TO workloop_runtime")
    op.drop_index("ix_compliance_overrides_payroll_entry_id", table_name="compliance_overrides")
    op.drop_index("ix_compliance_overrides_payroll_run_id", table_name="compliance_overrides")
    op.drop_constraint(
        op.f("ck_compliance_overrides_rule_code"), "compliance_overrides", type_="check"
    )
    op.drop_constraint(
        op.f("fk_compliance_overrides_payroll_entry_id_payroll_entries"),
        "compliance_overrides",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_compliance_overrides_payroll_run_id_payroll_runs"),
        "compliance_overrides",
        type_="foreignkey",
    )
    op.drop_column("compliance_overrides", "rule_code")
    op.drop_column("compliance_overrides", "payroll_entry_id")
    op.drop_column("compliance_overrides", "payroll_run_id")
