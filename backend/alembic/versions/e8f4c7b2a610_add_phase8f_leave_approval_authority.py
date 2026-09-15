"""Add Phase 8F leave approval authority and protected audit actions.

Revision ID: e8f4c7b2a610
Revises: d1e5f8a2c904
Created: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8f4c7b2a610"
down_revision: str | Sequence[str] | None = "d1e5f8a2c904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
PRIOR_SIGNATURE = "public._append_audit_event_phase8f_prior(text,text,uuid,text[],text,jsonb)"

HUMAN_CONTEXT = """
session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() AS caller
  WHERE caller.app_user_id=public.workloop_app_user_id()
    AND caller.account_status='active'
    AND caller.profile_app_user_id=caller.app_user_id
    AND caller.profile_company_id=public.workloop_company_id()
    AND caller.company_id=caller.profile_company_id
    AND caller.role=public.workloop_role()
    AND ((caller.role='admin' AND caller.profile_employee_id IS NULL
          AND caller.employee_id IS NULL AND caller.branch_id IS NULL
          AND public.workloop_employee_id() IS NULL)
      OR (caller.role IN ('manager','employee')
          AND caller.profile_employee_id=public.workloop_employee_id()
          AND caller.employee_id=caller.profile_employee_id
          AND caller.employee_company_id=caller.profile_company_id
          AND caller.employee_branch_id=public.workloop_branch_id()
          AND caller.employee_active
          AND caller.employment_status IN ('Active','Probation','On Leave')
          AND caller.branch_id=caller.employee_branch_id
          AND caller.branch_company_id=caller.profile_company_id))
)
""".strip()


def _authority_functions() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.leave_decision_visibility(p_target_employee_id uuid)
RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  target public.employees%ROWTYPE;
BEGIN
  IF NOT ({HUMAN_CONTEXT}) OR p_target_employee_id IS NULL THEN
    RETURN NULL;
  END IF;
  SELECT employee.* INTO target
  FROM public.employees AS employee
  WHERE employee.id=p_target_employee_id
    AND employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id()
    AND employee.active
    AND employee.employment_status IN ('Active','Probation','On Leave');
  IF NOT FOUND THEN RETURN NULL; END IF;
  IF public.workloop_role()='admin' THEN RETURN 'administrator'; END IF;
  IF public.workloop_role()='manager'
    AND target.reporting_manager_id=public.workloop_employee_id()
    AND target.id<>public.workloop_employee_id() THEN
    RETURN 'directReport';
  END IF;
  IF target.id<>public.workloop_employee_id()
    AND public.can_act_for_delegated_leave(target.id) THEN
    RETURN 'activeDelegation';
  END IF;
  RETURN NULL;
END
$function$
"""
    )
    op.execute(
        """
CREATE FUNCTION public.leave_queue_employee(p_target_employee_id uuid)
RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  result jsonb;
BEGIN
  IF public.leave_decision_visibility(p_target_employee_id) IS NULL THEN RETURN NULL; END IF;
  SELECT jsonb_build_object(
    'id',employee.id,
    'employeeNumber',employee.emp_no,
    'name',employee.name,
    'jobTitle',employee.job_title,
    'department',employee.department
  ) INTO result
  FROM public.employees AS employee
  WHERE employee.id=p_target_employee_id
    AND employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id();
  RETURN result;
END
$function$
"""
    )
    op.execute(
        """
CREATE FUNCTION public.leave_decision_employee_status(p_target_employee_id uuid)
RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE result text;
BEGIN
  IF public.leave_decision_visibility(p_target_employee_id) IS NULL THEN RETURN NULL; END IF;
  SELECT employee.employment_status INTO result
  FROM public.employees AS employee
  WHERE employee.id=p_target_employee_id
    AND employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id();
  RETURN result;
END
$function$
"""
    )
    op.execute(
        """
CREATE FUNCTION public.lock_leave_decision_authority(p_target_employee_id uuid)
RETURNS text
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  visibility text;
  target public.employees%ROWTYPE;
  locked_id uuid;
BEGIN
  visibility := public.leave_decision_visibility(p_target_employee_id);
  IF visibility NOT IN ('directReport','activeDelegation') THEN RETURN NULL; END IF;
  SELECT employee.* INTO target
  FROM public.employees AS employee
  WHERE employee.id=p_target_employee_id
    AND employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id()
  FOR UPDATE;
  IF NOT FOUND OR NOT target.active
    OR target.employment_status NOT IN ('Active','Probation','On Leave') THEN RETURN NULL; END IF;
  IF target.reporting_manager_id IS NULL THEN RETURN NULL; END IF;
  SELECT employee.id INTO locked_id
  FROM public.employees AS employee
  WHERE employee.id=target.reporting_manager_id
    AND employee.company_id=target.company_id
    AND employee.branch_id=target.branch_id
    AND employee.active
    AND employee.employment_status IN ('Active','Probation','On Leave')
  FOR UPDATE;
  IF NOT FOUND THEN RETURN NULL; END IF;
  IF visibility='activeDelegation' THEN
    SELECT delegation.id INTO locked_id
    FROM public.leave_approval_delegates AS delegation
    JOIN public.employees AS delegate
      ON delegate.id=delegation.delegate_employee_id
     AND delegate.company_id=delegation.company_id
     AND delegate.branch_id=delegation.branch_id
    WHERE delegation.company_id=target.company_id
      AND delegation.branch_id=target.branch_id
      AND delegation.approver_employee_id=target.reporting_manager_id
      AND delegation.delegate_employee_id=public.workloop_employee_id()
      AND public.workloop_business_date() BETWEEN delegation.from_date AND delegation.to_date
      AND delegate.active
      AND delegate.employment_status IN ('Active','Probation','On Leave')
    ORDER BY delegation.id
    FOR UPDATE OF delegation,delegate;
    IF NOT FOUND THEN RETURN NULL; END IF;
  END IF;
  IF public.leave_decision_visibility(p_target_employee_id) IS DISTINCT FROM visibility THEN
    RETURN NULL;
  END IF;
  RETURN visibility;
END
$function$
"""
    )
    for function in (
        "leave_decision_visibility(uuid)",
        "leave_queue_employee(uuid)",
        "leave_decision_employee_status(uuid)",
        "lock_leave_decision_authority(uuid)",
    ):
        op.execute(f"ALTER FUNCTION public.{function} OWNER TO workloop_migration")
        op.execute(f"REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION public.{function} TO workloop_runtime")


def _audit_projection() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.read_leave_audit_projection(p_request_id uuid)
RETURNS TABLE(
  id uuid,leave_request_id uuid,action text,reason text,
  old_status text,new_status text,created_at timestamptz
)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE request_row public.leave_requests%ROWTYPE;
BEGIN
  IF NOT ({HUMAN_CONTEXT}) OR p_request_id IS NULL THEN RETURN; END IF;
  SELECT request.* INTO request_row
  FROM public.leave_requests AS request
  WHERE request.id=p_request_id
    AND request.company_id=public.workloop_company_id()
    AND request.branch_id=public.workloop_branch_id();
  IF NOT FOUND THEN RETURN; END IF;
  IF NOT (public.workloop_role()='admin'
    OR request_row.employee_id=public.workloop_employee_id()
    OR public.leave_decision_visibility(request_row.employee_id) IS NOT NULL
    OR request_row.approved_by_app_user_id=public.workloop_app_user_id()
    OR request_row.manager_approved_by_app_user_id=public.workloop_app_user_id()) THEN
    RETURN;
  END IF;
  RETURN QUERY
  SELECT audit.id,audit.leave_request_id,audit.action,audit.reason,
         audit.old_status,audit.new_status,audit.created_at
  FROM public.leave_audit_log AS audit
  WHERE audit.leave_request_id=p_request_id
    AND audit.company_id=public.workloop_company_id()
    AND audit.branch_id=public.workloop_branch_id()
  ORDER BY audit.created_at,audit.id;
END
$function$
"""
    )
    op.execute(
        "ALTER FUNCTION public.read_leave_audit_projection(uuid) OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public.read_leave_audit_projection(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.read_leave_audit_projection(uuid) TO workloop_runtime"
    )


def _domain_audit_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.append_leave_domain_decision_audit(
  p_request_id uuid,p_action text,p_reason text,p_old_status text,p_new_status text
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  request_row public.leave_requests%ROWTYPE;
  event_id uuid;
BEGIN
  IF NOT ({HUMAN_CONTEXT})
    OR p_action NOT IN ('manager_approved','manager_rejected','approved','rejected')
    OR p_reason IS NULL
    OR p_new_status IS DISTINCT FROM (CASE p_action
      WHEN 'manager_approved' THEN 'ManagerApproved'
      WHEN 'manager_rejected' THEN 'ManagerRejected'
      WHEN 'approved' THEN 'Approved'
      ELSE 'Rejected' END) THEN
    RAISE EXCEPTION 'leave domain audit denied' USING ERRCODE='42501';
  END IF;
  SELECT request.* INTO request_row
  FROM public.leave_requests AS request
  WHERE request.id=p_request_id
    AND request.company_id=public.workloop_company_id()
    AND request.branch_id=public.workloop_branch_id();
  IF NOT FOUND OR request_row.status<>p_new_status
    OR NOT ((p_old_status='Pending' AND p_new_status IN (
      'ManagerApproved','ManagerRejected','Approved','Rejected'))
      OR (p_old_status='ManagerApproved' AND p_new_status IN ('Approved','Rejected')))
    OR (p_new_status IN ('ManagerApproved','ManagerRejected') AND (
      request_row.manager_approved_by_app_user_id<>public.workloop_app_user_id()
      OR request_row.manager_approved_at IS NULL))
    OR (p_new_status IN ('Approved','Rejected') AND (
      request_row.approved_by_app_user_id<>public.workloop_app_user_id()
      OR request_row.approved_at IS NULL))
    OR (p_new_status IN ('ManagerRejected','Rejected') AND btrim(p_reason)='')
    OR (public.workloop_role()='admin'
      OR public.leave_decision_visibility(request_row.employee_id)
         IN ('directReport','activeDelegation')) IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'leave domain audit denied' USING ERRCODE='42501';
  END IF;
  INSERT INTO public.leave_audit_log(
    company_id,branch_id,leave_request_id,action,actor_app_user_id,
    reason,old_status,new_status,created_at)
  VALUES(
    public.workloop_company_id(),public.workloop_branch_id(),p_request_id,p_action,
    public.workloop_app_user_id(),p_reason,p_old_status,p_new_status,statement_timestamp())
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
"""
    )
    op.execute(
        "ALTER FUNCTION public.append_leave_domain_decision_audit(uuid,text,text,text,text) "
        "OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "public.append_leave_domain_decision_audit(uuid,text,text,text,text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION "
        "public.append_leave_domain_decision_audit(uuid,text,text,text,text) TO workloop_runtime"
    )


def _wrap_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase8f_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(
        f"""
CREATE FUNCTION public.append_audit_event(
  p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],
  p_reason text,p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  event_id uuid;
  request_row public.leave_requests%ROWTYPE;
  delegation_row public.leave_approval_delegates%ROWTYPE;
  domain_row public.leave_audit_log%ROWTYPE;
  expected_status text;
  expected_domain_action text;
  transition text;
  source text;
BEGIN
  IF p_action NOT IN (
    'leave_request_manager_approved','leave_request_manager_rejected',
    'leave_request_approved','leave_request_rejected',
    'leave_delegation_created','leave_delegation_updated','leave_delegation_deleted'
  ) THEN
    RETURN public._append_audit_event_phase8f_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF NOT ({HUMAN_CONTEXT}) OR jsonb_typeof(p_metadata) IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;

  IF p_action LIKE 'leave_delegation_%' THEN
    SELECT delegation.* INTO delegation_row
    FROM public.leave_approval_delegates AS delegation
    WHERE delegation.id=p_entity_id
      AND delegation.company_id=public.workloop_company_id()
      AND delegation.branch_id=public.workloop_branch_id();
    IF public.workloop_role()<>'admin' OR p_entity_type<>'leave_approval_delegate'
      OR NOT FOUND
      OR (p_action='leave_delegation_created' AND (
        p_changed_fields IS DISTINCT FROM
          ARRAY['id','approver_employee_id','delegate_employee_id','dates']::text[]
        OR p_reason<>'Leave approval delegation created' OR p_metadata<>'{{}}'::jsonb))
      OR (p_action='leave_delegation_updated' AND (
        p_changed_fields IS DISTINCT FROM
          ARRAY['approver_employee_id','delegate_employee_id','dates']::text[]
        OR p_reason<>'Leave approval delegation updated' OR p_metadata<>'{{}}'::jsonb))
      OR (p_action='leave_delegation_deleted' AND (
        p_changed_fields IS DISTINCT FROM ARRAY['id']::text[]
        OR p_reason<>'Leave approval delegation deleted'
        OR p_metadata->>'approver_employee_id'<>delegation_row.approver_employee_id::text
        OR p_metadata->>'delegate_employee_id'<>delegation_row.delegate_employee_id::text)) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    transition := p_metadata->>'transition';
    source := p_metadata->>'decision_source';
    expected_status := CASE p_action
      WHEN 'leave_request_manager_approved' THEN 'ManagerApproved'
      WHEN 'leave_request_manager_rejected' THEN 'ManagerRejected'
      WHEN 'leave_request_approved' THEN 'Approved'
      ELSE 'Rejected' END;
    expected_domain_action := CASE p_action
      WHEN 'leave_request_manager_approved' THEN 'manager_approved'
      WHEN 'leave_request_manager_rejected' THEN 'manager_rejected'
      WHEN 'leave_request_approved' THEN 'approved'
      ELSE 'rejected' END;
    SELECT request.* INTO request_row
    FROM public.leave_requests AS request
    WHERE request.id=p_entity_id
      AND request.company_id=public.workloop_company_id()
      AND request.branch_id=public.workloop_branch_id();
    SELECT audit.* INTO domain_row
    FROM public.leave_audit_log AS audit
    WHERE audit.leave_request_id=p_entity_id
      AND audit.company_id=public.workloop_company_id()
      AND audit.branch_id=public.workloop_branch_id()
    ORDER BY audit.created_at DESC,audit.id DESC LIMIT 1;
    IF p_entity_type<>'leave_request'
      OR p_changed_fields IS DISTINCT FROM ARRAY['status','balance']::text[]
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>2
      OR request_row.status<>expected_status
      OR domain_row.action<>expected_domain_action
      OR domain_row.actor_app_user_id<>public.workloop_app_user_id()
      OR domain_row.new_status<>expected_status
      OR domain_row.reason<>p_reason
      OR transition<>domain_row.old_status||'_to_'||domain_row.new_status
      OR source NOT IN ('directReport','activeDelegation','administrator')
      OR ((source='administrator') IS DISTINCT FROM (public.workloop_role()='admin'))
      OR (source<>'administrator' AND public.leave_decision_visibility(request_row.employee_id)
          IS DISTINCT FROM source)
      OR (expected_status IN ('ManagerApproved','ManagerRejected') AND (
        request_row.manager_approved_by_app_user_id<>public.workloop_app_user_id()
        OR request_row.manager_approved_at IS NULL))
      OR (expected_status IN ('Approved','Rejected') AND (
        request_row.approved_by_app_user_id<>public.workloop_app_user_id()
        OR request_row.approved_at IS NULL))
      OR (expected_status IN ('ManagerRejected','Rejected') AND btrim(p_reason)='') THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;

  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(
    public.workloop_company_id(),public.workloop_branch_id(),'human',
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
        "leave_approval_delegates",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
    )
    _authority_functions()
    _audit_projection()
    _domain_audit_function()
    _wrap_audit()


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase8f_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.execute("DROP FUNCTION public.append_leave_domain_decision_audit(uuid,text,text,text,text)")
    op.execute("DROP FUNCTION public.read_leave_audit_projection(uuid)")
    op.execute("DROP FUNCTION public.lock_leave_decision_authority(uuid)")
    op.execute("DROP FUNCTION public.leave_decision_employee_status(uuid)")
    op.execute("DROP FUNCTION public.leave_queue_employee(uuid)")
    op.execute("DROP FUNCTION public.leave_decision_visibility(uuid)")
    op.drop_column("leave_approval_delegates", "updated_at")
