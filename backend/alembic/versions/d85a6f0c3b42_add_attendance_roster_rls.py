"""Add Phase 5F attendance and roster row security.

Revision ID: d85a6f0c3b42
Revises: c74f5e9b2a31
Created: 2026-09-06 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d85a6f0c3b42"
down_revision: str | Sequence[str] | None = "c74f5e9b2a31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RLS_TABLES: tuple[str, ...] = (
    "attendance_settings",
    "shifts",
    "shift_assignments",
    "clock_events",
    "attendance_records",
    "attendance_periods",
    "regularisation_requests",
    "attendance_audit_log",
    "roster_assignments",
    "shift_swap_requests",
    "biometric_mappings",
)

HUMAN_CONTEXT = """
current_user = 'workloop_runtime'
AND session_user = 'workloop_runtime'
AND public.workloop_actor_kind() = 'human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND EXISTS (
  SELECT 1
  FROM public.resolve_workloop_principal() AS principal
  WHERE principal.app_user_id = public.workloop_app_user_id()
    AND principal.account_status = 'active'
    AND principal.profile_app_user_id = principal.app_user_id
    AND principal.role = public.workloop_role()
    AND principal.profile_company_id = public.workloop_company_id()
    AND principal.company_id = principal.profile_company_id
    AND (
      (
        principal.role = 'admin'
        AND principal.profile_employee_id IS NULL
        AND principal.employee_id IS NULL
        AND principal.branch_id IS NULL
        AND public.workloop_employee_id() IS NULL
      )
      OR
      (
        principal.role IN ('manager', 'employee')
        AND principal.profile_employee_id = public.workloop_employee_id()
        AND principal.employee_id = principal.profile_employee_id
        AND principal.employee_company_id = principal.profile_company_id
        AND principal.employee_branch_id = public.workloop_branch_id()
        AND principal.employee_active
        AND principal.employment_status IN ('Active', 'Probation', 'On Leave')
        AND principal.branch_id = principal.employee_branch_id
        AND principal.branch_company_id = principal.profile_company_id
      )
    )
)
""".strip()


def _policy(
    name: str,
    table: str,
    command: str,
    *,
    using: str | None = None,
    check: str | None = None,
) -> None:
    clauses: list[str] = []
    if using is not None:
        clauses.append(f"USING ({using})")
    if check is not None:
        clauses.append(f"WITH CHECK ({check})")
    op.execute(
        f"CREATE POLICY {name} ON public.{table} FOR {command} "
        "TO workloop_runtime " + " ".join(clauses)
    )


def _admin_branch() -> str:
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()"""


def _self_scope() -> str:
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND employee_id = public.workloop_employee_id()"""


def _create_policies() -> None:
    admin = _admin_branch()
    self_scope = _self_scope()

    for table in ("attendance_settings", "shift_assignments"):
        for command in ("SELECT", "INSERT", "UPDATE"):
            _policy(
                f"phase5f_{table}_{command.lower()}_runtime",
                table,
                command,
                using=admin if command != "INSERT" else None,
                check=admin if command in {"INSERT", "UPDATE"} else None,
            )

    staff_shift = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND is_active"""
    _policy(
        "phase5f_shifts_select_runtime",
        "shifts",
        "SELECT",
        using=f"({admin}) OR ({staff_shift})",
    )
    for command in ("INSERT", "UPDATE"):
        _policy(
            f"phase5f_shifts_{command.lower()}_runtime",
            "shifts",
            command,
            using=admin if command == "UPDATE" else None,
            check=admin,
        )

    _policy(
        "phase5f_clock_events_select_runtime",
        "clock_events",
        "SELECT",
        using=f"({admin}) OR ({self_scope})",
    )
    _policy(
        "phase5f_clock_events_insert_runtime",
        "clock_events",
        "INSERT",
        check=admin,
    )

    _policy(
        "phase5f_attendance_records_select_runtime",
        "attendance_records",
        "SELECT",
        using=f"({admin}) OR ({self_scope})",
    )
    for command in ("INSERT", "UPDATE"):
        _policy(
            f"phase5f_attendance_records_{command.lower()}_runtime",
            "attendance_records",
            command,
            using=admin if command == "UPDATE" else None,
            check=admin,
        )

    for command in ("SELECT", "INSERT", "UPDATE"):
        _policy(
            f"phase5f_attendance_periods_{command.lower()}_runtime",
            "attendance_periods",
            command,
            using=admin if command != "INSERT" else None,
            check=admin if command in {"INSERT", "UPDATE"} else None,
        )

    regularisation_scope = f"({admin}) OR ({self_scope})"
    _policy(
        "phase5f_regularisation_requests_select_runtime",
        "regularisation_requests",
        "SELECT",
        using=regularisation_scope,
    )
    _policy(
        "phase5f_regularisation_requests_insert_runtime",
        "regularisation_requests",
        "INSERT",
        check=self_scope,
    )
    _policy(
        "phase5f_regularisation_requests_update_runtime",
        "regularisation_requests",
        "UPDATE",
        using=admin,
        check=admin,
    )

    audit_insert = f"""{admin}
AND actor_app_user_id = public.workloop_app_user_id()"""
    _policy(
        "phase5f_attendance_audit_log_select_runtime",
        "attendance_audit_log",
        "SELECT",
        using=admin,
    )
    _policy(
        "phase5f_attendance_audit_log_insert_runtime",
        "attendance_audit_log",
        "INSERT",
        check=audit_insert,
    )

    roster_select = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND (
  public.workloop_role() = 'admin'
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND employee_id = public.workloop_employee_id()
    AND published
  )
)"""
    _policy(
        "phase5f_roster_assignments_select_runtime",
        "roster_assignments",
        "SELECT",
        using=roster_select,
    )
    _policy(
        "phase5f_roster_assignments_insert_runtime",
        "roster_assignments",
        "INSERT",
        check=admin,
    )
    roster_update = f"""{admin}
AND NOT published"""
    _policy(
        "phase5f_roster_assignments_update_runtime",
        "roster_assignments",
        "UPDATE",
        using=roster_update,
        check=admin,
    )
    roster_delete = f"""{admin}
AND NOT published
AND NOT EXISTS (
  SELECT 1 FROM public.shift_swap_requests AS swap
  WHERE swap.company_id = roster_assignments.company_id
    AND swap.branch_id = roster_assignments.branch_id
    AND (
      (
        swap.requester_employee_id = roster_assignments.employee_id
        AND swap.requester_date = roster_assignments.date
      )
      OR (
        swap.target_employee_id = roster_assignments.employee_id
        AND swap.target_date = roster_assignments.date
      )
    )
)"""
    _policy(
        "phase5f_roster_assignments_delete_runtime",
        "roster_assignments",
        "DELETE",
        using=roster_delete,
    )

    swap_select = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND (
  public.workloop_role() = 'admin'
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND public.workloop_employee_id() IN (
      requester_employee_id, target_employee_id
    )
  )
)"""
    _policy(
        "phase5f_shift_swap_requests_select_runtime",
        "shift_swap_requests",
        "SELECT",
        using=swap_select,
    )
    swap_insert = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND requester_employee_id = public.workloop_employee_id()
AND target_employee_id <> public.workloop_employee_id()
AND status = 'pending'"""
    _policy(
        "phase5f_shift_swap_requests_insert_runtime",
        "shift_swap_requests",
        "INSERT",
        check=swap_insert,
    )
    swap_update_using = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND status = 'pending'
AND (
  public.workloop_role() = 'admin'
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND requester_employee_id = public.workloop_employee_id()
  )
)"""
    swap_update_check = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND status <> 'approved'
AND (
  public.workloop_role() = 'admin'
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND requester_employee_id = public.workloop_employee_id()
    AND status = 'cancelled'
  )
)"""
    _policy(
        "phase5f_shift_swap_requests_update_runtime",
        "shift_swap_requests",
        "UPDATE",
        using=swap_update_using,
        check=swap_update_check,
    )

    for command in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        _policy(
            f"phase5f_biometric_mappings_{command.lower()}_runtime",
            "biometric_mappings",
            command,
            using=admin if command != "INSERT" else None,
            check=admin if command in {"INSERT", "UPDATE"} else None,
        )


def _admin_function_guard() -> str:
    return """
  IF session_user <> 'workloop_runtime'
     OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
     OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL
     OR public.workloop_role() IS DISTINCT FROM 'admin'
     OR public.workloop_company_id() IS NULL
     OR public.workloop_branch_id() IS NULL
     OR public.workloop_employee_id() IS NOT NULL
     OR p_actor_app_user_id IS DISTINCT FROM public.workloop_app_user_id()
     OR NOT EXISTS (
       SELECT 1
       FROM public.resolve_workloop_principal() AS principal
       WHERE principal.app_user_id = public.workloop_app_user_id()
         AND principal.account_status = 'active'
         AND principal.profile_app_user_id = principal.app_user_id
         AND principal.role = 'admin'
         AND principal.profile_company_id = public.workloop_company_id()
         AND principal.company_id = principal.profile_company_id
         AND principal.profile_employee_id IS NULL
         AND principal.employee_id IS NULL
         AND principal.branch_id IS NULL
     )
     OR NOT EXISTS (
       SELECT 1
       FROM public.branches AS selected_branch
       WHERE selected_branch.id = public.workloop_branch_id()
         AND selected_branch.company_id = public.workloop_company_id()
     ) THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
"""


def _shift_swap_function_sql(*, hardened: bool) -> str:
    guard = _admin_function_guard() if hardened else ""
    swap_scope = (
        """
  IF v_swap.company_id <> public.workloop_company_id()
     OR v_swap.branch_id <> public.workloop_branch_id() THEN
    RAISE EXCEPTION 'shift_swap_out_of_scope';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.employees AS requester
    JOIN public.employees AS target
      ON target.id = v_swap.target_employee_id
     AND target.company_id = v_swap.company_id
     AND target.branch_id = v_swap.branch_id
    WHERE requester.id = v_swap.requester_employee_id
      AND requester.company_id = v_swap.company_id
      AND requester.branch_id = v_swap.branch_id
      AND requester.active
      AND requester.employment_status IN ('Active', 'Probation', 'On Leave')
      AND target.active
      AND target.employment_status IN ('Active', 'Probation', 'On Leave')
  ) THEN
    RAISE EXCEPTION 'shift_swap_employee_ineligible';
  END IF;
"""
        if hardened
        else ""
    )
    published_check = (
        """
       OR NOT v_req_row.published
       OR (v_swap.target_date IS NOT NULL AND NOT v_tgt_row.published)"""
        if hardened
        else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION public.admin_execute_shift_swap(
  p_swap_id uuid, p_actor_app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  v_swap public.shift_swap_requests%ROWTYPE;
  v_req_id uuid;
  v_tgt_id uuid;
  v_req_row public.roster_assignments%ROWTYPE;
  v_tgt_row public.roster_assignments%ROWTYPE;
BEGIN
{guard}
  SELECT * INTO v_swap FROM public.shift_swap_requests
  WHERE id = p_swap_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'shift_swap_not_found';
  END IF;
{swap_scope}
  IF v_swap.status <> 'pending' THEN
    RAISE EXCEPTION 'shift_swap_not_pending';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.user_profiles AS profile
    JOIN public.app_users AS account ON account.id = profile.app_user_id
    WHERE profile.app_user_id = p_actor_app_user_id
      AND profile.company_id = v_swap.company_id
      AND profile.role = 'admin'
      AND account.status = 'active'
  ) THEN
    RAISE EXCEPTION 'shift_swap_forbidden';
  END IF;
  IF v_swap.requester_employee_id = v_swap.target_employee_id THEN
    RAISE EXCEPTION 'shift_swap_same_employee';
  END IF;

  SELECT id INTO v_req_id
  FROM public.roster_assignments
  WHERE employee_id = v_swap.requester_employee_id
    AND date = v_swap.requester_date
    AND company_id = v_swap.company_id
    AND branch_id = v_swap.branch_id;
  IF v_req_id IS NULL THEN
    RAISE EXCEPTION 'shift_swap_requester_unassigned';
  END IF;

  IF v_swap.target_date IS NOT NULL THEN
    IF v_swap.requester_date = v_swap.target_date THEN
      RAISE EXCEPTION 'shift_swap_same_day';
    END IF;
    SELECT id INTO v_tgt_id
    FROM public.roster_assignments
    WHERE employee_id = v_swap.target_employee_id
      AND date = v_swap.target_date
      AND company_id = v_swap.company_id
      AND branch_id = v_swap.branch_id;
    IF v_tgt_id IS NULL THEN
      RAISE EXCEPTION 'shift_swap_target_unassigned';
    END IF;

    IF v_req_id < v_tgt_id THEN
      SELECT * INTO v_req_row FROM public.roster_assignments
      WHERE id = v_req_id FOR UPDATE;
      SELECT * INTO v_tgt_row FROM public.roster_assignments
      WHERE id = v_tgt_id FOR UPDATE;
    ELSE
      SELECT * INTO v_tgt_row FROM public.roster_assignments
      WHERE id = v_tgt_id FOR UPDATE;
      SELECT * INTO v_req_row FROM public.roster_assignments
      WHERE id = v_req_id FOR UPDATE;
    END IF;

    IF v_req_row.id IS NULL
       OR v_req_row.employee_id IS DISTINCT FROM v_swap.requester_employee_id
       OR v_req_row.date IS DISTINCT FROM v_swap.requester_date
       OR v_req_row.company_id IS DISTINCT FROM v_swap.company_id
       OR v_req_row.branch_id IS DISTINCT FROM v_swap.branch_id
       OR v_tgt_row.id IS NULL
       OR v_tgt_row.employee_id IS DISTINCT FROM v_swap.target_employee_id
       OR v_tgt_row.date IS DISTINCT FROM v_swap.target_date
       OR v_tgt_row.company_id IS DISTINCT FROM v_swap.company_id
       OR v_tgt_row.branch_id IS DISTINCT FROM v_swap.branch_id{published_check} THEN
      RAISE EXCEPTION 'shift_swap_roster_changed';
    END IF;

    IF EXISTS (
      SELECT 1 FROM public.roster_assignments
      WHERE company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
        AND (
          (employee_id = v_swap.target_employee_id
             AND date = v_swap.requester_date AND id <> v_req_id)
          OR (employee_id = v_swap.requester_employee_id
             AND date = v_swap.target_date AND id <> v_tgt_id)
        )
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;

    UPDATE public.roster_assignments SET employee_id = v_swap.target_employee_id
    WHERE id = v_req_id;
    UPDATE public.roster_assignments SET employee_id = v_swap.requester_employee_id
    WHERE id = v_tgt_id;
  ELSE
    SELECT * INTO v_req_row FROM public.roster_assignments
    WHERE id = v_req_id FOR UPDATE;
    IF v_req_row.id IS NULL
       OR v_req_row.employee_id IS DISTINCT FROM v_swap.requester_employee_id
       OR v_req_row.date IS DISTINCT FROM v_swap.requester_date
       OR v_req_row.company_id IS DISTINCT FROM v_swap.company_id
       OR v_req_row.branch_id IS DISTINCT FROM v_swap.branch_id
       {"OR NOT v_req_row.published" if hardened else ""} THEN
      RAISE EXCEPTION 'shift_swap_roster_changed';
    END IF;

    IF EXISTS (
      SELECT 1 FROM public.roster_assignments
      WHERE employee_id = v_swap.target_employee_id
        AND date = v_swap.requester_date
        AND company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;
    UPDATE public.roster_assignments SET employee_id = v_swap.target_employee_id
    WHERE id = v_req_id;
  END IF;

  UPDATE public.shift_swap_requests
  SET status = 'approved',
      admin_approved_at = pg_catalog.now(),
      admin_approved_by_app_user_id = p_actor_app_user_id,
      rejection_reason = ''
  WHERE id = p_swap_id;
  RETURN true;
END;
$function$;
"""


def _replace_shift_swap_function(*, hardened: bool) -> None:
    signature = "public.admin_execute_shift_swap(uuid, uuid)"
    op.execute(_shift_swap_function_sql(hardened=hardened))
    op.execute(f"ALTER FUNCTION {signature} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO workloop_runtime")


def upgrade() -> None:
    _replace_shift_swap_function(hardened=True)
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    _create_policies()
    op.execute(
        "GRANT INSERT, UPDATE, DELETE ON TABLE public.roster_assignments TO workloop_runtime"
    )
    op.execute("GRANT INSERT, UPDATE ON TABLE public.shift_swap_requests TO workloop_runtime")
    op.execute("GRANT DELETE ON TABLE public.biometric_mappings TO workloop_runtime")


def downgrade() -> None:
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON TABLE public.roster_assignments FROM workloop_runtime"
    )
    op.execute("REVOKE INSERT, UPDATE ON TABLE public.shift_swap_requests FROM workloop_runtime")
    op.execute("REVOKE DELETE ON TABLE public.biometric_mappings FROM workloop_runtime")
    for table in reversed(RLS_TABLES):
        for command in ("delete", "update", "insert", "select"):
            op.execute(f"DROP POLICY IF EXISTS phase5f_{table}_{command}_runtime ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
    _replace_shift_swap_function(hardened=False)
