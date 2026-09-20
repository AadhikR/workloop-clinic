"""Add Phase 10B attendance configuration authority.

Revision ID: a6c8e0f2b4d7
Revises: f4b8d2e6a901
Created: 2026-09-18 10:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a6c8e0f2b4d7"
down_revision: str | Sequence[str] | None = "f4b8d2e6a901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10B_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
PHASE9H_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
AUDIT_SIGNATURE = "public.append_audit_event(text, text, uuid, text[], text, jsonb)"
PRIVATE_AUDIT_SIGNATURE = (
    "public._append_audit_event_phase10a(text, text, uuid, text[], text, jsonb)"
)


def _install_audit_wrapper() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} RENAME TO _append_audit_event_phase10a")
    op.execute(f"REVOKE ALL ON FUNCTION {PRIVATE_AUDIT_SIGNATURE} FROM PUBLIC, workloop_runtime")
    op.execute(r"""
CREATE FUNCTION public.append_audit_event(
  p_action text, p_entity_type text, p_entity_id uuid, p_changed_fields text[],
  p_reason text, p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE event_id uuid;
BEGIN
  IF p_action NOT IN ('attendance_settings_changed','shift_created','shift_changed',
      'shift_deactivated','shift_assigned') THEN
    RETURN public._append_audit_event_phase10a(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF session_user <> 'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_role() IS DISTINCT FROM 'admin'
    OR public.workloop_app_user_id() IS NULL
    OR public.workloop_employee_id() IS NOT NULL
    OR public.workloop_company_id() IS NULL
    OR public.workloop_branch_id() IS NULL
    OR public.workloop_business_date() IS NULL
    OR p_reason IS NULL OR btrim(p_reason) = ''
    OR jsonb_typeof(COALESCE(p_metadata,'{}'::jsonb)) <> 'object'
    OR NOT EXISTS (
      SELECT 1 FROM public.resolve_workloop_principal() caller
      WHERE caller.app_user_id=public.workloop_app_user_id()
        AND caller.account_status='active' AND caller.role='admin'
        AND caller.profile_company_id=public.workloop_company_id()
        AND caller.company_id=caller.profile_company_id
        AND caller.profile_employee_id IS NULL AND caller.employee_id IS NULL
        AND caller.branch_id IS NULL
    ) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action='attendance_settings_changed' THEN
    IF p_entity_type<>'attendance_settings' OR COALESCE(p_metadata,'{}'::jsonb)<>'{}'::jsonb
      OR NOT (p_changed_fields <@ ARRAY['working_days','weekend_days','default_hours_per_day',
        'late_grace_minutes','early_departure_grace_minutes','overtime_requires_approval',
        'max_daily_overtime_hours','late_deduction_policy','late_deduction_amount','wfh_enabled',
        'regularisation_max_days_per_month','regularisation_window_days','biometric_api_enabled',
        'biometric_api_key_configured']::text[])
      OR NOT EXISTS (SELECT 1 FROM public.attendance_settings s WHERE s.id=p_entity_id
        AND s.company_id=public.workloop_company_id() AND s.branch_id=public.workloop_branch_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action IN ('shift_created','shift_changed','shift_deactivated') THEN
    IF p_entity_type<>'shift' OR COALESCE(p_metadata,'{}'::jsonb)<>'{}'::jsonb
      OR NOT EXISTS (SELECT 1 FROM public.shifts s WHERE s.id=p_entity_id
        AND s.company_id=public.workloop_company_id() AND s.branch_id=public.workloop_branch_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    IF p_entity_type<>'shift_assignment'
      OR p_changed_fields IS DISTINCT FROM ARRAY['employee_id','shift_id','effective_from','effective_to']::text[]
      OR NOT EXISTS (SELECT 1 FROM public.shift_assignments a WHERE a.id=p_entity_id
        AND a.company_id=public.workloop_company_id() AND a.branch_id=public.workloop_branch_id()
        AND a.employee_id=(p_metadata->>'employee_id')::uuid
        AND a.shift_id=(p_metadata->>'shift_id')::uuid
        AND a.effective_from=(p_metadata->>'effective_from')::date
        AND a.effective_to IS NOT DISTINCT FROM NULLIF(p_metadata->>'effective_to','')::date) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;
  INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,
    system_actor_key,initiated_by_app_user_id,action,entity_type,entity_id,
    changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
    p_changed_fields,p_reason,COALESCE(p_metadata,'{}'::jsonb))
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
""")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.alter_column(
        "attendance_settings",
        "working_days",
        server_default=sa.text("ARRAY['Sun','Mon','Tue','Wed','Thu']::text[]"),
    )
    op.execute(
        "ALTER TABLE public.attendance_settings "
        "DISABLE TRIGGER trg_attendance_settings_set_updated_at"
    )
    op.execute("""
UPDATE public.attendance_settings settings
SET working_days = settings.working_days || ARRAY(
  SELECT day FROM unnest(ARRAY['Sun','Mon','Tue','Wed','Thu','Fri','Sat']::text[]) day
  WHERE NOT day=ANY(settings.working_days) AND NOT day=ANY(settings.weekend_days)
)
WHERE cardinality(ARRAY(SELECT DISTINCT day FROM unnest(settings.working_days || settings.weekend_days) day)) < 7
""")
    op.execute(
        "ALTER TABLE public.attendance_settings "
        "ENABLE TRIGGER trg_attendance_settings_set_updated_at"
    )
    op.execute("ALTER TABLE public.shifts DISABLE TRIGGER trg_shifts_set_updated_at")
    op.execute("UPDATE public.shifts SET color=upper(color)")
    op.execute("ALTER TABLE public.shifts ENABLE TRIGGER trg_shifts_set_updated_at")
    op.alter_column("shifts", "color", server_default=sa.text("'#6366F1'"))
    op.create_check_constraint(
        "phase10b_attendance_settings_days",
        "attendance_settings",
        "cardinality(working_days) > 0 AND cardinality(weekend_days) > 0 AND cardinality(working_days) + cardinality(weekend_days) = 7 AND NOT working_days && weekend_days AND working_days <@ ARRAY['Sun','Mon','Tue','Wed','Thu','Fri','Sat']::text[] AND weekend_days <@ ARRAY['Sun','Mon','Tue','Wed','Thu','Fri','Sat']::text[] AND ARRAY['Sun','Mon','Tue','Wed','Thu','Fri','Sat']::text[] <@ (working_days || weekend_days)",
    )
    op.create_check_constraint(
        "phase10b_attendance_settings_bounds",
        "attendance_settings",
        "default_hours_per_day BETWEEN 0.25 AND 24 AND late_grace_minutes BETWEEN 0 AND 240 AND early_departure_grace_minutes BETWEEN 0 AND 240 AND max_daily_overtime_hours BETWEEN 0 AND 12 AND regularisation_max_days_per_month BETWEEN 0 AND 31 AND regularisation_window_days BETWEEN 0 AND 365",
    )
    op.create_check_constraint(
        "phase10b_attendance_settings_secret",
        "attendance_settings",
        "octet_length(biometric_api_key) <= 512 AND (NOT biometric_api_enabled OR octet_length(btrim(biometric_api_key)) BETWEEN 16 AND 512)",
    )
    op.create_check_constraint(
        "phase10b_shifts_text",
        "shifts",
        "octet_length(btrim(name)) BETWEEN 1 AND 80 AND color ~ '^#[0-9A-F]{6}$' AND (code IS NULL OR code ~ '^[A-Z0-9]([A-Z0-9-]{0,10}[A-Z0-9])?$')",
    )
    op.create_check_constraint(
        "phase10b_shifts_bounds",
        "shifts",
        "break_minutes BETWEEN 0 AND 240 AND expected_hours BETWEEN 0.25 AND 24 AND late_grace_minutes BETWEEN 0 AND 240 AND early_departure_grace_minutes BETWEEN 0 AND 240 AND (min_hours_flexible IS NULL OR min_hours_flexible BETWEEN 0.25 AND expected_hours) AND min_staff BETWEEN 0 AND 999",
    )
    op.create_check_constraint(
        "phase10b_shifts_shape",
        "shifts",
        "(shift_type='fixed' AND start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time AND NOT is_overnight AND split_start_time IS NULL AND split_end_time IS NULL AND min_hours_flexible IS NULL AND shift_category IN ('morning','afternoon','night')) OR (shift_type='overnight' AND start_time IS NOT NULL AND end_time IS NOT NULL AND end_time <= start_time AND is_overnight AND split_start_time IS NULL AND split_end_time IS NULL AND min_hours_flexible IS NULL AND shift_category='night') OR (shift_type='split' AND start_time IS NOT NULL AND end_time IS NOT NULL AND split_start_time IS NOT NULL AND split_end_time IS NOT NULL AND start_time < end_time AND end_time <= split_start_time AND split_start_time < split_end_time AND NOT is_overnight AND min_hours_flexible IS NULL AND shift_category='split') OR (shift_type='flexible' AND start_time IS NULL AND end_time IS NULL AND split_start_time IS NULL AND split_end_time IS NULL AND NOT is_overnight AND break_minutes=0 AND min_hours_flexible IS NOT NULL AND shift_category='flexible')",
    )
    op.add_column(
        "shift_assignments",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "CREATE TRIGGER trg_shift_assignments_set_updated_at BEFORE UPDATE ON public.shift_assignments FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
    )
    op.create_index(
        "ix_shift_assignments_scope_employee_effective",
        "shift_assignments",
        ["company_id", "branch_id", "employee_id", sa.text("effective_from DESC"), "id"],
    )
    op.execute(
        "ALTER TABLE public.shift_assignments ADD CONSTRAINT shift_assignments_no_overlap EXCLUDE USING gist (company_id WITH =, branch_id WITH =, employee_id WITH =, daterange(effective_from,effective_to,'[]') WITH &&)"
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10B_REPLAY)
    _install_audit_wrapper()


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC, workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(f"ALTER FUNCTION {PRIVATE_AUDIT_SIGNATURE} RENAME TO append_audit_event")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE9H_REPLAY)
    op.execute("ALTER TABLE public.shift_assignments DROP CONSTRAINT shift_assignments_no_overlap")
    op.drop_index("ix_shift_assignments_scope_employee_effective", table_name="shift_assignments")
    op.execute("DROP TRIGGER trg_shift_assignments_set_updated_at ON public.shift_assignments")
    op.drop_column("shift_assignments", "updated_at")
    for name, table in reversed(
        (
            ("phase10b_shifts_shape", "shifts"),
            ("phase10b_shifts_bounds", "shifts"),
            ("phase10b_shifts_text", "shifts"),
            ("phase10b_attendance_settings_secret", "attendance_settings"),
            ("phase10b_attendance_settings_bounds", "attendance_settings"),
            ("phase10b_attendance_settings_days", "attendance_settings"),
        )
    ):
        op.drop_constraint(name, table, type_="check")
    op.alter_column("shifts", "color", server_default=sa.text("'#6366f1'"))
    op.alter_column(
        "attendance_settings",
        "working_days",
        server_default=sa.text("ARRAY['Mon','Tue','Wed','Thu']::text[]"),
    )
    op.execute("DROP EXTENSION btree_gist")
