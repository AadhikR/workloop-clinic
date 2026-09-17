"""Add Phase 9D payroll draft calculation authority.

Revision ID: c5e7a9b1d3f4
Revises: a1c3e5f7b9d2
Created: 2026-09-17 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c5e7a9b1d3f4"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
AUDIT_PRIOR_SIGNATURE = "public._append_audit_event_phase9d_prior(text,text,uuid,text[],text,jsonb)"
REPLACE_SIGNATURE = "public.replace_payroll_entries(uuid,jsonb)"
REPLACE_PRIOR_SIGNATURE = "public._replace_payroll_entries_phase9d_prior(uuid,jsonb)"

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


def _allow_payroll_replay() -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        "(replay_resource_kind IN "
        "('branch','employee','department','user_profile','leave_request','expense_claim',"
        "'salary_advance','payroll_run') AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )


def _replace_function() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {REPLACE_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.replace_payroll_entries(uuid,jsonb) "
        "RENAME TO _replace_payroll_entries_phase9d_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {REPLACE_PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {REPLACE_PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(
        f"""
CREATE FUNCTION public.replace_payroll_entries(p_payroll_run_id uuid,p_entries jsonb)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  run public.payroll_runs%ROWTYPE;
  entry jsonb;
  key text;
  employee_id uuid;
  employee_ids uuid[] := ARRAY[]::uuid[];
  scalar_keys text[] := ARRAY[
    'basic_salary','housing_allowance','transport_allowance','allowance','increment','bonus',
    'other_pay','leave_deduction','variable_allowance','calculated_net_pay'];
  allowed_keys text[] := ARRAY[
    'employee_id','basic_salary','housing_allowance','transport_allowance','allowance',
    'increment','bonus','other_pay','leave_deduction','variable_allowance',
    'additional_allowances','deductions','excluded','source_snapshot','source_snapshot_digest',
    'calculated_net_pay'];
  value numeric;
  snapshot_digest text;
  total numeric;
  count_value integer;
BEGIN
  IF NOT ({ADMIN_CONTEXT}) THEN RAISE EXCEPTION 'workloop_admin_context_required'; END IF;
  IF p_entries IS NULL OR pg_catalog.jsonb_typeof(p_entries)<>'array' THEN
    RAISE EXCEPTION 'replace_payroll_entries_requires_array';
  END IF;
  SELECT item.* INTO run FROM public.payroll_runs AS item
  WHERE item.id=p_payroll_run_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'payroll_run_not_found'; END IF;
  IF run.company_id<>public.workloop_company_id()
     OR run.branch_id<>public.workloop_branch_id() THEN
    RAISE EXCEPTION 'payroll_run_out_of_scope';
  END IF;
  IF run.status<>'draft' OR run.approval_status<>'draft' THEN
    RAISE EXCEPTION 'payroll_run_not_draft';
  END IF;

  FOR entry IN SELECT * FROM pg_catalog.jsonb_array_elements(p_entries)
  LOOP
    IF pg_catalog.jsonb_typeof(entry)<>'object' THEN
      RAISE EXCEPTION 'payroll_entry_not_object';
    END IF;
    FOR key IN SELECT pg_catalog.jsonb_object_keys(entry)
    LOOP
      IF key<>ALL(allowed_keys) THEN RAISE EXCEPTION 'payroll_entry_unknown_key: %',key; END IF;
    END LOOP;
    IF entry->>'employee_id' IS NULL THEN RAISE EXCEPTION 'payroll_entry_missing_employee'; END IF;
    employee_id := (entry->>'employee_id')::uuid;
    IF employee_id=ANY(employee_ids) THEN
      RAISE EXCEPTION 'payroll_entry_duplicate_employee: %',employee_id;
    END IF;
    employee_ids := pg_catalog.array_append(employee_ids,employee_id);
    FOREACH key IN ARRAY scalar_keys
    LOOP
      IF NOT entry?key OR pg_catalog.jsonb_typeof(entry->key)<>'string'
         OR NOT pg_catalog.pg_input_is_valid(entry->>key,'numeric') THEN
        RAISE EXCEPTION 'payroll_entry_scalar_not_fixed: %',key;
      END IF;
      value := (entry->>key)::numeric;
      IF value IN ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
         OR pg_catalog.scale(value)>2 OR pg_catalog.abs(value)>9999999999.99 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_range: %',key;
      END IF;
      IF key NOT IN ('variable_allowance','calculated_net_pay') AND value<0 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_negative: %',key;
      END IF;
    END LOOP;
    IF pg_catalog.jsonb_typeof(entry->'additional_allowances')<>'array'
       OR pg_catalog.jsonb_typeof(entry->'deductions')<>'array'
       OR pg_catalog.jsonb_typeof(entry->'excluded')<>'boolean'
       OR pg_catalog.jsonb_typeof(entry->'source_snapshot')<>'object' THEN
      RAISE EXCEPTION 'payroll_entry_shape_invalid';
    END IF;
    IF COALESCE(entry->>'source_snapshot_digest','')!~'^[0-9a-f]{{64}}$' THEN
      RAISE EXCEPTION 'payroll_entry_snapshot_digest_invalid';
    END IF;
  END LOOP;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.unnest(employee_ids) AS candidate(id)
    WHERE NOT EXISTS (
      SELECT 1 FROM public.employees AS employee WHERE employee.id=candidate.id
        AND employee.company_id=run.company_id AND employee.branch_id=run.branch_id)) THEN
    RAISE EXCEPTION 'payroll_entry_employee_out_of_scope';
  END IF;

  DELETE FROM public.payroll_entries WHERE payroll_run_id=p_payroll_run_id;
  IF pg_catalog.jsonb_array_length(p_entries)=0 THEN
    UPDATE public.payroll_runs
    SET source_snapshot_digest='4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945',
        total_disbursed=0,employee_count=0,updated_at=statement_timestamp()
    WHERE id=p_payroll_run_id;
    RETURN;
  END IF;
  INSERT INTO public.payroll_entries(
    payroll_run_id,company_id,branch_id,employee_id,basic_salary,housing_allowance,
    transport_allowance,allowance,increment,bonus,other_pay,leave_deduction,
    variable_allowance,additional_allowances,deductions,source_snapshot,excluded,
    wps_payment_status,wps_rejection_reason)
  SELECT p_payroll_run_id,run.company_id,run.branch_id,(item->>'employee_id')::uuid,
    (item->>'basic_salary')::numeric,(item->>'housing_allowance')::numeric,
    (item->>'transport_allowance')::numeric,(item->>'allowance')::numeric,
    (item->>'increment')::numeric,(item->>'bonus')::numeric,(item->>'other_pay')::numeric,
    (item->>'leave_deduction')::numeric,(item->>'variable_allowance')::numeric,
    item->'additional_allowances',item->'deductions',item->'source_snapshot',
    (item->>'excluded')::boolean,'pending',''
  FROM pg_catalog.jsonb_array_elements(p_entries) AS item;

  SELECT pg_catalog.min(item->>'source_snapshot_digest'),
         COALESCE(pg_catalog.sum(CASE WHEN (item->>'excluded')::boolean THEN 0
           ELSE greatest((item->>'calculated_net_pay')::numeric,0::numeric) END),0::numeric),
         pg_catalog.count(*) FILTER (WHERE NOT (item->>'excluded')::boolean)
  INTO snapshot_digest,total,count_value
  FROM pg_catalog.jsonb_array_elements(p_entries) AS item;
  IF EXISTS (
    SELECT 1 FROM pg_catalog.jsonb_array_elements(p_entries) AS item
    WHERE item->>'source_snapshot_digest'<>snapshot_digest) THEN
    RAISE EXCEPTION 'payroll_entry_snapshot_digest_mixed';
  END IF;
  UPDATE public.payroll_runs SET source_snapshot_digest=snapshot_digest,
    total_disbursed=total,employee_count=count_value,updated_at=statement_timestamp()
  WHERE id=p_payroll_run_id;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {REPLACE_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {REPLACE_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {REPLACE_SIGNATURE} TO workloop_runtime")


def _wrap_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase9d_prior"
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
DECLARE event_id uuid; run public.payroll_runs%ROWTYPE;
BEGIN
  IF p_action NOT IN ('payroll_draft_created','payroll_draft_refreshed',
      'payroll_entries_replaced','payroll_draft_deleted') THEN
    RETURN public._append_audit_event_phase9d_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF NOT ({ADMIN_CONTEXT}) OR p_entity_type<>'payroll_run'
     OR pg_catalog.jsonb_typeof(p_metadata) IS DISTINCT FROM 'object'
     OR COALESCE(pg_catalog.btrim(p_reason),'')='' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  SELECT item.* INTO run FROM public.payroll_runs AS item
  WHERE item.id=p_entity_id AND item.company_id=public.workloop_company_id()
    AND item.branch_id=public.workloop_branch_id();
  IF NOT FOUND OR run.status<>'draft' OR run.approval_status<>'draft' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action='payroll_draft_created' THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY[
      'period','payment_date','sequence_no','scr_bank_routing_code','status','approval_status']::text[]
      OR p_metadata<>'{{}}'::jsonb OR run.run_by_app_user_id<>public.workloop_app_user_id()
      OR run.source_snapshot_digest<>'' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action IN ('payroll_draft_refreshed','payroll_entries_replaced') THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY[
      'source_snapshot_digest','employee_count','total_disbursed','updated_at']::text[]
      OR p_metadata<>'{{}}'::jsonb OR run.source_snapshot_digest!~'^[0-9a-f]{{64}}$' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='payroll_draft_deleted' THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY['status']::text[]
      OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata))<>1
      OR COALESCE(p_metadata->>'summary_digest','')!~'^[0-9a-f]{{64}}$' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
    p_changed_fields,p_reason,p_metadata)
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def upgrade() -> None:
    op.add_column(
        "payroll_entries",
        sa.Column(
            "source_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "source_snapshot_object",
        "payroll_entries",
        "jsonb_typeof(source_snapshot)='object'",
    )
    op.add_column(
        "payroll_runs",
        sa.Column(
            "source_snapshot_digest", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
    )
    op.create_check_constraint(
        "source_snapshot_digest",
        "payroll_runs",
        "source_snapshot_digest='' OR source_snapshot_digest~'^[0-9a-f]{64}$'",
    )
    _allow_payroll_replay()
    _replace_function()
    _wrap_audit()


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM public.audit_events WHERE action IN (
      'payroll_draft_created','payroll_draft_refreshed','payroll_entries_replaced',
      'payroll_draft_deleted'))
     OR EXISTS (SELECT 1 FROM public.idempotency_records
                WHERE replay_resource_kind='payroll_run') THEN
    RAISE EXCEPTION 'cannot downgrade Phase 9D while payroll draft audit or replay rows exist';
  END IF;
END
$block$
"""
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase9d_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {REPLACE_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {REPLACE_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._replace_payroll_entries_phase9d_prior"
        "(uuid,jsonb) RENAME TO replace_payroll_entries"
    )
    op.execute(f"ALTER FUNCTION {REPLACE_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {REPLACE_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {REPLACE_SIGNATURE} TO workloop_runtime")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        "(replay_resource_kind IN "
        "('branch','employee','department','user_profile','leave_request','expense_claim',"
        "'salary_advance') AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
    op.drop_constraint("source_snapshot_digest", "payroll_runs", type_="check")
    op.drop_column("payroll_runs", "source_snapshot_digest")
    op.drop_constraint("source_snapshot_object", "payroll_entries", type_="check")
    op.drop_column("payroll_entries", "source_snapshot")
