"""Add Phase 5G document, benefit, and notification row security.

Revision ID: e96f7a1b4c53
Revises: d85a6f0c3b42
Created: 2026-09-06 00:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

revision: str = "e96f7a1b4c53"
down_revision: str | Sequence[str] | None = "d85a6f0c3b42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = (
    "employee_documents",
    "insurance_policies",
    "employee_insurance",
    "insurance_dependants",
    "notifications",
)

HUMAN_CONTEXT = """
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
      (principal.role = 'admin' AND principal.profile_employee_id IS NULL
       AND principal.employee_id IS NULL AND principal.branch_id IS NULL
       AND public.workloop_employee_id() IS NULL)
      OR
      (principal.role IN ('manager', 'employee')
       AND principal.profile_employee_id = public.workloop_employee_id()
       AND principal.employee_id = principal.profile_employee_id
       AND principal.employee_company_id = principal.profile_company_id
       AND principal.employee_branch_id = public.workloop_branch_id()
       AND principal.employee_active
       AND principal.employment_status IN ('Active', 'Probation', 'On Leave')
       AND principal.branch_id = principal.employee_branch_id
       AND principal.branch_company_id = principal.profile_company_id)
    )
)
""".strip()

JOB_CONTEXT = """
current_user = 'workloop_expiry_processing'
AND session_user = 'workloop_expiry_processing'
AND public.workloop_actor_kind() = 'scheduled_job'
AND public.workloop_actor_key() = 'expiry_processing'
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_business_date() IS NOT NULL
""".strip()


def _policy(
    name: str,
    table: str,
    command: str,
    role: str = "workloop_runtime",
    *,
    using: str | None = None,
    check: str | None = None,
) -> None:
    clauses = []
    if using is not None:
        clauses.append(f"USING ({using})")
    if check is not None:
        clauses.append(f"WITH CHECK ({check})")
    op.execute(
        f"CREATE POLICY {name} ON public.{table} FOR {command} TO {role} " + " ".join(clauses)
    )


def _admin(table: str = "") -> str:
    prefix = f"{table}." if table else ""
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND {prefix}company_id = public.workloop_company_id()
AND {prefix}branch_id = public.workloop_branch_id()"""


def _self() -> str:
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND employee_id = public.workloop_employee_id()"""


def _create_policies() -> None:
    admin = _admin()
    self_scope = _self()

    _policy(
        "phase5g_employee_documents_select_runtime",
        "employee_documents",
        "SELECT",
        using=f"({admin}) OR ({self_scope})",
    )
    _policy(
        "phase5g_employee_documents_insert_runtime",
        "employee_documents",
        "INSERT",
        check=f"""(({admin}) AND submitted_by = 'hr' AND status = 'verified'
AND reviewed_by_app_user_id = public.workloop_app_user_id() AND reviewed_at IS NOT NULL)
OR (({self_scope}) AND submitted_by = 'employee' AND status = 'pending_verification'
AND reviewed_by_app_user_id IS NULL AND reviewed_at IS NULL)""",
    )
    _policy(
        "phase5g_employee_documents_update_runtime",
        "employee_documents",
        "UPDATE",
        using=admin,
        check=admin,
    )
    _policy(
        "phase5g_employee_documents_delete_runtime",
        "employee_documents",
        "DELETE",
        using=f"{admin} AND status IN ('pending_verification', 'rejected')",
    )
    _policy(
        "phase5g_employee_documents_select_expiry",
        "employee_documents",
        "SELECT",
        "workloop_expiry_processing",
        using=f"""{JOB_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND status = 'verified'""",
    )

    linked_policy = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND insurance_policies.company_id = public.workloop_company_id()
AND insurance_policies.branch_id = public.workloop_branch_id()
AND EXISTS (
  SELECT 1 FROM public.employee_insurance AS link
  WHERE link.policy_id = insurance_policies.id
    AND link.company_id = insurance_policies.company_id
    AND link.branch_id = insurance_policies.branch_id
    AND link.employee_id = public.workloop_employee_id()
)"""
    _policy(
        "phase5g_insurance_policies_select_runtime",
        "insurance_policies",
        "SELECT",
        using=f"({_admin('insurance_policies')}) OR ({linked_policy})",
    )
    for command in ("INSERT", "UPDATE", "DELETE"):
        _policy(
            f"phase5g_insurance_policies_{command.lower()}_runtime",
            "insurance_policies",
            command,
            using=admin if command != "INSERT" else None,
            check=admin if command in {"INSERT", "UPDATE"} else None,
        )
    _policy(
        "phase5g_insurance_policies_select_expiry",
        "insurance_policies",
        "SELECT",
        "workloop_expiry_processing",
        using=f"{JOB_CONTEXT} AND company_id = public.workloop_company_id() AND branch_id = public.workloop_branch_id()",
    )

    _policy(
        "phase5g_employee_insurance_select_runtime",
        "employee_insurance",
        "SELECT",
        using=f"({admin}) OR ({self_scope})",
    )
    for command in ("INSERT", "UPDATE"):
        _policy(
            f"phase5g_employee_insurance_{command.lower()}_runtime",
            "employee_insurance",
            command,
            using=admin if command == "UPDATE" else None,
            check=admin,
        )
    _policy(
        "phase5g_employee_insurance_select_expiry",
        "employee_insurance",
        "SELECT",
        "workloop_expiry_processing",
        using=f"{JOB_CONTEXT} AND company_id = public.workloop_company_id() AND branch_id = public.workloop_branch_id()",
    )

    for command in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        _policy(
            f"phase5g_insurance_dependants_{command.lower()}_runtime",
            "insurance_dependants",
            command,
            using=admin if command != "INSERT" else None,
            check=admin if command in {"INSERT", "UPDATE"} else None,
        )

    recipient = f"""{HUMAN_CONTEXT}
AND recipient_app_user_id = public.workloop_app_user_id()
AND company_id = public.workloop_company_id()
AND ((public.workloop_role() = 'admin' AND (branch_id IS NULL OR branch_id = public.workloop_branch_id()))
 OR (public.workloop_role() IN ('manager', 'employee') AND branch_id = public.workloop_branch_id()))"""
    _policy("phase5g_notifications_select_runtime", "notifications", "SELECT", using=recipient)
    _policy(
        "phase5g_notifications_update_runtime",
        "notifications",
        "UPDATE",
        using=recipient,
        check=recipient,
    )
    job_notification = f"""{JOB_CONTEXT}
AND company_id = public.workloop_company_id()
AND ((public.workloop_branch_id() IS NULL AND branch_id IS NULL)
 OR (public.workloop_branch_id() IS NOT NULL AND branch_id = public.workloop_branch_id()))"""
    _policy(
        "phase5g_notifications_select_expiry",
        "notifications",
        "SELECT",
        "workloop_expiry_processing",
        using=job_notification,
    )
    _policy(
        "phase5g_notifications_insert_expiry",
        "notifications",
        "INSERT",
        "workloop_expiry_processing",
        check=f"""{job_notification}
AND created_by_app_user_id IS NULL
AND type IN ('document_expiry','clinical_credential_expiry','insurance_expiry','probation_ending','contract_expiry','cert_expiry','clinical_licence_expiry','policy_renewal')""",
    )


def _create_notification_function() -> None:
    op.execute(r"""
CREATE FUNCTION public.create_workflow_notification(p_type text, p_related_entity_id text)
RETURNS uuid
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  source_id uuid;
  source_company uuid;
  source_branch uuid;
  source_employee uuid;
  recipient_id uuid;
  notification_id uuid;
  entity_type text;
  notification_title text;
  notification_body text;
BEGIN
  IF session_user <> 'workloop_runtime'
     OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
     OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL
     OR public.workloop_company_id() IS NULL THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id = public.workloop_app_user_id()
      AND caller.account_status = 'active'
      AND caller.profile_company_id = public.workloop_company_id()
      AND caller.role = public.workloop_role()
  ) THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END IF;
  BEGIN source_id := p_related_entity_id::uuid;
  EXCEPTION WHEN invalid_text_representation THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END;

  IF p_type IN ('leave_approved', 'leave_rejected') THEN
    SELECT request.company_id, request.branch_id, request.employee_id
      INTO source_company, source_branch, source_employee
    FROM public.leave_requests AS request
    JOIN public.employees AS employee ON employee.id = request.employee_id
      AND employee.company_id = request.company_id AND employee.branch_id = request.branch_id
    WHERE request.id = source_id
      AND request.company_id = public.workloop_company_id()
      AND request.branch_id = public.workloop_branch_id()
      AND ((p_type = 'leave_approved' AND request.status = 'Approved')
        OR (p_type = 'leave_rejected' AND request.status IN ('Rejected', 'ManagerRejected')))
      AND (public.workloop_role() = 'admin'
        OR (public.workloop_role() = 'manager' AND employee.reporting_manager_id = public.workloop_employee_id())
        OR public.can_act_for_delegated_leave(request.employee_id));
    entity_type := 'leave_request';
    notification_title := CASE p_type WHEN 'leave_approved' THEN 'Leave approved' ELSE 'Leave rejected' END;
    notification_body := CASE p_type WHEN 'leave_approved' THEN 'Your leave request was approved.' ELSE 'Your leave request was rejected.' END;
  ELSIF p_type = 'payslip_available' THEN
    SELECT payslip.company_id, payslip.branch_id, payslip.employee_id
      INTO source_company, source_branch, source_employee
    FROM public.payslips AS payslip
    WHERE payslip.id = source_id AND payslip.company_id = public.workloop_company_id()
      AND payslip.branch_id = public.workloop_branch_id() AND public.workloop_role() = 'admin';
    entity_type := 'payslip'; notification_title := 'Payslip available';
    notification_body := 'Your payslip is available.';
  ELSIF p_type = 'roster_published' THEN
    SELECT roster.company_id, roster.branch_id, roster.employee_id
      INTO source_company, source_branch, source_employee
    FROM public.roster_assignments AS roster
    WHERE roster.id = source_id AND roster.company_id = public.workloop_company_id()
      AND roster.branch_id = public.workloop_branch_id() AND roster.published
      AND public.workloop_role() = 'admin';
    entity_type := 'roster_assignment'; notification_title := 'Roster published';
    notification_body := 'Your roster was published.';
  ELSE
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END IF;

  IF source_employee IS NULL THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END IF;
  SELECT profile.app_user_id INTO STRICT recipient_id
  FROM public.user_profiles AS profile JOIN public.app_users AS account ON account.id = profile.app_user_id
  WHERE profile.employee_id = source_employee AND profile.company_id = source_company
    AND account.status::text = 'active';

  INSERT INTO public.notifications(company_id, branch_id, created_by_app_user_id,
    recipient_app_user_id, type, title, body, related_entity_type, related_entity_id)
  VALUES (source_company, source_branch, public.workloop_app_user_id(), recipient_id,
    p_type, notification_title, notification_body, entity_type, source_id::text)
  ON CONFLICT (company_id, recipient_app_user_id, type, related_entity_type, related_entity_id)
  DO NOTHING
  RETURNING id INTO notification_id;
  IF notification_id IS NULL THEN
    SELECT id INTO notification_id
    FROM public.notifications
    WHERE company_id = source_company
      AND recipient_app_user_id = recipient_id
      AND type = p_type
      AND related_entity_type = entity_type
      AND related_entity_id = source_id::text;
  END IF;
  RETURN notification_id;
EXCEPTION WHEN no_data_found OR too_many_rows THEN
  RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public.create_workflow_notification(text, text) OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public.create_workflow_notification(text, text) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.create_workflow_notification(text, text) TO workloop_runtime"
    )


def upgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    _create_policies()
    _create_notification_function()
    op.execute(
        "GRANT DELETE ON TABLE public.employee_documents, public.insurance_policies, public.insurance_dependants TO workloop_runtime"
    )
    op.execute("REVOKE UPDATE ON TABLE public.notifications FROM workloop_runtime")
    op.execute("GRANT UPDATE (read_at) ON TABLE public.notifications TO workloop_runtime")
    op.execute("REVOKE INSERT ON TABLE public.notifications FROM workloop_runtime")
    op.execute(
        "GRANT SELECT (id,company_id,branch_id,employee_id,document_type,expiry_date,status) ON TABLE public.employee_documents TO workloop_expiry_processing"
    )
    op.execute(
        "GRANT SELECT (id,company_id,branch_id,insurer_name,tier_name,renewal_date) ON TABLE public.insurance_policies TO workloop_expiry_processing"
    )
    op.execute(
        "GRANT SELECT (id,company_id,branch_id,employee_id,policy_id,expiry_date,tier_name) ON TABLE public.employee_insurance TO workloop_expiry_processing"
    )
    op.execute(
        "GRANT SELECT (company_id,branch_id,recipient_app_user_id,type,related_entity_type,related_entity_id), INSERT (company_id,branch_id,created_by_app_user_id,recipient_app_user_id,type,title,body,related_entity_type,related_entity_id) ON TABLE public.notifications TO workloop_expiry_processing"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT ON TABLE public.employee_documents, public.insurance_policies, public.employee_insurance, public.notifications FROM workloop_expiry_processing"
    )
    op.execute("REVOKE INSERT ON TABLE public.notifications FROM workloop_expiry_processing")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.create_workflow_notification(text, text) FROM workloop_runtime"
    )
    op.execute("DROP FUNCTION public.create_workflow_notification(text, text)")
    op.execute("GRANT INSERT, UPDATE ON TABLE public.notifications TO workloop_runtime")
    op.execute(
        "REVOKE DELETE ON TABLE public.employee_documents, public.insurance_policies, public.insurance_dependants FROM workloop_runtime"
    )
    for table in reversed(RLS_TABLES):
        for suffix in (
            "insert_expiry",
            "select_expiry",
            "delete_runtime",
            "update_runtime",
            "insert_runtime",
            "select_runtime",
        ):
            op.execute(f"DROP POLICY IF EXISTS phase5g_{table}_{suffix} ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
