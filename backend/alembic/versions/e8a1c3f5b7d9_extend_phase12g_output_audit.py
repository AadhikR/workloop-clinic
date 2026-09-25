"""Close the protected output audit and payslip delivery boundaries for Part 12G.

Revision ID: e8a1c3f5b7d9
Revises: d6f8a0c2e4b7
Created: 2026-09-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e8a1c3f5b7d9"
down_revision: str | Sequence[str] | None = "d6f8a0c2e4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNATURE = (
    "public.append_phase12_output_audit(text,text,uuid,text,text,text,text,integer,bigint,text)"
)

PART_12F_ALLOWLIST = r"""
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
"""

PART_12G_ALLOWLIST = r"""
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
"""

PAYSLIP_HUMAN_CONTEXT = r"""
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
"""


def _function_sql(*, include_phase12g: bool) -> str:
    role_guard = (
        "OR public.workloop_role() NOT IN ('admin','employee')"
        if include_phase12g
        else "OR public.workloop_role() IS DISTINCT FROM 'admin'\n    "
        "OR public.workloop_employee_id() IS NOT NULL"
    )
    role_resolution = (
        r"""
  SELECT caller.role,caller.employee_id INTO actor_role,actor_employee
  FROM public.resolve_workloop_principal() AS caller
  WHERE caller.app_user_id = event_actor
    AND caller.account_status = 'active'
    AND caller.profile_company_id = event_company
    AND caller.role IN ('admin','employee')
    AND ((caller.role = 'admin' AND caller.profile_employee_id IS NULL
          AND caller.employee_id IS NULL AND caller.branch_id IS NULL
          AND public.workloop_employee_id() IS NULL)
      OR (caller.role = 'employee' AND caller.profile_employee_id IS NOT NULL
          AND caller.employee_id = caller.profile_employee_id
          AND caller.employee_id = public.workloop_employee_id()
          AND caller.branch_id = event_branch));

  IF actor_role IS NULL THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;
"""
        if include_phase12g
        else r"""
  IF NOT EXISTS (
    SELECT 1 FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id = event_actor
      AND caller.account_status = 'active'
      AND caller.profile_company_id = event_company
      AND caller.role = 'admin'
      AND caller.profile_employee_id IS NULL
      AND caller.employee_id IS NULL
      AND caller.branch_id IS NULL
  ) THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;
  actor_role := 'admin';
"""
    )
    allowlist = PART_12F_ALLOWLIST + (PART_12G_ALLOWLIST if include_phase12g else "")
    return rf"""
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
    {role_guard}
    OR event_actor IS NULL
    OR event_company IS NULL
    OR event_branch IS NULL
    OR p_entity_id IS NULL
    OR p_result NOT IN ('succeeded','denied_before_stream')
    OR p_filter_digest !~ '^sha256:[0-9a-f]{{64}}$'
    OR p_source_digest !~ '^sha256:[0-9a-f]{{64}}$'
    OR p_renderer_version !~ '^[A-Za-z0-9._-]{{1,64}}$'
    OR p_row_count < 0
    OR p_byte_count <= 0
  THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;

  {role_resolution}

  IF NOT EXISTS (
    SELECT 1 FROM public.branches selected_branch
    WHERE selected_branch.id = event_branch
      AND selected_branch.company_id = event_company
  ) THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;

  IF NOT ({allowlist}
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


def _secure_function() -> None:
    op.execute(f"ALTER FUNCTION {SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO workloop_runtime")


def _replace_payslip_policy(*, include_admin: bool) -> None:
    allowed_role = ("public.workloop_role() = 'admin' OR " if include_admin else "") + (
        "(public.workloop_role() = 'employee' AND employee_id = public.workloop_employee_id())"
    )
    op.execute("DROP POLICY phase5f_payslips_select_runtime ON public.payslips")
    op.execute(
        f"""
CREATE POLICY phase5f_payslips_select_runtime ON public.payslips
FOR SELECT TO workloop_runtime
USING (
{PAYSLIP_HUMAN_CONTEXT}
  AND company_id = public.workloop_company_id()
  AND branch_id = public.workloop_branch_id()
  AND ({allowed_role})
)
"""
    )


def upgrade() -> None:
    op.execute(_function_sql(include_phase12g=True))
    _secure_function()
    _replace_payslip_policy(include_admin=True)


def downgrade() -> None:
    _replace_payslip_policy(include_admin=False)
    op.execute(_function_sql(include_phase12g=False))
    _secure_function()
