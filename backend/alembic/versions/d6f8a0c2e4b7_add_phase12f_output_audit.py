"""Add the fixed-purpose Phase 12F output audit writer.

Revision ID: d6f8a0c2e4b7
Revises: c3e5a7b9d1f6
Created: 2026-09-25 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d6f8a0c2e4b7"
down_revision: str | Sequence[str] | None = "c3e5a7b9d1f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNATURE = (
    "public.append_phase12_output_audit(text,text,uuid,text,text,text,text,integer,bigint,text)"
)


def upgrade() -> None:
    op.execute(
        r"""
CREATE FUNCTION public.append_phase12_output_audit(
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
BEGIN
  IF session_user <> 'workloop_runtime'
    OR current_user <> 'workloop_migration'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR public.workloop_role() IS DISTINCT FROM 'admin'
    OR public.workloop_employee_id() IS NOT NULL
    OR event_actor IS NULL
    OR event_company IS NULL
    OR event_branch IS NULL
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

  IF NOT EXISTS (
    SELECT 1
    FROM public.resolve_workloop_principal() AS caller
    WHERE caller.app_user_id = event_actor
      AND caller.account_status = 'active'
      AND caller.profile_company_id = event_company
      AND caller.role = 'admin'
      AND caller.profile_employee_id IS NULL
      AND caller.employee_id IS NULL
      AND caller.branch_id IS NULL
  ) OR NOT EXISTS (
    SELECT 1
    FROM public.branches AS selected_branch
    WHERE selected_branch.id = event_branch
      AND selected_branch.company_id = event_company
  ) THEN
    RAISE EXCEPTION 'phase 12 output audit denied' USING ERRCODE = '42501';
  END IF;

  IF NOT (
    (p_action = 'report_csv_exported' AND p_entity_type = 'report'
      AND p_format = 'csv' AND p_entity_id = event_branch)
    OR (p_action = 'attendance_csv_exported' AND p_entity_type = 'attendance_period'
      AND p_format = 'csv' AND EXISTS (
        SELECT 1 FROM public.attendance_periods source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch))
    OR (p_action = 'roster_csv_exported' AND p_entity_type = 'roster_month'
      AND p_format = 'csv' AND p_entity_id = event_branch)
    OR (p_action = 'leave_balance_csv_exported' AND p_entity_type = 'leave_balance_year'
      AND p_format = 'csv' AND p_entity_id = event_branch)
    OR (p_action = 'employee_csv_exported' AND p_entity_type = 'employee_export'
      AND p_format = 'csv' AND p_entity_id = event_branch)
    OR (p_action = 'nafis_csv_exported' AND p_entity_type = 'nafis_report'
      AND p_format = 'csv' AND EXISTS (
        SELECT 1 FROM public.nafis_reports source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch))
    OR (p_action = 'sif_previewed' AND p_entity_type = 'payroll_run'
      AND p_format = 'sif_preview' AND EXISTS (
        SELECT 1 FROM public.payroll_runs source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch
          AND source.status = 'generated' AND source.approval_status = 'approved'))
    OR (p_action = 'sif_exported' AND p_entity_type = 'payroll_run'
      AND p_format = 'sif' AND EXISTS (
        SELECT 1 FROM public.payroll_runs source
        WHERE source.id = p_entity_id AND source.company_id = event_company
          AND source.branch_id = event_branch
          AND source.status = 'generated' AND source.approval_status = 'approved'))
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
    )
    op.execute(f"ALTER FUNCTION {SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {SIGNATURE} TO workloop_runtime")


def downgrade() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {SIGNATURE}")
