"""Add retained portal removal, administrator ratings, and scoped history readers."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a5c7e9b1d4"
down_revision: str | Sequence[str] | None = "e2c4f6a8b0d3"
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

FUNCTIONS = (
    "public.set_portal_record_archival(text,uuid,timestamptz,boolean)",
    "public.set_admin_appraisal_section_rating(uuid,uuid,timestamptz,numeric,text)",
    "public.cancel_pending_advance(uuid,timestamptz)",
    "public.read_recent_manager_leave_actions(uuid,integer)",
    "public.read_own_advance_progress(uuid,uuid,integer)",
    "public.set_manager_appraisal_section_rating(uuid,uuid,timestamptz,numeric,text)",
    "public.submit_manager_appraisal_review(uuid,timestamptz,jsonb)",
)


CONTRACT_OUTPUT_AUDIT = """
    OR (actor_role = 'admin' AND p_action = 'employment_contract_pdf_exported'
      AND p_entity_type = 'employee' AND p_format = 'pdf' AND EXISTS (
        SELECT 1 FROM public.employees source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch))
"""


def _contract_output_audit(add: bool) -> None:
    anchor = "    OR (actor_role = 'admin' AND p_action = 'offboarding_letter_pdf_exported'"
    source = anchor if add else CONTRACT_OUTPUT_AUDIT + anchor
    target = CONTRACT_OUTPUT_AUDIT + anchor if add else anchor
    op.execute(f"""
DO $patch$ DECLARE definition text; BEGIN
  SELECT pg_get_functiondef('public.append_phase12_output_audit('
    'text,text,uuid,text,text,text,text,integer,bigint,text)'::regprocedure) INTO definition;
  IF position($source${source}$source$ IN definition)=0 THEN
    RAISE EXCEPTION 'unexpected_contract_output_audit'; END IF;
  EXECUTE replace(definition,$source${source}$source$,$target${target}$target$);
END $patch$;
""")


def upgrade() -> None:
    _contract_output_audit(True)
    op.execute("""
DO $$ DECLARE definition text; BEGIN
  SELECT pg_get_functiondef(
    'public.transition_training_record(uuid,timestamptz,text,date,numeric,text,boolean)'::regprocedure)
    INTO definition;
  IF position('source.updated_at<>p_expected' IN definition)=0 THEN
    RAISE EXCEPTION 'unexpected_training_version_contract'; END IF;
  EXECUTE replace(definition,'source.updated_at<>p_expected',
    'date_trunc(''milliseconds'',source.updated_at)<>date_trunc(''milliseconds'',p_expected)');
END $$;
""")
    for table in ("appraisals", "incident_reports", "expense_claims"):
        op.add_column(table, sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("""
CREATE FUNCTION public.guard_portal_archival() RETURNS trigger
LANGUAGE plpgsql SET search_path TO pg_catalog,public,pg_temp AS $function$
BEGIN
  IF current_user<>'workloop_migration' AND (
    (TG_OP='INSERT' AND NEW.archived_at IS NOT NULL)
    OR (TG_OP='UPDATE' AND (OLD.archived_at IS NOT NULL
      OR NEW.archived_at IS DISTINCT FROM OLD.archived_at))
    OR (TG_OP='DELETE' AND OLD.archived_at IS NOT NULL)) THEN
    RAISE EXCEPTION 'retained record denied' USING ERRCODE='42501';
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $function$;
REVOKE ALL ON FUNCTION public.guard_portal_archival() FROM PUBLIC,workloop_runtime;
""")
    for table in ("appraisals", "incident_reports", "expense_claims"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_portal_archival BEFORE INSERT OR UPDATE OR DELETE "
            f"ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.guard_portal_archival()"
        )
    op.execute(f"""
CREATE FUNCTION public.set_portal_record_archival(
 p_kind text,p_id uuid,p_expected timestamptz,p_archived boolean
) RETURNS text LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
DECLARE source record; target_table text; cycle_status text;
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role()<>'admin' THEN
    RETURN 'operation_not_permitted'; END IF;
  target_table:=CASE p_kind WHEN 'appraisal' THEN 'appraisals'
    WHEN 'incident_report' THEN 'incident_reports' WHEN 'expense_claim' THEN 'expense_claims' END;
  IF target_table IS NULL OR p_archived IS NULL OR p_expected IS NULL THEN
    RETURN 'validation_failed'; END IF;
  EXECUTE format('SELECT * FROM public.%I WHERE id=$1 AND company_id=$2 AND branch_id=$3
    FOR UPDATE',target_table) INTO source
    USING p_id,public.workloop_company_id(),public.workloop_branch_id();
  IF source.id IS NULL THEN RETURN 'resource_not_found'; END IF;
  IF date_trunc('milliseconds',source.updated_at)<>date_trunc('milliseconds',p_expected)
     OR (source.archived_at IS NOT NULL)=p_archived THEN RETURN 'state_conflict'; END IF;
  IF p_kind='appraisal' THEN
    SELECT status INTO cycle_status FROM public.appraisal_cycles
      WHERE id=source.cycle_id AND company_id=source.company_id AND branch_id=source.branch_id
      FOR UPDATE;
    IF source.status<>'pending' OR cycle_status IS DISTINCT FROM 'active' THEN
      RETURN 'state_conflict'; END IF;
  ELSIF p_kind='incident_report' THEN
    IF source.status<>'open' THEN RETURN 'state_conflict'; END IF;
  ELSIF source.status NOT IN ('pending','manager_rejected','rejected')
      OR source.payroll_run_id IS NOT NULL THEN RETURN 'state_conflict';
  END IF;
  EXECUTE format('UPDATE public.%I SET archived_at=$1,updated_at=statement_timestamp()
    WHERE id=$2',target_table) USING
    CASE WHEN p_archived THEN statement_timestamp() ELSE NULL END,p_id;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,action,entity_type,entity_id,
    changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),CASE WHEN p_archived THEN 'portal_record_archived'
    ELSE 'portal_record_restored' END,p_kind,p_id,ARRAY['archived_at','updated_at'],
    CASE WHEN p_archived THEN 'Record removed from active register and retained'
    ELSE 'Retained record restored to active register' END,'{{}}'::jsonb);
  RETURN 'ok';
END $function$;

CREATE FUNCTION public.set_admin_appraisal_section_rating(
 p_id uuid,p_section uuid,p_expected timestamptz,p_rating numeric,p_comments text
) RETURNS text LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
DECLARE source public.appraisals%ROWTYPE; cycle_status text;
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role()<>'admin' THEN
    RETURN 'operation_not_permitted'; END IF;
  SELECT * INTO source FROM public.appraisals WHERE id=p_id
    AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
    FOR UPDATE;
  IF NOT FOUND THEN RETURN 'resource_not_found'; END IF;
  SELECT status INTO cycle_status FROM public.appraisal_cycles WHERE id=source.cycle_id
    AND company_id=source.company_id AND branch_id=source.branch_id FOR UPDATE;
  IF source.status<>'pending' OR source.archived_at IS NOT NULL
    OR cycle_status IS DISTINCT FROM 'active'
    OR date_trunc('milliseconds',source.updated_at)<>date_trunc('milliseconds',p_expected)
    THEN RETURN 'state_conflict'; END IF;
  IF p_rating IS NULL OR p_rating<1 OR p_rating>5 OR p_rating<>round(p_rating,1)
    OR p_comments IS NULL OR octet_length(p_comments)>10000 THEN
    RETURN 'validation_failed'; END IF;
  PERFORM 1 FROM public.appraisal_sections WHERE id=p_section AND appraisal_id=p_id
    AND company_id=source.company_id AND branch_id=source.branch_id FOR UPDATE;
  IF NOT FOUND THEN RETURN 'resource_not_found'; END IF;
  UPDATE public.appraisal_sections SET rating=p_rating,comments=p_comments WHERE id=p_section;
  UPDATE public.appraisals SET updated_at=statement_timestamp() WHERE id=p_id;
  INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
    action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(source.company_id,source.branch_id,'human',public.workloop_app_user_id(),
    'appraisal_section_admin_rated','appraisal',p_id,
    ARRAY['section.rating','section.comments','updated_at'],'Appraisal section rated',
    jsonb_build_object('section_id',p_section));
  RETURN 'ok';
END $function$;

CREATE FUNCTION public.cancel_pending_advance(p_id uuid,p_expected timestamptz)
RETURNS text LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
DECLARE source public.salary_advances%ROWTYPE;
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role()<>'admin' THEN
    RETURN 'operation_not_permitted'; END IF;
  SELECT * INTO source FROM public.salary_advances WHERE id=p_id
    AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
    FOR UPDATE;
  IF NOT FOUND THEN RETURN 'resource_not_found'; END IF;
  IF source.status<>'pending' OR source.disbursed_date IS NOT NULL
    OR date_trunc('milliseconds',source.updated_at)<>date_trunc('milliseconds',p_expected)
    OR EXISTS(SELECT 1 FROM public.advance_repayments WHERE advance_id=p_id)
    THEN RETURN 'state_conflict'; END IF;
  UPDATE public.salary_advances SET status='cancelled',
    rejection_reason='Cancelled by administrator',updated_at=statement_timestamp() WHERE id=p_id;
  INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
    action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(source.company_id,source.branch_id,'human',public.workloop_app_user_id(),
    'salary_advance_admin_cancelled','salary_advance',p_id,ARRAY['status','rejection_reason'],
    'Pending advance cancelled by administrator','{{}}'::jsonb);
  RETURN 'ok';
END $function$;

CREATE FUNCTION public.read_recent_manager_leave_actions(p_cursor uuid,p_limit integer)
RETURNS TABLE(id uuid,request_id uuid,employee_id uuid,employee_name text,leave_type text,
 start_date date,end_date date,action text,reason text,actor_name text,action_at timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role()<>'manager'
    OR p_limit IS NULL OR p_limit<1 OR p_limit>101 THEN RETURN; END IF;
  RETURN QUERY
  SELECT event.id,request.id,request.employee_id,employee.name,kind.name,
    request.start_date,request.end_date,event.action,event.reason,'You'::text,event.created_at
  FROM public.leave_audit_log event
  JOIN public.leave_requests request ON request.id=event.leave_request_id
    AND request.company_id=event.company_id AND request.branch_id=event.branch_id
  JOIN public.employees employee ON employee.id=request.employee_id
    AND employee.company_id=request.company_id AND employee.branch_id=request.branch_id
  JOIN public.leave_types kind ON kind.id=request.leave_type_id
    AND kind.company_id=request.company_id AND kind.branch_id=request.branch_id
  WHERE event.company_id=public.workloop_company_id()
    AND event.branch_id=public.workloop_branch_id()
    AND event.actor_app_user_id=public.workloop_app_user_id()
    AND request.employee_id<>public.workloop_employee_id()
    AND public.leave_decision_visibility(request.employee_id) IS NOT NULL
    AND event.action IN ('approved','rejected','manager_approved','manager_rejected')
    AND event.created_at>=statement_timestamp()-interval '90 days'
    AND (p_cursor IS NULL OR event.id>p_cursor)
  ORDER BY event.id ASC LIMIT p_limit;
END $function$;

CREATE FUNCTION public.read_own_advance_progress(p_id uuid,p_cursor uuid,p_limit integer)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
DECLARE result jsonb;
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role() NOT IN ('manager','employee')
    OR p_limit IS NULL OR p_limit<1 OR p_limit>101 THEN RETURN NULL; END IF;
  WITH source AS (
    SELECT advance.* FROM public.salary_advances advance
    WHERE advance.id=p_id AND advance.company_id=public.workloop_company_id()
      AND advance.branch_id=public.workloop_branch_id()
      AND advance.employee_id=public.workloop_employee_id()
  ), payments AS MATERIALIZED (
    SELECT repayment.id,repayment.amount,repayment.paid_date,
      payroll.period payroll_period,repayment.created_at
    FROM public.advance_repayments repayment JOIN source ON source.id=repayment.advance_id
      AND source.company_id=repayment.company_id AND source.branch_id=repayment.branch_id
    LEFT JOIN public.payroll_runs payroll ON payroll.id=repayment.payroll_run_id
      AND payroll.company_id=repayment.company_id AND payroll.branch_id=repayment.branch_id
  ), visible AS (
    SELECT * FROM payments WHERE p_cursor IS NULL OR id>p_cursor ORDER BY id LIMIT p_limit
  )
  SELECT jsonb_build_object('advance',jsonb_build_object(
    'id',source.id,'amount',source.amount,'repayment_start_month',source.repayment_start_month,
    'repayment_months',source.repayment_months,'status',source.status,
    'outstanding_balance',source.outstanding_balance,'updated_at',source.updated_at),
    'total_paid',COALESCE((SELECT sum(amount) FROM payments),0),
    'business_period',to_char(public.workloop_business_date(),'YYYY-MM'),
    'payments',COALESCE((SELECT jsonb_agg(to_jsonb(visible) ORDER BY id) FROM visible),'[]'::jsonb))
  INTO result FROM source;
  RETURN result;
END $function$;
""")
    op.execute(f"""
CREATE FUNCTION public.set_manager_appraisal_section_rating(
 p_id uuid,p_section uuid,p_expected timestamptz,p_rating numeric,p_comments text
) RETURNS text LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
DECLARE source public.appraisals%ROWTYPE; cycle_status text; manager_id uuid;
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role()<>'manager' THEN
    RETURN 'operation_not_permitted'; END IF;
  SELECT * INTO source FROM public.appraisals WHERE id=p_id
    AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
    FOR UPDATE;
  IF NOT FOUND THEN RETURN 'resource_not_found'; END IF;
  SELECT status INTO cycle_status FROM public.appraisal_cycles WHERE id=source.cycle_id
    AND company_id=source.company_id AND branch_id=source.branch_id FOR UPDATE;
  SELECT reporting_manager_id INTO manager_id FROM public.employees
    WHERE id=source.employee_id AND company_id=source.company_id AND branch_id=source.branch_id
      AND active AND employment_status<>'Terminated' FOR UPDATE;
  IF manager_id IS DISTINCT FROM public.workloop_employee_id()
    OR source.employee_id=public.workloop_employee_id() THEN RETURN 'resource_not_found'; END IF;
  IF source.status<>'pending' OR source.archived_at IS NOT NULL
    OR cycle_status IS DISTINCT FROM 'active' OR p_expected IS NULL
    OR date_trunc('milliseconds',source.updated_at)<>date_trunc('milliseconds',p_expected)
    THEN RETURN 'state_conflict'; END IF;
  IF p_rating IS NULL OR p_rating<1 OR p_rating>5 OR p_rating<>round(p_rating,1)
    OR p_comments IS NULL OR octet_length(p_comments)>10000 THEN
    RETURN 'validation_failed'; END IF;
  PERFORM 1 FROM public.appraisal_sections WHERE id=p_section AND appraisal_id=p_id
    AND company_id=source.company_id AND branch_id=source.branch_id FOR UPDATE;
  IF NOT FOUND THEN RETURN 'resource_not_found'; END IF;
  UPDATE public.appraisal_sections SET rating=p_rating,comments=p_comments WHERE id=p_section;
  UPDATE public.appraisals SET updated_at=statement_timestamp() WHERE id=p_id;
  PERFORM public.append_audit_event('appraisal_section_rated','appraisal',p_id,
    ARRAY['section.rating','section.comments','updated_at'],'Appraisal section rated',
    jsonb_build_object('section_id',p_section));
  RETURN 'ok';
END $function$;

CREATE FUNCTION public.submit_manager_appraisal_review(
 p_id uuid,p_expected timestamptz,p_sections jsonb
) RETURNS text LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp AS $function$
DECLARE source public.appraisals%ROWTYPE; section jsonb; result text; rating numeric;
BEGIN
  IF NOT ({CONTEXT}) OR public.workloop_role()<>'manager' THEN
    RETURN 'operation_not_permitted'; END IF;
  IF jsonb_typeof(p_sections) IS DISTINCT FROM 'array' OR jsonb_array_length(p_sections)<>5
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_sections) value
      WHERE jsonb_typeof(value)<>'object'
        OR (SELECT count(*) FROM jsonb_object_keys(value))<>3
        OR NOT value ?& ARRAY['id','rating','comments']
        OR jsonb_typeof(value->'id')<>'string'
        OR jsonb_typeof(value->'rating')<>'string'
        OR jsonb_typeof(value->'comments')<>'string'
        OR value->>'id' !~ ('^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-'
          || '[0-9a-f]{{4}}-[0-9a-f]{{12}}$')
        OR value->>'rating' !~ '^[1-5]\\.[0-9]$')
    OR (SELECT count(DISTINCT value->>'id') FROM jsonb_array_elements(p_sections) value)<>5
    THEN RETURN 'validation_failed'; END IF;
  SELECT * INTO source FROM public.appraisals WHERE id=p_id
    AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
    FOR UPDATE;
  IF NOT FOUND THEN RETURN 'resource_not_found'; END IF;
  IF p_expected IS NULL
    OR date_trunc('milliseconds',source.updated_at)<>date_trunc('milliseconds',p_expected)
    THEN RETURN 'state_conflict'; END IF;
  IF (SELECT count(*) FROM public.appraisal_sections WHERE appraisal_id=p_id)<>5
    OR EXISTS(SELECT 1 FROM public.appraisal_sections actual
      WHERE actual.appraisal_id=p_id AND NOT EXISTS(SELECT 1 FROM (VALUES
        ('Clinical Competency',2.00),('Patient Care Quality',2.00),
        ('Communication and Teamwork',1.50),('Punctuality and Attendance',1.00),
        ('Professional Development',1.00)) expected(name,weight)
        WHERE expected.name=actual.section_name AND expected.weight=actual.weight))
    OR EXISTS(SELECT 1 FROM jsonb_array_elements(p_sections) value
      WHERE NOT EXISTS(SELECT 1 FROM public.appraisal_sections actual
        WHERE actual.id=(value->>'id')::uuid AND actual.appraisal_id=p_id))
    THEN RETURN 'state_conflict'; END IF;
  FOR section IN SELECT value FROM jsonb_array_elements(p_sections) value ORDER BY value->>'id'
  LOOP
    result:=public.set_manager_appraisal_section_rating(p_id,(section->>'id')::uuid,
      source.updated_at,(section->>'rating')::numeric,section->>'comments');
    IF result<>'ok' THEN RETURN result; END IF;
    SELECT * INTO source FROM public.appraisals WHERE id=p_id;
  END LOOP;
  SELECT round(sum(item.weight*item.rating)/sum(item.weight),1) INTO rating
    FROM public.appraisal_sections item WHERE item.appraisal_id=p_id;
  UPDATE public.appraisals SET status='reviewed',overall_rating=rating,
    reviewed_by_app_user_id=public.workloop_app_user_id(),reviewed_at=statement_timestamp(),
    updated_at=statement_timestamp() WHERE id=p_id;
  INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
    action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(source.company_id,source.branch_id,'human',public.workloop_app_user_id(),
    'appraisal_manager_reviewed','appraisal',p_id,
    ARRAY['status','overall_rating','reviewed_at','reviewed_by_app_user_id'],
    'Manager submitted complete appraisal review','{{}}'::jsonb);
  RETURN 'ok';
END $function$;
""")
    for function in FUNCTIONS:
        op.execute(f"ALTER FUNCTION {function} OWNER TO workloop_migration")
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO workloop_runtime")


def downgrade() -> None:
    op.execute("""
DO $$ BEGIN
  IF EXISTS(SELECT 1 FROM public.appraisals WHERE archived_at IS NOT NULL)
    OR EXISTS(SELECT 1 FROM public.incident_reports WHERE archived_at IS NOT NULL)
    OR EXISTS(SELECT 1 FROM public.expense_claims WHERE archived_at IS NOT NULL)
    OR EXISTS(SELECT 1 FROM public.audit_events WHERE action IN (
      'portal_record_archived','portal_record_restored','appraisal_section_admin_rated',
      'salary_advance_admin_cancelled','appraisal_manager_reviewed',
      'employment_contract_pdf_exported')) THEN
    RAISE EXCEPTION 'portal_retained_data_requires_preservation';
  END IF;
END $$;
""")
    _contract_output_audit(False)
    for function in FUNCTIONS:
        op.execute(f"DROP FUNCTION {function}")
    for table in ("appraisals", "incident_reports", "expense_claims"):
        op.execute(f"DROP TRIGGER trg_{table}_portal_archival ON public.{table}")
        op.drop_column(table, "archived_at")
    op.execute("DROP FUNCTION public.guard_portal_archival()")
    op.execute("""
DO $$ DECLARE definition text; BEGIN
  SELECT pg_get_functiondef(
    'public.transition_training_record(uuid,timestamptz,text,date,numeric,text,boolean)'::regprocedure)
    INTO definition;
  EXECUTE replace(definition,
    'date_trunc(''milliseconds'',source.updated_at)<>date_trunc(''milliseconds'',p_expected)',
    'source.updated_at<>p_expected');
END $$;
""")
