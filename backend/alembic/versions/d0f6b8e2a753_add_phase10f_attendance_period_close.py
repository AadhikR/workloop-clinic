"""Add Phase 10F attendance period close authority.

Revision ID: d0f6b8e2a753
Revises: c9e5a7d1f642
Created: 2026-09-21 20:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "d0f6b8e2a753"
down_revision: str | Sequence[str] | None = "c9e5a7d1f642"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10F_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request','attendance_period') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
PHASE10E_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""

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


def _create_rls(table: str) -> None:
    op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY phase10f_{table}_select_runtime ON public.{table} "
        f"FOR SELECT TO workloop_runtime USING ({ADMIN_SCOPE})"
    )
    op.execute(
        f"CREATE POLICY phase10f_{table}_insert_runtime ON public.{table} "
        f"FOR INSERT TO workloop_runtime WITH CHECK ({ADMIN_SCOPE})"
    )
    op.execute(
        f"CREATE POLICY phase10f_{table}_migration ON public.{table} "
        "FOR ALL TO workloop_migration USING (true) WITH CHECK (true)"
    )
    op.execute(f"GRANT SELECT, INSERT ON public.{table} TO workloop_runtime")


def upgrade() -> None:
    op.add_column(
        "attendance_periods",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("attendance_periods", sa.Column("current_version_id", sa.UUID(), nullable=True))
    op.add_column("attendance_periods", sa.Column("source_version", sa.Text(), nullable=True))
    op.add_column(
        "attendance_periods",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute("UPDATE public.attendance_periods SET payroll_ready=false WHERE status='closed'")
    op.create_check_constraint(
        "phase10f_period_format",
        "attendance_periods",
        "period ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$'",
    )

    op.create_table(
        "attendance_period_versions",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("attendance_period_id", sa.UUID(), nullable=False),
        sa.Column("prior_version_id", sa.UUID(), nullable=True),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payroll_ready", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.Column("source_canonical", sa.Text(), nullable=False),
        sa.Column("source_payload", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("amendment_reason", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("closed_by_app_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "closed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "period ~ '^(19|20)[0-9]{2}-(0[1-9]|1[0-2])$'",
            name=op.f("ck_attendance_period_versions_period"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_attendance_period_versions_version")),
        sa.CheckConstraint(
            "source_version ~ '^sha256:[0-9a-f]{64}$'",
            name=op.f("ck_attendance_period_versions_source_version"),
        ),
        sa.CheckConstraint(
            "record_count >= 0", name=op.f("ck_attendance_period_versions_record_count")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_payload)='object' AND source_canonical::jsonb=source_payload",
            name=op.f("ck_attendance_period_versions_source_payload"),
        ),
        sa.CheckConstraint(
            "(version=1 AND prior_version_id IS NULL AND amendment_reason='') OR (version>1 AND prior_version_id IS NOT NULL AND octet_length(btrim(amendment_reason)) BETWEEN 3 AND 500)",
            name=op.f("ck_attendance_period_versions_amendment"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_versions_company_id_companies"),
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_versions_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["attendance_period_id"],
            ["attendance_periods.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_versions_attendance_period_id_attendance_periods"),
        ),
        sa.ForeignKeyConstraint(
            ["prior_version_id"],
            ["attendance_period_versions.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_versions_prior_version_id_attendance_period_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["closed_by_app_user_id"],
            ["app_users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_versions_closed_by_app_user_id_app_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_period_versions")),
        sa.UniqueConstraint(
            "attendance_period_id", "version", name="uq_attendance_period_versions_period_version"
        ),
        sa.UniqueConstraint("source_version", name="uq_attendance_period_versions_source_version"),
    )
    op.create_index(
        "ix_attendance_period_versions_scope_period_version",
        "attendance_period_versions",
        ["company_id", "branch_id", "period", "version"],
    )
    op.create_foreign_key(
        op.f("fk_attendance_periods_current_version_id_attendance_period_versions"),
        "attendance_periods",
        "attendance_period_versions",
        ["current_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "phase10f_period_state",
        "attendance_periods",
        "(status='open' AND NOT payroll_ready AND version=0 AND current_version_id IS NULL AND source_version IS NULL) OR (status='closed' AND version >= 0 AND ((NOT payroll_ready AND current_version_id IS NULL AND source_version IS NULL) OR (payroll_ready AND version >= 1 AND current_version_id IS NOT NULL AND source_version ~ '^sha256:[0-9a-f]{64}$')))",
    )

    op.create_table(
        "attendance_period_record_snapshots",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("period_version_id", sa.UUID(), nullable=False),
        sa.Column("source_record_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("absence_days", sa.Numeric(4, 2), nullable=False),
        sa.Column("absence_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("late_minutes", sa.Integer(), nullable=False),
        sa.Column("late_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("standard_overtime_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("standard_overtime_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("rest_day_overtime_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("rest_day_overtime_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("calculation_version", sa.Integer(), nullable=False),
        sa.Column("source_digest", sa.Text(), nullable=False),
        sa.Column("source_clock_event_ids", sa.ARRAY(sa.UUID()), nullable=False),
        sa.Column("salary_source_version", sa.Text(), nullable=False),
        sa.Column("source_payload", sa.JSON().with_variant(JSONB, "postgresql"), nullable=False),
        sa.CheckConstraint(
            "absence_days >= 0 AND absence_amount >= 0 AND late_minutes >= 0 AND late_amount >= 0 AND standard_overtime_hours >= 0 AND standard_overtime_amount >= 0 AND rest_day_overtime_hours >= 0 AND rest_day_overtime_amount >= 0 AND calculation_version >= 1",
            name=op.f("ck_attendance_period_record_snapshots_nonnegative"),
        ),
        sa.CheckConstraint(
            "source_digest ~ '^[0-9a-f]{64}$' AND salary_source_version <> '' AND jsonb_typeof(source_payload)='object'",
            name=op.f("ck_attendance_period_record_snapshots_source"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_record_snapshots_company_id_companies"),
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_record_snapshots_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["period_version_id"],
            ["attendance_period_versions.id"],
            ondelete="RESTRICT",
            name=op.f(
                "fk_attendance_period_record_snapshots_period_version_id_attendance_period_versions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"],
            ["attendance_records.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_record_snapshots_source_record_id_attendance_records"),
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_record_snapshots_employee_id_employees"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_period_record_snapshots")),
        sa.UniqueConstraint(
            "period_version_id",
            "source_record_id",
            name="uq_attendance_period_record_snapshots_version_record",
        ),
    )
    op.create_index(
        "ix_attendance_period_snapshots_version_employee",
        "attendance_period_record_snapshots",
        ["period_version_id", "employee_id", "date", "source_record_id"],
    )

    op.create_table(
        "attendance_period_audit_log",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("period_version_id", sa.UUID(), nullable=False),
        sa.Column("period", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor_app_user_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('PERIOD_CLOSED','PERIOD_AMENDED')",
            name=op.f("ck_attendance_period_audit_log_action"),
        ),
        sa.CheckConstraint(
            "octet_length(btrim(reason)) BETWEEN 3 AND 500",
            name=op.f("ck_attendance_period_audit_log_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_audit_log_company_id_companies"),
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_audit_log_branch_id_branches"),
        ),
        sa.ForeignKeyConstraint(
            ["period_version_id"],
            ["attendance_period_versions.id"],
            ondelete="RESTRICT",
            name=op.f(
                "fk_attendance_period_audit_log_period_version_id_attendance_period_versions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["actor_app_user_id"],
            ["app_users.id"],
            ondelete="RESTRICT",
            name=op.f("fk_attendance_period_audit_log_actor_app_user_id_app_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_period_audit_log")),
    )
    op.create_index(
        "ix_attendance_period_audit_scope_period",
        "attendance_period_audit_log",
        ["company_id", "branch_id", "period", "created_at"],
    )

    op.execute("""
CREATE FUNCTION public.phase10f_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user='workloop_migration' THEN
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'closed attendance evidence is append-only' USING ERRCODE='42501';
END $$;
CREATE TRIGGER trg_phase10f_period_versions_append_only BEFORE UPDATE OR DELETE ON public.attendance_period_versions FOR EACH ROW EXECUTE FUNCTION public.phase10f_append_only();
CREATE TRIGGER trg_phase10f_period_snapshots_append_only BEFORE UPDATE OR DELETE ON public.attendance_period_record_snapshots FOR EACH ROW EXECUTE FUNCTION public.phase10f_append_only();
CREATE TRIGGER trg_phase10f_period_audit_append_only BEFORE UPDATE OR DELETE ON public.attendance_period_audit_log FOR EACH ROW EXECUTE FUNCTION public.phase10f_append_only();
CREATE FUNCTION public.phase10f_attendance_record_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user='workloop_migration' THEN
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  IF OLD.period_closed THEN
    RAISE EXCEPTION 'closed attendance record is immutable' USING ERRCODE='42501';
  END IF;
  IF NEW.period_closed AND (to_jsonb(NEW)-'period_closed'-'updated_at') IS DISTINCT FROM (to_jsonb(OLD)-'period_closed'-'updated_at') THEN
    RAISE EXCEPTION 'close may only freeze an attendance record' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_phase10f_attendance_record_guard BEFORE UPDATE OR DELETE ON public.attendance_records FOR EACH ROW EXECUTE FUNCTION public.phase10f_attendance_record_guard();
CREATE FUNCTION public.phase10f_attendance_period_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user='workloop_migration' THEN RETURN NEW; END IF;
  IF OLD.status='closed' AND NEW.status<>'closed' THEN
    RAISE EXCEPTION 'closed attendance period cannot reopen' USING ERRCODE='42501';
  END IF;
  IF OLD.payroll_ready AND (NEW.version < OLD.version OR NEW.current_version_id IS NULL OR NEW.source_version IS NULL) THEN
    RAISE EXCEPTION 'closed attendance period evidence cannot be removed' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_phase10f_attendance_period_guard BEFORE UPDATE ON public.attendance_periods FOR EACH ROW EXECUTE FUNCTION public.phase10f_attendance_period_guard();
CREATE TRIGGER trg_attendance_periods_set_updated_at BEFORE UPDATE ON public.attendance_periods FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
""")
    op.execute("REVOKE ALL ON FUNCTION public.phase10f_append_only() FROM PUBLIC, workloop_runtime")
    op.execute(
        "REVOKE ALL ON FUNCTION public.phase10f_attendance_record_guard() FROM PUBLIC, workloop_runtime"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.phase10f_attendance_period_guard() FROM PUBLIC, workloop_runtime"
    )
    op.execute(r"""
CREATE FUNCTION public.phase10f_lock_clock_events(
  p_company_id uuid, p_branch_id uuid, p_start timestamptz, p_end timestamptz
) RETURNS SETOF uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF session_user <> 'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_role() IS DISTINCT FROM 'admin'
    OR public.workloop_app_user_id() IS NULL
    OR public.workloop_employee_id() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR p_company_id IS DISTINCT FROM public.workloop_company_id()
    OR p_branch_id IS DISTINCT FROM public.workloop_branch_id()
    OR p_start IS NULL OR p_end IS NULL OR p_start >= p_end
    OR NOT EXISTS (
      SELECT 1 FROM public.resolve_workloop_principal() principal
      WHERE principal.app_user_id=public.workloop_app_user_id()
        AND principal.account_status='active' AND principal.role='admin'
        AND principal.profile_company_id=p_company_id
        AND principal.company_id=principal.profile_company_id
        AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL
        AND principal.branch_id IS NULL
    ) THEN
    RAISE EXCEPTION 'attendance period event lock denied' USING ERRCODE='42501';
  END IF;
  LOCK TABLE public.clock_events IN SHARE MODE;
  RETURN QUERY
  SELECT event.id FROM public.clock_events event
  WHERE event.company_id=p_company_id AND event.branch_id=p_branch_id
    AND event.event_time>=p_start AND event.event_time<p_end
  ORDER BY event.id FOR UPDATE;
END;
$function$;
REVOKE ALL ON FUNCTION public.phase10f_lock_clock_events(uuid,uuid,timestamptz,timestamptz)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.phase10f_lock_clock_events(uuid,uuid,timestamptz,timestamptz)
  TO workloop_runtime;
CREATE FUNCTION public.phase10f_lock_period_evidence(
  p_company_id uuid, p_branch_id uuid, p_version_id uuid
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE found_version boolean;
BEGIN
  IF session_user <> 'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_role() IS DISTINCT FROM 'admin'
    OR public.workloop_app_user_id() IS NULL
    OR public.workloop_employee_id() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR p_company_id IS DISTINCT FROM public.workloop_company_id()
    OR p_branch_id IS DISTINCT FROM public.workloop_branch_id()
    OR p_version_id IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM public.resolve_workloop_principal() principal
      WHERE principal.app_user_id=public.workloop_app_user_id()
        AND principal.account_status='active' AND principal.role='admin'
        AND principal.profile_company_id=p_company_id
        AND principal.company_id=principal.profile_company_id
        AND principal.profile_employee_id IS NULL AND principal.employee_id IS NULL
        AND principal.branch_id IS NULL
    ) THEN
    RAISE EXCEPTION 'attendance period evidence lock denied' USING ERRCODE='42501';
  END IF;
  SELECT true INTO found_version FROM public.attendance_period_versions version
  WHERE version.id=p_version_id AND version.company_id=p_company_id
    AND version.branch_id=p_branch_id FOR UPDATE;
  IF found_version IS DISTINCT FROM true THEN
    RETURN false;
  END IF;
  PERFORM 1 FROM public.attendance_period_record_snapshots snapshot
  WHERE snapshot.period_version_id=p_version_id AND snapshot.company_id=p_company_id
    AND snapshot.branch_id=p_branch_id ORDER BY snapshot.id FOR UPDATE;
  RETURN true;
END;
$function$;
REVOKE ALL ON FUNCTION public.phase10f_lock_period_evidence(uuid,uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.phase10f_lock_period_evidence(uuid,uuid,uuid)
  TO workloop_runtime;
""")
    for table in (
        "attendance_period_versions",
        "attendance_period_record_snapshots",
        "attendance_period_audit_log",
    ):
        _create_rls(table)

    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10F_REPLAY)


def downgrade() -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10E_REPLAY)
    op.execute("DROP TRIGGER trg_attendance_periods_set_updated_at ON public.attendance_periods")
    op.execute("DROP FUNCTION IF EXISTS public.phase10f_lock_period_evidence(uuid,uuid,uuid)")
    op.execute(
        "DROP FUNCTION IF EXISTS public.phase10f_lock_clock_events(uuid,uuid,timestamptz,timestamptz)"
    )
    op.execute("DROP TRIGGER trg_phase10f_attendance_period_guard ON public.attendance_periods")
    op.execute("DROP FUNCTION public.phase10f_attendance_period_guard()")
    op.execute("DROP TRIGGER trg_phase10f_attendance_record_guard ON public.attendance_records")
    op.execute("DROP FUNCTION public.phase10f_attendance_record_guard()")
    op.execute(
        "DROP TRIGGER trg_phase10f_period_audit_append_only ON public.attendance_period_audit_log"
    )
    op.execute(
        "DROP TRIGGER trg_phase10f_period_snapshots_append_only ON public.attendance_period_record_snapshots"
    )
    op.execute(
        "DROP TRIGGER trg_phase10f_period_versions_append_only ON public.attendance_period_versions"
    )
    op.execute("DROP FUNCTION public.phase10f_append_only()")
    op.drop_index(
        "ix_attendance_period_audit_scope_period", table_name="attendance_period_audit_log"
    )
    op.drop_table("attendance_period_audit_log")
    op.drop_index(
        "ix_attendance_period_snapshots_version_employee",
        table_name="attendance_period_record_snapshots",
    )
    op.drop_table("attendance_period_record_snapshots")
    op.drop_constraint(
        op.f("fk_attendance_periods_current_version_id_attendance_period_versions"),
        "attendance_periods",
        type_="foreignkey",
    )
    op.drop_constraint("phase10f_period_state", "attendance_periods", type_="check")
    op.drop_index(
        "ix_attendance_period_versions_scope_period_version",
        table_name="attendance_period_versions",
    )
    op.drop_table("attendance_period_versions")
    op.drop_constraint("phase10f_period_format", "attendance_periods", type_="check")
    op.drop_column("attendance_periods", "updated_at")
    op.drop_column("attendance_periods", "source_version")
    op.drop_column("attendance_periods", "current_version_id")
    op.drop_column("attendance_periods", "version")
