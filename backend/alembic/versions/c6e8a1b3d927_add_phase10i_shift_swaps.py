"""Add Phase 10I shift-swap authority.

Revision ID: c6e8a1b3d927
Revises: b4d7f9a2c816
Created: 2026-09-22 09:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c6e8a1b3d927"
down_revision: str | Sequence[str] | None = "b4d7f9a2c816"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10I_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request','attendance_period','roster_assignment','roster_publication_version','shift_swap_request') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
PHASE10H_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request','attendance_period','roster_assignment','roster_publication_version') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""

HUMAN_CONTEXT = """
current_user='workloop_runtime' AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() principal
  WHERE principal.app_user_id=public.workloop_app_user_id()
    AND principal.account_status='active' AND principal.role=public.workloop_role()
    AND principal.profile_company_id=public.workloop_company_id()
    AND principal.company_id=principal.profile_company_id
    AND ((principal.role='admin' AND principal.profile_employee_id IS NULL
          AND principal.employee_id IS NULL AND principal.branch_id IS NULL
          AND public.workloop_employee_id() IS NULL)
      OR (principal.role IN ('manager','employee')
          AND principal.profile_employee_id=public.workloop_employee_id()
          AND principal.employee_id=principal.profile_employee_id
          AND principal.employee_branch_id=public.workloop_branch_id()
          AND principal.branch_id=principal.employee_branch_id
          AND principal.employee_active
          AND principal.employment_status IN ('Active','Probation','On Leave')))
)
""".strip()


def _add_request_contract() -> None:
    columns = (
        sa.Column("contract_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expected_roster_source_version", sa.Text(), nullable=True),
        sa.Column("source_publication_version_id", sa.UUID(), nullable=True),
        sa.Column("requester_assignment_id", sa.UUID(), nullable=True),
        sa.Column("target_assignment_id", sa.UUID(), nullable=True),
        sa.Column("expected_requester_assignment_version", sa.Integer(), nullable=True),
        sa.Column("expected_target_assignment_version", sa.Integer(), nullable=True),
        sa.Column("approved_publication_version_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_app_user_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    for column in columns:
        op.add_column("shift_swap_requests", column)
    op.create_foreign_key(
        "fk_shift_swap_requests_source_publication_version_id",
        "shift_swap_requests",
        "roster_publication_versions",
        ["source_publication_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_shift_swap_requests_approved_publication_version_id",
        "shift_swap_requests",
        "roster_publication_versions",
        ["approved_publication_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for side in ("requester", "target"):
        op.create_foreign_key(
            f"fk_shift_swap_requests_{side}_assignment_id",
            "shift_swap_requests",
            "roster_assignments",
            [f"{side}_assignment_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_foreign_key(
        "fk_shift_swap_requests_decided_by_app_user_id",
        "shift_swap_requests",
        "app_users",
        ["decided_by_app_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "phase10i_contract",
        "shift_swap_requests",
        "(contract_version=0 AND expected_roster_source_version IS NULL AND "
        "source_publication_version_id IS NULL AND requester_assignment_id IS NULL AND "
        "target_assignment_id IS NULL AND expected_requester_assignment_version IS NULL AND "
        "expected_target_assignment_version IS NULL AND approved_publication_version_id IS NULL "
        "AND decided_at IS NULL AND decided_by_app_user_id IS NULL AND version=1) OR "
        "(contract_version=1 AND target_date IS NOT NULL AND requester_date<>target_date AND "
        "octet_length(btrim(reason)) BETWEEN 3 AND 500 AND "
        "expected_roster_source_version~'^sha256:[0-9a-f]{64}$' AND "
        "source_publication_version_id IS NOT NULL AND requester_assignment_id IS NOT NULL AND "
        "target_assignment_id IS NOT NULL AND requester_assignment_id<>target_assignment_id AND "
        "expected_requester_assignment_version>=1 AND expected_target_assignment_version>=1 "
        "AND version>=1)",
    )
    op.create_check_constraint(
        "phase10i_decision",
        "shift_swap_requests",
        "contract_version=0 OR ((status='pending' AND decided_at IS NULL AND "
        "decided_by_app_user_id IS NULL AND approved_publication_version_id IS NULL AND "
        "rejection_reason='') OR (status='approved' AND decided_at IS NOT NULL AND "
        "decided_by_app_user_id IS NOT NULL AND approved_publication_version_id IS NOT NULL AND "
        "rejection_reason='') OR (status='rejected' AND decided_at IS NOT NULL AND "
        "decided_by_app_user_id IS NOT NULL AND approved_publication_version_id IS NULL AND "
        "octet_length(btrim(rejection_reason)) BETWEEN 3 AND 500) OR "
        "(status='cancelled' AND decided_at IS NOT NULL AND decided_by_app_user_id IS NOT NULL "
        "AND approved_publication_version_id IS NULL AND rejection_reason=''))",
    )
    op.create_index(
        "ix_shift_swap_requests_phase10i_scope_status",
        "shift_swap_requests",
        ["company_id", "branch_id", "status", "created_at", "id"],
    )
    op.execute("""
CREATE UNIQUE INDEX uq_shift_swap_requests_phase10i_pending_pair
ON public.shift_swap_requests(
  company_id,branch_id,
  LEAST(requester_assignment_id,target_assignment_id),
  GREATEST(requester_assignment_id,target_assignment_id))
WHERE contract_version=1 AND status='pending';
""")


def _create_history() -> None:
    op.create_table(
        "shift_swap_history",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("shift_swap_request_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("actor_app_user_id", sa.UUID(), nullable=False),
        sa.Column("publication_version_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('requested','cancelled','rejected','approved')",
            name=op.f("ck_shift_swap_history_action"),
        ),
        sa.CheckConstraint(
            "to_status IN ('pending','cancelled','rejected','approved') AND "
            "(from_status IS NULL OR from_status='pending')",
            name=op.f("ck_shift_swap_history_status"),
        ),
        sa.CheckConstraint(
            "octet_length(btrim(reason)) BETWEEN 3 AND 500",
            name=op.f("ck_shift_swap_history_reason"),
        ),
        sa.CheckConstraint(
            "(action='approved')=(publication_version_id IS NOT NULL)",
            name=op.f("ck_shift_swap_history_publication"),
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shift_swap_request_id"], ["shift_swap_requests.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["publication_version_id"], ["roster_publication_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shift_swap_history")),
    )
    op.create_index(
        "ix_shift_swap_history_scope_request",
        "shift_swap_history",
        ["company_id", "branch_id", "shift_swap_request_id", "created_at", "id"],
    )
    op.execute("""
CREATE FUNCTION public.phase10i_shift_swap_history_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF current_user='workloop_migration' THEN
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'shift_swap_history is append only' USING ERRCODE='42501';
END $$;
CREATE TRIGGER trg_phase10i_shift_swap_history_append_only
BEFORE UPDATE OR DELETE ON public.shift_swap_history
FOR EACH ROW EXECUTE FUNCTION public.phase10i_shift_swap_history_append_only();
ALTER FUNCTION public.phase10i_shift_swap_history_append_only() OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.phase10i_shift_swap_history_append_only() FROM PUBLIC,workloop_runtime;
""")


def _replace_policies() -> None:
    for name in (
        "phase5f_shift_swap_requests_select_runtime",
        "phase5f_shift_swap_requests_insert_runtime",
        "phase5f_shift_swap_requests_update_runtime",
    ):
        op.execute(f"DROP POLICY {name} ON public.shift_swap_requests")
    op.execute(f"""
CREATE POLICY phase10i_shift_swap_requests_select_runtime ON public.shift_swap_requests
FOR SELECT TO workloop_runtime USING ({HUMAN_CONTEXT} AND (
  public.workloop_role()='admin' OR (public.workloop_role() IN ('manager','employee')
    AND public.workloop_employee_id() IN (requester_employee_id,target_employee_id))));
CREATE POLICY phase10i_shift_swap_requests_insert_runtime ON public.shift_swap_requests
FOR INSERT TO workloop_runtime WITH CHECK ({HUMAN_CONTEXT}
  AND public.workloop_role() IN ('manager','employee')
  AND requester_employee_id=public.workloop_employee_id()
  AND target_employee_id<>public.workloop_employee_id()
  AND contract_version=1 AND status='pending' AND version=1);
CREATE POLICY phase10i_shift_swap_requests_update_runtime ON public.shift_swap_requests
FOR UPDATE TO workloop_runtime USING ({HUMAN_CONTEXT} AND contract_version=1
  AND status='pending' AND (public.workloop_role()='admin' OR
    (public.workloop_role() IN ('manager','employee')
      AND requester_employee_id=public.workloop_employee_id())))
WITH CHECK ({HUMAN_CONTEXT} AND contract_version=1
  AND ((public.workloop_role()='admin' AND status='rejected'
        AND decided_by_app_user_id=public.workloop_app_user_id())
    OR (public.workloop_role() IN ('manager','employee') AND status='cancelled'
        AND requester_employee_id=public.workloop_employee_id()
        AND decided_by_app_user_id=public.workloop_app_user_id())));
""")
    op.execute("ALTER TABLE public.shift_swap_history ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.shift_swap_history FORCE ROW LEVEL SECURITY")
    op.execute(f"""
CREATE POLICY phase10i_shift_swap_history_admin_select ON public.shift_swap_history
FOR SELECT TO workloop_runtime USING ({HUMAN_CONTEXT} AND public.workloop_role()='admin');
CREATE POLICY phase10i_shift_swap_history_runtime_insert ON public.shift_swap_history
FOR INSERT TO workloop_runtime WITH CHECK ({HUMAN_CONTEXT}
  AND actor_app_user_id=public.workloop_app_user_id()
  AND ((public.workloop_role()='admin' AND action='rejected')
    OR (public.workloop_role() IN ('manager','employee')
        AND action IN ('requested','cancelled'))));
CREATE POLICY phase10i_shift_swap_history_migration ON public.shift_swap_history
FOR ALL TO workloop_migration USING (true) WITH CHECK (true);
GRANT SELECT,INSERT ON public.shift_swap_history TO workloop_runtime;
REVOKE INSERT ON public.shift_swap_requests FROM workloop_runtime;
""")


def _create_staff_submission_function() -> None:
    op.execute(r"""
CREATE FUNCTION public.staff_submit_shift_swap(
  p_target_employee_id uuid,p_requester_date date,p_target_date date,
  p_reason text,p_expected_source_version text)
RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  v_company_id uuid := public.workloop_company_id();
  v_branch_id uuid := public.workloop_branch_id();
  v_requester_employee_id uuid := public.workloop_employee_id();
  v_actor_app_user_id uuid := public.workloop_app_user_id();
  v_month public.roster_months%ROWTYPE;
  v_requester public.roster_publication_memberships%ROWTYPE;
  v_target public.roster_publication_memberships%ROWTYPE;
  v_requester_employee public.employees%ROWTYPE;
  v_target_employee public.employees%ROWTYPE;
  v_swap_id uuid := gen_random_uuid();
BEGIN
  IF current_user<>'workloop_migration' OR session_user<>'workloop_runtime'
     OR public.workloop_actor_kind()<>'human' OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR public.workloop_role() NOT IN ('manager','employee')
     OR v_company_id IS NULL OR v_branch_id IS NULL
     OR v_requester_employee_id IS NULL OR v_actor_app_user_id IS NULL
     OR p_target_employee_id=v_requester_employee_id
     OR p_requester_date=p_target_date
     OR to_char(p_requester_date,'YYYY-MM')<>to_char(p_target_date,'YYYY-MM')
     OR octet_length(btrim(p_reason)) NOT BETWEEN 3 AND 500
     OR p_expected_source_version !~ '^sha256:[0-9a-f]{64}$'
     OR NOT EXISTS (
       SELECT 1 FROM public.resolve_workloop_principal() principal
       WHERE principal.app_user_id=v_actor_app_user_id
         AND principal.account_status='active'
         AND principal.role=public.workloop_role()
         AND principal.profile_company_id=v_company_id
         AND principal.company_id=principal.profile_company_id
         AND principal.profile_employee_id=v_requester_employee_id
         AND principal.employee_id=principal.profile_employee_id
         AND principal.employee_branch_id=v_branch_id
         AND principal.branch_id=principal.employee_branch_id
         AND principal.employee_active
         AND principal.employment_status IN ('Active','Probation','On Leave'))
  THEN RAISE EXCEPTION 'shift_swap_forbidden' USING ERRCODE='42501'; END IF;

  SELECT * INTO v_month FROM public.roster_months
  WHERE company_id=v_company_id AND branch_id=v_branch_id
    AND period=to_char(p_requester_date,'YYYY-MM') AND status='published'
    AND source_version=p_expected_source_version
  FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'shift_swap_roster_changed'; END IF;

  SELECT * INTO v_requester FROM public.roster_publication_memberships
  WHERE publication_version_id=v_month.current_version_id
    AND employee_id=v_requester_employee_id AND date=p_requester_date;
  SELECT * INTO v_target FROM public.roster_publication_memberships
  WHERE publication_version_id=v_month.current_version_id
    AND employee_id=p_target_employee_id AND date=p_target_date;
  IF v_requester.id IS NULL OR v_target.id IS NULL
     OR v_requester.source_assignment_id=v_target.source_assignment_id
     OR v_requester.actual_evidence_id IS NOT NULL
     OR v_target.actual_evidence_id IS NOT NULL
  THEN RAISE EXCEPTION 'shift_swap_assignments_unavailable'; END IF;

  SELECT * INTO v_requester_employee FROM public.employees
  WHERE id=v_requester_employee_id AND company_id=v_company_id AND branch_id=v_branch_id;
  SELECT * INTO v_target_employee FROM public.employees
  WHERE id=p_target_employee_id AND company_id=v_company_id AND branch_id=v_branch_id;
  IF v_requester_employee.id IS NULL OR v_target_employee.id IS NULL
     OR NOT v_requester_employee.active OR NOT v_target_employee.active
     OR v_requester_employee.employment_status NOT IN ('Active','Probation')
     OR v_target_employee.employment_status NOT IN ('Active','Probation')
     OR v_requester_employee.department IS DISTINCT FROM v_target_employee.department
     OR (v_requester_employee.employment_start_date IS NOT NULL
         AND v_requester_employee.employment_start_date>p_target_date)
     OR (v_requester_employee.termination_date IS NOT NULL
         AND v_requester_employee.termination_date<p_target_date)
     OR (v_target_employee.employment_start_date IS NOT NULL
         AND v_target_employee.employment_start_date>p_requester_date)
     OR (v_target_employee.termination_date IS NOT NULL
         AND v_target_employee.termination_date<p_requester_date)
  THEN RAISE EXCEPTION 'shift_swap_employee_ineligible'; END IF;

  INSERT INTO public.shift_swap_requests(
    id,company_id,branch_id,requester_employee_id,target_employee_id,
    requester_date,target_date,reason,contract_version,
    expected_roster_source_version,source_publication_version_id,
    requester_assignment_id,target_assignment_id,
    expected_requester_assignment_version,expected_target_assignment_version)
  VALUES (v_swap_id,v_company_id,v_branch_id,v_requester_employee_id,p_target_employee_id,
    p_requester_date,p_target_date,btrim(p_reason),1,p_expected_source_version,
    v_month.current_version_id,v_requester.source_assignment_id,v_target.source_assignment_id,
    v_requester.source_assignment_version,v_target.source_assignment_version);
  INSERT INTO public.shift_swap_history(company_id,branch_id,shift_swap_request_id,
    action,from_status,to_status,actor_app_user_id,reason)
  VALUES (v_company_id,v_branch_id,v_swap_id,'requested',NULL,'pending',
    v_actor_app_user_id,btrim(p_reason));
  RETURN v_swap_id;
END
$function$;
ALTER FUNCTION public.staff_submit_shift_swap(uuid,date,date,text,text)
OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.staff_submit_shift_swap(uuid,date,date,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.staff_submit_shift_swap(uuid,date,date,text,text)
TO workloop_runtime;
""")


def _create_participant_name_function() -> None:
    op.execute(r"""
CREATE FUNCTION public.shift_swap_participant_name(p_swap_id uuid,p_employee_id uuid)
RETURNS text
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  v_name text;
BEGIN
  IF current_user<>'workloop_migration' OR session_user<>'workloop_runtime'
     OR public.workloop_actor_kind()<>'human' OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR NOT EXISTS (
       SELECT 1 FROM public.resolve_workloop_principal() principal
       WHERE principal.app_user_id=public.workloop_app_user_id()
         AND principal.account_status='active'
         AND principal.role=public.workloop_role()
         AND principal.profile_company_id=public.workloop_company_id()
         AND principal.company_id=principal.profile_company_id
         AND ((principal.role='admin' AND principal.profile_employee_id IS NULL
               AND principal.employee_id IS NULL AND principal.branch_id IS NULL
               AND public.workloop_employee_id() IS NULL)
           OR (principal.role IN ('manager','employee')
               AND principal.profile_employee_id=public.workloop_employee_id()
               AND principal.employee_id=principal.profile_employee_id
               AND principal.employee_branch_id=public.workloop_branch_id()
               AND principal.branch_id=principal.employee_branch_id
               AND principal.employee_active
               AND principal.employment_status IN ('Active','Probation','On Leave'))))
     OR NOT EXISTS (
       SELECT 1 FROM public.shift_swap_requests swap
       WHERE swap.id=p_swap_id
         AND swap.company_id=public.workloop_company_id()
         AND swap.branch_id=public.workloop_branch_id()
         AND p_employee_id IN (swap.requester_employee_id,swap.target_employee_id)
         AND (public.workloop_role()='admin'
           OR public.workloop_employee_id() IN
             (swap.requester_employee_id,swap.target_employee_id)))
  THEN RETURN NULL; END IF;
  SELECT employee.name INTO v_name FROM public.employees employee
  WHERE employee.id=p_employee_id
    AND employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id();
  RETURN v_name;
END
$function$;
ALTER FUNCTION public.shift_swap_participant_name(uuid,uuid) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.shift_swap_participant_name(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.shift_swap_participant_name(uuid,uuid) TO workloop_runtime;
""")


def _replace_function() -> None:
    op.execute("""
ALTER FUNCTION public.admin_execute_shift_swap(uuid,uuid)
RENAME TO _admin_execute_shift_swap_phase10h;
REVOKE ALL ON FUNCTION public._admin_execute_shift_swap_phase10h(uuid,uuid) FROM PUBLIC,workloop_runtime;
""")
    op.execute(r"""
CREATE FUNCTION public.admin_execute_shift_swap(p_swap_id uuid,p_actor_app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  v_swap public.shift_swap_requests%ROWTYPE;
  v_month public.roster_months%ROWTYPE;
  v_requester public.roster_assignments%ROWTYPE;
  v_target public.roster_assignments%ROWTYPE;
  v_requester_employee public.employees%ROWTYPE;
  v_target_employee public.employees%ROWTYPE;
  v_employee_count integer;
  v_membership_count integer;
  v_version_id uuid := gen_random_uuid();
  v_version integer;
  v_now timestamptz := clock_timestamp();
  v_payload jsonb;
  v_canonical text;
  v_source_version text;
  v_affected_digest text;
BEGIN
  IF current_user<>'workloop_migration' OR session_user<>'workloop_runtime'
     OR public.workloop_actor_kind()<>'human' OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL OR public.workloop_role()<>'admin'
     OR public.workloop_app_user_id() IS DISTINCT FROM p_actor_app_user_id
     OR public.workloop_employee_id() IS NOT NULL
     OR NOT EXISTS (
       SELECT 1 FROM public.resolve_workloop_principal() principal
       WHERE principal.app_user_id=p_actor_app_user_id
         AND principal.account_status='active' AND principal.role='admin'
         AND principal.profile_company_id=public.workloop_company_id()
         AND principal.company_id=principal.profile_company_id
         AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL
         AND principal.branch_id IS NULL)
  THEN RAISE EXCEPTION 'shift_swap_forbidden' USING ERRCODE='42501'; END IF;

  SELECT * INTO v_swap FROM public.shift_swap_requests
  WHERE id=p_swap_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'shift_swap_not_found'; END IF;
  IF v_swap.contract_version=0 THEN
    RETURN public._admin_execute_shift_swap_phase10h(p_swap_id,p_actor_app_user_id);
  END IF;
  IF v_swap.status<>'pending' THEN RAISE EXCEPTION 'shift_swap_not_pending'; END IF;
  IF v_swap.company_id IS DISTINCT FROM public.workloop_company_id()
     OR v_swap.branch_id IS DISTINCT FROM public.workloop_branch_id()
  THEN RAISE EXCEPTION 'shift_swap_forbidden' USING ERRCODE='42501'; END IF;

  SELECT * INTO v_month FROM public.roster_months
  WHERE company_id=v_swap.company_id AND branch_id=v_swap.branch_id
    AND current_version_id=v_swap.source_publication_version_id
    AND source_version=v_swap.expected_roster_source_version AND status='published'
  FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'shift_swap_roster_changed'; END IF;

  PERFORM employee.id FROM public.employees AS employee
  WHERE employee.id IN (v_swap.requester_employee_id,v_swap.target_employee_id)
    AND employee.company_id=v_swap.company_id AND employee.branch_id=v_swap.branch_id
  ORDER BY employee.id FOR UPDATE;
  GET DIAGNOSTICS v_employee_count=ROW_COUNT;
  SELECT * INTO v_requester_employee FROM public.employees
   WHERE id=v_swap.requester_employee_id;
  SELECT * INTO v_target_employee FROM public.employees
   WHERE id=v_swap.target_employee_id;
  IF v_employee_count<>2 OR NOT v_requester_employee.active OR NOT v_target_employee.active
     OR v_requester_employee.employment_status NOT IN ('Active','Probation')
     OR v_target_employee.employment_status NOT IN ('Active','Probation')
     OR v_requester_employee.department IS DISTINCT FROM v_target_employee.department
     OR (v_requester_employee.employment_start_date IS NOT NULL
         AND v_requester_employee.employment_start_date>v_swap.target_date)
     OR (v_requester_employee.termination_date IS NOT NULL
         AND v_requester_employee.termination_date<v_swap.target_date)
     OR (v_target_employee.employment_start_date IS NOT NULL
         AND v_target_employee.employment_start_date>v_swap.requester_date)
     OR (v_target_employee.termination_date IS NOT NULL
         AND v_target_employee.termination_date<v_swap.requester_date)
  THEN RAISE EXCEPTION 'shift_swap_employee_ineligible'; END IF;

  PERFORM roster.id FROM public.roster_assignments roster
  WHERE roster.id IN (v_swap.requester_assignment_id,v_swap.target_assignment_id)
  ORDER BY roster.id FOR UPDATE;
  SELECT * INTO v_requester FROM public.roster_assignments
   WHERE id=v_swap.requester_assignment_id;
  SELECT * INTO v_target FROM public.roster_assignments
   WHERE id=v_swap.target_assignment_id;
  IF v_requester.id IS NULL OR v_target.id IS NULL
     OR v_requester.employee_id IS DISTINCT FROM v_swap.requester_employee_id
     OR v_target.employee_id IS DISTINCT FROM v_swap.target_employee_id
     OR v_requester.date IS DISTINCT FROM v_swap.requester_date
     OR v_target.date IS DISTINCT FROM v_swap.target_date
     OR v_requester.version IS DISTINCT FROM v_swap.expected_requester_assignment_version
     OR v_target.version IS DISTINCT FROM v_swap.expected_target_assignment_version
     OR NOT v_requester.published OR NOT v_target.published
  THEN RAISE EXCEPTION 'shift_swap_roster_changed'; END IF;

  PERFORM membership.id FROM public.roster_publication_memberships membership
  WHERE membership.publication_version_id=v_month.current_version_id
    AND membership.source_assignment_id IN
      (v_swap.requester_assignment_id,v_swap.target_assignment_id)
    AND membership.actual_evidence_id IS NULL
  ORDER BY membership.source_assignment_id FOR SHARE;
  SELECT count(*) INTO v_membership_count
  FROM public.roster_publication_memberships membership
  WHERE membership.publication_version_id=v_month.current_version_id
    AND membership.source_assignment_id IN
      (v_swap.requester_assignment_id,v_swap.target_assignment_id)
    AND membership.actual_evidence_id IS NULL;
  IF v_membership_count<>2 THEN RAISE EXCEPTION 'shift_swap_roster_changed'; END IF;
  IF EXISTS (SELECT 1 FROM public.shifts shift
    WHERE shift.id IN (v_requester.shift_id,v_target.shift_id) AND NOT shift.is_active)
  THEN RAISE EXCEPTION 'shift_swap_shift_ineligible'; END IF;
  IF EXISTS (SELECT 1 FROM public.leave_requests leave_request
    WHERE leave_request.company_id=v_swap.company_id
      AND leave_request.branch_id=v_swap.branch_id
      AND leave_request.status IN ('Approved','ManagerApproved')
      AND ((leave_request.employee_id=v_swap.requester_employee_id
            AND v_swap.target_date BETWEEN leave_request.start_date AND leave_request.end_date)
        OR (leave_request.employee_id=v_swap.target_employee_id
            AND v_swap.requester_date BETWEEN leave_request.start_date AND leave_request.end_date)))
  THEN RAISE EXCEPTION 'shift_swap_leave_conflict'; END IF;
  IF EXISTS (SELECT 1 FROM public.payroll_entries entry
    JOIN public.payroll_runs run ON run.id=entry.payroll_run_id
    CROSS JOIN LATERAL jsonb_array_elements(
      COALESCE(entry.source_snapshot->'automaticInputs','[]'::jsonb)) source
    WHERE run.company_id=v_swap.company_id AND run.branch_id=v_swap.branch_id
      AND source->>'sourceType'='roster'
      AND source->>'sourceVersion'=v_month.source_version)
  THEN RAISE EXCEPTION 'shift_swap_payroll_frozen'; END IF;

  UPDATE public.roster_assignments SET employee_id=v_swap.target_employee_id,version=version+1
   WHERE id=v_swap.requester_assignment_id;
  UPDATE public.roster_assignments SET employee_id=v_swap.requester_employee_id,version=version+1
   WHERE id=v_swap.target_assignment_id;
  v_version := v_month.version+1;

  WITH transformed AS (
    SELECT membership.*,
      CASE WHEN membership.source_assignment_id=v_swap.requester_assignment_id
        THEN v_swap.target_employee_id
        WHEN membership.source_assignment_id=v_swap.target_assignment_id
        THEN v_swap.requester_employee_id ELSE membership.employee_id END next_employee_id,
      CASE WHEN membership.source_assignment_id=v_swap.requester_assignment_id
        THEN v_target_employee.name
        WHEN membership.source_assignment_id=v_swap.target_assignment_id
        THEN v_requester_employee.name ELSE membership.employee_name END next_employee_name,
      CASE WHEN membership.source_assignment_id IN
        (v_swap.requester_assignment_id,v_swap.target_assignment_id)
        THEN membership.source_assignment_version+1
        ELSE membership.source_assignment_version END next_assignment_version
    FROM public.roster_publication_memberships membership
    WHERE membership.publication_version_id=v_month.current_version_id
  )
  SELECT jsonb_build_object(
    'branchId',v_swap.branch_id::text,'companyId',v_swap.company_id::text,
    'kind','swap','memberships',jsonb_agg(jsonb_build_object(
      'date',date::text,'employeeId',next_employee_id::text,
      'employeeName',next_employee_name,'rosterAssignmentId',source_assignment_id::text,
      'rosterAssignmentVersion',next_assignment_version,'shiftId',shift_id::text,
      'shiftName',shift_name,'plannedHours',planned_hours::text)
      ORDER BY date,next_employee_id,source_assignment_id),
    'period',v_month.period,
    'publishedAt',to_char(v_now AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'),
    'version',v_version,'swapRequestId',p_swap_id::text)
  INTO v_payload FROM transformed;
  v_canonical := v_payload::text;
  v_source_version := 'sha256:'||pg_catalog.encode(
    pg_catalog.sha256(pg_catalog.convert_to(v_canonical,'UTF8')),'hex');
  SELECT 'sha256:'||pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
    jsonb_agg(source_assignment_id::text ORDER BY source_assignment_id)::text,'UTF8')),'hex')
  INTO v_affected_digest FROM public.roster_publication_memberships
  WHERE publication_version_id=v_month.current_version_id;

  INSERT INTO public.roster_publication_versions(
    id,company_id,branch_id,roster_month_id,prior_version_id,period,version,kind,
    source_version,source_canonical,source_payload,affected_row_digest,record_count,
    actor_app_user_id,reason,published_at)
  VALUES (v_version_id,v_swap.company_id,v_swap.branch_id,v_month.id,
    v_month.current_version_id,v_month.period,v_version,'swap',v_source_version,
    v_canonical,v_payload,v_affected_digest,(
      SELECT count(*) FROM public.roster_publication_memberships
      WHERE publication_version_id=v_month.current_version_id),p_actor_app_user_id,
    left('Shift swap: '||v_swap.reason,500),v_now);

  INSERT INTO public.roster_publication_memberships(
    company_id,branch_id,publication_version_id,source_assignment_id,
    source_assignment_version,employee_id,employee_name,department,shift_id,shift_name,
    shift_code,shift_category,date,planned_hours,notes,actual_evidence_id,actual_hours,
    overtime_approval_id,overtime_hours,overtime_amount,attendance_overlap_hours,
    attendance_source_ids,salary_source_version,source_payload)
  SELECT membership.company_id,membership.branch_id,v_version_id,
    membership.source_assignment_id,
    CASE WHEN membership.source_assignment_id IN
      (v_swap.requester_assignment_id,v_swap.target_assignment_id)
      THEN membership.source_assignment_version+1 ELSE membership.source_assignment_version END,
    CASE WHEN membership.source_assignment_id=v_swap.requester_assignment_id
      THEN v_swap.target_employee_id WHEN membership.source_assignment_id=v_swap.target_assignment_id
      THEN v_swap.requester_employee_id ELSE membership.employee_id END,
    CASE WHEN membership.source_assignment_id=v_swap.requester_assignment_id
      THEN v_target_employee.name WHEN membership.source_assignment_id=v_swap.target_assignment_id
      THEN v_requester_employee.name ELSE membership.employee_name END,
    membership.department,membership.shift_id,membership.shift_name,membership.shift_code,
    membership.shift_category,membership.date,membership.planned_hours,membership.notes,
    membership.actual_evidence_id,membership.actual_hours,membership.overtime_approval_id,
    membership.overtime_hours,membership.overtime_amount,membership.attendance_overlap_hours,
    membership.attendance_source_ids,membership.salary_source_version,
    jsonb_build_object('date',membership.date::text,'employeeId',
      (CASE WHEN membership.source_assignment_id=v_swap.requester_assignment_id
        THEN v_swap.target_employee_id WHEN membership.source_assignment_id=v_swap.target_assignment_id
        THEN v_swap.requester_employee_id ELSE membership.employee_id END)::text,
      'rosterAssignmentId',membership.source_assignment_id::text,
      'shiftId',membership.shift_id::text,'plannedHours',membership.planned_hours::text)
  FROM public.roster_publication_memberships membership
  WHERE membership.publication_version_id=v_month.current_version_id;

  UPDATE public.roster_months SET version=v_version,current_version_id=v_version_id,
    source_version=v_source_version,published_at=v_now,
    published_by_app_user_id=p_actor_app_user_id,updated_at=v_now
  WHERE id=v_month.id;
  UPDATE public.shift_swap_requests SET status='approved',admin_approved_at=v_now,
    admin_approved_by_app_user_id=p_actor_app_user_id,rejection_reason='',decided_at=v_now,
    decided_by_app_user_id=p_actor_app_user_id,approved_publication_version_id=v_version_id,
    version=version+1 WHERE id=p_swap_id;
  INSERT INTO public.shift_swap_history(company_id,branch_id,shift_swap_request_id,
    action,from_status,to_status,actor_app_user_id,publication_version_id,reason)
  VALUES (v_swap.company_id,v_swap.branch_id,p_swap_id,'approved','pending','approved',
    p_actor_app_user_id,v_version_id,left('Shift swap: '||v_swap.reason,500));
  PERFORM public.append_audit_event('shift_swap_approved','shift_swap_request',p_swap_id,
    ARRAY['status','admin_approved_by_app_user_id']::text[],
    'Shift swap approved','{"transition":"pending_to_approved"}'::jsonb);
  RETURN true;
END
$function$;
ALTER FUNCTION public.admin_execute_shift_swap(uuid,uuid) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.admin_execute_shift_swap(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.admin_execute_shift_swap(uuid,uuid) TO workloop_runtime;
""")


def upgrade() -> None:
    _add_request_contract()
    _create_history()
    _replace_policies()
    _create_staff_submission_function()
    _create_participant_name_function()
    _replace_function()
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10I_REPLAY)


def downgrade() -> None:
    op.execute("""
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.shift_swap_requests WHERE contract_version=1)
     OR EXISTS (SELECT 1 FROM public.shift_swap_history)
     OR EXISTS (SELECT 1 FROM public.roster_publication_versions WHERE kind='swap')
  THEN RAISE EXCEPTION 'phase10i_shift_swap_data_requires_preservation'; END IF;
END $$;
""")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10H_REPLAY)
    op.execute("DROP FUNCTION IF EXISTS public.shift_swap_participant_name(uuid,uuid)")
    op.execute("DROP FUNCTION IF EXISTS public.staff_submit_shift_swap(uuid,date,date,text,text)")
    op.execute("GRANT INSERT ON public.shift_swap_requests TO workloop_runtime")
    op.execute("DROP FUNCTION public.admin_execute_shift_swap(uuid,uuid)")
    op.execute(
        "ALTER FUNCTION public._admin_execute_shift_swap_phase10h(uuid,uuid) RENAME TO admin_execute_shift_swap"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.admin_execute_shift_swap(uuid,uuid) TO workloop_runtime"
    )
    op.execute("DROP POLICY phase10i_shift_swap_history_migration ON public.shift_swap_history")
    op.execute(
        "DROP POLICY phase10i_shift_swap_history_runtime_insert ON public.shift_swap_history"
    )
    op.execute("DROP POLICY phase10i_shift_swap_history_admin_select ON public.shift_swap_history")
    op.execute(
        "DROP TRIGGER trg_phase10i_shift_swap_history_append_only ON public.shift_swap_history"
    )
    op.execute("DROP FUNCTION public.phase10i_shift_swap_history_append_only()")
    op.drop_index("ix_shift_swap_history_scope_request", table_name="shift_swap_history")
    op.drop_table("shift_swap_history")
    for name in (
        "phase10i_shift_swap_requests_update_runtime",
        "phase10i_shift_swap_requests_insert_runtime",
        "phase10i_shift_swap_requests_select_runtime",
    ):
        op.execute(f"DROP POLICY {name} ON public.shift_swap_requests")
    op.execute("DROP INDEX public.uq_shift_swap_requests_phase10i_pending_pair")
    op.drop_index("ix_shift_swap_requests_phase10i_scope_status", table_name="shift_swap_requests")
    op.drop_constraint("phase10i_decision", "shift_swap_requests", type_="check")
    op.drop_constraint("phase10i_contract", "shift_swap_requests", type_="check")
    for name in (
        "fk_shift_swap_requests_decided_by_app_user_id",
        "fk_shift_swap_requests_target_assignment_id",
        "fk_shift_swap_requests_requester_assignment_id",
        "fk_shift_swap_requests_approved_publication_version_id",
        "fk_shift_swap_requests_source_publication_version_id",
    ):
        op.drop_constraint(name, "shift_swap_requests", type_="foreignkey")
    for column in (
        "version",
        "decided_by_app_user_id",
        "decided_at",
        "approved_publication_version_id",
        "expected_target_assignment_version",
        "expected_requester_assignment_version",
        "target_assignment_id",
        "requester_assignment_id",
        "source_publication_version_id",
        "expected_roster_source_version",
        "contract_version",
    ):
        op.drop_column("shift_swap_requests", column)
    op.execute(f"""
CREATE POLICY phase5f_shift_swap_requests_select_runtime ON public.shift_swap_requests
FOR SELECT TO workloop_runtime USING ({HUMAN_CONTEXT} AND (
  public.workloop_role()='admin' OR (public.workloop_role() IN ('manager','employee')
    AND public.workloop_employee_id() IN (requester_employee_id,target_employee_id))));
CREATE POLICY phase5f_shift_swap_requests_insert_runtime ON public.shift_swap_requests
FOR INSERT TO workloop_runtime WITH CHECK ({HUMAN_CONTEXT}
  AND public.workloop_role() IN ('manager','employee')
  AND requester_employee_id=public.workloop_employee_id()
  AND target_employee_id<>public.workloop_employee_id() AND status='pending');
CREATE POLICY phase5f_shift_swap_requests_update_runtime ON public.shift_swap_requests
FOR UPDATE TO workloop_runtime USING ({HUMAN_CONTEXT} AND status='pending' AND (
  public.workloop_role()='admin' OR (public.workloop_role() IN ('manager','employee')
    AND requester_employee_id=public.workloop_employee_id())))
WITH CHECK ({HUMAN_CONTEXT} AND status<>'approved' AND (
  public.workloop_role()='admin' OR (public.workloop_role() IN ('manager','employee')
    AND requester_employee_id=public.workloop_employee_id() AND status='cancelled')));
""")
