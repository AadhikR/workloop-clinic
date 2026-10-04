"""Add the atomic branch payroll routing command.

Revision ID: f1a3c5e7b9d2
Revises: e8a1c3f5b7d9
"""

from alembic import op

revision: str = "f1a3c5e7b9d2"
down_revision: str | None = "e8a1c3f5b7d9"
branch_labels = None
depends_on = None

SIGNATURE = "public.change_branch_payroll_routing(uuid,timestamptz,text,jsonb)"


def upgrade() -> None:
    op.execute("""
CREATE FUNCTION public.change_branch_payroll_routing(
  p_branch uuid,p_expected timestamptz,p_code text,p_drafts jsonb)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $function$
DECLARE branch public.branches%ROWTYPE; run public.payroll_runs%ROWTYPE;
  expected jsonb; changed jsonb := '[]'::jsonb; count_drafts integer := 0;
BEGIN
  IF session_user<>'workloop_runtime' OR current_user<>'workloop_migration'
    OR public.workloop_role() IS DISTINCT FROM 'admin'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL OR public.workloop_employee_id() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR p_branch IS DISTINCT FROM public.workloop_branch_id()
    OR NOT EXISTS (SELECT 1 FROM public.resolve_workloop_principal() principal
      WHERE principal.app_user_id=public.workloop_app_user_id()
        AND principal.account_status='active' AND principal.role='admin'
        AND principal.profile_company_id=public.workloop_company_id()
        AND principal.company_id=principal.profile_company_id
        AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL
        AND principal.branch_id IS NULL)
  THEN RAISE EXCEPTION 'routing command denied' USING ERRCODE='42501'; END IF;
  IF p_code IS NULL OR p_code!~'^[0-9]{9}$' OR p_expected IS NULL
    OR jsonb_typeof(p_drafts) IS DISTINCT FROM 'array' OR jsonb_array_length(p_drafts)>1000
  THEN RAISE EXCEPTION 'invalid routing command' USING ERRCODE='22023'; END IF;
  SELECT * INTO branch FROM public.branches
    WHERE id=p_branch AND company_id=public.workloop_company_id() FOR UPDATE;
  IF NOT FOUND OR date_trunc('milliseconds',branch.updated_at)<>p_expected
  THEN RAISE EXCEPTION 'branch changed' USING ERRCODE='40001'; END IF;
  IF EXISTS (SELECT 1 FROM jsonb_array_elements(p_drafts) item
    WHERE jsonb_typeof(item)<>'object'
      OR (SELECT count(*) FROM jsonb_object_keys(item))<>3
      OR NOT (item ?& ARRAY['id','expectedUpdatedAt','sourceDigest'])
      OR COALESCE(item->>'sourceDigest','!')!~'^(?:[0-9a-f]{64})?$')
    OR (SELECT count(DISTINCT item->>'id') FROM jsonb_array_elements(p_drafts) item)
       <>jsonb_array_length(p_drafts)
  THEN RAISE EXCEPTION 'invalid draft set' USING ERRCODE='22023'; END IF;
  FOR run IN SELECT * FROM public.payroll_runs
    WHERE company_id=branch.company_id AND branch_id=p_branch AND status='draft'
    ORDER BY id FOR UPDATE
  LOOP
    count_drafts := count_drafts+1;
    SELECT item INTO expected FROM jsonb_array_elements(p_drafts) item
      WHERE (item->>'id')::uuid=run.id;
    IF expected IS NULL OR run.approval_status<>'draft' OR run.wps_status<>'draft'
      OR date_trunc('milliseconds',run.updated_at)
         IS DISTINCT FROM (expected->>'expectedUpdatedAt')::timestamptz
      OR run.source_snapshot_digest IS DISTINCT FROM expected->>'sourceDigest'
    THEN RAISE EXCEPTION 'draft changed or approved' USING ERRCODE='40001'; END IF;
  END LOOP;
  IF count_drafts<>jsonb_array_length(p_drafts)
  THEN RAISE EXCEPTION 'draft set changed' USING ERRCODE='40001'; END IF;
  UPDATE public.branches SET default_bank_routing_code=p_code,
    updated_at=GREATEST(clock_timestamp(),branch.updated_at+interval '1 millisecond')
    WHERE id=p_branch;
  INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
    action,entity_type,entity_id,changed_fields,reason,metadata)
    VALUES(branch.company_id,p_branch,'human',public.workloop_app_user_id(),
      'branch_payroll_routing_changed','branch',p_branch,
      ARRAY['default_bank_routing_code','updated_at'],'Branch payroll routing change','{}');
  FOR run IN SELECT * FROM public.payroll_runs
    WHERE company_id=branch.company_id AND branch_id=p_branch AND status='draft' ORDER BY id
  LOOP
    UPDATE public.payroll_runs SET scr_bank_routing_code=p_code,
      updated_at=GREATEST(clock_timestamp(),run.updated_at+interval '1 millisecond')
      WHERE id=run.id RETURNING * INTO run;
    INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
      action,entity_type,entity_id,changed_fields,reason,metadata)
      VALUES(branch.company_id,p_branch,'human',public.workloop_app_user_id(),
        'payroll_routing_changed','payroll_run',run.id,
        ARRAY['scr_bank_routing_code','updated_at'],'Branch payroll routing change','{}');
    changed := changed || jsonb_build_array(jsonb_build_object('id',run.id,
      'expectedUpdatedAt',to_char(run.updated_at AT TIME ZONE 'UTC',
        'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
      'sourceDigest',run.source_snapshot_digest));
  END LOOP;
  RETURN changed;
END
$function$
""")
    op.execute(f"ALTER FUNCTION {SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO workloop_runtime")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {SIGNATURE}")
