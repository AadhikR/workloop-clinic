"""Add Phase 5G lifecycle and asset row security.

Revision ID: f07a8b2c5d64
Revises: e96f7a1b4c53
Created: 2026-09-06 00:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

revision: str = "f07a8b2c5d64"
down_revision: str | Sequence[str] | None = "e96f7a1b4c53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = (
    "employee_contracts",
    "offboarding_checklists",
    "offboarding_tasks",
    "offboarding_task_templates",
    "assets",
    "asset_assignments",
)

HUMAN_CONTEXT = """
current_user = 'workloop_runtime' AND session_user = 'workloop_runtime'
AND public.workloop_actor_kind() = 'human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() AS principal
  WHERE principal.app_user_id = public.workloop_app_user_id()
    AND principal.account_status = 'active'
    AND principal.profile_app_user_id = principal.app_user_id
    AND principal.role = public.workloop_role()
    AND principal.profile_company_id = public.workloop_company_id()
    AND principal.company_id = principal.profile_company_id
    AND ((principal.role = 'admin' AND principal.profile_employee_id IS NULL
      AND principal.employee_id IS NULL AND principal.branch_id IS NULL
      AND public.workloop_employee_id() IS NULL)
    OR (principal.role IN ('manager','employee')
      AND principal.profile_employee_id = public.workloop_employee_id()
      AND principal.employee_id = principal.profile_employee_id
      AND principal.employee_company_id = principal.profile_company_id
      AND principal.employee_branch_id = public.workloop_branch_id()
      AND principal.employee_active
      AND principal.employment_status IN ('Active','Probation','On Leave')
      AND principal.branch_id = principal.employee_branch_id
      AND principal.branch_company_id = principal.profile_company_id))
)
""".strip()


def _policy(
    name: str, table: str, command: str, *, using: str | None = None, check: str | None = None
) -> None:
    clauses = []
    if using is not None:
        clauses.append(f"USING ({using})")
    if check is not None:
        clauses.append(f"WITH CHECK ({check})")
    op.execute(
        f"CREATE POLICY {name} ON public.{table} FOR {command} TO workloop_runtime "
        + " ".join(clauses)
    )


def _admin(table: str = "") -> str:
    prefix = f"{table}." if table else ""
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND {prefix}company_id = public.workloop_company_id()
AND {prefix}branch_id = public.workloop_branch_id()"""


def _create_policies() -> None:
    admin = _admin()
    self_assignment = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager','employee')
AND company_id = public.workloop_company_id() AND branch_id = public.workloop_branch_id()
AND employee_id = public.workloop_employee_id()"""

    _policy(
        "phase5g_employee_contracts_select_runtime", "employee_contracts", "SELECT", using=admin
    )
    _policy(
        "phase5g_employee_contracts_insert_runtime",
        "employee_contracts",
        "INSERT",
        check=f"{admin} AND renewed_by_app_user_id = public.workloop_app_user_id()",
    )

    for table in ("offboarding_checklists",):
        for command in ("SELECT", "INSERT", "UPDATE"):
            _policy(
                f"phase5g_{table}_{command.lower()}_runtime",
                table,
                command,
                using=admin if command != "INSERT" else None,
                check=admin if command in {"INSERT", "UPDATE"} else None,
            )
    for command in ("SELECT", "INSERT", "UPDATE"):
        _policy(
            f"phase5g_offboarding_tasks_{command.lower()}_runtime",
            "offboarding_tasks",
            command,
            using=admin if command != "INSERT" else None,
            check=admin if command in {"INSERT", "UPDATE"} else None,
        )
    _policy(
        "phase5g_offboarding_tasks_delete_runtime",
        "offboarding_tasks",
        "DELETE",
        using=f"{admin} AND NOT completed",
    )
    _policy(
        "phase5g_offboarding_task_templates_select_runtime",
        "offboarding_task_templates",
        "SELECT",
        using=admin,
    )

    assigned_asset = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager','employee')
AND assets.company_id = public.workloop_company_id()
AND assets.branch_id = public.workloop_branch_id()
AND EXISTS (SELECT 1 FROM public.asset_assignments AS assignment
  WHERE assignment.asset_id = assets.id
    AND assignment.company_id = assets.company_id
    AND assignment.branch_id = assets.branch_id
    AND assignment.employee_id = public.workloop_employee_id()
    AND assignment.return_date IS NULL)"""
    asset_admin = _admin("assets")
    _policy(
        "phase5g_assets_select_runtime",
        "assets",
        "SELECT",
        using=f"({asset_admin}) OR ({assigned_asset})",
    )
    for command in ("INSERT", "UPDATE"):
        _policy(
            f"phase5g_assets_{command.lower()}_runtime",
            "assets",
            command,
            using=admin if command == "UPDATE" else None,
            check=admin,
        )
    _policy(
        "phase5g_assets_delete_runtime",
        "assets",
        "DELETE",
        using=f"""{admin}
AND NOT EXISTS (SELECT 1 FROM public.asset_assignments AS assignment WHERE assignment.asset_id = assets.id)""",
    )

    _policy(
        "phase5g_asset_assignments_select_runtime",
        "asset_assignments",
        "SELECT",
        using=f"({admin}) OR ({self_assignment})",
    )
    _policy("phase5g_asset_assignments_insert_runtime", "asset_assignments", "INSERT", check=admin)
    _policy(
        "phase5g_asset_assignments_update_runtime",
        "asset_assignments",
        "UPDATE",
        using=admin,
        check=admin,
    )


def upgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    _create_policies()
    op.execute("GRANT DELETE ON TABLE public.offboarding_tasks, public.assets TO workloop_runtime")
    op.execute(
        "REVOKE INSERT, UPDATE ON TABLE public.offboarding_task_templates FROM workloop_runtime"
    )


def downgrade() -> None:
    op.execute(
        "GRANT INSERT, UPDATE ON TABLE public.offboarding_task_templates TO workloop_runtime"
    )
    op.execute(
        "REVOKE DELETE ON TABLE public.offboarding_tasks, public.assets FROM workloop_runtime"
    )
    for table in reversed(RLS_TABLES):
        for suffix in ("delete_runtime", "update_runtime", "insert_runtime", "select_runtime"):
            op.execute(f"DROP POLICY IF EXISTS phase5g_{table}_{suffix} ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
