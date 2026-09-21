"""Add Phase 10G roster draft and compliance authority.

Revision ID: a1c3e5f7b902
Revises: d0f6b8e2a753
Created: 2026-09-22 02:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "a1c3e5f7b902"
down_revision: str | Sequence[str] | None = "d0f6b8e2a753"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10G_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request','attendance_period','roster_assignment') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
PHASE10F_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request','attendance_period') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""

ADMIN_CONTEXT = """
current_user='workloop_migration'
AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_role()='admin'
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_employee_id() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() principal
  WHERE principal.app_user_id=public.workloop_app_user_id()
    AND principal.account_status='active' AND principal.role='admin'
    AND principal.profile_company_id=public.workloop_company_id()
    AND principal.company_id=principal.profile_company_id
    AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL
    AND principal.branch_id IS NULL
)
AND EXISTS (
  SELECT 1 FROM public.branches branch
  WHERE branch.id=public.workloop_branch_id()
    AND branch.company_id=public.workloop_company_id()
)
""".strip()


def upgrade() -> None:
    op.add_column(
        "roster_assignments",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_check_constraint(
        "phase10g_roster_draft",
        "roster_assignments",
        "version >= 1 AND planned_hours IS NOT NULL AND planned_hours BETWEEN 0.25 AND 24 "
        "AND octet_length(notes) <= 500",
    )
    op.create_index(
        "ix_roster_assignments_scope_date_employee",
        "roster_assignments",
        ["company_id", "branch_id", "date", "employee_id", "id"],
    )

    op.add_column("compliance_overrides", sa.Column("roster_month", sa.Text(), nullable=True))
    op.add_column("compliance_overrides", sa.Column("violation_digest", sa.Text(), nullable=True))
    op.add_column("compliance_overrides", sa.Column("violation_snapshot", JSONB(), nullable=True))
    op.drop_constraint(
        op.f("ck_compliance_overrides_rule_code"), "compliance_overrides", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_compliance_overrides_rule_code"),
        "compliance_overrides",
        "rule_code IS NULL OR rule_code IN ('visa_expired','emirates_id_expired',"
        "'labour_card_expired','passport_expired','professional_licence_expired',"
        "'leave_conflict','staffing_shortfall')",
    )
    op.create_check_constraint(
        "phase10g_roster_override",
        "compliance_overrides",
        "(override_type<>'roster_publish' AND roster_month IS NULL "
        "AND violation_digest IS NULL AND violation_snapshot IS NULL) OR "
        "(override_type='roster_publish' AND branch_id IS NOT NULL "
        "AND payroll_run_id IS NULL AND payroll_entry_id IS NULL "
        "AND rule_code IN ('leave_conflict','staffing_shortfall') "
        "AND roster_month ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$' "
        "AND violation_digest ~ '^sha256:[0-9a-f]{64}$' "
        "AND jsonb_typeof(violation_snapshot)='object' "
        "AND octet_length(btrim(reason)) BETWEEN 10 AND 500)",
    )
    op.create_index(
        "uq_compliance_overrides_roster_violation",
        "compliance_overrides",
        ["branch_id", "roster_month", "violation_digest"],
        unique=True,
        postgresql_where=sa.text("override_type='roster_publish'"),
    )

    op.execute("""
CREATE FUNCTION public.phase10g_roster_draft_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF current_user='workloop_migration' THEN
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  IF OLD.published OR (TG_OP='UPDATE' AND NEW.published) THEN
    RAISE EXCEPTION 'published roster assignment is immutable' USING ERRCODE='42501';
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  IF NEW.version<>OLD.version+1 THEN
    RAISE EXCEPTION 'roster assignment version must advance once' USING ERRCODE='40001';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_phase10g_roster_draft_guard
BEFORE UPDATE OR DELETE ON public.roster_assignments
FOR EACH ROW EXECUTE FUNCTION public.phase10g_roster_draft_guard();
""")
    op.execute("ALTER FUNCTION public.phase10g_roster_draft_guard() OWNER TO workloop_migration")
    op.execute(
        "REVOKE ALL ON FUNCTION public.phase10g_roster_draft_guard() FROM PUBLIC, workloop_runtime"
    )

    op.execute(f"""
CREATE FUNCTION public.create_roster_compliance_override(
  p_id uuid,p_period text,p_rule_code text,p_violation_digest text,p_reason text,p_snapshot jsonb
) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF NOT ({ADMIN_CONTEXT}) THEN
    RAISE EXCEPTION 'roster compliance override denied' USING ERRCODE='42501';
  END IF;
  IF p_period !~ '^(19|20)[0-9]{{2}}-(0[1-9]|1[0-2])$'
     OR p_rule_code NOT IN ('leave_conflict','staffing_shortfall')
     OR p_snapshot->>'code' IS DISTINCT FROM p_rule_code
     OR p_violation_digest !~ '^sha256:[0-9a-f]{{64}}$'
     OR octet_length(pg_catalog.btrim(p_reason)) NOT BETWEEN 10 AND 500
     OR pg_catalog.jsonb_typeof(p_snapshot)<>'object'
     OR NOT EXISTS (
       SELECT 1 FROM public.branches branch
       WHERE branch.id=public.workloop_branch_id()
         AND branch.company_id=public.workloop_company_id()
         AND (p_rule_code<>'staffing_shortfall' OR branch.enable_staffing_rules))
  THEN
    RAISE EXCEPTION 'invalid roster compliance override' USING ERRCODE='23514';
  END IF;
  INSERT INTO public.compliance_overrides(
    id,company_id,branch_id,override_type,employee_ids,reason,
    created_by_app_user_id,rule_code,roster_month,violation_digest,violation_snapshot
  ) VALUES (
    p_id,public.workloop_company_id(),public.workloop_branch_id(),'roster_publish',NULL,
    pg_catalog.btrim(p_reason),public.workloop_app_user_id(),p_rule_code,
    p_period,p_violation_digest,p_snapshot
  );
END
$function$;
""")
    op.execute(
        "ALTER FUNCTION public.create_roster_compliance_override(uuid,text,text,text,text,jsonb) "
        "OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.create_roster_compliance_override(uuid,text,text,text,text,jsonb) "
        "FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.create_roster_compliance_override(uuid,text,text,text,text,jsonb) "
        "TO workloop_runtime"
    )

    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10G_REPLAY)


def downgrade() -> None:
    op.execute("""
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.roster_assignments WHERE version<>1)
     OR EXISTS (
       SELECT 1 FROM public.compliance_overrides WHERE override_type='roster_publish'
     ) THEN
    RAISE EXCEPTION 'phase10g_roster_data_requires_preservation';
  END IF;
END $$;
""")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10F_REPLAY)
    op.execute(
        "REVOKE ALL ON FUNCTION public.create_roster_compliance_override(uuid,text,text,text,text,jsonb) "
        "FROM workloop_runtime"
    )
    op.execute(
        "DROP FUNCTION public.create_roster_compliance_override(uuid,text,text,text,text,jsonb)"
    )
    op.execute("DROP TRIGGER trg_phase10g_roster_draft_guard ON public.roster_assignments")
    op.execute("DROP FUNCTION public.phase10g_roster_draft_guard()")
    op.drop_index("uq_compliance_overrides_roster_violation", table_name="compliance_overrides")
    op.drop_constraint("phase10g_roster_override", "compliance_overrides", type_="check")
    op.drop_constraint(
        op.f("ck_compliance_overrides_rule_code"), "compliance_overrides", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_compliance_overrides_rule_code"),
        "compliance_overrides",
        "rule_code IS NULL OR rule_code IN ('visa_expired','emirates_id_expired',"
        "'labour_card_expired','passport_expired','professional_licence_expired')",
    )
    op.drop_column("compliance_overrides", "violation_snapshot")
    op.drop_column("compliance_overrides", "violation_digest")
    op.drop_column("compliance_overrides", "roster_month")
    op.drop_index("ix_roster_assignments_scope_date_employee", table_name="roster_assignments")
    op.drop_constraint("phase10g_roster_draft", "roster_assignments", type_="check")
    op.drop_column("roster_assignments", "version")
