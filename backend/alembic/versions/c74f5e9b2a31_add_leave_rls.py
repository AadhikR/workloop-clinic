"""Add Phase 5F leave row security.

Revision ID: c74f5e9b2a31
Revises: b63e4d8a1f20
Created: 2026-09-06 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c74f5e9b2a31"
down_revision: str | Sequence[str] | None = "b63e4d8a1f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RLS_TABLES: tuple[str, ...] = (
    "leave_settings",
    "leave_types",
    "public_holidays",
    "leave_requests",
    "leave_audit_log",
    "leave_balances",
    "leave_approval_delegates",
)

DELEGATE_FUNCTION = "public.can_act_for_delegated_leave(uuid)"

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


def _staff_branch() -> str:
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()"""


def _employee_scope(table: str) -> str:
    return f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND (
  public.workloop_role() = 'admin'
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND employee_id = public.workloop_employee_id()
  )
  OR (
    public.workloop_role() = 'manager'
    AND EXISTS (
      SELECT 1 FROM public.employees AS target_employee
      WHERE target_employee.id = employee_id
        AND target_employee.company_id = {table}.company_id
        AND target_employee.branch_id = {table}.branch_id
        AND target_employee.reporting_manager_id = public.workloop_employee_id()
    )
  )
  OR public.can_act_for_delegated_leave(employee_id)
)"""


def _create_delegate_function() -> None:
    op.execute(
        """
CREATE FUNCTION public.can_act_for_delegated_leave(p_target_employee_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
  SELECT COALESCE(
    session_user = 'workloop_runtime'
    AND public.workloop_actor_kind() = 'human'
    AND public.workloop_actor_key() IS NULL
    AND public.workloop_business_date() IS NOT NULL
    AND public.workloop_app_user_id() IS NOT NULL
    AND public.workloop_role() IN ('manager', 'employee')
    AND public.workloop_company_id() IS NOT NULL
    AND public.workloop_branch_id() IS NOT NULL
    AND public.workloop_employee_id() IS NOT NULL
    AND p_target_employee_id IS NOT NULL
    AND p_target_employee_id <> public.workloop_employee_id()
    AND EXISTS (
      SELECT 1
      FROM public.resolve_workloop_principal() AS caller
      WHERE caller.app_user_id = public.workloop_app_user_id()
        AND caller.account_status = 'active'
        AND caller.profile_app_user_id = caller.app_user_id
        AND caller.role = public.workloop_role()
        AND caller.role IN ('manager', 'employee')
        AND caller.profile_company_id = public.workloop_company_id()
        AND caller.company_id = caller.profile_company_id
        AND caller.profile_employee_id = public.workloop_employee_id()
        AND caller.employee_id = caller.profile_employee_id
        AND caller.employee_company_id = caller.profile_company_id
        AND caller.employee_branch_id = public.workloop_branch_id()
        AND caller.employee_active
        AND caller.employment_status IN ('Active', 'Probation', 'On Leave')
        AND caller.branch_id = caller.employee_branch_id
        AND caller.branch_company_id = caller.profile_company_id
    )
    AND EXISTS (
      SELECT 1
      FROM public.leave_approval_delegates AS delegation
      JOIN public.employees AS approver
        ON approver.id = delegation.approver_employee_id
       AND approver.company_id = delegation.company_id
       AND approver.branch_id = delegation.branch_id
      JOIN public.user_profiles AS approver_profile
        ON approver_profile.employee_id = approver.id
       AND approver_profile.company_id = approver.company_id
       AND approver_profile.role = 'manager'
      JOIN public.app_users AS approver_account
        ON approver_account.id = approver_profile.app_user_id
       AND approver_account.status = 'active'
      JOIN public.employees AS target_employee
        ON target_employee.id = p_target_employee_id
       AND target_employee.company_id = delegation.company_id
       AND target_employee.branch_id = delegation.branch_id
       AND target_employee.reporting_manager_id = approver.id
      WHERE delegation.company_id = public.workloop_company_id()
        AND delegation.branch_id = public.workloop_branch_id()
        AND delegation.delegate_employee_id = public.workloop_employee_id()
        AND public.workloop_business_date()
            BETWEEN delegation.from_date AND delegation.to_date
        AND approver.active
        AND approver.employment_status IN ('Active', 'Probation', 'On Leave')
        AND target_employee.active
        AND target_employee.employment_status IN ('Active', 'Probation', 'On Leave')
    ),
    false
  )
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {DELEGATE_FUNCTION} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {DELEGATE_FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {DELEGATE_FUNCTION} TO workloop_runtime")


def _create_policies() -> None:
    admin = _admin_branch()
    staff = _staff_branch()

    settings_select = f"({admin}) OR ({staff})"
    _policy(
        "phase5f_leave_settings_select_runtime",
        "leave_settings",
        "SELECT",
        using=settings_select,
    )
    for command in ("INSERT", "UPDATE"):
        _policy(
            f"phase5f_leave_settings_{command.lower()}_runtime",
            "leave_settings",
            command,
            using=admin if command == "UPDATE" else None,
            check=admin,
        )

    leave_type_staff = f"""{staff}
AND is_active"""
    _policy(
        "phase5f_leave_types_select_runtime",
        "leave_types",
        "SELECT",
        using=f"({admin}) OR ({leave_type_staff})",
    )
    for command in ("INSERT", "UPDATE"):
        _policy(
            f"phase5f_leave_types_{command.lower()}_runtime",
            "leave_types",
            command,
            using=admin if command == "UPDATE" else None,
            check=admin,
        )

    holiday_select = f"({admin}) OR ({staff})"
    _policy(
        "phase5f_public_holidays_select_runtime",
        "public_holidays",
        "SELECT",
        using=holiday_select,
    )
    _policy(
        "phase5f_public_holidays_insert_runtime",
        "public_holidays",
        "INSERT",
        check=admin,
    )
    unused_future_holiday = f"""{admin}
AND date > public.workloop_business_date()
AND NOT EXISTS (
  SELECT 1 FROM public.leave_requests AS request
  WHERE request.company_id = public_holidays.company_id
    AND request.branch_id = public_holidays.branch_id
    AND public_holidays.date BETWEEN request.start_date AND request.end_date
)
AND NOT EXISTS (
  SELECT 1 FROM public.attendance_records AS attendance
  WHERE attendance.company_id = public_holidays.company_id
    AND attendance.branch_id = public_holidays.branch_id
    AND attendance.date = public_holidays.date
)"""
    _policy(
        "phase5f_public_holidays_update_runtime",
        "public_holidays",
        "UPDATE",
        using=unused_future_holiday,
        check=f"{admin}\nAND date > public.workloop_business_date()",
    )
    _policy(
        "phase5f_public_holidays_delete_runtime",
        "public_holidays",
        "DELETE",
        using=unused_future_holiday,
    )

    request_scope = _employee_scope("leave_requests")
    _policy(
        "phase5f_leave_requests_select_runtime",
        "leave_requests",
        "SELECT",
        using=request_scope,
    )
    request_insert = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND (
  public.workloop_role() = 'admin'
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND employee_id = public.workloop_employee_id()
  )
)"""
    _policy(
        "phase5f_leave_requests_insert_runtime",
        "leave_requests",
        "INSERT",
        check=request_insert,
    )
    request_self = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND employee_id = public.workloop_employee_id()"""
    request_team = f"""{request_scope}
AND public.workloop_role() IN ('manager', 'employee')
AND employee_id <> public.workloop_employee_id()"""
    request_update = f"""({admin}) OR (
  {request_self}
  AND status = 'Pending'
) OR ({request_team})"""
    request_update_check = f"""({admin}) OR (
  {request_self}
  AND status = 'Cancelled'
) OR (
  {request_team}
  AND status IN ('Approved', 'ManagerApproved', 'ManagerRejected')
)"""
    _policy(
        "phase5f_leave_requests_update_runtime",
        "leave_requests",
        "UPDATE",
        using=request_update,
        check=request_update_check,
    )

    audit_insert = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND actor_app_user_id = public.workloop_app_user_id()
AND EXISTS (
  SELECT 1 FROM public.leave_requests AS visible_request
  WHERE visible_request.id = leave_request_id
    AND visible_request.company_id = leave_audit_log.company_id
    AND visible_request.branch_id = leave_audit_log.branch_id
)"""
    _policy(
        "phase5f_leave_audit_log_select_runtime",
        "leave_audit_log",
        "SELECT",
        using=admin,
    )
    _policy(
        "phase5f_leave_audit_log_insert_runtime",
        "leave_audit_log",
        "INSERT",
        check=audit_insert,
    )

    balance_scope = _employee_scope("leave_balances")
    _policy(
        "phase5f_leave_balances_select_runtime",
        "leave_balances",
        "SELECT",
        using=balance_scope,
    )
    _policy(
        "phase5f_leave_balances_insert_runtime",
        "leave_balances",
        "INSERT",
        check=balance_scope,
    )
    _policy(
        "phase5f_leave_balances_update_runtime",
        "leave_balances",
        "UPDATE",
        using=balance_scope,
        check=balance_scope,
    )

    delegation_participant = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND public.workloop_employee_id() IN (approver_employee_id, delegate_employee_id)"""
    _policy(
        "phase5f_leave_approval_delegates_select_runtime",
        "leave_approval_delegates",
        "SELECT",
        using=f"({admin}) OR ({delegation_participant})",
    )
    _policy(
        "phase5f_leave_approval_delegates_insert_runtime",
        "leave_approval_delegates",
        "INSERT",
        check=admin,
    )
    future_delegation = f"""{admin}
AND from_date > public.workloop_business_date()"""
    _policy(
        "phase5f_leave_approval_delegates_update_runtime",
        "leave_approval_delegates",
        "UPDATE",
        using=future_delegation,
        check=future_delegation,
    )
    _policy(
        "phase5f_leave_approval_delegates_delete_runtime",
        "leave_approval_delegates",
        "DELETE",
        using=future_delegation,
    )


def upgrade() -> None:
    _create_delegate_function()
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    _create_policies()
    op.execute(
        "GRANT DELETE ON TABLE public.public_holidays, "
        "public.leave_approval_delegates TO workloop_runtime"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE DELETE ON TABLE public.public_holidays, "
        "public.leave_approval_delegates FROM workloop_runtime"
    )
    for table in reversed(RLS_TABLES):
        for command in ("delete", "update", "insert", "select"):
            op.execute(f"DROP POLICY IF EXISTS phase5f_{table}_{command}_runtime ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
    op.execute(f"DROP FUNCTION {DELEGATE_FUNCTION}")
