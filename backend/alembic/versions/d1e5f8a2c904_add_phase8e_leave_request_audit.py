"""Add Phase 8E leave request audit and self auto-approval policy.

Revision ID: d1e5f8a2c904
Revises: a83d5e7c1b29
Created: 2026-09-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d1e5f8a2c904"
down_revision: str | Sequence[str] | None = "a83d5e7c1b29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
PRIOR_SIGNATURE = "public._append_audit_event_phase8e_prior(text,text,uuid,text[],text,jsonb)"

HUMAN_CONTEXT = """
current_user='workloop_runtime' AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
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


def _replace_request_update_policy() -> None:
    op.execute(
        "ALTER POLICY phase5f_leave_requests_update_runtime ON public.leave_requests "
        "RENAME TO phase8e_prior_leave_requests_update_runtime"
    )
    op.execute(
        "ALTER POLICY phase8e_prior_leave_requests_update_runtime ON public.leave_requests "
        "TO workloop_migration"
    )
    admin = f"""{HUMAN_CONTEXT}
AND public.workloop_role()='admin'
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()"""
    request_scope = f"""{HUMAN_CONTEXT}
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()
AND (
  public.workloop_role()='admin'
  OR (public.workloop_role() IN ('manager','employee')
      AND employee_id=public.workloop_employee_id())
  OR (public.workloop_role()='manager' AND EXISTS (
    SELECT 1 FROM public.employees AS target_employee
    WHERE target_employee.id=employee_id
      AND target_employee.company_id=leave_requests.company_id
      AND target_employee.branch_id=leave_requests.branch_id
      AND target_employee.reporting_manager_id=public.workloop_employee_id()
  ))
  OR public.can_act_for_delegated_leave(employee_id)
)"""
    request_self = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager','employee')
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()
AND employee_id=public.workloop_employee_id()"""
    request_team = f"""{request_scope}
AND public.workloop_role() IN ('manager','employee')
AND employee_id<>public.workloop_employee_id()"""
    using = f"""({admin}) OR (
  {request_self}
  AND status='Pending'
) OR ({request_team})"""
    auto_approved = f"""{request_self}
AND status='Approved'
AND approved_by_app_user_id=public.workloop_app_user_id()
AND approved_at IS NOT NULL
AND approval_comment='Auto-approved by leave type policy'
AND EXISTS (
  SELECT 1 FROM public.leave_types AS request_type
  WHERE request_type.id=leave_requests.leave_type_id
    AND request_type.company_id=leave_requests.company_id
    AND request_type.branch_id=leave_requests.branch_id
    AND request_type.is_active AND request_type.auto_approve
)"""
    check = f"""({admin}) OR (
  {request_self}
  AND status='Cancelled'
) OR ({auto_approved}) OR (
  {request_team}
  AND status IN ('Approved','ManagerApproved','ManagerRejected')
)"""
    op.execute(
        "CREATE POLICY phase5f_leave_requests_update_runtime ON public.leave_requests "
        f"FOR UPDATE TO workloop_runtime USING ({using}) WITH CHECK ({check})"
    )


def _add_policy_lock_policies() -> None:
    staff = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager','employee')
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()"""
    op.execute(
        "CREATE POLICY phase8e_leave_settings_lock_runtime ON public.leave_settings "
        f"FOR UPDATE TO workloop_runtime USING ({staff}) WITH CHECK (false)"
    )
    op.execute(
        "CREATE POLICY phase8e_leave_types_lock_runtime ON public.leave_types "
        f"FOR UPDATE TO workloop_runtime USING ({staff} AND is_active) WITH CHECK (false)"
    )


def _allow_leave_request_replay() -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        "(replay_resource_kind IN "
        "('branch','employee','department','user_profile','leave_request') "
        "AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )


def _wrap_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase8e_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(r"""
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
  type_auto_approve boolean;
  domain_action text;
  domain_actor uuid;
  domain_old_status text;
  domain_new_status text;
  linked_attachment_status text;
  submission_mode text;
  transition_name text;
BEGIN
  IF p_action NOT IN ('leave_request_submitted','leave_request_auto_approved',
      'leave_request_cancelled') THEN
    RETURN public._append_audit_event_phase8e_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF session_user<>'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR public.workloop_app_user_id() IS NULL
    OR public.workloop_company_id() IS NULL
    OR public.workloop_branch_id() IS NULL
    OR p_entity_type<>'leave_request'
    OR jsonb_typeof(p_metadata) IS DISTINCT FROM 'object'
    OR NOT EXISTS (
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
    ) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;

  SELECT request.* INTO request_row
  FROM public.leave_requests AS request
  WHERE request.id=p_entity_id
    AND request.company_id=public.workloop_company_id()
    AND request.branch_id=public.workloop_branch_id();
  IF NOT FOUND THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  SELECT audit.action,audit.actor_app_user_id,audit.old_status,audit.new_status
    INTO domain_action,domain_actor,domain_old_status,domain_new_status
  FROM public.leave_audit_log AS audit
  WHERE audit.leave_request_id=request_row.id
    AND audit.company_id=request_row.company_id
    AND audit.branch_id=request_row.branch_id
  ORDER BY audit.created_at DESC,audit.id DESC
  LIMIT 1;
  SELECT attachment.status INTO linked_attachment_status
  FROM public.leave_attachments AS attachment
  WHERE attachment.leave_request_id=request_row.id
    AND attachment.company_id=request_row.company_id
    AND attachment.branch_id=request_row.branch_id;

  IF p_action='leave_request_submitted' THEN
    submission_mode := p_metadata->>'submission_mode';
    IF p_changed_fields IS DISTINCT FROM
        ARRAY['id','status','days_requested','approval_level_required']::text[]
      OR p_reason<>'Leave request submitted'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>2
      OR p_metadata->>'transition'<>'created_to_pending'
      OR submission_mode NOT IN ('self','administrator')
      OR request_row.status<>'Pending'
      OR domain_action<>'submitted'
      OR domain_actor<>public.workloop_app_user_id()
      OR domain_old_status<>'' OR domain_new_status<>'Pending'
      OR linked_attachment_status IS NOT NULL AND linked_attachment_status<>'attached'
      OR NOT ((submission_mode='self'
               AND public.workloop_role() IN ('manager','employee')
               AND request_row.employee_id=public.workloop_employee_id())
        OR (submission_mode='administrator' AND public.workloop_role()='admin'
            AND public.workloop_employee_id() IS NULL)) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='leave_request_auto_approved' THEN
    SELECT leave_type.auto_approve AND leave_type.is_active INTO type_auto_approve
    FROM public.leave_types AS leave_type
    WHERE leave_type.id=request_row.leave_type_id
      AND leave_type.company_id=request_row.company_id
      AND leave_type.branch_id=request_row.branch_id;
    IF p_changed_fields IS DISTINCT FROM
        ARRAY['status','approved_by_app_user_id','approved_at','approval_comment']::text[]
      OR p_reason<>'Leave request auto-approved by leave type policy'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>2
      OR p_metadata->>'transition'<>'pending_to_approved'
      OR p_metadata->>'decision_source'<>'leave_type_policy'
      OR request_row.status<>'Approved'
      OR request_row.approved_by_app_user_id<>public.workloop_app_user_id()
      OR request_row.approval_comment<>'Auto-approved by leave type policy'
      OR type_auto_approve IS DISTINCT FROM true
      OR domain_action<>'auto_approved'
      OR domain_actor<>public.workloop_app_user_id()
      OR domain_old_status<>'Pending' OR domain_new_status<>'Approved' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    transition_name := p_metadata->>'transition';
    IF p_changed_fields IS DISTINCT FROM ARRAY['status']::text[]
      OR p_reason<>'Leave request cancelled'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>1
      OR transition_name NOT IN ('pending_to_cancelled','approved_to_cancelled')
      OR request_row.status<>'Cancelled'
      OR domain_action<>'cancelled'
      OR domain_actor<>public.workloop_app_user_id()
      OR domain_new_status<>'Cancelled'
      OR domain_old_status<>(CASE transition_name
           WHEN 'pending_to_cancelled' THEN 'Pending' ELSE 'Approved' END)
      OR linked_attachment_status IS NOT NULL
         AND linked_attachment_status NOT IN ('cleanup_pending','removed')
      OR NOT ((transition_name='pending_to_cancelled'
               AND public.workloop_role() IN ('manager','employee')
               AND request_row.employee_id=public.workloop_employee_id())
        OR (transition_name='approved_to_cancelled'
            AND public.workloop_role()='admin'
            AND public.workloop_employee_id() IS NULL
            AND request_row.start_date>public.workloop_business_date())) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;

  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(
    public.workloop_company_id(),public.workloop_branch_id(),
    CASE WHEN p_action='leave_request_auto_approved' THEN 'system_rule' ELSE 'human' END,
    CASE WHEN p_action='leave_request_auto_approved' THEN NULL
         ELSE public.workloop_app_user_id() END,
    CASE WHEN p_action='leave_request_auto_approved' THEN 'leave_auto_approval'
         ELSE NULL END,
    CASE WHEN p_action='leave_request_auto_approved' THEN public.workloop_app_user_id()
         ELSE NULL END,
    p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata)
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
""")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def upgrade() -> None:
    _allow_leave_request_replay()
    _replace_request_update_policy()
    _add_policy_lock_policies()
    _wrap_audit()


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase8e_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.execute("DROP POLICY IF EXISTS phase8e_leave_types_lock_runtime ON public.leave_types")
    op.execute("DROP POLICY IF EXISTS phase8e_leave_settings_lock_runtime ON public.leave_settings")
    op.execute("DROP POLICY phase5f_leave_requests_update_runtime ON public.leave_requests")
    op.execute(
        "ALTER POLICY phase8e_prior_leave_requests_update_runtime ON public.leave_requests "
        "TO workloop_runtime"
    )
    op.execute(
        "ALTER POLICY phase8e_prior_leave_requests_update_runtime ON public.leave_requests "
        "RENAME TO phase5f_leave_requests_update_runtime"
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        "(replay_resource_kind IN ('branch','employee','department','user_profile') "
        "AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
