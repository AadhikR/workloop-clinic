"""Add Phase 9C salary advance authority and protected audit actions.

Revision ID: a1c3e5f7b9d2
Revises: f9b2c4d6e8a1
Created: 2026-09-16 20:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1c3e5f7b9d2"
down_revision: str | Sequence[str] | None = "f9b2c4d6e8a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
AUDIT_PRIOR_SIGNATURE = "public._append_audit_event_phase9c_prior(text,text,uuid,text[],text,jsonb)"
REPAYMENT_SIGNATURE = "public.record_advance_repayment(uuid,uuid,uuid,numeric,date)"
REPAYMENT_PRIOR_SIGNATURE = (
    "public._record_advance_repayment_phase9c_prior(uuid,uuid,uuid,numeric,date)"
)

HUMAN_CONTEXT = """
session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
""".strip()


def _allow_advance_replay() -> None:
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


def _lock_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.lock_salary_advance(p_advance_id uuid)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE advance public.salary_advances%ROWTYPE;
BEGIN
  IF NOT ({HUMAN_CONTEXT}) THEN RETURN false; END IF;
  SELECT item.* INTO advance FROM public.salary_advances AS item
  WHERE item.id=p_advance_id
    AND item.company_id=public.workloop_company_id()
    AND item.branch_id=public.workloop_branch_id()
  FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  IF public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL THEN
    RETURN EXISTS (
      SELECT 1 FROM public.resolve_workloop_principal() AS principal
      WHERE principal.app_user_id=public.workloop_app_user_id()
        AND principal.account_status='active' AND principal.role='admin'
        AND principal.profile_company_id=advance.company_id
        AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL);
  END IF;
  RETURN public.workloop_role() IN ('manager','employee')
    AND public.workloop_employee_id()=advance.employee_id
    AND EXISTS (
      SELECT 1 FROM public.resolve_workloop_principal() AS principal
      WHERE principal.app_user_id=public.workloop_app_user_id()
        AND principal.account_status='active'
        AND principal.role IN ('manager','employee')
        AND principal.profile_company_id=advance.company_id
        AND principal.employee_id=advance.employee_id
        AND principal.employee_branch_id=advance.branch_id
        AND principal.employee_active
        AND principal.employment_status IN ('Active','Probation','On Leave'));
END
$function$
"""
    )
    op.execute("ALTER FUNCTION public.lock_salary_advance(uuid) OWNER TO workloop_migration")
    op.execute("REVOKE ALL ON FUNCTION public.lock_salary_advance(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.lock_salary_advance(uuid) TO workloop_runtime")


def _replace_repayment_function() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {REPAYMENT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
        "RENAME TO _record_advance_repayment_phase9c_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {REPAYMENT_PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {REPAYMENT_PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(
        """
CREATE FUNCTION public.record_advance_repayment(
  p_advance_id uuid,
  p_payroll_run_id uuid,
  p_idempotency_key uuid,
  p_amount numeric,
  p_paid_date date DEFAULT CURRENT_DATE)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  v_advance    public.salary_advances%ROWTYPE;
  v_existing   public.advance_repayments%ROWTYPE;
  v_run_co     uuid;
  v_run_br     uuid;
  v_amount     numeric;
  v_paid_date  date;
  v_new_bal    numeric;
  v_new_status text;
  v_repay_id   uuid;
BEGIN
  IF session_user <> 'workloop_runtime'
     OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
     OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL
     OR public.workloop_role() IS DISTINCT FROM 'admin'
     OR public.workloop_company_id() IS NULL
     OR public.workloop_branch_id() IS NULL
     OR public.workloop_employee_id() IS NOT NULL
     OR NOT EXISTS (
       SELECT 1 FROM public.resolve_workloop_principal() AS principal
       WHERE principal.app_user_id=public.workloop_app_user_id()
         AND principal.account_status='active'
         AND principal.profile_app_user_id=principal.app_user_id
         AND principal.role='admin'
         AND principal.profile_company_id=public.workloop_company_id()
         AND principal.company_id=principal.profile_company_id
         AND principal.profile_employee_id IS NULL
         AND principal.employee_id IS NULL AND principal.branch_id IS NULL)
     OR NOT EXISTS (
       SELECT 1 FROM public.branches AS branch
       WHERE branch.id=public.workloop_branch_id()
         AND branch.company_id=public.workloop_company_id()) THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
  IF p_advance_id IS NULL OR p_idempotency_key IS NULL THEN
    RAISE EXCEPTION 'advance_repayment_missing_key';
  END IF;
  v_paid_date := p_paid_date;
  IF v_paid_date IS NULL THEN RAISE EXCEPTION 'advance_repayment_missing_paid_date'; END IF;
  IF v_paid_date <> public.workloop_business_date() THEN
    RAISE EXCEPTION 'advance_repayment_untrusted_paid_date';
  END IF;
  v_amount := p_amount;
  IF v_amount IS NULL OR v_amount='NaN'::numeric
     OR v_amount='Infinity'::numeric OR v_amount='-Infinity'::numeric THEN
    RAISE EXCEPTION 'advance_repayment_amount_not_finite';
  END IF;
  IF pg_catalog.scale(v_amount)>2 THEN RAISE EXCEPTION 'advance_repayment_amount_scale'; END IF;
  IF v_amount<=0 OR v_amount>9999999999.99 THEN
    RAISE EXCEPTION 'advance_repayment_amount_range';
  END IF;

  SELECT * INTO v_advance FROM public.salary_advances
  WHERE id=p_advance_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'advance_repayment_advance_not_found'; END IF;
  IF v_advance.company_id<>public.workloop_company_id()
     OR v_advance.branch_id<>public.workloop_branch_id() THEN
    RAISE EXCEPTION 'advance_repayment_out_of_scope';
  END IF;
  SELECT * INTO v_existing FROM public.advance_repayments
  WHERE advance_id=p_advance_id AND idempotency_key=p_idempotency_key;
  IF FOUND THEN
    IF v_existing.payroll_run_id IS NOT DISTINCT FROM p_payroll_run_id
       AND v_existing.amount=v_amount AND v_existing.paid_date=v_paid_date
       AND v_existing.company_id=v_advance.company_id
       AND v_existing.branch_id=v_advance.branch_id THEN
      RETURN pg_catalog.jsonb_build_object(
        'repaymentId',v_existing.id,'newBalance',v_advance.outstanding_balance,
        'newStatus',v_advance.status,'alreadyRecorded',true);
    END IF;
    RAISE EXCEPTION 'advance_repayment_idempotency_conflict';
  END IF;
  IF p_payroll_run_id IS NOT NULL THEN
    SELECT * INTO v_existing FROM public.advance_repayments
    WHERE advance_id=p_advance_id AND payroll_run_id=p_payroll_run_id;
    IF FOUND THEN RAISE EXCEPTION 'advance_repayment_payroll_conflict'; END IF;
  END IF;
  IF v_advance.status<>'active' OR v_advance.outstanding_balance<=0 THEN
    RAISE EXCEPTION 'advance_repayment_not_active';
  END IF;
  IF p_payroll_run_id IS NOT NULL THEN
    SELECT company_id,branch_id INTO v_run_co,v_run_br
    FROM public.payroll_runs WHERE id=p_payroll_run_id FOR SHARE;
    IF NOT FOUND OR v_run_co<>v_advance.company_id OR v_run_br<>v_advance.branch_id THEN
      RAISE EXCEPTION 'advance_repayment_payroll_scope';
    END IF;
  END IF;
  IF v_amount>v_advance.outstanding_balance THEN
    RAISE EXCEPTION 'advance_repayment_exceeds_outstanding';
  END IF;
  INSERT INTO public.advance_repayments(
    company_id,branch_id,advance_id,payroll_run_id,idempotency_key,amount,paid_date)
  VALUES(v_advance.company_id,v_advance.branch_id,p_advance_id,p_payroll_run_id,
         p_idempotency_key,v_amount,v_paid_date)
  RETURNING id INTO v_repay_id;
  UPDATE public.salary_advances
  SET outstanding_balance=outstanding_balance-v_amount,
      status=CASE WHEN outstanding_balance-v_amount=0 THEN 'settled' ELSE 'active' END,
      updated_at=statement_timestamp()
  WHERE id=p_advance_id
  RETURNING outstanding_balance,status INTO v_new_bal,v_new_status;
  RETURN pg_catalog.jsonb_build_object(
    'repaymentId',v_repay_id,'newBalance',v_new_bal,
    'newStatus',v_new_status,'alreadyRecorded',false);
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {REPAYMENT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {REPAYMENT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {REPAYMENT_SIGNATURE} TO workloop_runtime")


def _wrap_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase9c_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(
        f"""
CREATE FUNCTION public.append_audit_event(
  p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],
  p_reason text,p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE event_id uuid; advance public.salary_advances%ROWTYPE; repayment_id uuid;
BEGIN
  IF p_action NOT LIKE 'salary_advance_%' THEN
    RETURN public._append_audit_event_phase9c_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF NOT ({HUMAN_CONTEXT}) OR p_entity_type<>'salary_advance'
    OR jsonb_typeof(p_metadata) IS DISTINCT FROM 'object'
    OR coalesce(btrim(p_reason),'')='' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  SELECT item.* INTO advance FROM public.salary_advances AS item
  WHERE item.id=p_entity_id AND item.company_id=public.workloop_company_id()
    AND item.branch_id=public.workloop_branch_id();
  IF NOT FOUND THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501'; END IF;

  IF p_action='salary_advance_requested' THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY[
      'amount','reason','repayment_months','repayment_start_month','monthly_deduction',
      'outstanding_balance','status']::text[]
      OR p_metadata<>'{{}}'::jsonb OR advance.status<>'pending'
      OR advance.outstanding_balance<>advance.amount
      OR advance.monthly_deduction<>round(advance.amount/advance.repayment_months,2)
      OR NOT (public.workloop_role()='admin'
        OR advance.employee_id=public.workloop_employee_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='salary_advance_schedule_changed' THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY[
      'amount','repayment_months','repayment_start_month','monthly_deduction',
      'outstanding_balance']::text[]
      OR p_metadata<>'{{}}'::jsonb OR public.workloop_role()<>'admin'
      OR advance.status<>'pending' OR advance.outstanding_balance<>advance.amount
      OR advance.monthly_deduction<>round(advance.amount/advance.repayment_months,2) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='salary_advance_withdrawn' THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY['status','rejection_reason']::text[]
      OR p_metadata<>'{{}}'::jsonb OR advance.status<>'cancelled'
      OR advance.rejection_reason<>'Withdrawn by employee'
      OR advance.employee_id<>public.workloop_employee_id() THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='salary_advance_approved' THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY[
      'status','disbursed_date','monthly_deduction','outstanding_balance']::text[]
      OR p_metadata<>'{{}}'::jsonb OR public.workloop_role()<>'admin'
      OR advance.status<>'active' OR advance.disbursed_date IS NULL
      OR advance.outstanding_balance<>advance.amount THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='salary_advance_rejected' THEN
    IF p_changed_fields IS DISTINCT FROM ARRAY['status','rejection_reason']::text[]
      OR p_metadata<>'{{}}'::jsonb OR public.workloop_role()<>'admin'
      OR advance.status<>'cancelled' OR coalesce(btrim(advance.rejection_reason),'')='' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action IN ('salary_advance_repayment_recorded','salary_advance_settled') THEN
    IF NOT (
        (p_action='salary_advance_settled' AND p_changed_fields=
          ARRAY['status','outstanding_balance']::text[])
        OR (p_action='salary_advance_repayment_recorded' AND p_changed_fields=
          ARRAY['outstanding_balance','status']::text[]))
      OR public.workloop_role()<>'admin'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>3
      OR p_metadata->>'repayment_kind' NOT IN ('manual','payroll','settlement')
      OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'repayment_id','uuid') THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
    repayment_id := (p_metadata->>'repayment_id')::uuid;
    IF NOT EXISTS (
      SELECT 1 FROM public.advance_repayments AS repayment
      WHERE repayment.id=repayment_id AND repayment.advance_id=advance.id
        AND repayment.company_id=advance.company_id AND repayment.branch_id=advance.branch_id
        AND repayment.payroll_run_id IS NOT DISTINCT FROM
          CASE WHEN p_metadata->>'payroll_run_id' IS NULL THEN NULL
               WHEN pg_catalog.pg_input_is_valid(p_metadata->>'payroll_run_id','uuid')
                 THEN (p_metadata->>'payroll_run_id')::uuid ELSE NULL END)
      OR ((p_metadata->>'repayment_kind')='payroll')
        IS DISTINCT FROM ((p_metadata->>'payroll_run_id') IS NOT NULL)
      OR (p_action='salary_advance_settled'
        AND (advance.status<>'settled' OR advance.outstanding_balance<>0))
      OR (p_action='salary_advance_repayment_recorded'
        AND advance.status NOT IN ('active','settled')) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
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


def upgrade() -> None:
    _allow_advance_replay()
    _lock_function()
    _replace_repayment_function()
    _wrap_audit()


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
  IF EXISTS (
    SELECT 1 FROM public.audit_events WHERE action LIKE 'salary_advance_%'
  ) OR EXISTS (
    SELECT 1 FROM public.idempotency_records WHERE replay_resource_kind='salary_advance'
  ) THEN
    RAISE EXCEPTION 'cannot downgrade Phase 9C while advance audit or replay rows exist';
  END IF;
END
$block$
"""
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase9c_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {REPAYMENT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {REPAYMENT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._record_advance_repayment_phase9c_prior"
        "(uuid,uuid,uuid,numeric,date) RENAME TO record_advance_repayment"
    )
    op.execute(f"ALTER FUNCTION {REPAYMENT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {REPAYMENT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {REPAYMENT_SIGNATURE} TO workloop_runtime")
    op.execute("DROP FUNCTION public.lock_salary_advance(uuid)")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        "(replay_resource_kind IN "
        "('branch','employee','department','user_profile','leave_request','expense_claim') "
        "AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
