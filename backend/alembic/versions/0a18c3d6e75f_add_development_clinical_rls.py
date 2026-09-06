"""Add Phase 5G development and clinical row security.

Revision ID: 0a18c3d6e75f
Revises: f07a8b2c5d64
Created: 2026-09-06 00:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

from alembic import op

revision: str = "0a18c3d6e75f"
down_revision: str | Sequence[str] | None = "f07a8b2c5d64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RLS_TABLES = (
    "training_records",
    "certifications",
    "appraisal_cycles",
    "appraisals",
    "appraisal_sections",
    "cme_requirements",
    "incident_reports",
    "letter_requests",
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

JOB_CONTEXT = """current_user = 'workloop_expiry_processing'
AND session_user = 'workloop_expiry_processing'
AND public.workloop_actor_kind() = 'scheduled_job'
AND public.workloop_actor_key() = 'expiry_processing'
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_business_date() IS NOT NULL"""


def _policy(
    name: str,
    table: str,
    command: str,
    role: str = "workloop_runtime",
    *,
    using: str | None = None,
    check: str | None = None,
) -> None:
    clauses = []
    if using is not None:
        clauses.append(f"USING ({using})")
    if check is not None:
        clauses.append(f"WITH CHECK ({check})")
    op.execute(
        f"CREATE POLICY {name} ON public.{table} FOR {command} TO {role} " + " ".join(clauses)
    )


def _admin(table: str = "") -> str:
    prefix = f"{table}." if table else ""
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND {prefix}company_id = public.workloop_company_id()
AND {prefix}branch_id = public.workloop_branch_id()"""


def _create_policies() -> None:
    admin = _admin()
    self_scope = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager','employee')
AND company_id = public.workloop_company_id() AND branch_id = public.workloop_branch_id()
AND employee_id = public.workloop_employee_id()"""
    report_scope = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'manager'
AND company_id = public.workloop_company_id() AND branch_id = public.workloop_branch_id()
AND EXISTS (SELECT 1 FROM public.employees AS target
  WHERE target.id = employee_id AND target.company_id = public.workloop_company_id()
    AND target.branch_id = public.workloop_branch_id()
    AND target.reporting_manager_id = public.workloop_employee_id())"""

    for table in ("training_records", "certifications"):
        visible = f"({admin}) OR ({self_scope}) OR ({report_scope})"
        _policy(f"phase5g_{table}_select_runtime", table, "SELECT", using=visible)
        if table == "training_records":
            insert_check = f"""({admin}) OR (({self_scope}) AND status = 'planned' AND cost = 0
AND score IS NULL AND passed IS NULL AND NOT is_cme)
OR (({report_scope}) AND employee_id <> public.workloop_employee_id() AND status = 'planned')"""
            update_scope = visible
            delete_scope = f"(({admin}) OR (({report_scope}) AND employee_id <> public.workloop_employee_id())) AND status = 'planned'"
        else:
            insert_check = f"""(({admin}) AND status = 'verified' AND reviewed_by_app_user_id = public.workloop_app_user_id() AND reviewed_at IS NOT NULL)
OR ((({self_scope}) OR (({report_scope}) AND employee_id <> public.workloop_employee_id()))
AND status = 'pending_review' AND reviewed_by_app_user_id IS NULL AND reviewed_at IS NULL)"""
            update_scope = visible
            delete_scope = f"(({admin}) OR (({report_scope}) AND employee_id <> public.workloop_employee_id())) AND status IN ('pending_review','rejected')"
        _policy(f"phase5g_{table}_insert_runtime", table, "INSERT", check=insert_check)
        _policy(
            f"phase5g_{table}_update_runtime",
            table,
            "UPDATE",
            using=update_scope,
            check=update_scope,
        )
        _policy(f"phase5g_{table}_delete_runtime", table, "DELETE", using=delete_scope)

    _policy(
        "phase5g_certifications_select_expiry",
        "certifications",
        "SELECT",
        "workloop_expiry_processing",
        using=f"{JOB_CONTEXT} AND company_id = public.workloop_company_id() AND branch_id = public.workloop_branch_id() AND status = 'verified'",
    )

    cycle_admin = _admin("appraisal_cycles")
    cycle_link = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager','employee')
AND appraisal_cycles.company_id = public.workloop_company_id()
AND appraisal_cycles.branch_id = public.workloop_branch_id()
AND EXISTS (SELECT 1 FROM public.appraisals AS appraisal
 JOIN public.employees AS target ON target.id = appraisal.employee_id
   AND target.company_id = appraisal.company_id AND target.branch_id = appraisal.branch_id
 WHERE appraisal.cycle_id = appraisal_cycles.id
   AND (appraisal.employee_id = public.workloop_employee_id()
     OR (public.workloop_role() = 'manager' AND target.reporting_manager_id = public.workloop_employee_id())))"""
    _policy(
        "phase5g_appraisal_cycles_select_runtime",
        "appraisal_cycles",
        "SELECT",
        using=f"({cycle_admin}) OR ({cycle_link})",
    )
    for command in ("INSERT", "UPDATE"):
        _policy(
            f"phase5g_appraisal_cycles_{command.lower()}_runtime",
            "appraisal_cycles",
            command,
            using=admin if command == "UPDATE" else None,
            check=admin,
        )
    _policy(
        "phase5g_appraisal_cycles_delete_runtime",
        "appraisal_cycles",
        "DELETE",
        using=f"""{admin} AND status = 'draft'
AND NOT EXISTS (SELECT 1 FROM public.appraisals AS appraisal WHERE appraisal.cycle_id = appraisal_cycles.id)""",
    )

    appraisal_visible = f"({admin}) OR ({self_scope}) OR ({report_scope})"
    _policy("phase5g_appraisals_select_runtime", "appraisals", "SELECT", using=appraisal_visible)
    _policy("phase5g_appraisals_insert_runtime", "appraisals", "INSERT", check=admin)
    _policy(
        "phase5g_appraisals_update_runtime",
        "appraisals",
        "UPDATE",
        using=f"({admin}) OR (({report_scope}) AND employee_id <> public.workloop_employee_id())",
        check=f"({admin}) OR (({report_scope}) AND employee_id <> public.workloop_employee_id())",
    )

    section_admin = _admin("appraisal_sections")
    section_staff = f"""{HUMAN_CONTEXT}
AND appraisal_sections.company_id = public.workloop_company_id()
AND appraisal_sections.branch_id = public.workloop_branch_id()
AND EXISTS (SELECT 1 FROM public.appraisals AS appraisal
 JOIN public.employees AS target ON target.id = appraisal.employee_id
   AND target.company_id = appraisal.company_id AND target.branch_id = appraisal.branch_id
 WHERE appraisal.id = appraisal_sections.appraisal_id
   AND (appraisal.employee_id = public.workloop_employee_id()
    OR (public.workloop_role() = 'manager' AND target.reporting_manager_id = public.workloop_employee_id())))"""
    _policy(
        "phase5g_appraisal_sections_select_runtime",
        "appraisal_sections",
        "SELECT",
        using=f"({section_admin}) OR ({section_staff})",
    )
    _policy(
        "phase5g_appraisal_sections_insert_runtime", "appraisal_sections", "INSERT", check=admin
    )
    _policy(
        "phase5g_appraisal_sections_update_runtime",
        "appraisal_sections",
        "UPDATE",
        using=f"({section_admin}) OR ({section_staff})",
        check=f"({section_admin}) OR ({section_staff})",
    )

    for command in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        _policy(
            f"phase5g_cme_requirements_{command.lower()}_runtime",
            "cme_requirements",
            command,
            using=admin if command != "INSERT" else None,
            check=admin if command in {"INSERT", "UPDATE"} else None,
        )
    for table in ("incident_reports",):
        for command in ("SELECT", "INSERT", "UPDATE"):
            _policy(
                f"phase5g_{table}_{command.lower()}_runtime",
                table,
                command,
                using=admin if command != "INSERT" else None,
                check=admin if command in {"INSERT", "UPDATE"} else None,
            )
    _policy(
        "phase5g_letter_requests_select_runtime",
        "letter_requests",
        "SELECT",
        using=f"({admin}) OR ({self_scope})",
    )
    _policy("phase5g_letter_requests_insert_runtime", "letter_requests", "INSERT", check=self_scope)
    _policy(
        "phase5g_letter_requests_update_runtime",
        "letter_requests",
        "UPDATE",
        using=admin,
        check=admin,
    )


def upgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    _create_policies()
    op.execute(
        "GRANT DELETE ON TABLE public.training_records, public.certifications, public.appraisal_cycles, public.cme_requirements TO workloop_runtime"
    )
    op.execute(
        "GRANT SELECT (id,company_id,branch_id,employee_id,certification_name,issuing_body,expiry_date,status) ON TABLE public.certifications TO workloop_expiry_processing"
    )


def downgrade() -> None:
    op.execute("REVOKE SELECT ON TABLE public.certifications FROM workloop_expiry_processing")
    op.execute(
        "REVOKE DELETE ON TABLE public.training_records, public.certifications, public.appraisal_cycles, public.cme_requirements FROM workloop_runtime"
    )
    for table in reversed(RLS_TABLES):
        for suffix in (
            "select_expiry",
            "delete_runtime",
            "update_runtime",
            "insert_runtime",
            "select_runtime",
        ):
            op.execute(f"DROP POLICY IF EXISTS phase5g_{table}_{suffix} ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
