"""Add Phase 9F payroll approval and immutable payslip authority.

Revision ID: b8e2c4d6f9a1
Revises: d7f1b3c5e9a2
Created: 2026-09-17 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8e2c4d6f9a1"
down_revision: str | Sequence[str] | None = "d7f1b3c5e9a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
AUDIT_PRIOR_SIGNATURE = "public._append_audit_event_phase9f_prior(text,text,uuid,text[],text,jsonb)"
IMMUTABLE_TRIGGER_SIGNATURE = "public.reject_immutable_payroll_evidence_mutation()"
LOCK_SIGNATURE = "public.lock_payroll_run(uuid)"
TRANSITION_SIGNATURE = "public.transition_payroll_run(uuid,text,text,timestamp with time zone)"
FINALIZE_SIGNATURE = "public.finalize_payroll_run(uuid,numeric,integer,timestamp with time zone)"

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


def _immutable_rows() -> None:
    op.execute(
        """
CREATE FUNCTION public.reject_immutable_payroll_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql VOLATILE
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF session_user<>'workloop_migration' THEN
    RAISE EXCEPTION 'immutable payroll evidence cannot be changed' USING ERRCODE='42501';
  END IF;
  RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {IMMUTABLE_TRIGGER_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {IMMUTABLE_TRIGGER_SIGNATURE} FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER trg_payslips_immutable BEFORE UPDATE OR DELETE ON public.payslips "
        "FOR EACH ROW EXECUTE FUNCTION public.reject_immutable_payroll_evidence_mutation()"
    )
    op.execute(
        "CREATE TRIGGER trg_payroll_approval_log_immutable BEFORE UPDATE OR DELETE "
        "ON public.payroll_approval_log FOR EACH ROW EXECUTE FUNCTION "
        "public.reject_immutable_payroll_evidence_mutation()"
    )
    op.execute("REVOKE UPDATE, DELETE ON public.payslips FROM workloop_runtime")
    op.execute("REVOKE UPDATE, DELETE ON public.payroll_approval_log FROM workloop_runtime")
    op.execute("REVOKE UPDATE ON public.payroll_runs FROM workloop_runtime")
    op.execute("DROP POLICY phase5f_payslips_select_runtime ON public.payslips")
    op.execute(
        """
CREATE POLICY phase5f_payslips_select_runtime ON public.payslips
FOR SELECT TO workloop_runtime
USING (
  session_user='workloop_runtime'
  AND public.workloop_actor_kind()='human'
  AND public.workloop_actor_key() IS NULL
  AND public.workloop_business_date() IS NOT NULL
  AND public.workloop_app_user_id() IS NOT NULL
  AND public.workloop_company_id() IS NOT NULL
  AND public.workloop_branch_id() IS NOT NULL
  AND company_id=public.workloop_company_id()
  AND branch_id=public.workloop_branch_id()
  AND public.workloop_role()='employee'
  AND employee_id=public.workloop_employee_id()
)
"""
    )


def _transition_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.transition_payroll_run(
  p_run_id uuid,p_action text,p_reason text,p_expected_updated_at timestamptz)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE run public.payroll_runs%ROWTYPE; actor uuid;
BEGIN
  IF NOT ({ADMIN_CONTEXT}) OR p_action NOT IN ('submit','recall','approve','reject') THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
  actor := public.workloop_app_user_id();
  SELECT item.* INTO run FROM public.payroll_runs AS item WHERE item.id=p_run_id FOR UPDATE;
  IF NOT FOUND OR run.company_id<>public.workloop_company_id()
     OR run.branch_id<>public.workloop_branch_id() THEN
    RETURN;
  END IF;
  IF p_expected_updated_at IS NULL
     OR pg_catalog.date_trunc('milliseconds',run.updated_at)
        <>pg_catalog.date_trunc('milliseconds',p_expected_updated_at) THEN
    RAISE EXCEPTION 'stale_financial_state';
  END IF;
  IF p_action='submit' THEN
    IF run.status<>'draft' OR run.approval_status<>'draft'
       OR run.source_snapshot_digest!~'^[0-9a-f]{{64}}$'
       OR NOT EXISTS (SELECT 1 FROM public.payroll_entries WHERE payroll_run_id=run.id) THEN
      RAISE EXCEPTION 'stale_financial_state';
    END IF;
    UPDATE public.payroll_runs SET approval_status='pending_approval',
      submitted_by_app_user_id=actor,submitted_for_approval_at=statement_timestamp(),
      approved_by_app_user_id=NULL,approved_at=NULL,rejection_reason='',
      rejected_by_app_user_id=NULL,rejected_at=NULL,updated_at=statement_timestamp()
    WHERE id=run.id;
    INSERT INTO public.payroll_approval_log(
      company_id,branch_id,payroll_run_id,action,performed_by_app_user_id,notes)
    VALUES(run.company_id,run.branch_id,run.id,'submitted',actor,'');
  ELSIF p_action='recall' THEN
    IF run.status<>'draft' OR run.approval_status<>'pending_approval'
       OR COALESCE(pg_catalog.btrim(p_reason),'')='' THEN
      RAISE EXCEPTION 'stale_financial_state';
    END IF;
    UPDATE public.payroll_runs SET approval_status='draft',
      submitted_by_app_user_id=NULL,submitted_for_approval_at=NULL,
      approved_by_app_user_id=NULL,approved_at=NULL,updated_at=statement_timestamp()
    WHERE id=run.id;
    INSERT INTO public.payroll_approval_log(
      company_id,branch_id,payroll_run_id,action,performed_by_app_user_id,notes)
    VALUES(run.company_id,run.branch_id,run.id,'recalled',actor,pg_catalog.btrim(p_reason));
  ELSIF p_action='approve' THEN
    IF run.status<>'draft' OR run.approval_status<>'pending_approval'
       OR actor=run.run_by_app_user_id OR actor=run.submitted_by_app_user_id THEN
      RAISE EXCEPTION 'payroll_approval_separation_required';
    END IF;
    UPDATE public.payroll_runs SET approval_status='approved',
      approved_by_app_user_id=actor,approved_at=statement_timestamp(),
      rejection_reason='',rejected_by_app_user_id=NULL,rejected_at=NULL,
      updated_at=statement_timestamp() WHERE id=run.id;
    INSERT INTO public.payroll_approval_log(
      company_id,branch_id,payroll_run_id,action,performed_by_app_user_id,notes)
    VALUES(run.company_id,run.branch_id,run.id,'approved',actor,'');
  ELSE
    IF run.status<>'draft' OR run.approval_status<>'pending_approval'
       OR actor=run.submitted_by_app_user_id
       OR COALESCE(pg_catalog.btrim(p_reason),'')='' THEN
      RAISE EXCEPTION 'payroll_rejection_denied';
    END IF;
    UPDATE public.payroll_runs SET approval_status='draft',
      submitted_by_app_user_id=NULL,submitted_for_approval_at=NULL,
      approved_by_app_user_id=NULL,approved_at=NULL,rejection_reason=pg_catalog.btrim(p_reason),
      rejected_by_app_user_id=actor,rejected_at=statement_timestamp(),
      updated_at=statement_timestamp() WHERE id=run.id;
    INSERT INTO public.payroll_approval_log(
      company_id,branch_id,payroll_run_id,action,performed_by_app_user_id,notes)
    VALUES(run.company_id,run.branch_id,run.id,'rejected',actor,pg_catalog.btrim(p_reason));
  END IF;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {TRANSITION_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {TRANSITION_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {TRANSITION_SIGNATURE} TO workloop_runtime")


def _lock_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.lock_payroll_run(p_run_id uuid)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE run public.payroll_runs%ROWTYPE;
BEGIN
  IF NOT ({ADMIN_CONTEXT}) THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
  SELECT item.* INTO run FROM public.payroll_runs AS item WHERE item.id=p_run_id FOR UPDATE;
  IF NOT FOUND OR run.company_id<>public.workloop_company_id()
     OR run.branch_id<>public.workloop_branch_id() THEN
    RAISE EXCEPTION 'payroll_run_not_found';
  END IF;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {LOCK_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {LOCK_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {LOCK_SIGNATURE} TO workloop_runtime")


def _finalize_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.finalize_payroll_run(
  p_run_id uuid,p_total numeric,p_count integer,p_expected_updated_at timestamptz)
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE run public.payroll_runs%ROWTYPE;
BEGIN
  IF NOT ({ADMIN_CONTEXT}) OR p_total IS NULL OR p_total<0 OR pg_catalog.scale(p_total)>2
     OR p_count IS NULL OR p_count<0 THEN
    RAISE EXCEPTION 'payroll_generation_denied';
  END IF;
  SELECT item.* INTO run FROM public.payroll_runs AS item WHERE item.id=p_run_id FOR UPDATE;
  IF NOT FOUND OR run.company_id<>public.workloop_company_id()
     OR run.branch_id<>public.workloop_branch_id()
     OR run.status<>'draft' OR run.approval_status<>'approved'
     OR pg_catalog.date_trunc('milliseconds',run.updated_at)
        <>pg_catalog.date_trunc('milliseconds',p_expected_updated_at)
     OR run.total_disbursed<>p_total OR run.employee_count<>p_count
     OR (SELECT pg_catalog.count(*) FROM public.payslips WHERE payroll_run_id=run.id)<>p_count
     OR COALESCE((SELECT pg_catalog.sum(net_pay) FROM public.payslips
                  WHERE payroll_run_id=run.id),0::numeric)<>p_total THEN
    RAISE EXCEPTION 'stale_financial_state';
  END IF;
  UPDATE public.payroll_runs SET status='generated',total_disbursed=p_total,
    employee_count=p_count,updated_at=statement_timestamp() WHERE id=run.id;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {FINALIZE_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {FINALIZE_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FINALIZE_SIGNATURE} TO workloop_runtime")


def _wrap_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase9f_prior"
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
  claim public.expense_claims%ROWTYPE;
BEGIN
  IF p_action NOT IN ('payroll_submitted','payroll_recalled','payroll_approved',
      'payroll_rejected','payroll_generated','expense_paid','payslips_issued') THEN
    RETURN public._append_audit_event_phase9f_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF NOT ({ADMIN_CONTEXT}) OR COALESCE(pg_catalog.btrim(p_reason),'')=''
     OR pg_catalog.jsonb_typeof(p_metadata) IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action='expense_paid' THEN
    SELECT item.* INTO claim FROM public.expense_claims AS item
    WHERE item.id=p_entity_id AND item.company_id=public.workloop_company_id()
      AND item.branch_id=public.workloop_branch_id();
    IF NOT FOUND OR p_entity_type<>'expense_claim'
       OR p_changed_fields IS DISTINCT FROM ARRAY['status','payroll_run_id']::text[]
       OR p_metadata<>'{{}}'::jsonb OR claim.status<>'paid'
       OR claim.payroll_run_id IS NULL
       OR NOT EXISTS (
         SELECT 1 FROM public.payroll_runs AS payroll
         WHERE payroll.id=claim.payroll_run_id AND payroll.company_id=claim.company_id
           AND payroll.branch_id=claim.branch_id) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    SELECT item.* INTO run FROM public.payroll_runs AS item
    WHERE item.id=p_entity_id AND item.company_id=public.workloop_company_id()
      AND item.branch_id=public.workloop_branch_id();
    IF NOT FOUND OR p_entity_type<>'payroll_run' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
    IF p_action='payroll_submitted' THEN
      IF p_changed_fields IS DISTINCT FROM ARRAY[
          'approval_status','submitted_by_app_user_id','submitted_for_approval_at']::text[]
         OR p_metadata<>'{{}}'::jsonb OR run.status<>'draft'
         OR run.approval_status<>'pending_approval'
         OR run.submitted_by_app_user_id<>public.workloop_app_user_id()
         OR NOT EXISTS (SELECT 1 FROM public.payroll_approval_log AS history
           WHERE history.payroll_run_id=run.id AND history.action='submitted'
             AND history.performed_by_app_user_id=public.workloop_app_user_id()) THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSIF p_action='payroll_recalled' THEN
      IF p_changed_fields IS DISTINCT FROM ARRAY[
          'approval_status','submitted_by_app_user_id','submitted_for_approval_at']::text[]
         OR p_metadata<>'{{}}'::jsonb OR run.status<>'draft' OR run.approval_status<>'draft'
         OR NOT EXISTS (SELECT 1 FROM public.payroll_approval_log AS history
           WHERE history.payroll_run_id=run.id AND history.action='recalled'
             AND history.performed_by_app_user_id=public.workloop_app_user_id()
             AND pg_catalog.btrim(history.notes)<>'') THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSIF p_action='payroll_approved' THEN
      IF p_changed_fields IS DISTINCT FROM ARRAY[
          'approval_status','approved_by_app_user_id','approved_at']::text[]
         OR p_metadata<>'{{}}'::jsonb OR run.status<>'draft'
         OR run.approval_status<>'approved'
         OR run.approved_by_app_user_id<>public.workloop_app_user_id()
         OR run.run_by_app_user_id=public.workloop_app_user_id()
         OR run.submitted_by_app_user_id=public.workloop_app_user_id() THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSIF p_action='payroll_rejected' THEN
      IF p_changed_fields IS DISTINCT FROM ARRAY[
          'approval_status','rejection_reason','rejected_by_app_user_id','rejected_at']::text[]
         OR p_metadata<>'{{}}'::jsonb OR run.status<>'draft'
         OR run.approval_status<>'draft'
         OR run.rejected_by_app_user_id<>public.workloop_app_user_id()
         OR pg_catalog.btrim(run.rejection_reason)=''
         OR run.rejection_reason<>p_reason THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSIF p_action='payroll_generated' THEN
      IF p_changed_fields IS DISTINCT FROM ARRAY[
          'status','total_disbursed','employee_count']::text[]
         OR p_metadata<>'{{}}'::jsonb OR run.status<>'generated'
         OR run.approval_status<>'approved' THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSIF p_action='payslips_issued' THEN
      IF p_changed_fields IS DISTINCT FROM ARRAY[
          'status','total_disbursed','employee_count']::text[]
         OR run.status<>'generated' OR run.approval_status<>'approved'
         OR (SELECT pg_catalog.count(*) FROM pg_catalog.jsonb_object_keys(p_metadata))<>2
         OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'payslip_count','integer')
         OR (p_metadata->>'payslip_count')::integer<>run.employee_count
         OR COALESCE(p_metadata->>'snapshot_digest','')!~'^[0-9a-f]{{64}}$'
         OR (SELECT pg_catalog.count(*) FROM public.payslips AS slip
             WHERE slip.payroll_run_id=run.id)<>run.employee_count THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
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
    _immutable_rows()
    _lock_function()
    _transition_function()
    _finalize_function()
    _wrap_audit()


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM public.audit_events WHERE action IN (
    'payroll_submitted','payroll_recalled','payroll_approved','payroll_rejected',
    'payroll_generated','expense_paid','payslips_issued')) THEN
    RAISE EXCEPTION 'cannot downgrade Phase 9F while approval or generation evidence exists';
  END IF;
END
$block$
"""
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase9f_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.execute(f"DROP FUNCTION {FINALIZE_SIGNATURE}")
    op.execute(f"DROP FUNCTION {TRANSITION_SIGNATURE}")
    op.execute(f"DROP FUNCTION IF EXISTS {LOCK_SIGNATURE}")
    op.execute("DROP TRIGGER trg_payroll_approval_log_immutable ON public.payroll_approval_log")
    op.execute("DROP TRIGGER trg_payslips_immutable ON public.payslips")
    op.execute("DROP FUNCTION public.reject_immutable_payroll_evidence_mutation()")
    op.execute("DROP POLICY phase5f_payslips_select_runtime ON public.payslips")
    op.execute(
        """
CREATE POLICY phase5f_payslips_select_runtime ON public.payslips
FOR SELECT TO workloop_runtime
USING (
  session_user='workloop_runtime'
  AND public.workloop_actor_kind()='human'
  AND public.workloop_actor_key() IS NULL
  AND public.workloop_business_date() IS NOT NULL
  AND public.workloop_app_user_id() IS NOT NULL
  AND public.workloop_company_id() IS NOT NULL
  AND public.workloop_branch_id() IS NOT NULL
  AND company_id=public.workloop_company_id()
  AND branch_id=public.workloop_branch_id()
  AND (
    public.workloop_role()='admin'
    OR (public.workloop_role() IN ('manager','employee')
        AND employee_id=public.workloop_employee_id())
  )
)
"""
    )
    op.execute("GRANT UPDATE ON public.payroll_runs TO workloop_runtime")
