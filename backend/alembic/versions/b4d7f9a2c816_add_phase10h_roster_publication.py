"""Add Phase 10H roster publication and payroll authority.

Revision ID: b4d7f9a2c816
Revises: a1c3e5f7b902
Created: 2026-09-22 05:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from alembic import op

revision: str = "b4d7f9a2c816"
down_revision: str | Sequence[str] | None = "a1c3e5f7b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10H_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request','attendance_period','roster_assignment','roster_publication_version') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
PHASE10G_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request','attendance_period','roster_assignment') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""

ADMIN_SCOPE = """
current_user='workloop_runtime'
AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_role()='admin'
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_employee_id() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() principal
  WHERE principal.app_user_id=public.workloop_app_user_id()
    AND principal.account_status='active' AND principal.role='admin'
    AND principal.profile_company_id=public.workloop_company_id()
    AND principal.company_id=principal.profile_company_id
    AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL
    AND principal.branch_id IS NULL
)
""".strip()

STAFF_SCOPE = """
current_user='workloop_runtime'
AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_role() IN ('manager','employee')
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_employee_id() IS NOT NULL
AND public.workloop_business_date() IS NOT NULL
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() principal
  WHERE principal.app_user_id=public.workloop_app_user_id()
    AND principal.account_status='active' AND principal.role=public.workloop_role()
    AND principal.profile_company_id=public.workloop_company_id()
    AND principal.company_id=principal.profile_company_id
    AND principal.employee_id=public.workloop_employee_id()
    AND principal.branch_id=public.workloop_branch_id()
)
""".strip()

DEFINER_ADMIN_CONTEXT = """
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
""".strip()

DEFINER_STAFF_CONTEXT = """
current_user='workloop_migration'
AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_role() IN ('manager','employee')
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_employee_id() IS NOT NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() principal
  WHERE principal.app_user_id=public.workloop_app_user_id()
    AND principal.account_status='active' AND principal.role=public.workloop_role()
    AND principal.profile_company_id=public.workloop_company_id()
    AND principal.company_id=principal.profile_company_id
    AND principal.employee_id=public.workloop_employee_id()
    AND principal.branch_id=public.workloop_branch_id()
)
""".strip()


def _scope_foreign_keys() -> tuple[sa.ForeignKeyConstraint, sa.ForeignKeyConstraint]:
    return (
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
    )


def _append_only(table: str) -> None:
    op.execute(f"""
CREATE FUNCTION public.phase10h_{table}_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF current_user='workloop_migration' THEN
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION '{table} is append only' USING ERRCODE='42501';
END $$;
CREATE TRIGGER trg_phase10h_{table}_append_only
BEFORE UPDATE OR DELETE ON public.{table}
FOR EACH ROW EXECUTE FUNCTION public.phase10h_{table}_append_only();
ALTER FUNCTION public.phase10h_{table}_append_only() OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.phase10h_{table}_append_only() FROM PUBLIC, workloop_runtime;
""")


def _rls(table: str, *, staff_select: str | None = None) -> None:
    op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY phase10h_{table}_admin_runtime ON public.{table} "
        f"FOR ALL TO workloop_runtime USING ({ADMIN_SCOPE}) WITH CHECK ({ADMIN_SCOPE})"
    )
    if staff_select is not None:
        op.execute(
            f"CREATE POLICY phase10h_{table}_staff_select_runtime ON public.{table} "
            f"FOR SELECT TO workloop_runtime USING ({STAFF_SCOPE} AND ({staff_select}))"
        )
    op.execute(
        f"CREATE POLICY phase10h_{table}_migration ON public.{table} "
        "FOR ALL TO workloop_migration USING (true) WITH CHECK (true)"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{table} TO workloop_runtime")


def upgrade() -> None:
    op.create_table(
        "roster_months",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_version_id", sa.UUID(), nullable=True),
        sa.Column("source_version", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_app_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("status IN ('draft','published')", name=op.f("ck_roster_months_status")),
        sa.CheckConstraint(
            "period ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$'", name=op.f("ck_roster_months_period")
        ),
        sa.CheckConstraint(
            "(status='draft' AND version=0 AND current_version_id IS NULL AND source_version IS NULL AND published_at IS NULL AND published_by_app_user_id IS NULL) OR (status='published' AND version>=1 AND current_version_id IS NOT NULL AND source_version ~ '^sha256:[0-9a-f]{64}$' AND published_at IS NOT NULL AND published_by_app_user_id IS NOT NULL)",
            name=op.f("ck_roster_months_state"),
        ),
        *_scope_foreign_keys(),
        sa.ForeignKeyConstraint(
            ["published_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_months")),
        sa.UniqueConstraint("branch_id", "period", name="uq_roster_months_branch_id_period"),
    )
    op.create_index(
        "ix_roster_months_scope_period", "roster_months", ["company_id", "branch_id", "period"]
    )

    op.create_table(
        "roster_publication_versions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("roster_month_id", sa.UUID(), nullable=False),
        sa.Column("prior_version_id", sa.UUID(), nullable=True),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("source_canonical", sa.Text(), nullable=False),
        sa.Column("source_payload", JSONB(), nullable=False),
        sa.Column("affected_row_digest", sa.Text(), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("actor_app_user_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "period ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$'",
            name=op.f("ck_roster_publication_versions_period"),
        ),
        sa.CheckConstraint(
            "version>=1 AND record_count>=1", name=op.f("ck_roster_publication_versions_counts")
        ),
        sa.CheckConstraint(
            "kind IN ('publication','actual_hours','overtime_approval','swap')",
            name=op.f("ck_roster_publication_versions_kind"),
        ),
        sa.CheckConstraint(
            "source_version ~ '^sha256:[0-9a-f]{64}$' AND affected_row_digest ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_roster_publication_versions_digests"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_payload)='object' AND source_canonical::jsonb=source_payload",
            name=op.f("ck_roster_publication_versions_payload"),
        ),
        sa.CheckConstraint(
            "(version=1 AND prior_version_id IS NULL AND kind='publication') OR (version>1 AND prior_version_id IS NOT NULL AND kind<>'publication' AND octet_length(btrim(reason)) BETWEEN 3 AND 500)",
            name=op.f("ck_roster_publication_versions_transition"),
        ),
        *_scope_foreign_keys(),
        sa.ForeignKeyConstraint(["roster_month_id"], ["roster_months.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["prior_version_id"], ["roster_publication_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_publication_versions")),
        sa.UniqueConstraint(
            "roster_month_id", "version", name="uq_roster_publication_versions_month_version"
        ),
        sa.UniqueConstraint("source_version", name="uq_roster_publication_versions_source_version"),
    )
    op.create_index(
        "ix_roster_publication_versions_scope_period_version",
        "roster_publication_versions",
        ["company_id", "branch_id", "period", "version"],
    )
    op.create_foreign_key(
        "fk_roster_months_current_version_id_roster_publication_versions",
        "roster_months",
        "roster_publication_versions",
        ["current_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "roster_actual_hours_evidence",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("roster_month_id", sa.UUID(), nullable=False),
        sa.Column("source_assignment_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("prior_evidence_id", sa.UUID(), nullable=True),
        sa.Column("actual_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("evidence_source", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_app_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "actual_hours BETWEEN 0 AND 24", name=op.f("ck_roster_actual_hours_evidence_hours")
        ),
        sa.CheckConstraint(
            "octet_length(btrim(reason)) BETWEEN 3 AND 500",
            name=op.f("ck_roster_actual_hours_evidence_reason"),
        ),
        *_scope_foreign_keys(),
        sa.ForeignKeyConstraint(["roster_month_id"], ["roster_months.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_assignment_id"], ["roster_assignments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prior_evidence_id"], ["roster_actual_hours_evidence.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_actual_hours_evidence")),
    )
    op.create_index(
        "ix_roster_actual_hours_scope_assignment",
        "roster_actual_hours_evidence",
        ["company_id", "branch_id", "roster_month_id", "source_assignment_id", "created_at"],
    )

    op.create_table(
        "roster_overtime_approvals",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("roster_month_id", sa.UUID(), nullable=False),
        sa.Column("source_assignment_id", sa.UUID(), nullable=False),
        sa.Column("actual_evidence_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("overtime_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("overtime_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("attendance_overlap_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "attendance_source_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.Column("salary_source_version", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_app_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "overtime_hours>0 AND overtime_amount>=0 AND attendance_overlap_hours=0",
            name=op.f("ck_roster_overtime_approvals_amounts"),
        ),
        sa.CheckConstraint(
            "salary_source_version<>''", name=op.f("ck_roster_overtime_approvals_salary_source")
        ),
        sa.CheckConstraint(
            "octet_length(btrim(reason)) BETWEEN 3 AND 500",
            name=op.f("ck_roster_overtime_approvals_reason"),
        ),
        *_scope_foreign_keys(),
        sa.ForeignKeyConstraint(["roster_month_id"], ["roster_months.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_assignment_id"], ["roster_assignments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["actual_evidence_id"], ["roster_actual_hours_evidence.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_overtime_approvals")),
    )
    op.create_index(
        "ix_roster_overtime_scope_assignment",
        "roster_overtime_approvals",
        ["company_id", "branch_id", "roster_month_id", "source_assignment_id", "created_at"],
    )

    op.create_table(
        "roster_publication_memberships",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("publication_version_id", sa.UUID(), nullable=False),
        sa.Column("source_assignment_id", sa.UUID(), nullable=False),
        sa.Column("source_assignment_version", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("employee_name", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=False),
        sa.Column("shift_id", sa.UUID(), nullable=False),
        sa.Column("shift_name", sa.Text(), nullable=False),
        sa.Column("shift_code", sa.Text(), nullable=True),
        sa.Column("shift_category", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("planned_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("actual_evidence_id", sa.UUID(), nullable=True),
        sa.Column("actual_hours", sa.Numeric(5, 2), nullable=True),
        sa.Column("overtime_approval_id", sa.UUID(), nullable=True),
        sa.Column("overtime_hours", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "overtime_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "attendance_overlap_hours",
            sa.Numeric(5, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "attendance_source_ids",
            ARRAY(UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.Column("salary_source_version", sa.Text(), nullable=True),
        sa.Column("source_payload", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "source_assignment_version>=1 AND planned_hours BETWEEN 0.25 AND 24 AND (actual_hours IS NULL OR actual_hours BETWEEN 0 AND 24) AND overtime_hours>=0 AND overtime_amount>=0 AND attendance_overlap_hours>=0",
            name=op.f("ck_roster_publication_memberships_hours"),
        ),
        sa.CheckConstraint(
            "(actual_evidence_id IS NULL AND actual_hours IS NULL AND overtime_approval_id IS NULL AND overtime_hours=0 AND overtime_amount=0) OR (actual_evidence_id IS NOT NULL AND actual_hours IS NOT NULL AND ((overtime_approval_id IS NULL AND overtime_hours=0 AND overtime_amount=0) OR (actual_hours>planned_hours AND overtime_approval_id IS NOT NULL AND overtime_hours=actual_hours-planned_hours AND attendance_overlap_hours=0)))",
            name=op.f("ck_roster_publication_memberships_evidence"),
        ),
        *_scope_foreign_keys(),
        sa.ForeignKeyConstraint(
            ["publication_version_id"], ["roster_publication_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_assignment_id"], ["roster_assignments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shift_id", "company_id", "branch_id"],
            ["shifts.id", "shifts.company_id", "shifts.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actual_evidence_id"], ["roster_actual_hours_evidence.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["overtime_approval_id"], ["roster_overtime_approvals.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roster_publication_memberships")),
        sa.UniqueConstraint(
            "publication_version_id",
            "source_assignment_id",
            name="uq_roster_publication_memberships_version_assignment",
        ),
    )
    op.create_index(
        "ix_roster_publication_memberships_version_employee",
        "roster_publication_memberships",
        ["publication_version_id", "employee_id", "date", "source_assignment_id"],
    )

    for table in (
        "roster_publication_versions",
        "roster_publication_memberships",
        "roster_actual_hours_evidence",
        "roster_overtime_approvals",
    ):
        _append_only(table)

    _rls("roster_months", staff_select="status='published'")
    _rls(
        "roster_publication_versions",
        staff_select="id IN (SELECT current_version_id FROM public.roster_months WHERE company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id() AND status='published')",
    )
    _rls(
        "roster_publication_memberships",
        staff_select="employee_id=public.workloop_employee_id() AND publication_version_id IN (SELECT current_version_id FROM public.roster_months WHERE company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id() AND status='published')",
    )
    _rls("roster_actual_hours_evidence")
    _rls("roster_overtime_approvals")

    op.execute(f"""
CREATE FUNCTION public.phase10h_publish_assignments(p_ids uuid[],p_versions integer[]) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  v_count integer;
BEGIN
  IF NOT ({DEFINER_ADMIN_CONTEXT}) OR cardinality(p_ids)=0
     OR cardinality(p_ids) IS DISTINCT FROM cardinality(p_versions)
     OR cardinality(p_ids) IS DISTINCT FROM (SELECT count(DISTINCT value) FROM unnest(p_ids) value)
  THEN
    RAISE EXCEPTION 'roster publication denied' USING ERRCODE='42501';
  END IF;
  PERFORM 1 FROM public.roster_assignments roster
   WHERE roster.id=ANY(p_ids) ORDER BY roster.id FOR UPDATE;
  SELECT count(*) INTO v_count
  FROM unnest(p_ids,p_versions) expected(id,version)
  JOIN public.roster_assignments roster ON roster.id=expected.id
  WHERE roster.company_id=public.workloop_company_id()
    AND roster.branch_id=public.workloop_branch_id()
    AND NOT roster.published AND roster.version=expected.version;
  IF v_count<>cardinality(p_ids) THEN
    RAISE EXCEPTION 'stale roster publication' USING ERRCODE='40001';
  END IF;
  UPDATE public.roster_assignments roster
     SET published=true,version=roster.version+1
    FROM unnest(p_ids,p_versions) expected(id,version)
   WHERE roster.id=expected.id AND roster.version=expected.version;
END
$function$;
ALTER FUNCTION public.phase10h_publish_assignments(uuid[],integer[]) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.phase10h_publish_assignments(uuid[],integer[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.phase10h_publish_assignments(uuid[],integer[]) TO workloop_runtime;
""")

    op.execute(f"""
CREATE FUNCTION public.phase10h_lock_roster_overrides(p_period text) RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  v_count integer;
BEGIN
  IF NOT ({DEFINER_ADMIN_CONTEXT})
     OR p_period !~ '^(19|20)[0-9]{{2}}-(0[1-9]|1[0-2])$'
  THEN
    RAISE EXCEPTION 'roster override lock denied' USING ERRCODE='42501';
  END IF;
  PERFORM 1 FROM public.compliance_overrides
   WHERE company_id=public.workloop_company_id()
     AND branch_id=public.workloop_branch_id() AND roster_month=p_period
   ORDER BY id FOR SHARE;
  GET DIAGNOSTICS v_count = ROW_COUNT;
  RETURN v_count;
END
$function$;
ALTER FUNCTION public.phase10h_lock_roster_overrides(text) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.phase10h_lock_roster_overrides(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.phase10h_lock_roster_overrides(text) TO workloop_runtime;
""")

    op.execute(f"""
CREATE FUNCTION public.phase10h_colleague_schedule(p_date date)
RETURNS TABLE(employee_id uuid,employee_name text,roster_assignment_id uuid,shift_id uuid,shift_name text,shift_code text,shift_category text,work_date date)
LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF current_user<>'workloop_migration' OR session_user<>'workloop_runtime'
     OR public.workloop_actor_kind()<>'human' OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_role() NOT IN ('manager','employee')
     OR public.workloop_employee_id() IS NULL OR public.workloop_business_date() IS NULL
     OR NOT ({DEFINER_STAFF_CONTEXT})
  THEN
    RAISE EXCEPTION 'colleague schedule denied' USING ERRCODE='42501';
  END IF;
  RETURN QUERY
  SELECT membership.employee_id,membership.employee_name,membership.source_assignment_id,
         membership.shift_id,membership.shift_name,membership.shift_code,
         membership.shift_category,membership.date
  FROM public.roster_months month
  JOIN public.roster_publication_memberships membership
    ON membership.publication_version_id=month.current_version_id
   AND membership.company_id=month.company_id AND membership.branch_id=month.branch_id
  WHERE month.company_id=public.workloop_company_id()
    AND month.branch_id=public.workloop_branch_id() AND month.status='published'
    AND membership.date=p_date AND membership.employee_id<>public.workloop_employee_id()
  ORDER BY membership.employee_name,membership.employee_id,membership.source_assignment_id;
END
$function$;
ALTER FUNCTION public.phase10h_colleague_schedule(date) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.phase10h_colleague_schedule(date) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.phase10h_colleague_schedule(date) TO workloop_runtime;
""")

    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10H_REPLAY)


def downgrade() -> None:
    op.execute("""
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.roster_publication_versions)
     OR EXISTS (SELECT 1 FROM public.roster_actual_hours_evidence)
     OR EXISTS (SELECT 1 FROM public.roster_overtime_approvals) THEN
    RAISE EXCEPTION 'phase10h_roster_publication_data_requires_preservation';
  END IF;
END $$;
""")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10G_REPLAY)
    op.execute("DROP FUNCTION public.phase10h_colleague_schedule(date)")
    op.execute("DROP FUNCTION IF EXISTS public.phase10h_lock_roster_overrides(text)")
    op.execute("DROP FUNCTION public.phase10h_publish_assignments(uuid[],integer[])")
    for table in (
        "roster_overtime_approvals",
        "roster_actual_hours_evidence",
        "roster_publication_memberships",
        "roster_publication_versions",
    ):
        op.execute(f"DROP TRIGGER trg_phase10h_{table}_append_only ON public.{table}")
        op.execute(f"DROP FUNCTION public.phase10h_{table}_append_only()")
    op.drop_index(
        "ix_roster_publication_memberships_version_employee",
        table_name="roster_publication_memberships",
    )
    op.drop_table("roster_publication_memberships")
    op.drop_index("ix_roster_overtime_scope_assignment", table_name="roster_overtime_approvals")
    op.drop_table("roster_overtime_approvals")
    op.drop_index(
        "ix_roster_actual_hours_scope_assignment", table_name="roster_actual_hours_evidence"
    )
    op.drop_table("roster_actual_hours_evidence")
    op.drop_constraint(
        "fk_roster_months_current_version_id_roster_publication_versions",
        "roster_months",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_roster_publication_versions_scope_period_version",
        table_name="roster_publication_versions",
    )
    op.drop_table("roster_publication_versions")
    op.drop_index("ix_roster_months_scope_period", table_name="roster_months")
    op.drop_table("roster_months")
