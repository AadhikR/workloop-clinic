"""Close Phase 5H authorization and audit findings.

Revision ID: 2c4d6e8f0a1b
Revises: 1b29d4e7f860
Created: 2026-09-07 00:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

revision: str = "2c4d6e8f0a1b"
down_revision: str | Sequence[str] | None = "1b29d4e7f860"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text, text, uuid, text[], text, jsonb)"
PRIVATE_AUDIT_SIGNATURE = (
    "public._append_audit_event_phase5g(text, text, uuid, text[], text, jsonb)"
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
    AND principal.profile_company_id = public.workloop_company_id()
    AND principal.company_id = principal.profile_company_id
    AND principal.role = public.workloop_role()
    AND (
      (principal.role = 'admin'
       AND principal.profile_employee_id IS NULL
       AND principal.employee_id IS NULL
       AND principal.branch_id IS NULL
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


def _replace_appraisal_policy() -> None:
    report = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'manager'
AND appraisal_sections.company_id = public.workloop_company_id()
AND appraisal_sections.branch_id = public.workloop_branch_id()
AND EXISTS (
  SELECT 1
  FROM public.appraisals AS appraisal
  JOIN public.employees AS target
    ON target.id = appraisal.employee_id
   AND target.company_id = appraisal.company_id
   AND target.branch_id = appraisal.branch_id
  WHERE appraisal.id = appraisal_sections.appraisal_id
    AND appraisal.employee_id <> public.workloop_employee_id()
    AND target.reporting_manager_id = public.workloop_employee_id()
)"""
    admin = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND appraisal_sections.company_id = public.workloop_company_id()
AND appraisal_sections.branch_id = public.workloop_branch_id()"""
    op.execute(
        "ALTER POLICY phase5g_appraisal_sections_update_runtime ON public.appraisal_sections "
        "RENAME TO phase5h_prior_appraisal_sections_update_runtime"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_appraisal_sections_update_runtime "
        "ON public.appraisal_sections TO workloop_migration"
    )
    op.execute(
        "CREATE POLICY phase5g_appraisal_sections_update_runtime "
        "ON public.appraisal_sections FOR UPDATE TO workloop_runtime "
        f"USING (({admin}) OR ({report})) WITH CHECK (({admin}) OR ({report}))"
    )


def _remove_unsupported_deletes() -> None:
    op.execute(
        "ALTER POLICY phase5g_offboarding_tasks_delete_runtime ON public.offboarding_tasks "
        "RENAME TO phase5h_prior_offboarding_tasks_delete_runtime"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_offboarding_tasks_delete_runtime "
        "ON public.offboarding_tasks TO workloop_migration"
    )
    op.execute("REVOKE DELETE ON TABLE public.offboarding_tasks FROM workloop_runtime")


def _replace_notification_policies() -> None:
    op.execute(
        "ALTER POLICY phase5g_notifications_select_runtime ON public.notifications "
        "RENAME TO phase5h_prior_notifications_select_runtime"
    )
    op.execute(
        "ALTER POLICY phase5g_notifications_update_runtime ON public.notifications "
        "RENAME TO phase5h_prior_notifications_update_runtime"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_notifications_select_runtime ON public.notifications "
        "TO workloop_migration"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_notifications_update_runtime ON public.notifications "
        "TO workloop_migration"
    )
    recipient = f"""{HUMAN_CONTEXT}
AND recipient_app_user_id = public.workloop_app_user_id()
AND company_id = public.workloop_company_id()
AND ((public.workloop_role() = 'admin'
      AND public.workloop_branch_id() IS NOT NULL
      AND (branch_id IS NULL OR branch_id = public.workloop_branch_id()))
 OR (public.workloop_role() IN ('manager', 'employee')
      AND branch_id = public.workloop_branch_id()))"""
    op.execute(
        "CREATE POLICY phase5g_notifications_select_runtime ON public.notifications "
        f"FOR SELECT TO workloop_runtime USING ({recipient})"
    )
    op.execute(
        "CREATE POLICY phase5g_notifications_update_runtime ON public.notifications "
        f"FOR UPDATE TO workloop_runtime USING ({recipient}) WITH CHECK ({recipient})"
    )

    op.execute(
        "ALTER POLICY phase5g_notifications_select_expiry ON public.notifications "
        "RENAME TO phase5h_prior_notifications_select_expiry"
    )
    op.execute(
        "ALTER POLICY phase5g_notifications_insert_expiry ON public.notifications "
        "RENAME TO phase5h_prior_notifications_insert_expiry"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_notifications_select_expiry ON public.notifications "
        "TO workloop_migration"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_notifications_insert_expiry ON public.notifications "
        "TO workloop_migration"
    )
    job = """
current_user = 'workloop_expiry_processing'
AND session_user = 'workloop_expiry_processing'
AND public.workloop_actor_kind() = 'scheduled_job'
AND public.workloop_actor_key() = 'expiry_processing'
AND public.workloop_business_date() IS NOT NULL
AND company_id = public.workloop_company_id()
AND ((public.workloop_branch_id() IS NULL AND branch_id IS NULL)
 OR branch_id = public.workloop_branch_id())
AND created_by_app_user_id IS NULL
AND type IN ('document_expiry','clinical_credential_expiry','insurance_expiry',
  'probation_ending','contract_expiry','cert_expiry','clinical_licence_expiry','policy_renewal')
""".strip()
    op.execute(
        "CREATE POLICY phase5g_notifications_select_expiry ON public.notifications "
        f"FOR SELECT TO workloop_expiry_processing USING ({job})"
    )
    source_match = """
pg_catalog.pg_input_is_valid(split_part(related_entity_id, ':', 1), 'uuid')
AND CASE type
  WHEN 'document_expiry' THEN
    (related_entity_type = 'employee_document' AND EXISTS (
      SELECT 1 FROM public.employee_documents AS source
      JOIN public.employees AS employee ON employee.id = source.employee_id
        AND employee.company_id = source.company_id AND employee.branch_id = source.branch_id
      WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
        AND source.company_id = notifications.company_id
        AND source.branch_id = notifications.branch_id AND source.status = 'verified'
        AND source.document_type NOT IN ('DHA Licence','DOH Licence','MOH Licence',
          'BLS Certificate','ACLS Certificate','PALS Certificate','NRP Certificate','CME Certificate')
        AND employee.active AND employee.employment_status <> 'Terminated'
        AND source.expiry_date BETWEEN public.workloop_business_date()
          AND public.workloop_business_date() + 60
        AND related_entity_id = source.id::text || ':document:' || CASE
          WHEN source.expiry_date <= public.workloop_business_date() + 14 THEN '14'
          WHEN source.expiry_date <= public.workloop_business_date() + 30 THEN '30'
          ELSE '60' END))
    OR (related_entity_type = 'employee' AND EXISTS (
      SELECT 1 FROM public.employees AS source
      WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
        AND source.company_id = notifications.company_id
        AND source.branch_id = notifications.branch_id AND source.active
        AND source.employment_status <> 'Terminated'
        AND ((source.visa_expiry BETWEEN public.workloop_business_date()
              AND public.workloop_business_date() + 60
              AND related_entity_id = source.id::text || ':visa:' || CASE
                WHEN source.visa_expiry <= public.workloop_business_date() + 14 THEN '14'
                WHEN source.visa_expiry <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
          OR (source.passport_expiry BETWEEN public.workloop_business_date()
              AND public.workloop_business_date() + 60
              AND related_entity_id = source.id::text || ':passport:' || CASE
                WHEN source.passport_expiry <= public.workloop_business_date() + 14 THEN '14'
                WHEN source.passport_expiry <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
          OR (source.emirates_id_expiry BETWEEN public.workloop_business_date()
              AND public.workloop_business_date() + 60
              AND related_entity_id = source.id::text || ':emirates_id:' || CASE
                WHEN source.emirates_id_expiry <= public.workloop_business_date() + 14 THEN '14'
                WHEN source.emirates_id_expiry <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
          OR (source.labour_card_expiry BETWEEN public.workloop_business_date()
              AND public.workloop_business_date() + 60
              AND related_entity_id = source.id::text || ':labour_card:' || CASE
                WHEN source.labour_card_expiry <= public.workloop_business_date() + 14 THEN '14'
                WHEN source.labour_card_expiry <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END))))
  WHEN 'clinical_credential_expiry' THEN related_entity_type = 'employee_document' AND EXISTS (
    SELECT 1 FROM public.employee_documents AS source
    JOIN public.employees AS employee ON employee.id = source.employee_id
      AND employee.company_id = source.company_id AND employee.branch_id = source.branch_id
    WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
      AND source.company_id = notifications.company_id
      AND source.branch_id = notifications.branch_id AND source.status = 'verified'
      AND source.document_type IN ('DHA Licence','DOH Licence','MOH Licence',
        'BLS Certificate','ACLS Certificate','PALS Certificate','NRP Certificate','CME Certificate')
      AND employee.active AND employee.employment_status <> 'Terminated'
      AND source.expiry_date BETWEEN public.workloop_business_date()
        AND public.workloop_business_date() + 90
      AND related_entity_id = source.id::text || ':clinical:' || CASE
        WHEN source.expiry_date <= public.workloop_business_date() + 14 THEN '14'
        WHEN source.expiry_date <= public.workloop_business_date() + 30 THEN '30' ELSE '90' END)
  WHEN 'cert_expiry' THEN related_entity_type = 'certification' AND EXISTS (
    SELECT 1 FROM public.certifications AS source
    JOIN public.employees AS employee ON employee.id = source.employee_id
      AND employee.company_id = source.company_id AND employee.branch_id = source.branch_id
    WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
      AND source.company_id = notifications.company_id
      AND source.branch_id = notifications.branch_id AND source.status = 'verified'
      AND employee.active AND employee.employment_status <> 'Terminated'
      AND source.expiry_date BETWEEN public.workloop_business_date()
        AND public.workloop_business_date() + 60
      AND related_entity_id = source.id::text || ':certification:' || CASE
        WHEN source.expiry_date <= public.workloop_business_date() + 14 THEN '14'
        WHEN source.expiry_date <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
  WHEN 'insurance_expiry' THEN related_entity_type = 'employee_insurance' AND EXISTS (
    SELECT 1 FROM public.employee_insurance AS source
    JOIN public.employees AS employee ON employee.id = source.employee_id
      AND employee.company_id = source.company_id AND employee.branch_id = source.branch_id
    WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
      AND source.company_id = notifications.company_id
      AND source.branch_id = notifications.branch_id
      AND employee.active AND employee.employment_status <> 'Terminated'
      AND source.expiry_date BETWEEN public.workloop_business_date()
        AND public.workloop_business_date() + 60
      AND related_entity_id = source.id::text || ':insurance:' || CASE
        WHEN source.expiry_date <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
  WHEN 'probation_ending' THEN related_entity_type = 'employee' AND EXISTS (
    SELECT 1 FROM public.employees AS source
    WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
      AND source.company_id = notifications.company_id
      AND source.branch_id = notifications.branch_id AND source.active
      AND source.employment_status = 'Probation'
      AND source.probation_end_date BETWEEN public.workloop_business_date()
        AND public.workloop_business_date() + 14
      AND related_entity_id = source.id::text || ':probation:' || CASE
        WHEN source.probation_end_date <= public.workloop_business_date() + 7 THEN '7' ELSE '14' END)
  WHEN 'contract_expiry' THEN related_entity_type = 'employee' AND EXISTS (
    SELECT 1 FROM public.employees AS source
    WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
      AND source.company_id = notifications.company_id
      AND source.branch_id = notifications.branch_id AND source.active
      AND source.employment_status <> 'Terminated' AND source.contract_type = 'Limited'
      AND source.contract_end_date BETWEEN public.workloop_business_date()
        AND public.workloop_business_date() + 60
      AND related_entity_id = source.id::text || ':contract:' || CASE
        WHEN source.contract_end_date <= public.workloop_business_date() + 7 THEN '7'
        WHEN source.contract_end_date <= public.workloop_business_date() + 14 THEN '14'
        WHEN source.contract_end_date <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
  WHEN 'clinical_licence_expiry' THEN related_entity_type = 'employee' AND EXISTS (
    SELECT 1 FROM public.employees AS source
    WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
      AND source.company_id = notifications.company_id
      AND source.branch_id = notifications.branch_id AND source.active
      AND source.employment_status <> 'Terminated'
      AND source.licence_authority IS NOT NULL AND source.licence_authority <> 'None'
      AND source.licence_expiry BETWEEN public.workloop_business_date()
        AND public.workloop_business_date() + 60
      AND related_entity_id = source.id::text || ':licence:' || CASE
        WHEN source.licence_expiry <= public.workloop_business_date() + 14 THEN '14'
        WHEN source.licence_expiry <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
  WHEN 'policy_renewal' THEN related_entity_type = 'insurance_policy' AND EXISTS (
    SELECT 1 FROM public.insurance_policies AS source
    WHERE source.id = split_part(related_entity_id, ':', 1)::uuid
      AND source.company_id = notifications.company_id
      AND source.branch_id = notifications.branch_id
      AND source.renewal_date BETWEEN public.workloop_business_date()
        AND public.workloop_business_date() + 60
      AND related_entity_id = source.id::text || ':policy:' || CASE
        WHEN source.renewal_date <= public.workloop_business_date() + 30 THEN '30' ELSE '60' END)
  ELSE false
END
""".strip()
    op.execute(
        "CREATE POLICY phase5g_notifications_insert_expiry ON public.notifications "
        "FOR INSERT TO workloop_expiry_processing WITH CHECK ("
        f"{job} AND {source_match} "
        "AND EXISTS (SELECT 1 FROM public.user_profiles AS profile "
        "JOIN public.app_users AS account ON account.id=profile.app_user_id "
        "WHERE profile.app_user_id=notifications.recipient_app_user_id "
        "AND profile.company_id=notifications.company_id "
        "AND profile.role='admin' AND profile.employee_id IS NULL "
        "AND account.status='active') "
        "AND title = CASE type "
        "WHEN 'document_expiry' THEN 'Document expiring' "
        "WHEN 'clinical_credential_expiry' THEN 'Clinical credential expiring' "
        "WHEN 'insurance_expiry' THEN 'Insurance expiring' "
        "WHEN 'probation_ending' THEN 'Probation ending' "
        "WHEN 'contract_expiry' THEN 'Contract expiring' "
        "WHEN 'cert_expiry' THEN 'Certification expiring' "
        "WHEN 'clinical_licence_expiry' THEN 'Clinical licence expiring' "
        "WHEN 'policy_renewal' THEN 'Policy renewal due' END "
        "AND body = 'Review this expiry item.'"
        ")"
    )


def _replace_notification_function() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.create_workflow_notification(text, text) "
        "FROM workloop_runtime"
    )
    op.execute(
        "ALTER FUNCTION public.create_workflow_notification(text, text) "
        "RENAME TO _create_workflow_notification_phase5g"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public._create_workflow_notification_phase5g(text, text) "
        "FROM PUBLIC"
    )
    op.execute(r"""
CREATE FUNCTION public.create_workflow_notification(p_type text, p_related_entity_id text)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  source_id uuid; source_company uuid; source_branch uuid; source_employee uuid;
  recipient_id uuid; notification_id uuid; entity_type text;
  notification_title text; notification_body text;
BEGIN
  IF session_user <> 'workloop_runtime'
     OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
     OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL
     OR public.workloop_company_id() IS NULL
     OR public.workloop_branch_id() IS NULL THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id = public.workloop_app_user_id()
      AND caller.account_status = 'active'
      AND caller.profile_app_user_id = caller.app_user_id
      AND caller.profile_company_id = public.workloop_company_id()
      AND caller.company_id = caller.profile_company_id
      AND caller.role = public.workloop_role()
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
    JOIN public.employees AS employee ON employee.id=request.employee_id
      AND employee.company_id=request.company_id AND employee.branch_id=request.branch_id
    WHERE request.id=source_id AND request.company_id=public.workloop_company_id()
      AND request.branch_id=public.workloop_branch_id()
      AND ((p_type='leave_approved' AND request.status='Approved')
        OR (p_type='leave_rejected' AND request.status IN ('Rejected','ManagerRejected')))
      AND (public.workloop_role()='admin'
        OR (public.workloop_role()='manager'
            AND request.employee_id <> public.workloop_employee_id()
            AND employee.reporting_manager_id=public.workloop_employee_id())
        OR (request.employee_id <> public.workloop_employee_id()
            AND public.can_act_for_delegated_leave(request.employee_id)));
    entity_type := 'leave_request';
    notification_title := CASE p_type WHEN 'leave_approved' THEN 'Leave approved' ELSE 'Leave rejected' END;
    notification_body := CASE p_type WHEN 'leave_approved' THEN 'Your leave request was approved.' ELSE 'Your leave request was rejected.' END;
  ELSIF p_type = 'payslip_available' THEN
    SELECT payslip.company_id,payslip.branch_id,payslip.employee_id
      INTO source_company,source_branch,source_employee
    FROM public.payslips AS payslip
    WHERE payslip.id=source_id AND payslip.company_id=public.workloop_company_id()
      AND payslip.branch_id=public.workloop_branch_id() AND public.workloop_role()='admin';
    entity_type := 'payslip'; notification_title := 'Payslip available';
    notification_body := 'Your payslip is available.';
  ELSIF p_type = 'roster_published' THEN
    SELECT roster.company_id,roster.branch_id,roster.employee_id
      INTO source_company,source_branch,source_employee
    FROM public.roster_assignments AS roster
    WHERE roster.id=source_id AND roster.company_id=public.workloop_company_id()
      AND roster.branch_id=public.workloop_branch_id() AND roster.published
      AND public.workloop_role()='admin';
    entity_type := 'roster_assignment'; notification_title := 'Roster published';
    notification_body := 'Your roster was published.';
  ELSE
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END IF;
  IF source_employee IS NULL THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE = '42501';
  END IF;
  SELECT profile.app_user_id INTO STRICT recipient_id
  FROM public.user_profiles AS profile
  JOIN public.app_users AS account ON account.id=profile.app_user_id
  JOIN public.employees AS employee ON employee.id=profile.employee_id
    AND employee.company_id=profile.company_id
  JOIN public.branches AS branch ON branch.id=employee.branch_id
    AND branch.company_id=employee.company_id
  WHERE profile.employee_id=source_employee AND profile.company_id=source_company
    AND employee.branch_id=source_branch AND employee.active
    AND employee.employment_status IN ('Active','Probation','On Leave')
    AND account.status='active';
  INSERT INTO public.notifications(company_id,branch_id,created_by_app_user_id,
    recipient_app_user_id,type,title,body,related_entity_type,related_entity_id)
  VALUES(source_company,source_branch,public.workloop_app_user_id(),recipient_id,
    p_type,notification_title,notification_body,entity_type,source_id::text)
  ON CONFLICT(company_id,recipient_app_user_id,type,related_entity_type,related_entity_id)
  DO NOTHING RETURNING id INTO notification_id;
  IF notification_id IS NULL THEN
    SELECT id INTO notification_id FROM public.notifications
    WHERE company_id=source_company AND recipient_app_user_id=recipient_id
      AND type=p_type AND related_entity_type=entity_type
      AND related_entity_id=source_id::text;
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


def _wrap_audit_function() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text, text, uuid, text[], text, jsonb) "
        "RENAME TO _append_audit_event_phase5g"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {PRIVATE_AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(r"""
CREATE FUNCTION public.append_audit_event(
  p_action text, p_entity_type text, p_entity_id uuid, p_changed_fields text[],
  p_reason text, p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE event_id uuid;
BEGIN
  IF session_user <> 'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR public.workloop_app_user_id() IS NULL
    OR public.workloop_company_id() IS NULL
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
  IF p_action IN ('role_changed','employment_access_changed',
      'employee_branch_corrected','payroll_wps_changed') THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action IN ('branch_created','branch_deleted') THEN
    IF public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
      OR NOT ((p_action='branch_created' AND public.workloop_branch_id() IS NULL)
        OR (p_action='branch_deleted' AND public.workloop_branch_id()=p_entity_id))
      OR p_entity_type<>'branch'
      OR p_changed_fields IS DISTINCT FROM ARRAY['id']::text[]
      OR p_reason IS NULL OR btrim(p_reason)=''
      OR COALESCE(p_metadata,'{}'::jsonb) <> '{}'::jsonb
      OR NOT EXISTS (SELECT 1 FROM public.branches AS branch
        WHERE branch.id=p_entity_id AND branch.company_id=public.workloop_company_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
    INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
      system_actor_key,initiated_by_app_user_id,action,entity_type,entity_id,
      changed_fields,reason,metadata)
    VALUES(public.workloop_company_id(),NULL,'human',public.workloop_app_user_id(),
      NULL,NULL,p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,'{}'::jsonb)
    RETURNING id INTO event_id;
    RETURN event_id;
  END IF;
  RETURN public._append_audit_event_phase5g(
    p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
END
$function$
""")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def _tighten_audit_table() -> None:
    op.execute(
        "ALTER TABLE public.audit_events RENAME CONSTRAINT ck_audit_events_primary_actor "
        "TO phase5h_prior_audit_primary_actor"
    )
    op.execute("""
ALTER TABLE public.audit_events ADD CONSTRAINT ck_audit_events_primary_actor CHECK (
  (actor_kind='human' AND actor_app_user_id IS NOT NULL AND system_actor_key IS NULL)
  OR (actor_kind<>'human' AND actor_app_user_id IS NULL
      AND system_actor_key IS NOT NULL AND btrim(system_actor_key)<>'')
)
""")
    op.execute(
        "ALTER POLICY phase5g_audit_events_select_runtime ON public.audit_events "
        "RENAME TO phase5h_prior_audit_events_select_runtime"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_audit_events_select_runtime ON public.audit_events "
        "TO workloop_migration"
    )
    op.execute("""
CREATE POLICY phase5g_audit_events_select_runtime ON public.audit_events
FOR SELECT TO workloop_runtime USING (
  current_user='workloop_runtime' AND session_user='workloop_runtime'
  AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
  AND public.workloop_business_date() IS NOT NULL
  AND public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL
  AND company_id=public.workloop_company_id()
  AND ((branch_id IS NULL AND public.workloop_branch_id() IS NULL)
    OR branch_id=public.workloop_branch_id())
  AND EXISTS (SELECT 1 FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id=public.workloop_app_user_id()
      AND caller.account_status='active' AND caller.profile_app_user_id=caller.app_user_id
      AND caller.role='admin' AND caller.profile_employee_id IS NULL
      AND caller.employee_id IS NULL AND caller.branch_id IS NULL
      AND caller.profile_company_id=audit_events.company_id
      AND caller.company_id=caller.profile_company_id)
)
""")
    op.execute(
        "ALTER POLICY phase5g_audit_events_insert_expiry ON public.audit_events "
        "RENAME TO phase5h_prior_audit_events_insert_expiry"
    )
    op.execute(
        "ALTER POLICY phase5h_prior_audit_events_insert_expiry ON public.audit_events "
        "TO workloop_migration"
    )
    op.execute("""
CREATE POLICY phase5g_audit_events_insert_expiry ON public.audit_events
FOR INSERT TO workloop_expiry_processing WITH CHECK (
  current_user='workloop_expiry_processing' AND session_user='workloop_expiry_processing'
  AND public.workloop_actor_kind()='scheduled_job'
  AND public.workloop_actor_key()='expiry_processing'
  AND public.workloop_business_date() IS NOT NULL
  AND company_id=public.workloop_company_id()
  AND ((branch_id IS NULL AND public.workloop_branch_id() IS NULL)
    OR branch_id=public.workloop_branch_id())
  AND actor_kind='scheduled_job' AND actor_app_user_id IS NULL
  AND system_actor_key='expiry_processing' AND initiated_by_app_user_id IS NULL
  AND action='expiry_notification_created'
  AND entity_type IN ('employee_document','certification','employee_insurance',
    'employee','insurance_policy')
  AND changed_fields=ARRAY['type','recipient_app_user_id']::text[]
  AND reason='Expiry notification created'
  AND jsonb_typeof(metadata)='object'
  AND metadata ? 'threshold_days' AND metadata ? 'source_date'
  AND metadata ? 'recipient_app_user_id' AND metadata ? 'source_kind'
  AND pg_catalog.pg_input_is_valid(metadata->>'recipient_app_user_id','uuid')
  AND pg_catalog.pg_input_is_valid(metadata->>'source_date','date')
  AND jsonb_typeof(metadata->'threshold_days')='number'
  AND (metadata->>'threshold_days')::integer IN (7,14,30,60,90)
  AND metadata->>'source_kind' IN ('document','clinical','certification','insurance',
    'probation','contract','licence','policy','visa','passport','emirates_id','labour_card')
  AND NOT EXISTS (SELECT 1 FROM jsonb_object_keys(metadata) AS key
    WHERE key <> ALL(ARRAY['threshold_days','source_date','recipient_app_user_id','source_kind']::text[]))
  AND EXISTS (SELECT 1 FROM public.notifications AS notification
    WHERE notification.company_id=audit_events.company_id
      AND notification.branch_id IS NOT DISTINCT FROM audit_events.branch_id
      AND notification.recipient_app_user_id=(metadata->>'recipient_app_user_id')::uuid
      AND notification.related_entity_type=audit_events.entity_type
      AND notification.related_entity_id=audit_events.entity_id::text || ':' ||
        (metadata->>'source_kind') || ':' || (metadata->>'threshold_days')
      AND notification.type=CASE metadata->>'source_kind'
        WHEN 'document' THEN 'document_expiry'
        WHEN 'clinical' THEN 'clinical_credential_expiry'
        WHEN 'certification' THEN 'cert_expiry'
        WHEN 'insurance' THEN 'insurance_expiry'
        WHEN 'probation' THEN 'probation_ending'
        WHEN 'contract' THEN 'contract_expiry'
        WHEN 'licence' THEN 'clinical_licence_expiry'
        WHEN 'policy' THEN 'policy_renewal'
        ELSE 'document_expiry' END)
  AND CASE entity_type
    WHEN 'employee_document' THEN EXISTS (SELECT 1 FROM public.employee_documents AS source
      WHERE source.id=audit_events.entity_id
        AND source.expiry_date=(metadata->>'source_date')::date
        AND metadata->>'source_kind' IN ('document','clinical'))
    WHEN 'certification' THEN EXISTS (SELECT 1 FROM public.certifications AS source
      WHERE source.id=audit_events.entity_id
        AND source.expiry_date=(metadata->>'source_date')::date
        AND metadata->>'source_kind'='certification')
    WHEN 'employee_insurance' THEN EXISTS (SELECT 1 FROM public.employee_insurance AS source
      WHERE source.id=audit_events.entity_id
        AND source.expiry_date=(metadata->>'source_date')::date
        AND metadata->>'source_kind'='insurance')
    WHEN 'insurance_policy' THEN EXISTS (SELECT 1 FROM public.insurance_policies AS source
      WHERE source.id=audit_events.entity_id
        AND source.renewal_date=(metadata->>'source_date')::date
        AND metadata->>'source_kind'='policy')
    WHEN 'employee' THEN EXISTS (SELECT 1 FROM public.employees AS source
      WHERE source.id=audit_events.entity_id AND CASE metadata->>'source_kind'
        WHEN 'probation' THEN source.probation_end_date
        WHEN 'contract' THEN source.contract_end_date
        WHEN 'licence' THEN source.licence_expiry
        WHEN 'visa' THEN source.visa_expiry
        WHEN 'passport' THEN source.passport_expiry
        WHEN 'emirates_id' THEN source.emirates_id_expiry
        WHEN 'labour_card' THEN source.labour_card_expiry END
          = (metadata->>'source_date')::date)
    ELSE false
  END
)
""")


def _lock_shift_swap_employees() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.admin_execute_shift_swap(uuid, uuid) "
        "FROM workloop_runtime"
    )
    op.execute(
        "ALTER FUNCTION public.admin_execute_shift_swap(uuid, uuid) "
        "RENAME TO _admin_execute_shift_swap_phase5g"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public._admin_execute_shift_swap_phase5g(uuid, uuid) FROM PUBLIC"
    )
    op.execute(r"""
DO $block$
DECLARE prior_definition text; next_definition text;
BEGIN
  SELECT pg_catalog.pg_get_functiondef(
    'public._admin_execute_shift_swap_phase5g(uuid,uuid)'::regprocedure)
    INTO prior_definition;
  next_definition := pg_catalog.replace(prior_definition,
    'CREATE OR REPLACE FUNCTION public._admin_execute_shift_swap_phase5g(',
    'CREATE FUNCTION public.admin_execute_shift_swap(');
  next_definition := pg_catalog.replace(next_definition,
    '  v_tgt_row public.roster_assignments%ROWTYPE;',
    '  v_tgt_row public.roster_assignments%ROWTYPE;' || E'\n  v_employee_count integer;');
  next_definition := pg_catalog.replace(next_definition,
    E'  IF v_swap.requester_employee_id = v_swap.target_employee_id THEN\n    RAISE EXCEPTION ''shift_swap_same_employee'';\n  END IF;',
    E'  IF v_swap.requester_employee_id = v_swap.target_employee_id THEN\n    RAISE EXCEPTION ''shift_swap_same_employee'';\n  END IF;\n\n  PERFORM employee.id FROM public.employees AS employee\n  WHERE employee.id IN (v_swap.requester_employee_id,v_swap.target_employee_id)\n    AND employee.company_id=v_swap.company_id AND employee.branch_id=v_swap.branch_id\n  ORDER BY employee.id FOR UPDATE;\n  GET DIAGNOSTICS v_employee_count = ROW_COUNT;\n  IF v_employee_count <> 2 OR EXISTS (SELECT 1 FROM public.employees AS employee\n    WHERE employee.id IN (v_swap.requester_employee_id,v_swap.target_employee_id)\n      AND (NOT employee.active OR employee.employment_status NOT IN (''Active'',''Probation'',''On Leave''))) THEN\n    RAISE EXCEPTION ''shift_swap_employee_ineligible'';\n  END IF;');
  IF next_definition=prior_definition THEN
    RAISE EXCEPTION 'shift swap employee locking did not match protected function';
  END IF;
  EXECUTE next_definition;
END
$block$
""")
    op.execute(
        "ALTER FUNCTION public.admin_execute_shift_swap(uuid, uuid) OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public.admin_execute_shift_swap(uuid, uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.admin_execute_shift_swap(uuid, uuid) TO workloop_runtime"
    )


def _create_relationship_lock_function() -> None:
    op.execute(r"""
CREATE FUNCTION public.lock_authorized_employee_relationships(p_employee_ids uuid[])
RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE expected_count integer;
BEGIN
  expected_count := cardinality(p_employee_ids);
  IF session_user<>'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR expected_count IS NULL OR expected_count<1 OR expected_count>100
    OR (SELECT count(DISTINCT value) FROM unnest(p_employee_ids) AS value)<>expected_count
    OR array_position(p_employee_ids,NULL) IS NOT NULL
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
              AND public.workloop_employee_id() IS NULL
              AND public.workloop_branch_id() IS NOT NULL)
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
    RAISE EXCEPTION 'employee relationship lock denied' USING ERRCODE='42501';
  END IF;
  PERFORM delegation.id FROM public.leave_approval_delegates AS delegation
  WHERE delegation.company_id=public.workloop_company_id()
    AND delegation.branch_id=public.workloop_branch_id()
    AND delegation.delegate_employee_id=public.workloop_employee_id()
    AND delegation.from_date<=public.workloop_business_date()
    AND delegation.to_date>=public.workloop_business_date()
  ORDER BY delegation.id FOR UPDATE;
  PERFORM employee.id FROM public.employees AS employee
  WHERE employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id()
    AND (employee.id=ANY(p_employee_ids) OR employee.id IN (
      SELECT delegation.approver_employee_id
      FROM public.leave_approval_delegates AS delegation
      WHERE delegation.company_id=public.workloop_company_id()
        AND delegation.branch_id=public.workloop_branch_id()
        AND delegation.delegate_employee_id=public.workloop_employee_id()
        AND delegation.from_date<=public.workloop_business_date()
        AND delegation.to_date>=public.workloop_business_date()))
  ORDER BY employee.id FOR UPDATE;
  IF EXISTS (
    SELECT 1 FROM unnest(p_employee_ids) AS requested(id)
    WHERE NOT EXISTS (SELECT 1 FROM public.employees AS employee
      WHERE employee.id=requested.id
        AND employee.company_id=public.workloop_company_id()
        AND employee.branch_id=public.workloop_branch_id()
        AND (public.workloop_role()='admin'
          OR (employee.id<>public.workloop_employee_id()
            AND employee.reporting_manager_id=public.workloop_employee_id())
          OR (employee.id<>public.workloop_employee_id() AND EXISTS (
            SELECT 1 FROM public.leave_approval_delegates AS delegation
            JOIN public.employees AS approver
              ON approver.id=delegation.approver_employee_id
             AND approver.company_id=delegation.company_id
             AND approver.branch_id=delegation.branch_id
            JOIN public.user_profiles AS profile
              ON profile.employee_id=approver.id
             AND profile.company_id=delegation.company_id
             AND profile.role='manager'
            JOIN public.app_users AS account
              ON account.id=profile.app_user_id AND account.status='active'
            WHERE delegation.company_id=public.workloop_company_id()
              AND delegation.branch_id=public.workloop_branch_id()
              AND delegation.delegate_employee_id=public.workloop_employee_id()
              AND delegation.from_date<=public.workloop_business_date()
              AND delegation.to_date>=public.workloop_business_date()
              AND approver.active
              AND approver.employment_status IN ('Active','Probation','On Leave')
              AND employee.reporting_manager_id=approver.id))))) THEN
    RAISE EXCEPTION 'employee relationship lock denied' USING ERRCODE='42501';
  END IF;
END
$function$
""")
    signature = "public.lock_authorized_employee_relationships(uuid[])"
    op.execute(f"ALTER FUNCTION {signature} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO workloop_runtime")


def _set_repayment_payroll_lock(*, enabled: bool) -> None:
    if not enabled:
        op.execute("DROP FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date)")
        op.execute(
            "ALTER FUNCTION public._record_advance_repayment_phase5g(uuid,uuid,uuid,numeric,date) "
            "RENAME TO record_advance_repayment"
        )
        op.execute(
            "ALTER FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
            "OWNER TO workloop_migration"
        )
        op.execute(
            "REVOKE ALL ON FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
            "FROM PUBLIC"
        )
        op.execute(
            "GRANT EXECUTE ON FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
            "TO workloop_runtime"
        )
        return
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
        "FROM workloop_runtime"
    )
    op.execute(
        "ALTER FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
        "RENAME TO _record_advance_repayment_phase5g"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public._record_advance_repayment_phase5g(uuid,uuid,uuid,numeric,date) "
        "FROM PUBLIC"
    )
    source = "FROM public.payroll_runs WHERE id = p_payroll_run_id"
    unlocked = f"{source};"
    locked = f"{source} FOR UPDATE;"
    before = unlocked if enabled else locked
    after = locked if enabled else unlocked
    op.execute(
        f"""
DO $block$
DECLARE prior_definition text; next_definition text;
BEGIN
  SELECT pg_catalog.pg_get_functiondef(
    'public._record_advance_repayment_phase5g(uuid,uuid,uuid,numeric,date)'::regprocedure)
    INTO prior_definition;
  next_definition := pg_catalog.replace(prior_definition,
    'CREATE OR REPLACE FUNCTION public._record_advance_repayment_phase5g(',
    'CREATE FUNCTION public.record_advance_repayment(');
  next_definition := pg_catalog.replace(next_definition, '{before}', '{after}');
  IF next_definition=prior_definition AND {str(enabled).lower()} THEN
    RAISE EXCEPTION 'advance repayment payroll lock replacement did not match protected function';
  ELSIF next_definition<>prior_definition THEN
    EXECUTE next_definition;
  END IF;
END
$block$
"""
    )
    op.execute(
        "ALTER FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
        "OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
        "FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.record_advance_repayment(uuid,uuid,uuid,numeric,date) "
        "TO workloop_runtime"
    )


def upgrade() -> None:
    _create_relationship_lock_function()
    _replace_appraisal_policy()
    _remove_unsupported_deletes()
    _replace_notification_policies()
    _replace_notification_function()
    _wrap_audit_function()
    _tighten_audit_table()
    _lock_shift_swap_employees()
    _set_repayment_payroll_lock(enabled=True)


def _restore_phase5g_policies() -> None:
    op.execute("DROP POLICY phase5g_appraisal_sections_update_runtime ON public.appraisal_sections")
    section_admin = f"""{HUMAN_CONTEXT}
AND public.workloop_role()='admin'
AND appraisal_sections.company_id=public.workloop_company_id()
AND appraisal_sections.branch_id=public.workloop_branch_id()"""
    section_staff = f"""{HUMAN_CONTEXT}
AND appraisal_sections.company_id=public.workloop_company_id()
AND appraisal_sections.branch_id=public.workloop_branch_id()
AND EXISTS (SELECT 1 FROM public.appraisals AS appraisal
 JOIN public.employees AS target ON target.id=appraisal.employee_id
  AND target.company_id=appraisal.company_id AND target.branch_id=appraisal.branch_id
 WHERE appraisal.id=appraisal_sections.appraisal_id
  AND (appraisal.employee_id=public.workloop_employee_id()
   OR (public.workloop_role()='manager'
    AND target.reporting_manager_id=public.workloop_employee_id())))"""
    op.execute(
        "CREATE POLICY phase5g_appraisal_sections_update_runtime "
        "ON public.appraisal_sections FOR UPDATE TO workloop_runtime "
        f"USING (({section_admin}) OR ({section_staff})) "
        f"WITH CHECK (({section_admin}) OR ({section_staff}))"
    )
    offboarding_admin = f"""{HUMAN_CONTEXT}
AND public.workloop_role()='admin'
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()"""
    op.execute("GRANT DELETE ON TABLE public.offboarding_tasks TO workloop_runtime")
    op.execute(
        "CREATE POLICY phase5g_offboarding_tasks_delete_runtime ON public.offboarding_tasks "
        f"FOR DELETE TO workloop_runtime USING ({offboarding_admin} AND NOT completed)"
    )

    for name in (
        "phase5g_notifications_select_runtime",
        "phase5g_notifications_update_runtime",
        "phase5g_notifications_select_expiry",
        "phase5g_notifications_insert_expiry",
    ):
        op.execute(f"DROP POLICY {name} ON public.notifications")
    recipient = f"""{HUMAN_CONTEXT}
AND recipient_app_user_id=public.workloop_app_user_id()
AND company_id=public.workloop_company_id()
AND ((public.workloop_role()='admin' AND (branch_id IS NULL OR branch_id=public.workloop_branch_id()))
 OR (public.workloop_role() IN ('manager','employee') AND branch_id=public.workloop_branch_id()))"""
    op.execute(
        "CREATE POLICY phase5g_notifications_select_runtime ON public.notifications "
        f"FOR SELECT TO workloop_runtime USING ({recipient})"
    )
    op.execute(
        "CREATE POLICY phase5g_notifications_update_runtime ON public.notifications "
        f"FOR UPDATE TO workloop_runtime USING ({recipient}) WITH CHECK ({recipient})"
    )
    job = """
current_user='workloop_expiry_processing'
AND session_user='workloop_expiry_processing'
AND public.workloop_actor_kind()='scheduled_job'
AND public.workloop_actor_key()='expiry_processing'
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_business_date() IS NOT NULL
AND company_id=public.workloop_company_id()
AND ((public.workloop_branch_id() IS NULL AND branch_id IS NULL)
 OR (public.workloop_branch_id() IS NOT NULL AND branch_id=public.workloop_branch_id()))
""".strip()
    op.execute(
        "CREATE POLICY phase5g_notifications_select_expiry ON public.notifications "
        f"FOR SELECT TO workloop_expiry_processing USING ({job})"
    )
    op.execute(
        "CREATE POLICY phase5g_notifications_insert_expiry ON public.notifications "
        f"FOR INSERT TO workloop_expiry_processing WITH CHECK ({job} "
        "AND created_by_app_user_id IS NULL "
        "AND type IN ('document_expiry','clinical_credential_expiry','insurance_expiry',"
        "'probation_ending','contract_expiry','cert_expiry','clinical_licence_expiry','policy_renewal'))"
    )


def _restore_phase5g_notification_function() -> None:
    op.execute("DROP FUNCTION public.create_workflow_notification(text, text)")
    op.execute(r"""
CREATE FUNCTION public.create_workflow_notification(p_type text, p_related_entity_id text)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  source_id uuid; source_company uuid; source_branch uuid; source_employee uuid;
  recipient_id uuid; notification_id uuid; entity_type text;
  notification_title text; notification_body text;
BEGIN
  IF session_user <> 'workloop_runtime'
     OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
     OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL
     OR public.workloop_company_id() IS NULL THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE='42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id=public.workloop_app_user_id()
      AND caller.account_status='active'
      AND caller.profile_company_id=public.workloop_company_id()
      AND caller.role=public.workloop_role()) THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE='42501';
  END IF;
  BEGIN source_id := p_related_entity_id::uuid;
  EXCEPTION WHEN invalid_text_representation THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE='42501';
  END;
  IF p_type IN ('leave_approved','leave_rejected') THEN
    SELECT request.company_id,request.branch_id,request.employee_id
      INTO source_company,source_branch,source_employee
    FROM public.leave_requests AS request
    JOIN public.employees AS employee ON employee.id=request.employee_id
      AND employee.company_id=request.company_id AND employee.branch_id=request.branch_id
    WHERE request.id=source_id AND request.company_id=public.workloop_company_id()
      AND request.branch_id=public.workloop_branch_id()
      AND ((p_type='leave_approved' AND request.status='Approved')
        OR (p_type='leave_rejected' AND request.status IN ('Rejected','ManagerRejected')))
      AND (public.workloop_role()='admin'
        OR (public.workloop_role()='manager'
          AND employee.reporting_manager_id=public.workloop_employee_id())
        OR public.can_act_for_delegated_leave(request.employee_id));
    entity_type := 'leave_request';
    notification_title := CASE p_type WHEN 'leave_approved' THEN 'Leave approved' ELSE 'Leave rejected' END;
    notification_body := CASE p_type WHEN 'leave_approved' THEN 'Your leave request was approved.' ELSE 'Your leave request was rejected.' END;
  ELSIF p_type='payslip_available' THEN
    SELECT payslip.company_id,payslip.branch_id,payslip.employee_id
      INTO source_company,source_branch,source_employee
    FROM public.payslips AS payslip
    WHERE payslip.id=source_id AND payslip.company_id=public.workloop_company_id()
      AND payslip.branch_id=public.workloop_branch_id() AND public.workloop_role()='admin';
    entity_type := 'payslip'; notification_title := 'Payslip available';
    notification_body := 'Your payslip is available.';
  ELSIF p_type='roster_published' THEN
    SELECT roster.company_id,roster.branch_id,roster.employee_id
      INTO source_company,source_branch,source_employee
    FROM public.roster_assignments AS roster
    WHERE roster.id=source_id AND roster.company_id=public.workloop_company_id()
      AND roster.branch_id=public.workloop_branch_id() AND roster.published
      AND public.workloop_role()='admin';
    entity_type := 'roster_assignment'; notification_title := 'Roster published';
    notification_body := 'Your roster was published.';
  ELSE
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE='42501';
  END IF;
  IF source_employee IS NULL THEN
    RAISE EXCEPTION 'workflow notification denied' USING ERRCODE='42501';
  END IF;
  SELECT profile.app_user_id INTO STRICT recipient_id
  FROM public.user_profiles AS profile
  JOIN public.app_users AS account ON account.id=profile.app_user_id
  WHERE profile.employee_id=source_employee AND profile.company_id=source_company
    AND account.status::text='active';
  INSERT INTO public.notifications(company_id,branch_id,created_by_app_user_id,
    recipient_app_user_id,type,title,body,related_entity_type,related_entity_id)
  VALUES(source_company,source_branch,public.workloop_app_user_id(),recipient_id,
    p_type,notification_title,notification_body,entity_type,source_id::text)
  ON CONFLICT(company_id,recipient_app_user_id,type,related_entity_type,related_entity_id)
  DO NOTHING RETURNING id INTO notification_id;
  IF notification_id IS NULL THEN
    SELECT id INTO notification_id FROM public.notifications
    WHERE company_id=source_company AND recipient_app_user_id=recipient_id
      AND type=p_type AND related_entity_type=entity_type
      AND related_entity_id=source_id::text;
  END IF;
  RETURN notification_id;
EXCEPTION WHEN no_data_found OR too_many_rows THEN
  RAISE EXCEPTION 'workflow notification denied' USING ERRCODE='42501';
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


def _restore_phase5g_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase5g(text, text, uuid, text[], text, jsonb) "
        "RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.execute("ALTER TABLE public.audit_events DROP CONSTRAINT ck_audit_events_primary_actor")
    op.execute("""
ALTER TABLE public.audit_events ADD CONSTRAINT ck_audit_events_primary_actor CHECK (
  (actor_kind='human' AND actor_app_user_id IS NOT NULL AND system_actor_key IS NULL)
  OR (actor_kind<>'human' AND actor_app_user_id IS NULL AND btrim(system_actor_key)<>'')
)
""")
    op.execute("DROP POLICY phase5g_audit_events_select_runtime ON public.audit_events")
    op.execute("""
CREATE POLICY phase5g_audit_events_select_runtime ON public.audit_events
FOR SELECT TO workloop_runtime USING (
  current_user='workloop_runtime' AND session_user='workloop_runtime'
  AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
  AND public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL
  AND company_id=public.workloop_company_id()
  AND ((branch_id IS NULL AND public.workloop_branch_id() IS NULL)
    OR branch_id=public.workloop_branch_id())
  AND EXISTS (SELECT 1 FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id=public.workloop_app_user_id() AND caller.account_status='active'
      AND caller.role='admin' AND caller.profile_company_id=audit_events.company_id)
)
""")
    op.execute("DROP POLICY phase5g_audit_events_insert_expiry ON public.audit_events")
    op.execute("""
CREATE POLICY phase5g_audit_events_insert_expiry ON public.audit_events
FOR INSERT TO workloop_expiry_processing WITH CHECK (
  current_user='workloop_expiry_processing' AND session_user='workloop_expiry_processing'
  AND public.workloop_actor_kind()='scheduled_job'
  AND public.workloop_actor_key()='expiry_processing'
  AND public.workloop_business_date() IS NOT NULL
  AND company_id=public.workloop_company_id()
  AND ((branch_id IS NULL AND public.workloop_branch_id() IS NULL)
    OR branch_id=public.workloop_branch_id())
  AND actor_kind='scheduled_job' AND actor_app_user_id IS NULL
  AND system_actor_key='expiry_processing' AND initiated_by_app_user_id IS NULL
  AND action='expiry_notification_created' AND entity_type='notification'
  AND changed_fields <@ ARRAY['type','recipient_app_user_id']::text[]
  AND jsonb_typeof(metadata)='object'
  AND NOT EXISTS (SELECT 1 FROM jsonb_object_keys(metadata) AS key
    WHERE key <> ALL(ARRAY['threshold_days','source_date']::text[]))
)
""")


def _restore_shift_swap_function() -> None:
    op.execute(r"""
DO $block$
DECLARE prior_definition text; next_definition text;
BEGIN
  SELECT pg_catalog.pg_get_functiondef(
    'public.admin_execute_shift_swap(uuid,uuid)'::regprocedure)
    INTO prior_definition;
  next_definition := pg_catalog.replace(prior_definition,
    E'  v_tgt_row public.roster_assignments%ROWTYPE;\n  v_employee_count integer;',
    '  v_tgt_row public.roster_assignments%ROWTYPE;');
  next_definition := pg_catalog.replace(next_definition,
    E'\n  PERFORM employee.id FROM public.employees AS employee\n  WHERE employee.id IN (v_swap.requester_employee_id,v_swap.target_employee_id)\n    AND employee.company_id=v_swap.company_id AND employee.branch_id=v_swap.branch_id\n  ORDER BY employee.id FOR UPDATE;\n  GET DIAGNOSTICS v_employee_count = ROW_COUNT;\n  IF v_employee_count <> 2 OR EXISTS (SELECT 1 FROM public.employees AS employee\n    WHERE employee.id IN (v_swap.requester_employee_id,v_swap.target_employee_id)\n      AND (NOT employee.active OR employee.employment_status NOT IN (''Active'',''Probation'',''On Leave''))) THEN\n    RAISE EXCEPTION ''shift_swap_employee_ineligible'';\n  END IF;', '');
  IF next_definition=prior_definition THEN
    RAISE EXCEPTION 'shift swap employee lock restoration did not match protected function';
  END IF;
  EXECUTE next_definition;
END
$block$
""")
    op.execute(
        "ALTER FUNCTION public.admin_execute_shift_swap(uuid, uuid) OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public.admin_execute_shift_swap(uuid, uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.admin_execute_shift_swap(uuid, uuid) TO workloop_runtime"
    )


def _restore_preserved_phase5g_objects() -> None:
    policy_pairs = (
        ("appraisal_sections", "phase5g_appraisal_sections_update_runtime", True),
        ("offboarding_tasks", "phase5g_offboarding_tasks_delete_runtime", False),
        ("notifications", "phase5g_notifications_select_runtime", True),
        ("notifications", "phase5g_notifications_update_runtime", True),
        ("notifications", "phase5g_notifications_select_expiry", True),
        ("notifications", "phase5g_notifications_insert_expiry", True),
        ("audit_events", "phase5g_audit_events_select_runtime", True),
        ("audit_events", "phase5g_audit_events_insert_expiry", True),
    )
    for table, name, has_replacement in policy_pairs:
        if has_replacement:
            op.execute(f"DROP POLICY {name} ON public.{table}")
        prior_name = name.replace("phase5g_", "phase5h_prior_")
        role = "workloop_expiry_processing" if name.endswith("_expiry") else "workloop_runtime"
        op.execute(f"ALTER POLICY {prior_name} ON public.{table} TO {role}")
        op.execute(f"ALTER POLICY {prior_name} ON public.{table} RENAME TO {name}")
    op.execute("GRANT DELETE ON TABLE public.offboarding_tasks TO workloop_runtime")

    op.execute("ALTER TABLE public.audit_events DROP CONSTRAINT ck_audit_events_primary_actor")
    op.execute(
        "ALTER TABLE public.audit_events RENAME CONSTRAINT phase5h_prior_audit_primary_actor "
        "TO ck_audit_events_primary_actor"
    )

    function_pairs = (
        (
            "public.admin_execute_shift_swap(uuid,uuid)",
            "public._admin_execute_shift_swap_phase5g(uuid,uuid)",
            "admin_execute_shift_swap",
        ),
        (
            AUDIT_SIGNATURE,
            PRIVATE_AUDIT_SIGNATURE,
            "append_audit_event",
        ),
        (
            "public.create_workflow_notification(text,text)",
            "public._create_workflow_notification_phase5g(text,text)",
            "create_workflow_notification",
        ),
    )
    for current_signature, prior_signature, public_name in function_pairs:
        op.execute(f"DROP FUNCTION {current_signature}")
        op.execute(f"ALTER FUNCTION {prior_signature} RENAME TO {public_name}")
        op.execute(f"ALTER FUNCTION {current_signature} OWNER TO workloop_migration")
        op.execute(f"REVOKE ALL ON FUNCTION {current_signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {current_signature} TO workloop_runtime")


def downgrade() -> None:
    _set_repayment_payroll_lock(enabled=False)
    _restore_preserved_phase5g_objects()
    op.execute("DROP FUNCTION public.lock_authorized_employee_relationships(uuid[])")
