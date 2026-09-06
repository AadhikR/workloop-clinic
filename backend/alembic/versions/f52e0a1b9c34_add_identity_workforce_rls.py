"""Add identity, organization, and workforce row security.

Revision ID: f52e0a1b9c34
Revises: e418c0d7a6b3
Created: 2026-09-06 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f52e0a1b9c34"
down_revision: str | Sequence[str] | None = "e418c0d7a6b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RLS_TABLES: tuple[str, ...] = (
    "companies",
    "branches",
    "app_users",
    "user_profiles",
    "employees",
    "employee_job_history",
    "departments",
    "department_staffing_rules",
)

PRINCIPAL_FUNCTION = "public.resolve_workloop_principal()"
ACTIVE_ACCOUNT_FUNCTION = "public.is_scoped_active_app_user(uuid)"

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
    role: str,
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
        f"CREATE POLICY {name} ON public.{table} FOR {command} TO {role} " + " ".join(clauses)
    )


def _create_principal_function() -> None:
    op.execute(
        """
CREATE FUNCTION public.resolve_workloop_principal()
RETURNS TABLE (
  app_user_id uuid,
  account_status text,
  profile_app_user_id uuid,
  profile_company_id uuid,
  role text,
  profile_employee_id uuid,
  company_id uuid,
  employee_id uuid,
  employee_company_id uuid,
  employee_branch_id uuid,
  employee_active boolean,
  employment_status text,
  branch_id uuid,
  branch_company_id uuid
)
LANGUAGE sql
STABLE
SECURITY DEFINER
ROWS 1
SET search_path TO pg_catalog, public, pg_temp
AS $function$
  SELECT
    app_user.id,
    app_user.status::text,
    profile.app_user_id,
    profile.company_id,
    profile.role::text,
    profile.employee_id,
    company.id,
    employee.id,
    employee.company_id,
    employee.branch_id,
    employee.active,
    employee.employment_status,
    employee_branch.id,
    employee_branch.company_id
  FROM public.app_users AS app_user
  LEFT JOIN public.user_profiles AS profile
    ON profile.app_user_id = app_user.id
  LEFT JOIN public.companies AS company
    ON company.id = profile.company_id
  LEFT JOIN public.employees AS employee
    ON employee.id = profile.employee_id
   AND employee.company_id = profile.company_id
  LEFT JOIN public.branches AS employee_branch
    ON employee_branch.id = employee.branch_id
   AND employee_branch.company_id = employee.company_id
  WHERE session_user = 'workloop_runtime'
    AND public.workloop_identity_issuer() IS NOT NULL
    AND public.workloop_identity_subject() IS NOT NULL
    AND app_user.identity_issuer = public.workloop_identity_issuer()
    AND app_user.identity_subject = public.workloop_identity_subject()
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {PRINCIPAL_FUNCTION} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {PRINCIPAL_FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {PRINCIPAL_FUNCTION} TO workloop_runtime")


def _create_active_account_function() -> None:
    op.execute(
        """
CREATE FUNCTION public.is_scoped_active_app_user(p_app_user_id uuid)
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
    AND public.workloop_role() = 'admin'
    AND public.workloop_employee_id() IS NULL
    AND EXISTS (
      SELECT 1
      FROM public.resolve_workloop_principal() AS caller
      WHERE caller.app_user_id = public.workloop_app_user_id()
        AND caller.account_status = 'active'
        AND caller.profile_app_user_id = caller.app_user_id
        AND caller.role = 'admin'
        AND caller.profile_company_id = public.workloop_company_id()
        AND caller.company_id = caller.profile_company_id
        AND caller.profile_employee_id IS NULL
        AND caller.employee_id IS NULL
        AND caller.branch_id IS NULL
    )
    AND (
      public.workloop_branch_id() IS NULL
      OR EXISTS (
        SELECT 1
        FROM public.branches AS selected_branch
        WHERE selected_branch.id = public.workloop_branch_id()
          AND selected_branch.company_id = public.workloop_company_id()
      )
    )
    AND (
      SELECT count(*) = 1
      FROM public.app_users AS target_app_user
      JOIN public.user_profiles AS target_profile
        ON target_profile.app_user_id = target_app_user.id
      LEFT JOIN public.employees AS target_employee
        ON target_employee.id = target_profile.employee_id
       AND target_employee.company_id = target_profile.company_id
      LEFT JOIN public.branches AS target_branch
        ON target_branch.id = target_employee.branch_id
       AND target_branch.company_id = target_employee.company_id
      WHERE target_app_user.id = p_app_user_id
        AND target_app_user.status::text = 'active'
        AND target_profile.company_id = public.workloop_company_id()
        AND (
          (
            target_profile.role::text = 'admin'
            AND target_profile.employee_id IS NULL
          )
          OR
          (
            target_profile.role::text IN ('manager', 'employee')
            AND target_profile.employee_id IS NOT NULL
            AND target_employee.id = target_profile.employee_id
            AND target_employee.active
            AND target_employee.employment_status IN ('Active', 'Probation', 'On Leave')
            AND target_branch.id = target_employee.branch_id
          )
        )
    ),
    false
  )
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {ACTIVE_ACCOUNT_FUNCTION} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {ACTIVE_ACCOUNT_FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {ACTIVE_ACCOUNT_FUNCTION} TO workloop_runtime")


def _create_policies() -> None:
    company_human = f"""{HUMAN_CONTEXT}
AND id = public.workloop_company_id()"""
    company_update = f"""{company_human}
AND public.workloop_role() = 'admin'
AND public.workloop_branch_id() IS NULL"""
    company_job = f"""{JOB_CONTEXT}
AND id = public.workloop_company_id()
AND (
  public.workloop_branch_id() IS NULL
  OR EXISTS (
    SELECT 1 FROM public.branches AS job_branch
    WHERE job_branch.id = public.workloop_branch_id()
      AND job_branch.company_id = companies.id
  )
)"""
    _policy(
        "phase5e_companies_select_runtime",
        "companies",
        "SELECT",
        "workloop_runtime",
        using=company_human,
    )
    _policy(
        "phase5e_companies_update_runtime",
        "companies",
        "UPDATE",
        "workloop_runtime",
        using=company_update,
        check=company_update,
    )
    _policy(
        "phase5e_companies_select_expiry",
        "companies",
        "SELECT",
        "workloop_expiry_processing",
        using=company_job,
    )

    branch_select = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND (
  (
    public.workloop_role() = 'admin'
    AND (
      public.workloop_branch_id() IS NULL
      OR id = public.workloop_branch_id()
    )
  )
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND id = public.workloop_branch_id()
  )
)"""
    branch_create = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND public.workloop_branch_id() IS NULL
AND company_id = public.workloop_company_id()"""
    branch_mutate = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND company_id = public.workloop_company_id()
AND id = public.workloop_branch_id()"""
    branch_job = f"""{JOB_CONTEXT}
AND company_id = public.workloop_company_id()
AND id = public.workloop_branch_id()"""
    _policy(
        "phase5e_branches_select_runtime",
        "branches",
        "SELECT",
        "workloop_runtime",
        using=branch_select,
    )
    _policy(
        "phase5e_branches_insert_runtime",
        "branches",
        "INSERT",
        "workloop_runtime",
        check=branch_create,
    )
    _policy(
        "phase5e_branches_update_runtime",
        "branches",
        "UPDATE",
        "workloop_runtime",
        using=branch_mutate,
        check=branch_mutate,
    )
    _policy(
        "phase5e_branches_delete_runtime",
        "branches",
        "DELETE",
        "workloop_runtime",
        using=branch_mutate,
    )
    _policy(
        "phase5e_branches_select_expiry",
        "branches",
        "SELECT",
        "workloop_expiry_processing",
        using=branch_job,
    )

    app_user_bootstrap = """
current_user = 'workloop_runtime'
AND session_user = 'workloop_runtime'
AND public.workloop_identity_issuer() IS NOT NULL
AND public.workloop_identity_subject() IS NOT NULL
AND identity_issuer = public.workloop_identity_issuer()
AND identity_subject = public.workloop_identity_subject()
AND status::text = 'active'
""".strip()
    app_user_job = f"""{JOB_CONTEXT}
AND status::text = 'active'
AND EXISTS (
  SELECT 1
  FROM public.user_profiles AS recipient_profile
  WHERE recipient_profile.app_user_id = app_users.id
    AND recipient_profile.company_id = public.workloop_company_id()
    AND recipient_profile.role::text = 'admin'
)
AND (
  public.workloop_branch_id() IS NULL
  OR EXISTS (
    SELECT 1 FROM public.branches AS job_branch
    WHERE job_branch.id = public.workloop_branch_id()
      AND job_branch.company_id = public.workloop_company_id()
  )
)"""
    _policy(
        "phase5e_app_users_select_runtime",
        "app_users",
        "SELECT",
        "workloop_runtime",
        using=app_user_bootstrap,
    )
    _policy(
        "phase5e_app_users_select_expiry",
        "app_users",
        "SELECT",
        "workloop_expiry_processing",
        using=app_user_job,
    )

    profile_select = f"""{HUMAN_CONTEXT}
AND (
  app_user_id = public.workloop_app_user_id()
  OR (
    public.workloop_role() = 'admin'
    AND public.workloop_branch_id() IS NULL
    AND company_id = public.workloop_company_id()
  )
)"""
    profile_update = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND public.workloop_branch_id() IS NULL
AND company_id = public.workloop_company_id()
AND app_user_id <> public.workloop_app_user_id()"""
    profile_job = f"""{JOB_CONTEXT}
AND company_id = public.workloop_company_id()
AND role::text = 'admin'
AND (
  public.workloop_branch_id() IS NULL
  OR EXISTS (
    SELECT 1 FROM public.branches AS job_branch
    WHERE job_branch.id = public.workloop_branch_id()
      AND job_branch.company_id = user_profiles.company_id
  )
)"""
    _policy(
        "phase5e_user_profiles_select_runtime",
        "user_profiles",
        "SELECT",
        "workloop_runtime",
        using=profile_select,
    )
    _policy(
        "phase5e_user_profiles_update_runtime",
        "user_profiles",
        "UPDATE",
        "workloop_runtime",
        using=profile_update,
        check=profile_update,
    )
    _policy(
        "phase5e_user_profiles_select_expiry",
        "user_profiles",
        "SELECT",
        "workloop_expiry_processing",
        using=profile_job,
    )

    employee_select = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND (
  public.workloop_role() = 'admin'
  OR id = public.workloop_employee_id()
  OR (
    public.workloop_role() = 'manager'
    AND reporting_manager_id = public.workloop_employee_id()
  )
)"""
    employee_insert = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()"""
    employee_update = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND (
  public.workloop_role() = 'admin'
  OR id = public.workloop_employee_id()
)"""
    employee_job = f"""{JOB_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()"""
    _policy(
        "phase5e_employees_select_runtime",
        "employees",
        "SELECT",
        "workloop_runtime",
        using=employee_select,
    )
    _policy(
        "phase5e_employees_insert_runtime",
        "employees",
        "INSERT",
        "workloop_runtime",
        check=employee_insert,
    )
    _policy(
        "phase5e_employees_update_runtime",
        "employees",
        "UPDATE",
        "workloop_runtime",
        using=employee_update,
        check=employee_update,
    )
    _policy(
        "phase5e_employees_select_expiry",
        "employees",
        "SELECT",
        "workloop_expiry_processing",
        using=employee_job,
    )

    admin_branch = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()"""
    history_insert = f"""{admin_branch}
AND changed_by_app_user_id = public.workloop_app_user_id()"""
    _policy(
        "phase5e_employee_job_history_select_runtime",
        "employee_job_history",
        "SELECT",
        "workloop_runtime",
        using=admin_branch,
    )
    _policy(
        "phase5e_employee_job_history_insert_runtime",
        "employee_job_history",
        "INSERT",
        "workloop_runtime",
        check=history_insert,
    )

    for table in ("departments", "department_staffing_rules"):
        for command in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            suffix = command.lower()
            _policy(
                f"phase5e_{table}_{suffix}_runtime",
                table,
                command,
                "workloop_runtime",
                using=admin_branch if command != "INSERT" else None,
                check=admin_branch if command in {"INSERT", "UPDATE"} else None,
            )


def _grant_privileges() -> None:
    op.execute("GRANT UPDATE ON TABLE public.companies TO workloop_runtime")
    op.execute("GRANT DELETE ON TABLE public.branches TO workloop_runtime")
    op.execute("GRANT INSERT, UPDATE ON TABLE public.employees TO workloop_runtime")
    op.execute("GRANT UPDATE (role) ON TABLE public.user_profiles TO workloop_runtime")
    op.execute(
        "GRANT DELETE ON TABLE public.departments, public.department_staffing_rules "
        "TO workloop_runtime"
    )

    op.execute("GRANT USAGE ON SCHEMA public TO workloop_expiry_processing")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.workloop_company_id(), "
        "public.workloop_branch_id(), public.workloop_actor_kind(), "
        "public.workloop_actor_key(), public.workloop_business_date() "
        "TO workloop_expiry_processing"
    )
    op.execute("GRANT SELECT (id) ON TABLE public.companies TO workloop_expiry_processing")
    op.execute(
        "GRANT SELECT (id, company_id) ON TABLE public.branches TO workloop_expiry_processing"
    )
    op.execute("GRANT SELECT (id, status) ON TABLE public.app_users TO workloop_expiry_processing")
    op.execute(
        "GRANT SELECT (app_user_id, company_id, employee_id, role) "
        "ON TABLE public.user_profiles TO workloop_expiry_processing"
    )
    op.execute(
        "GRANT SELECT ("
        "id, company_id, branch_id, name, active, employment_status, "
        "probation_end_date, contract_type, contract_end_date, visa_expiry, "
        "passport_expiry, emirates_id_expiry, labour_card_expiry, "
        "licence_authority, licence_expiry"
        ") ON TABLE public.employees TO workloop_expiry_processing"
    )


def upgrade() -> None:
    _create_principal_function()
    _create_active_account_function()
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    _create_policies()
    _grant_privileges()


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT ON TABLE public.companies, public.branches, public.app_users, "
        "public.user_profiles, public.employees FROM workloop_expiry_processing"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.workloop_company_id(), "
        "public.workloop_branch_id(), public.workloop_actor_kind(), "
        "public.workloop_actor_key(), public.workloop_business_date() "
        "FROM workloop_expiry_processing"
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM workloop_expiry_processing")

    op.execute("REVOKE UPDATE ON TABLE public.companies FROM workloop_runtime")
    op.execute("REVOKE DELETE ON TABLE public.branches FROM workloop_runtime")
    op.execute("REVOKE INSERT, UPDATE ON TABLE public.employees FROM workloop_runtime")
    op.execute("REVOKE UPDATE (role) ON TABLE public.user_profiles FROM workloop_runtime")
    op.execute(
        "REVOKE DELETE ON TABLE public.departments, public.department_staffing_rules "
        "FROM workloop_runtime"
    )

    for table in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS phase5e_{table}_delete_runtime ON public.{table}")
        op.execute(f"DROP POLICY IF EXISTS phase5e_{table}_update_runtime ON public.{table}")
        op.execute(f"DROP POLICY IF EXISTS phase5e_{table}_insert_runtime ON public.{table}")
        op.execute(f"DROP POLICY IF EXISTS phase5e_{table}_select_expiry ON public.{table}")
        op.execute(f"DROP POLICY IF EXISTS phase5e_{table}_select_runtime ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")

    op.execute(f"DROP FUNCTION {ACTIVE_ACCOUNT_FUNCTION}")
    op.execute(f"DROP FUNCTION {PRINCIPAL_FUNCTION}")
