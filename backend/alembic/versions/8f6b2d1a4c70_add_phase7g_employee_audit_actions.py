"""Add Phase 7G employee audit actions and portal-role policies.

Revision ID: 8f6b2d1a4c70
Revises: 7d4a9c2e6b10
Create Date: 2026-09-11 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8f6b2d1a4c70"
down_revision: str | Sequence[str] | None = "7d4a9c2e6b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
PRIOR_AUDIT_SIGNATURE = "public._append_audit_event_phase7g_prior(text,text,uuid,text[],text,jsonb)"

HUMAN_ADMIN_BRANCH = """
current_user='workloop_runtime'
AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
AND public.workloop_role()='admin'
AND public.workloop_employee_id() IS NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() AS caller
  WHERE caller.app_user_id=public.workloop_app_user_id()
    AND caller.account_status='active'
    AND caller.profile_app_user_id=caller.app_user_id
    AND caller.profile_company_id=public.workloop_company_id()
    AND caller.company_id=caller.profile_company_id
    AND caller.role='admin'
    AND caller.profile_employee_id IS NULL
    AND caller.employee_id IS NULL
    AND caller.branch_id IS NULL
)
AND EXISTS (
  SELECT 1 FROM public.branches AS selected_branch
  WHERE selected_branch.id=public.workloop_branch_id()
    AND selected_branch.company_id=public.workloop_company_id()
)
""".strip()


def _replace_audit_function() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase7g_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(r"""
CREATE FUNCTION public.append_audit_event(
  p_action text, p_entity_type text, p_entity_id uuid, p_changed_fields text[],
  p_reason text, p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  event_id uuid;
  employee_active boolean;
  employee_status text;
  employee_probation_end date;
  employee_probation_extended boolean;
  employee_termination_date date;
  employee_termination_reason text;
  employee_manager_id uuid;
  previous_manager_id uuid;
  new_manager_id uuid;
  profile_role text;
BEGIN
  IF p_action <> ALL(ARRAY[
    'employee_manager_changed',
    'employee_probation_confirmed',
    'employee_probation_extended',
    'employee_probation_terminated',
    'employee_archived',
    'employee_portal_role_changed'
  ]::text[]) THEN
    RETURN public._append_audit_event_phase7g_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;

  IF session_user<>'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR public.workloop_app_user_id() IS NULL
    OR public.workloop_company_id() IS NULL
    OR public.workloop_branch_id() IS NULL
    OR public.workloop_role() IS DISTINCT FROM 'admin'
    OR public.workloop_employee_id() IS NOT NULL
    OR p_reason IS NULL OR p_reason<>btrim(p_reason)
    OR char_length(p_reason) NOT BETWEEN 1 AND 1000
    OR jsonb_typeof(p_metadata) IS DISTINCT FROM 'object'
    OR NOT EXISTS (
      SELECT 1 FROM public.resolve_workloop_principal() AS caller
      WHERE caller.app_user_id=public.workloop_app_user_id()
        AND caller.account_status='active'
        AND caller.profile_app_user_id=caller.app_user_id
        AND caller.profile_company_id=public.workloop_company_id()
        AND caller.company_id=caller.profile_company_id
        AND caller.role='admin'
        AND caller.profile_employee_id IS NULL
        AND caller.employee_id IS NULL
        AND caller.branch_id IS NULL)
    OR NOT EXISTS (
      SELECT 1 FROM public.branches AS branch
      WHERE branch.id=public.workloop_branch_id()
        AND branch.company_id=public.workloop_company_id()) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;

  IF p_action='employee_portal_role_changed' THEN
    IF p_entity_type<>'user_profile'
      OR p_changed_fields IS DISTINCT FROM ARRAY['role']::text[]
      OR p_entity_id=public.workloop_app_user_id()
      OR NOT (p_metadata ? 'transition')
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>1
      OR p_metadata->>'transition' NOT IN ('employee_to_manager','manager_to_employee') THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
    SELECT profile.role::text INTO profile_role
    FROM public.user_profiles AS profile
    JOIN public.app_users AS account ON account.id=profile.app_user_id
    JOIN public.employees AS employee ON employee.id=profile.employee_id
      AND employee.company_id=profile.company_id
    WHERE profile.app_user_id=p_entity_id
      AND profile.company_id=public.workloop_company_id()
      AND employee.branch_id=public.workloop_branch_id()
      AND account.status::text='active'
      AND employee.active
      AND employee.employment_status IN ('Active','Probation','On Leave');
    IF NOT FOUND
      OR profile_role<>(CASE p_metadata->>'transition'
        WHEN 'employee_to_manager' THEN 'manager' ELSE 'employee' END) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    IF p_entity_type<>'employee' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
    SELECT employee.active,employee.employment_status,employee.probation_end_date,
      employee.probation_extended,employee.termination_date,employee.termination_reason,
      employee.reporting_manager_id
      INTO employee_active,employee_status,employee_probation_end,
        employee_probation_extended,employee_termination_date,employee_termination_reason,
        employee_manager_id
    FROM public.employees AS employee
    WHERE employee.id=p_entity_id
      AND employee.company_id=public.workloop_company_id()
      AND employee.branch_id=public.workloop_branch_id();
    IF NOT FOUND THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;

    CASE p_action
      WHEN 'employee_manager_changed' THEN
        IF p_changed_fields IS DISTINCT FROM ARRAY['reporting_manager_id']::text[]
          OR NOT (p_metadata ? 'previous_manager_id')
          OR NOT (p_metadata ? 'new_manager_id')
          OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>2
          OR NOT ((p_metadata->'previous_manager_id'='null'::jsonb)
            OR (jsonb_typeof(p_metadata->'previous_manager_id')='string'
              AND p_metadata->>'previous_manager_id' ~
                '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
              AND pg_catalog.pg_input_is_valid(p_metadata->>'previous_manager_id','uuid')))
          OR NOT ((p_metadata->'new_manager_id'='null'::jsonb)
            OR (jsonb_typeof(p_metadata->'new_manager_id')='string'
              AND p_metadata->>'new_manager_id' ~
                '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
              AND pg_catalog.pg_input_is_valid(p_metadata->>'new_manager_id','uuid'))) THEN
          RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
        END IF;
        previous_manager_id := (p_metadata->>'previous_manager_id')::uuid;
        new_manager_id := (p_metadata->>'new_manager_id')::uuid;
        IF previous_manager_id IS NOT DISTINCT FROM new_manager_id
          OR employee_manager_id IS DISTINCT FROM new_manager_id
          OR (previous_manager_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.employees AS manager
            WHERE manager.id=previous_manager_id
              AND manager.company_id=public.workloop_company_id()
              AND manager.branch_id=public.workloop_branch_id()))
          OR (new_manager_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM public.employees AS manager
            WHERE manager.id=new_manager_id AND manager.id<>p_entity_id
              AND manager.company_id=public.workloop_company_id()
              AND manager.branch_id=public.workloop_branch_id()
              AND manager.active
              AND manager.employment_status IN ('Active','Probation','On Leave'))) THEN
          RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
        END IF;
      WHEN 'employee_probation_confirmed' THEN
        IF p_changed_fields IS DISTINCT FROM
             ARRAY['employment_status','probation_end_date']::text[]
          OR p_metadata IS DISTINCT FROM '{"transition":"probation_to_active"}'::jsonb
          OR NOT employee_active OR employee_status<>'Active'
          OR employee_probation_end IS NOT NULL THEN
          RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
        END IF;
      WHEN 'employee_probation_extended' THEN
        IF p_changed_fields IS DISTINCT FROM
             ARRAY['probation_end_date','probation_extended']::text[]
          OR NOT (p_metadata ? 'previous_probation_end_date')
          OR NOT (p_metadata ? 'new_probation_end_date')
          OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>2
          OR jsonb_typeof(p_metadata->'previous_probation_end_date')<>'string'
          OR jsonb_typeof(p_metadata->'new_probation_end_date')<>'string'
          OR p_metadata->>'previous_probation_end_date' !~ '^\d{4}-\d{2}-\d{2}$'
          OR p_metadata->>'new_probation_end_date' !~ '^\d{4}-\d{2}-\d{2}$'
          OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'previous_probation_end_date','date')
          OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'new_probation_end_date','date')
          OR (p_metadata->>'new_probation_end_date')::date
             <=(p_metadata->>'previous_probation_end_date')::date
          OR NOT employee_active OR employee_status<>'Probation'
          OR NOT employee_probation_extended
          OR employee_probation_end IS DISTINCT FROM
             (p_metadata->>'new_probation_end_date')::date THEN
          RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
        END IF;
      WHEN 'employee_probation_terminated' THEN
        IF p_changed_fields IS DISTINCT FROM
             ARRAY['active','employment_status','termination_date','termination_reason']::text[]
          OR p_metadata IS DISTINCT FROM '{"transition":"probation_to_terminated"}'::jsonb
          OR employee_active OR employee_status<>'Terminated'
          OR employee_termination_date IS DISTINCT FROM public.workloop_business_date()
          OR employee_termination_reason<>p_reason THEN
          RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
        END IF;
      WHEN 'employee_archived' THEN
        IF p_changed_fields IS DISTINCT FROM
             ARRAY['active','employment_status','termination_date','termination_reason']::text[]
          OR NOT (p_metadata ? 'transition')
          OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>1
          OR p_metadata->>'transition' NOT IN
             ('active_to_terminated','on_leave_to_terminated')
          OR employee_active OR employee_status<>'Terminated'
          OR employee_termination_date IS DISTINCT FROM public.workloop_business_date()
          OR employee_termination_reason<>p_reason THEN
          RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
        END IF;
      ELSE
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END CASE;
  END IF;

  INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
    system_actor_key,initiated_by_app_user_id,action,entity_type,entity_id,
    changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
    p_changed_fields,p_reason,p_metadata)
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
""")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def _add_profile_policies() -> None:
    select_expression = f"""{HUMAN_ADMIN_BRANCH}
AND company_id=public.workloop_company_id()
AND employee_id IS NOT NULL
AND EXISTS (
  SELECT 1 FROM public.employees AS target_employee
  WHERE target_employee.id=user_profiles.employee_id
    AND target_employee.company_id=user_profiles.company_id
    AND target_employee.branch_id=public.workloop_branch_id()
)"""
    update_expression = f"""{select_expression}
AND app_user_id<>public.workloop_app_user_id()
AND role::text IN ('employee','manager')
AND public.is_scoped_active_app_user(app_user_id)
AND EXISTS (
  SELECT 1 FROM public.employees AS eligible_employee
  WHERE eligible_employee.id=user_profiles.employee_id
    AND eligible_employee.company_id=user_profiles.company_id
    AND eligible_employee.branch_id=public.workloop_branch_id()
    AND eligible_employee.active
    AND eligible_employee.employment_status IN ('Active','Probation','On Leave')
)"""
    op.execute(
        "CREATE POLICY phase7g_user_profiles_select_branch_runtime "
        "ON public.user_profiles FOR SELECT TO workloop_runtime "
        f"USING ({select_expression})"
    )
    op.execute(
        "CREATE POLICY phase7g_user_profiles_update_role_branch_runtime "
        "ON public.user_profiles FOR UPDATE TO workloop_runtime "
        f"USING ({update_expression}) WITH CHECK ({update_expression})"
    )


def upgrade() -> None:
    _replace_audit_function()
    _add_profile_policies()


def downgrade() -> None:
    op.execute(
        "DROP POLICY phase7g_user_profiles_update_role_branch_runtime ON public.user_profiles"
    )
    op.execute("DROP POLICY phase7g_user_profiles_select_branch_runtime ON public.user_profiles")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase7g_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
