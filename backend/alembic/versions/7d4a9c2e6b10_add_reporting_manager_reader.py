"""Add the current employee reporting-manager reader.

Revision ID: 7d4a9c2e6b10
Revises: 31d7b4c8e2f0
Create Date: 2026-09-10 19:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "7d4a9c2e6b10"
down_revision: str | Sequence[str] | None = "31d7b4c8e2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = "public.current_employee_reporting_manager()"


def upgrade() -> None:
    op.execute(
        """
CREATE FUNCTION public.current_employee_reporting_manager()
RETURNS TABLE (
  id uuid,
  name text,
  job_title text
)
LANGUAGE sql
STABLE
SECURITY DEFINER
ROWS 1
SET search_path TO pg_catalog, public, pg_temp
AS $function$
  SELECT
    manager.id,
    manager.name,
    manager.job_title
  FROM public.resolve_workloop_principal() AS principal
  JOIN public.employees AS employee
    ON employee.id = principal.employee_id
   AND employee.company_id = principal.employee_company_id
   AND employee.branch_id = principal.employee_branch_id
  JOIN public.employees AS manager
    ON manager.id = employee.reporting_manager_id
   AND manager.company_id = employee.company_id
   AND manager.branch_id = employee.branch_id
  WHERE session_user = 'workloop_runtime'
    AND public.workloop_actor_kind() = 'human'
    AND public.workloop_actor_key() IS NULL
    AND public.workloop_business_date() IS NOT NULL
    AND principal.app_user_id = public.workloop_app_user_id()
    AND principal.account_status = 'active'
    AND principal.profile_app_user_id = principal.app_user_id
    AND principal.profile_company_id = public.workloop_company_id()
    AND principal.company_id = principal.profile_company_id
    AND principal.role = public.workloop_role()
    AND principal.role IN ('manager', 'employee')
    AND principal.profile_employee_id = public.workloop_employee_id()
    AND principal.employee_id = principal.profile_employee_id
    AND principal.employee_company_id = principal.profile_company_id
    AND principal.employee_branch_id = public.workloop_branch_id()
    AND principal.employee_active
    AND principal.employment_status IN ('Active', 'Probation', 'On Leave')
    AND principal.branch_id = principal.employee_branch_id
    AND principal.branch_company_id = principal.profile_company_id
    AND employee.active
    AND employee.employment_status IN ('Active', 'Probation', 'On Leave')
    AND manager.active
    AND manager.employment_status IN ('Active', 'Probation', 'On Leave')
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {FUNCTION} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {FUNCTION} TO workloop_runtime")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {FUNCTION}")
