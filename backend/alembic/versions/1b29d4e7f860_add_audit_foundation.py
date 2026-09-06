"""Add the Phase 5G append-only audit foundation.

Revision ID: 1b29d4e7f860
Revises: 0a18c3d6e75f
Created: 2026-09-06 00:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "1b29d4e7f860"
down_revision: str | Sequence[str] | None = "0a18c3d6e75f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = "public.append_audit_event(text, text, uuid, text[], text, jsonb)"
SHIFT_SWAP_FUNCTION = "public.admin_execute_shift_swap(uuid, uuid)"


def _create_table() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_app_user_id", sa.UUID(), nullable=True),
        sa.Column("system_actor_key", sa.Text(), nullable=True),
        sa.Column("initiated_by_app_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("changed_fields", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.CheckConstraint(
            "actor_kind IN ('human','scheduled_job','migration','seed','system_rule')",
            name=op.f("ck_audit_events_actor_kind"),
        ),
        sa.CheckConstraint(
            "(actor_kind = 'human' AND actor_app_user_id IS NOT NULL AND system_actor_key IS NULL) OR (actor_kind <> 'human' AND actor_app_user_id IS NULL AND btrim(system_actor_key) <> '')",
            name=op.f("ck_audit_events_primary_actor"),
        ),
        sa.CheckConstraint("btrim(action) <> ''", name=op.f("ck_audit_events_action_nonblank")),
        sa.CheckConstraint(
            "btrim(entity_type) <> ''", name=op.f("ck_audit_events_entity_type_nonblank")
        ),
        sa.CheckConstraint("btrim(reason) <> ''", name=op.f("ck_audit_events_reason_nonblank")),
        sa.CheckConstraint(
            "array_position(changed_fields, NULL) IS NULL",
            name=op.f("ck_audit_events_changed_fields"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'", name=op.f("ck_audit_events_metadata_object")
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["actor_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_audit_events_actor_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["initiated_by_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_audit_events_initiator_profile",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_company_id_occurred_at",
        "audit_events",
        ["company_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_audit_events_company_id_branch_id_occurred_at",
        "audit_events",
        ["company_id", "branch_id", sa.text("occurred_at DESC")],
    )
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])


def _create_function() -> None:
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
  event_company uuid := public.workloop_company_id();
  event_branch uuid := public.workloop_branch_id();
  caller_role text := public.workloop_role();
  target_employee uuid;
  source_state text;
  source_aux_state text;
  source_flag boolean;
  source_actor uuid;
  source_secondary_actor uuid;
  allowed_fields text[];
  allowed_metadata text[];
BEGIN
  IF session_user <> 'workloop_runtime' OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL OR public.workloop_business_date() IS NULL
    OR public.workloop_app_user_id() IS NULL OR event_company IS NULL
    OR p_reason IS NULL OR btrim(p_reason) = ''
    OR jsonb_typeof(COALESCE(p_metadata, '{}'::jsonb)) <> 'object'
    OR COALESCE(cardinality(p_changed_fields), 0) = 0
    OR array_position(p_changed_fields, NULL) IS NOT NULL THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id = public.workloop_app_user_id() AND caller.account_status = 'active'
      AND caller.profile_company_id = event_company AND caller.role = caller_role
  ) THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;

  CASE p_action
    WHEN 'role_changed' THEN
      IF p_entity_type <> 'user_profile' OR caller_role <> 'admin' OR event_branch IS NOT NULL
        OR NOT EXISTS (SELECT 1 FROM public.user_profiles WHERE app_user_id = p_entity_id AND company_id = event_company)
      THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;
      allowed_fields := ARRAY['role'];
    WHEN 'employment_access_changed' THEN allowed_fields := ARRAY['active','employment_status','reporting_manager_id'];
    WHEN 'employee_branch_corrected' THEN allowed_fields := ARRAY['branch_id','reporting_manager_id'];
    WHEN 'salary_advance_approved' THEN allowed_fields := ARRAY['status','disbursement_date','monthly_deduction','outstanding_balance'];
    WHEN 'salary_advance_rejected' THEN allowed_fields := ARRAY['status','rejection_reason'];
    WHEN 'salary_advance_settled' THEN allowed_fields := ARRAY['status','outstanding_balance'];
    WHEN 'expense_approved' THEN allowed_fields := ARRAY['status','approved_by_app_user_id','approved_at'];
    WHEN 'expense_rejected' THEN allowed_fields := ARRAY['status','rejection_reason'];
    WHEN 'expense_paid' THEN allowed_fields := ARRAY['status','payroll_run_id'];
    WHEN 'regularisation_approved' THEN allowed_fields := ARRAY['status','actioned_by_app_user_id','actioned_at'];
    WHEN 'regularisation_rejected' THEN allowed_fields := ARRAY['status','rejection_reason'];
    WHEN 'payroll_submitted' THEN allowed_fields := ARRAY['status','approval_status','submitted_by_app_user_id'];
    WHEN 'payroll_recalled' THEN allowed_fields := ARRAY['status','approval_status'];
    WHEN 'payroll_approved' THEN allowed_fields := ARRAY['status','approval_status','approved_by_app_user_id'];
    WHEN 'payroll_rejected' THEN allowed_fields := ARRAY['status','approval_status','rejection_reason'];
    WHEN 'payroll_generated' THEN allowed_fields := ARRAY['status','total_gross','total_net'];
    WHEN 'payroll_wps_changed' THEN allowed_fields := ARRAY['wps_status','sif_status'];
    WHEN 'roster_published' THEN allowed_fields := ARRAY['published'];
    WHEN 'shift_swap_approved' THEN allowed_fields := ARRAY['status','admin_approved_by_app_user_id'];
    WHEN 'shift_swap_rejected' THEN allowed_fields := ARRAY['status','rejection_reason'];
    WHEN 'employee_document_verified' THEN allowed_fields := ARRAY['status','reviewed_by_app_user_id','reviewed_at'];
    WHEN 'employee_document_rejected' THEN allowed_fields := ARRAY['status','rejection_reason'];
    WHEN 'employee_document_deleted' THEN allowed_fields := ARRAY['status'];
    WHEN 'certification_verified' THEN allowed_fields := ARRAY['status','reviewed_by_app_user_id','reviewed_at'];
    WHEN 'certification_rejected' THEN allowed_fields := ARRAY['status'];
    WHEN 'certification_deleted' THEN allowed_fields := ARRAY['status'];
    WHEN 'appraisal_reviewed' THEN allowed_fields := ARRAY['status','overall_rating','reviewer_comments','development_plan'];
    WHEN 'appraisal_calibrated' THEN allowed_fields := ARRAY['status','overall_rating'];
    WHEN 'incident_closed' THEN allowed_fields := ARRAY['status','closed_date','closed_by_app_user_id'];
    WHEN 'offboarding_completed' THEN allowed_fields := ARRAY['status','completed_at','completed_by_app_user_id'];
    WHEN 'letter_completed' THEN allowed_fields := ARRAY['status','completed_at','actioned_by_app_user_id'];
    WHEN 'letter_rejected' THEN allowed_fields := ARRAY['status','rejection_reason','actioned_by_app_user_id'];
    ELSE RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501';
  END CASE;
  allowed_metadata := CASE
    WHEN p_action IN ('employee_document_deleted','certification_deleted')
      THEN ARRAY['transition','operation_id']::text[]
    WHEN p_action IN ('expense_approved','expense_rejected','payroll_approved','payroll_rejected','appraisal_calibrated')
      THEN ARRAY['transition','override_reason']::text[]
    ELSE ARRAY['transition']::text[]
  END;
  IF EXISTS (
    SELECT 1 FROM jsonb_object_keys(COALESCE(p_metadata, '{}'::jsonb)) AS key
    WHERE key <> ALL(allowed_metadata)
  ) THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;
  IF NOT (p_changed_fields <@ allowed_fields) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501';
  END IF;
  IF p_entity_type <> (CASE
    WHEN p_action = 'role_changed' THEN 'user_profile'
    WHEN p_action IN ('employment_access_changed','employee_branch_corrected') THEN 'employee'
    WHEN p_action LIKE 'salary_advance_%' THEN 'salary_advance'
    WHEN p_action LIKE 'expense_%' THEN 'expense_claim'
    WHEN p_action LIKE 'regularisation_%' THEN 'regularisation_request'
    WHEN p_action LIKE 'payroll_%' THEN 'payroll_run'
    WHEN p_action = 'roster_published' THEN 'roster_assignment'
    WHEN p_action LIKE 'shift_swap_%' THEN 'shift_swap_request'
    WHEN p_action LIKE 'employee_document_%' THEN 'employee_document'
    WHEN p_action LIKE 'certification_%' THEN 'certification'
    WHEN p_action LIKE 'appraisal_%' THEN 'appraisal'
    WHEN p_action = 'incident_closed' THEN 'incident_report'
    WHEN p_action = 'offboarding_completed' THEN 'offboarding_checklist'
    WHEN p_action LIKE 'letter_%' THEN 'letter_request'
  END) THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;

  IF p_action <> 'role_changed' THEN
    IF event_branch IS NULL THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;
    CASE p_entity_type
      WHEN 'employee' THEN SELECT id INTO target_employee FROM public.employees WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'salary_advance' THEN SELECT employee_id,status INTO target_employee,source_state FROM public.salary_advances WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'expense_claim' THEN SELECT employee_id,status,manager_approved_by_app_user_id,approved_by_app_user_id INTO target_employee,source_state,source_actor,source_secondary_actor FROM public.expense_claims WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'regularisation_request' THEN SELECT employee_id,status,approved_by_app_user_id INTO target_employee,source_state,source_actor FROM public.regularisation_requests WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'payroll_run' THEN SELECT status,approval_status,(rejected_at IS NOT NULL),submitted_by_app_user_id,CASE WHEN rejected_at IS NULL THEN approved_by_app_user_id ELSE rejected_by_app_user_id END INTO source_state,source_aux_state,source_flag,source_actor,source_secondary_actor FROM public.payroll_runs WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'roster_assignment' THEN SELECT employee_id,published INTO target_employee,source_flag FROM public.roster_assignments WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'shift_swap_request' THEN SELECT requester_employee_id,status,admin_approved_by_app_user_id INTO target_employee,source_state,source_actor FROM public.shift_swap_requests WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'employee_document' THEN SELECT employee_id,status,reviewed_by_app_user_id INTO target_employee,source_state,source_actor FROM public.employee_documents WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'certification' THEN SELECT employee_id,status,reviewed_by_app_user_id INTO target_employee,source_state,source_actor FROM public.certifications WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'appraisal' THEN SELECT employee_id,status,reviewed_by_app_user_id INTO target_employee,source_state,source_actor FROM public.appraisals WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'incident_report' THEN SELECT status,closed_by_app_user_id INTO source_state,source_actor FROM public.incident_reports WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'offboarding_checklist' THEN SELECT employee_id,status,completed_by_app_user_id INTO target_employee,source_state,source_actor FROM public.offboarding_checklists WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      WHEN 'letter_request' THEN SELECT employee_id,status,actioned_by_app_user_id INTO target_employee,source_state,source_actor FROM public.letter_requests WHERE id=p_entity_id AND company_id=event_company AND branch_id=event_branch;
      ELSE RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501';
    END CASE;
    IF NOT FOUND THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;
    IF caller_role = 'manager' THEN
      IF p_action NOT IN ('expense_approved','expense_rejected','appraisal_reviewed','certification_deleted')
        OR target_employee IS NULL OR NOT EXISTS (
          SELECT 1 FROM public.employees AS employee WHERE employee.id=target_employee
            AND employee.company_id=event_company AND employee.branch_id=event_branch
            AND employee.reporting_manager_id=public.workloop_employee_id()
        ) THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;
    ELSIF caller_role <> 'admin' THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501';
    END IF;

    IF NOT COALESCE((CASE p_action
      WHEN 'employment_access_changed' THEN true
      WHEN 'employee_branch_corrected' THEN true
      WHEN 'salary_advance_approved' THEN source_state = 'active'
      WHEN 'salary_advance_rejected' THEN source_state = 'cancelled'
      WHEN 'salary_advance_settled' THEN source_state = 'settled'
      WHEN 'expense_approved' THEN
        (caller_role = 'manager' AND source_state = 'manager_approved' AND source_actor = public.workloop_app_user_id())
        OR (caller_role = 'admin' AND source_state = 'approved' AND source_secondary_actor = public.workloop_app_user_id())
      WHEN 'expense_rejected' THEN
        (caller_role = 'manager' AND source_state = 'manager_rejected' AND source_actor = public.workloop_app_user_id())
        OR (caller_role = 'admin' AND source_state = 'rejected' AND source_secondary_actor = public.workloop_app_user_id())
      WHEN 'expense_paid' THEN source_state = 'paid'
      WHEN 'regularisation_approved' THEN source_state = 'Approved' AND source_actor = public.workloop_app_user_id()
      WHEN 'regularisation_rejected' THEN source_state = 'Rejected' AND source_actor = public.workloop_app_user_id()
      WHEN 'payroll_submitted' THEN source_aux_state = 'pending_approval' AND source_actor = public.workloop_app_user_id()
      WHEN 'payroll_recalled' THEN source_aux_state = 'draft' AND source_flag = false
      WHEN 'payroll_approved' THEN source_aux_state = 'approved' AND source_secondary_actor = public.workloop_app_user_id() AND source_actor <> public.workloop_app_user_id()
      WHEN 'payroll_rejected' THEN source_aux_state = 'draft' AND source_flag = true AND source_secondary_actor = public.workloop_app_user_id() AND source_actor <> public.workloop_app_user_id()
      WHEN 'payroll_generated' THEN source_state = 'generated'
      WHEN 'payroll_wps_changed' THEN true
      WHEN 'roster_published' THEN source_flag = true
      WHEN 'shift_swap_approved' THEN source_state = 'approved' AND source_actor = public.workloop_app_user_id()
      WHEN 'shift_swap_rejected' THEN source_state = 'rejected'
      WHEN 'employee_document_verified' THEN source_state = 'verified' AND source_actor = public.workloop_app_user_id()
      WHEN 'employee_document_rejected' THEN source_state = 'rejected' AND source_actor = public.workloop_app_user_id()
      WHEN 'employee_document_deleted' THEN source_state IN ('pending_verification','rejected')
      WHEN 'certification_verified' THEN source_state = 'verified' AND source_actor = public.workloop_app_user_id()
      WHEN 'certification_rejected' THEN source_state = 'rejected' AND source_actor = public.workloop_app_user_id()
      WHEN 'certification_deleted' THEN source_state IN ('pending_review','rejected')
      WHEN 'appraisal_reviewed' THEN source_state = 'reviewed' AND source_actor = public.workloop_app_user_id()
      WHEN 'appraisal_calibrated' THEN source_state = 'calibrated'
      WHEN 'incident_closed' THEN source_state = 'closed' AND source_actor = public.workloop_app_user_id()
      WHEN 'offboarding_completed' THEN source_state = 'completed' AND source_actor = public.workloop_app_user_id()
      WHEN 'letter_completed' THEN source_state = 'completed' AND source_actor = public.workloop_app_user_id()
      WHEN 'letter_rejected' THEN source_state = 'rejected' AND source_actor = public.workloop_app_user_id()
      ELSE false
    END), false) THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE = '42501'; END IF;
  END IF;

  INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
    system_actor_key,initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(event_company,event_branch,'human',public.workloop_app_user_id(),NULL,NULL,
    p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,COALESCE(p_metadata,'{}'::jsonb))
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
""")
    op.execute(f"ALTER FUNCTION {FUNCTION} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO workloop_runtime")


def _wire_shift_swap_audit(*, enabled: bool) -> None:
    audit_call = """  PERFORM public.append_audit_event(
    'shift_swap_approved', 'shift_swap_request', p_swap_id,
    ARRAY['status','admin_approved_by_app_user_id']::text[],
    'Shift swap approved',
    '{"transition":"pending_to_approved"}'::jsonb
  );
"""
    old_text = "  RETURN true;" if enabled else audit_call + "  RETURN true;"
    new_text = audit_call + "  RETURN true;" if enabled else "  RETURN true;"
    op.execute(
        f"""
DO $block$
DECLARE
  prior_definition text;
  next_definition text;
BEGIN
  SELECT pg_catalog.pg_get_functiondef('{SHIFT_SWAP_FUNCTION}'::regprocedure)
    INTO prior_definition;
  next_definition := pg_catalog.replace(
    prior_definition,
    $old_text${old_text}$old_text$,
    $new_text${new_text}$new_text$
  );
  IF next_definition = prior_definition THEN
    RAISE EXCEPTION 'shift swap audit wiring did not match the protected function';
  END IF;
  EXECUTE next_definition;
END
$block$
"""
    )


def _create_policies_and_grants() -> None:
    op.execute("ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY")
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
  AND jsonb_typeof(metadata) = 'object'
  AND NOT EXISTS (
    SELECT 1 FROM jsonb_object_keys(metadata) AS key
    WHERE key <> ALL(ARRAY['threshold_days','source_date']::text[])
  )
)
""")
    op.execute("GRANT SELECT ON TABLE public.audit_events TO workloop_runtime")
    op.execute(
        "GRANT INSERT (company_id,branch_id,actor_kind,system_actor_key,action,entity_type,entity_id,changed_fields,reason,metadata) ON TABLE public.audit_events TO workloop_expiry_processing"
    )


def upgrade() -> None:
    _create_table()
    _create_function()
    _wire_shift_swap_audit(enabled=True)
    _create_policies_and_grants()


def downgrade() -> None:
    op.execute("REVOKE INSERT ON TABLE public.audit_events FROM workloop_expiry_processing")
    op.execute("REVOKE SELECT ON TABLE public.audit_events FROM workloop_runtime")
    op.execute(f"REVOKE EXECUTE ON FUNCTION {FUNCTION} FROM workloop_runtime")
    _wire_shift_swap_audit(enabled=False)
    op.execute(f"DROP FUNCTION {FUNCTION}")
    op.drop_table("audit_events")
