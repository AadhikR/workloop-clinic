"""Add Phase 9E payroll-input refresh audit authority.

Revision ID: d7f1b3c5e9a2
Revises: c5e7a9b1d3f4
Created: 2026-09-17 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d7f1b3c5e9a2"
down_revision: str | Sequence[str] | None = "c5e7a9b1d3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
AUDIT_PRIOR_SIGNATURE = "public._append_audit_event_phase9e_prior(text,text,uuid,text[],text,jsonb)"

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


def upgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase9e_prior"
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
DECLARE
  event_id uuid;
  run public.payroll_runs%ROWTYPE;
  source_type text;
  source_types text[] := ARRAY['leave','attendance','roster','expense','advance'];
BEGIN
  IF p_action<>'payroll_inputs_refreshed' THEN
    RETURN public._append_audit_event_phase9e_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF NOT ({ADMIN_CONTEXT}) OR p_entity_type<>'payroll_run'
     OR p_changed_fields IS DISTINCT FROM ARRAY[
       'source_snapshot_digest','employee_count','total_disbursed','updated_at']::text[]
     OR COALESCE(pg_catalog.btrim(p_reason),'')=''
     OR pg_catalog.jsonb_typeof(p_metadata) IS DISTINCT FROM 'object'
     OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata))<>2
     OR pg_catalog.jsonb_typeof(p_metadata->'counts') IS DISTINCT FROM 'object'
     OR pg_catalog.jsonb_typeof(p_metadata->'digests') IS DISTINCT FROM 'object'
     OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata->'counts'))<>5
     OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata->'digests'))<>5
  THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  FOREACH source_type IN ARRAY source_types
  LOOP
    IF pg_catalog.jsonb_typeof(p_metadata->'counts'->source_type) IS DISTINCT FROM 'number'
       OR NOT pg_catalog.pg_input_is_valid(p_metadata->'counts'->>source_type,'integer')
       OR (p_metadata->'counts'->>source_type)::integer<0
       OR COALESCE(p_metadata->'digests'->>source_type,'')!~'^[0-9a-f]{{64}}$'
    THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END LOOP;
  SELECT item.* INTO run FROM public.payroll_runs AS item
  WHERE item.id=p_entity_id AND item.company_id=public.workloop_company_id()
    AND item.branch_id=public.workloop_branch_id();
  IF NOT FOUND OR run.status<>'draft' OR run.approval_status<>'draft'
     OR run.source_snapshot_digest!~'^[0-9a-f]{{64}}$' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
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


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM public.audit_events WHERE action='payroll_inputs_refreshed') THEN
    RAISE EXCEPTION 'cannot downgrade Phase 9E while payroll input audit rows exist';
  END IF;
END
$block$
"""
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase9e_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
