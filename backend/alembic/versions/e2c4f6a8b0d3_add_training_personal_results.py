"""Add protected training transitions and unverified personal results."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2c4f6a8b0d3"
down_revision: str | Sequence[str] | None = "f1a3c5e7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTEXT = """
session_user='workloop_runtime' AND current_user='workloop_migration'
AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND EXISTS(SELECT 1 FROM public.resolve_workloop_principal() principal
 WHERE principal.app_user_id=public.workloop_app_user_id()
 AND principal.account_status='active'
 AND principal.profile_app_user_id=principal.app_user_id
 AND principal.role=public.workloop_role()
 AND principal.profile_company_id=public.workloop_company_id()
 AND principal.company_id=principal.profile_company_id
 AND ((principal.role='admin' AND principal.profile_employee_id IS NULL
   AND principal.employee_id IS NULL AND principal.branch_id IS NULL
   AND public.workloop_employee_id() IS NULL)
 OR (principal.role IN ('employee','manager')
   AND principal.profile_employee_id=public.workloop_employee_id()
   AND principal.employee_id=principal.profile_employee_id
   AND principal.employee_company_id=principal.profile_company_id
   AND principal.employee_branch_id=public.workloop_branch_id()
   AND principal.employee_active
   AND principal.employment_status IN ('Active','Probation','On Leave')
   AND principal.branch_id=principal.employee_branch_id
   AND principal.branch_company_id=principal.profile_company_id)))
"""


def upgrade() -> None:
    op.add_column(
        "training_records",
        sa.Column("result_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_check_constraint(
        "personal_result_credit",
        "training_records",
        "result_verified OR NOT is_cme",
    )
    op.execute("""
CREATE FUNCTION public.guard_training_personal_authority() RETURNS trigger
LANGUAGE plpgsql SET search_path TO pg_catalog,public,pg_temp AS $function$
BEGIN
  IF current_user='workloop_runtime' AND public.workloop_role() IN ('employee','manager')
    AND OLD.employee_id=public.workloop_employee_id() AND (
      NEW.employee_id IS DISTINCT FROM OLD.employee_id
      OR NEW.company_id IS DISTINCT FROM OLD.company_id
      OR NEW.branch_id IS DISTINCT FROM OLD.branch_id
      OR NEW.status IS DISTINCT FROM OLD.status
      OR NEW.passed IS DISTINCT FROM OLD.passed
      OR NEW.score IS DISTINCT FROM OLD.score
      OR NEW.is_cme IS DISTINCT FROM OLD.is_cme
      OR NEW.cost IS DISTINCT FROM OLD.cost
      OR NEW.result_verified IS DISTINCT FROM OLD.result_verified
      OR (OLD.status<>'planned' AND (
        NEW.end_date IS DISTINCT FROM OLD.end_date
        OR NEW.duration_hours IS DISTINCT FROM OLD.duration_hours))) THEN
    RAISE EXCEPTION 'training authority denied' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END $function$;
CREATE TRIGGER trg_training_personal_authority BEFORE UPDATE ON public.training_records
FOR EACH ROW EXECUTE FUNCTION public.guard_training_personal_authority();
REVOKE ALL ON FUNCTION public.guard_training_personal_authority() FROM PUBLIC;
""")
    op.execute(f"""
CREATE FUNCTION public.transition_training_record(
 p_id uuid,p_expected timestamptz,p_command text,p_end date DEFAULT NULL,
 p_hours numeric DEFAULT NULL,p_score text DEFAULT '',p_passed boolean DEFAULT NULL
) RETURNS text LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
DECLARE target public.employees%ROWTYPE; source public.training_records%ROWTYPE;
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role() NOT IN ('admin','manager','employee')
    OR p_command NOT IN ('start','cancel','self_complete') OR p_command IS NULL
    OR p_expected IS NULL THEN RETURN 'operation_not_permitted'; END IF;
  SELECT * INTO source FROM public.training_records record WHERE record.id=p_id
    AND record.company_id=public.workloop_company_id()
    AND record.branch_id=public.workloop_branch_id()
    AND (public.workloop_role()='admin'
      OR record.employee_id=public.workloop_employee_id()
      OR (public.workloop_role()='manager' AND EXISTS(
        SELECT 1 FROM public.employees employee WHERE employee.id=record.employee_id
          AND employee.reporting_manager_id=public.workloop_employee_id())))
    FOR UPDATE;
  IF NOT FOUND THEN RETURN 'resource_not_found'; END IF;
  SELECT employee.* INTO target FROM public.employees employee
  JOIN public.training_records record ON record.employee_id=employee.id
    AND record.company_id=employee.company_id AND record.branch_id=employee.branch_id
  WHERE record.id=p_id AND record.company_id=public.workloop_company_id()
    AND record.branch_id=public.workloop_branch_id()
    AND (public.workloop_role()='admin'
      OR record.employee_id=public.workloop_employee_id()
      OR (public.workloop_role()='manager'
        AND employee.reporting_manager_id=public.workloop_employee_id()))
  FOR UPDATE OF employee;
  IF NOT FOUND OR NOT target.active
    OR target.employment_status NOT IN ('Active','Probation','On Leave')
    THEN RETURN 'resource_not_found'; END IF;
  IF p_command='self_complete' AND (
    public.workloop_role() NOT IN ('manager','employee')
    OR target.id<>public.workloop_employee_id()) THEN RETURN 'operation_not_permitted'; END IF;
  IF source.updated_at<>p_expected
    OR source.status NOT IN ('planned','in_progress')
    OR (p_command='start' AND source.status<>'planned') THEN RETURN 'state_conflict'; END IF;
  IF p_command='self_complete' THEN
    IF p_end IS NULL OR p_end>public.workloop_business_date()
      OR (source.start_date IS NOT NULL AND p_end<source.start_date)
      OR p_hours IS NULL OR p_hours<0 OR p_hours>9999.99 OR p_hours<>round(p_hours,2)
      OR p_score IS NULL OR octet_length(p_score)>120 OR p_passed IS NULL
      THEN RETURN 'validation_failed'; END IF;
    UPDATE public.training_records SET status='completed',end_date=p_end,
      duration_hours=p_hours,score=btrim(p_score),passed=p_passed,
      result_verified=false,is_cme=false WHERE id=p_id;
  ELSE
    UPDATE public.training_records SET status=CASE WHEN p_command='start'
      THEN 'in_progress' ELSE 'cancelled' END WHERE id=p_id;
  END IF;
  PERFORM public.append_audit_event(
    CASE WHEN p_command='self_complete' THEN 'training_completed' ELSE 'training_updated' END,
    'training_record',p_id,
    CASE WHEN p_command='self_complete'
      THEN ARRAY['status','end_date','duration_hours','score','passed','result_verified','is_cme']
      ELSE ARRAY['status'] END,
    CASE WHEN p_command='self_complete' THEN 'Personal training result awaiting verification'
      WHEN p_command='start' THEN 'Training started' ELSE 'Training cancelled' END,
    jsonb_build_object('transition',source.status||'_to_'||
      CASE WHEN p_command='self_complete' THEN 'self_completed'
        WHEN p_command='start' THEN 'in_progress' ELSE 'cancelled' END));
  RETURN 'ok';
END $function$;
ALTER FUNCTION public.transition_training_record(uuid,timestamptz,text,date,numeric,text,boolean)
OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.transition_training_record(
uuid,timestamptz,text,date,numeric,text,boolean)
FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.transition_training_record(
uuid,timestamptz,text,date,numeric,text,boolean)
TO workloop_runtime;
""")

    op.execute(
        "ALTER FUNCTION public.append_phase12_output_audit("
        "text,text,uuid,text,text,text,text,integer,bigint,text) "
        "RENAME TO _append_phase12_output_audit_restoration_e_prior"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public._append_phase12_output_audit_restoration_e_prior("
        "text,text,uuid,text,text,text,text,integer,bigint,text) FROM PUBLIC,workloop_runtime"
    )
    op.execute(MANAGER_SELF_OUTPUT_AUDIT)
    op.execute(
        "ALTER FUNCTION public.append_phase12_output_audit("
        "text,text,uuid,text,text,text,text,integer,bigint,text) OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.append_phase12_output_audit("
        "text,text,uuid,text,text,text,text,integer,bigint,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.append_phase12_output_audit("
        "text,text,uuid,text,text,text,text,integer,bigint,text) TO workloop_runtime"
    )
    op.execute(MANAGER_PAYSLIP_POLICY)


def downgrade() -> None:
    op.execute("""
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM public.training_records WHERE NOT result_verified) THEN
    RAISE EXCEPTION 'personal_training_results_require_preservation';
  END IF;
END $$;
DROP FUNCTION public.transition_training_record(uuid,timestamptz,text,date,numeric,text,boolean);
DROP TRIGGER trg_training_personal_authority ON public.training_records;
DROP FUNCTION public.guard_training_personal_authority();
""")
    op.drop_constraint("personal_result_credit", "training_records", type_="check")
    op.drop_column("training_records", "result_verified")
    op.execute("DROP POLICY restoration_e_manager_payslips ON public.payslips")
    op.execute(
        "DROP FUNCTION public.append_phase12_output_audit("
        "text,text,uuid,text,text,text,text,integer,bigint,text)"
    )
    op.execute(
        "ALTER FUNCTION public._append_phase12_output_audit_restoration_e_prior("
        "text,text,uuid,text,text,text,text,integer,bigint,text) "
        "RENAME TO append_phase12_output_audit"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.append_phase12_output_audit("
        "text,text,uuid,text,text,text,text,integer,bigint,text) TO workloop_runtime"
    )


MANAGER_SELF_OUTPUT_AUDIT = r"""
CREATE OR REPLACE FUNCTION public.append_phase12_output_audit(
  p_action text,
  p_entity_type text,
  p_entity_id uuid,
  p_format text,
  p_filter_digest text,
  p_source_digest text,
  p_renderer_version text,
  p_row_count integer,
  p_byte_count bigint,
  p_result text
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $function$
DECLARE
  event_id uuid;
  event_company uuid := public.workloop_company_id();
  event_branch uuid := public.workloop_branch_id();
  event_actor uuid := public.workloop_app_user_id();
  actor_role text;
  actor_employee uuid;
BEGIN
  IF session_user <> 'workloop_runtime'
    OR current_user <> 'workloop_migration'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR public.workloop_role() NOT IN ('admin','employee','manager')
    OR event_actor IS NULL
    OR event_company IS NULL
    OR event_branch IS NULL
    OR (public.workloop_role()='manager'
      AND p_action NOT IN ('payslip_pdf_exported','letter_pdf_exported'))
    OR p_entity_id IS NULL
    OR p_result NOT IN ('succeeded','denied_before_stream')
    OR p_filter_digest !~ '^sha256:[0-9a-f]{64}$'
    OR p_source_digest !~ '^sha256:[0-9a-f]{64}$'
    OR p_renderer_version !~ '^[A-Za-z0-9._-]{1,64}$'
    OR p_row_count < 0
    OR p_byte_count <= 0
  THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;

  SELECT caller.role,caller.employee_id INTO actor_role,actor_employee
  FROM public.resolve_workloop_principal() AS caller
  WHERE caller.app_user_id = event_actor
    AND caller.account_status = 'active'
    AND caller.profile_company_id = event_company
    AND caller.role IN ('admin','employee','manager')
    AND ((caller.role = 'admin' AND caller.profile_employee_id IS NULL
          AND caller.employee_id IS NULL AND caller.branch_id IS NULL
          AND public.workloop_employee_id() IS NULL)
      OR (caller.role IN ('employee','manager') AND caller.profile_employee_id IS NOT NULL
          AND caller.employee_id = caller.profile_employee_id
          AND caller.employee_id = public.workloop_employee_id()
          AND caller.branch_id = event_branch));

  IF actor_role IS NULL THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;


  IF NOT EXISTS (
    SELECT 1 FROM public.branches selected_branch
    WHERE selected_branch.id = event_branch
      AND selected_branch.company_id = event_company
  ) THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;

  IF NOT (
    (actor_role = 'admin' AND p_action = 'report_csv_exported'
      AND p_entity_type = 'report' AND p_format = 'csv' AND p_entity_id = event_branch)
    OR (actor_role = 'admin' AND p_action = 'attendance_csv_exported'
      AND p_entity_type = 'attendance_period' AND p_format = 'csv' AND EXISTS (
        SELECT 1 FROM public.attendance_periods source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch))
    OR (actor_role = 'admin' AND p_action = 'roster_csv_exported'
      AND p_entity_type = 'roster_month' AND p_format = 'csv' AND p_entity_id = event_branch)
    OR (actor_role = 'admin' AND p_action = 'leave_balance_csv_exported'
      AND p_entity_type = 'leave_balance_year' AND p_format = 'csv'
      AND p_entity_id = event_branch)
    OR (actor_role = 'admin' AND p_action = 'employee_csv_exported'
      AND p_entity_type = 'employee_export' AND p_format = 'csv'
      AND p_entity_id = event_branch)
    OR (actor_role = 'admin' AND p_action = 'nafis_csv_exported'
      AND p_entity_type = 'nafis_report' AND p_format = 'csv' AND EXISTS (
        SELECT 1 FROM public.nafis_reports source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch))
    OR (actor_role = 'admin' AND p_action = 'sif_previewed'
      AND p_entity_type = 'payroll_run' AND p_format = 'sif_preview' AND EXISTS (
        SELECT 1 FROM public.payroll_runs source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch
          AND source.status = 'generated' AND source.approval_status = 'approved'))
    OR (actor_role = 'admin' AND p_action = 'sif_exported'
      AND p_entity_type = 'payroll_run' AND p_format = 'sif' AND EXISTS (
        SELECT 1 FROM public.payroll_runs source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch
          AND source.status = 'generated' AND source.approval_status = 'approved'))

    OR (actor_role = 'admin' AND p_action = 'report_pdf_exported'
      AND p_entity_type = 'report' AND p_format = 'pdf' AND p_entity_id = event_branch)
    OR (p_action = 'payslip_pdf_exported' AND p_entity_type = 'payslip'
      AND p_format = 'pdf' AND EXISTS (
        SELECT 1 FROM public.payslips source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch
          AND (actor_role = 'admin' OR source.employee_id = actor_employee)))
    OR (actor_role = 'admin' AND p_action = 'payslip_zip_exported'
      AND p_entity_type = 'payroll_run' AND p_format = 'zip' AND EXISTS (
        SELECT 1 FROM public.payroll_runs source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch
          AND source.status = 'generated' AND source.approval_status = 'approved'))
    OR (p_action = 'letter_pdf_exported' AND p_entity_type = 'letter_request'
      AND p_format = 'pdf' AND EXISTS (
        SELECT 1 FROM public.letter_requests source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch AND source.status = 'completed'
          AND source.request_kind = 'letter'
          AND (actor_role = 'admin' OR source.employee_id = actor_employee)))
    OR (actor_role = 'admin' AND p_action = 'offboarding_letter_pdf_exported'
      AND p_entity_type = 'offboarding_checklist' AND p_format = 'pdf' AND EXISTS (
        SELECT 1 FROM public.offboarding_checklists source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch AND source.status = 'completed'
          AND source.final_settlement_id IS NOT NULL))
    OR (actor_role = 'admin' AND p_action = 'final_settlement_pdf_exported'
      AND p_entity_type = 'final_settlement' AND p_format = 'pdf' AND EXISTS (
        SELECT 1 FROM public.final_settlements source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch))

  ) THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;

  INSERT INTO public.audit_events(
    company_id, branch_id, actor_kind, actor_app_user_id, system_actor_key,
    initiated_by_app_user_id, action, entity_type, entity_id, changed_fields,
    reason, metadata
  ) VALUES (
    event_company, event_branch, 'human', event_actor, NULL,
    event_actor, p_action, p_entity_type, p_entity_id, ARRAY['output']::text[],
    'Phase 12 output delivery',
    pg_catalog.jsonb_build_object(
      'format', p_format,
      'filterDigest', p_filter_digest,
      'sourceDigest', p_source_digest,
      'rendererVersion', p_renderer_version,
      'rowCount', p_row_count,
      'byteCount', p_byte_count,
      'result', p_result
    )
  ) RETURNING id INTO event_id;

  RETURN event_id;
END
$function$
"""

MANAGER_PAYSLIP_POLICY = r"""
CREATE POLICY restoration_e_manager_payslips ON public.payslips
FOR SELECT TO workloop_runtime USING (

  current_user = 'workloop_runtime'
  AND session_user = 'workloop_runtime'
  AND public.workloop_actor_kind() = 'human'
  AND public.workloop_actor_key() IS NULL
  AND public.workloop_business_date() IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM public.resolve_workloop_principal() AS principal
    WHERE principal.app_user_id = public.workloop_app_user_id()
      AND principal.account_status = 'active'
      AND principal.profile_app_user_id = principal.app_user_id
      AND principal.role = public.workloop_role()
      AND principal.profile_company_id = public.workloop_company_id()
      AND principal.company_id = principal.profile_company_id
      AND (
        (principal.role = 'admin'
          AND principal.profile_employee_id IS NULL
          AND principal.employee_id IS NULL
          AND principal.branch_id IS NULL
          AND public.workloop_employee_id() IS NULL)
        OR
        (principal.role IN ('manager','employee')
          AND principal.profile_employee_id = public.workloop_employee_id()
          AND principal.employee_id = principal.profile_employee_id
          AND principal.employee_company_id = principal.profile_company_id
          AND principal.employee_branch_id = public.workloop_branch_id()
          AND principal.employee_active
          AND principal.employment_status IN ('Active','Probation','On Leave')
          AND principal.branch_id = principal.employee_branch_id
          AND principal.branch_company_id = principal.profile_company_id)
      )
  )
 AND public.workloop_role()='manager'
 AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
 AND employee_id=public.workloop_employee_id());
"""
