"""Add Phase 10C append-only attendance ingestion.

Revision ID: b7d9e1f3a5c6
Revises: a6c8e0f2b4d7
Created: 2026-09-20 10:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7d9e1f3a5c6"
down_revision: str | Sequence[str] | None = "a6c8e0f2b4d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10C_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
PHASE10B_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
AUDIT_SIGNATURE = "public.append_audit_event(text, text, uuid, text[], text, jsonb)"
PRIVATE_AUDIT_SIGNATURE = (
    "public._append_audit_event_phase10c(text, text, uuid, text[], text, jsonb)"
)


def _install_audit_wrapper() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} RENAME TO _append_audit_event_phase10c")
    op.execute(f"REVOKE ALL ON FUNCTION {PRIVATE_AUDIT_SIGNATURE} FROM PUBLIC, workloop_runtime")
    op.execute(r"""
CREATE FUNCTION public.append_audit_event(p_action text, p_entity_type text, p_entity_id uuid,
 p_changed_fields text[], p_reason text, p_metadata jsonb) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path TO pg_catalog, public, pg_temp AS $function$
DECLARE event_id uuid;
BEGIN
 IF p_action NOT IN ('attendance_manual_event_created','biometric_mapping_replaced',
   'biometric_mapping_deleted','attendance_biometric_batch_imported') THEN
   RETURN public._append_audit_event_phase10c(p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
 END IF;
 IF session_user <> 'workloop_runtime' OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
   OR public.workloop_role() IS DISTINCT FROM 'admin' OR public.workloop_app_user_id() IS NULL
   OR public.workloop_company_id() IS NULL OR public.workloop_branch_id() IS NULL
   OR p_reason IS NULL OR btrim(p_reason)='' OR COALESCE(p_metadata,'{}'::jsonb)<>'{}'::jsonb THEN
   RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
 END IF;
 IF (p_action='attendance_manual_event_created' AND (p_entity_type<>'clock_event' OR NOT EXISTS
   (SELECT 1 FROM public.clock_events e WHERE e.id=p_entity_id AND e.company_id=public.workloop_company_id() AND e.branch_id=public.workloop_branch_id() AND e.method='MANUAL')))
   OR (p_action IN ('biometric_mapping_replaced','biometric_mapping_deleted') AND (p_entity_type<>'biometric_mapping' OR NOT EXISTS
   (SELECT 1 FROM public.biometric_mappings m WHERE m.id=p_entity_id AND m.company_id=public.workloop_company_id() AND m.branch_id=public.workloop_branch_id())))
   OR (p_action='attendance_biometric_batch_imported' AND (p_entity_type<>'attendance_import_batch' OR NOT EXISTS
   (SELECT 1 FROM public.attendance_import_batches b WHERE b.id=p_entity_id AND b.company_id=public.workloop_company_id() AND b.branch_id=public.workloop_branch_id()))) THEN
   RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
 END IF;
 INSERT INTO public.audit_events(company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
 VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,'{}'::jsonb) RETURNING id INTO event_id;
 RETURN event_id;
END $function$;
""")
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def upgrade() -> None:
    op.create_table(
        "attendance_import_batches",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("submitted_by_app_user_id", sa.UUID(), nullable=False),
        sa.Column("batch_fingerprint", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "company_id",
            "branch_id",
            "batch_fingerprint",
            name="uq_attendance_import_batches_scope_fingerprint",
        ),
        sa.UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_attendance_import_batches_id_scope"
        ),
        sa.CheckConstraint("row_count BETWEEN 1 AND 5000", name="row_count"),
        sa.CheckConstraint("byte_count BETWEEN 1 AND 2097152", name="byte_count"),
    )
    op.create_index(
        "ix_attendance_import_batches_scope_created",
        "attendance_import_batches",
        ["company_id", "branch_id", sa.text("created_at DESC")],
    )
    op.add_column("clock_events", sa.Column("event_fingerprint", sa.Text(), nullable=True))
    op.add_column("clock_events", sa.Column("import_batch_id", sa.UUID(), nullable=True))
    op.add_column("clock_events", sa.Column("import_row_number", sa.Integer(), nullable=True))
    op.add_column("clock_events", sa.Column("source_badge_no", sa.Text(), nullable=True))
    op.add_column("clock_events", sa.Column("source_device_name", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_clock_events_import_batch_scope",
        "clock_events",
        "attendance_import_batches",
        ["import_batch_id", "company_id", "branch_id"],
        ["id", "company_id", "branch_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "phase10c_clock_event_provenance",
        "clock_events",
        "(import_batch_id IS NULL AND import_row_number IS NULL AND source_badge_no IS NULL AND source_device_name IS NULL AND event_fingerprint IS NULL) OR (method='BIOMETRIC' AND import_batch_id IS NOT NULL AND import_row_number IS NOT NULL AND source_badge_no IS NOT NULL AND source_device_name IS NOT NULL AND event_fingerprint IS NOT NULL)",
    )
    op.create_index(
        "uq_clock_events_fingerprint",
        "clock_events",
        ["company_id", "branch_id", "event_fingerprint"],
        unique=True,
        postgresql_where=sa.text("event_fingerprint IS NOT NULL"),
    )
    op.create_index(
        "uq_clock_events_method_minute",
        "clock_events",
        [
            "employee_id",
            "event_type",
            "method",
            sa.text("date_trunc('minute', event_time AT TIME ZONE 'UTC')"),
        ],
        unique=True,
        postgresql_where=sa.text("method IN ('MANUAL','BIOMETRIC')"),
    )
    op.create_index(
        "ix_clock_events_scope_employee_time",
        "clock_events",
        ["company_id", "branch_id", "employee_id", sa.text("event_time DESC"), "id"],
    )
    op.create_index(
        "ix_biometric_mappings_scope_badge",
        "biometric_mappings",
        ["company_id", "branch_id", "badge_no"],
    )
    op.create_unique_constraint(
        "uq_clock_events_id_scope", "clock_events", ["id", "company_id", "branch_id"]
    )
    op.create_table(
        "attendance_import_row_outcomes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("clock_event_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["batch_id", "company_id", "branch_id"],
            [
                "attendance_import_batches.id",
                "attendance_import_batches.company_id",
                "attendance_import_batches.branch_id",
            ],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["clock_event_id", "company_id", "branch_id"],
            ["clock_events.id", "clock_events.company_id", "clock_events.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "batch_id", "row_number", name="uq_attendance_import_row_outcomes_batch_row"
        ),
        sa.CheckConstraint("row_number >= 1", name="row_number"),
        sa.CheckConstraint(
            "outcome IN ('accepted','duplicate','unknown_badge','invalid')", name="outcome"
        ),
        sa.CheckConstraint(
            "(outcome='accepted') = (clock_event_id IS NOT NULL)", name="event_for_accepted_only"
        ),
    )
    op.execute("""
CREATE FUNCTION public.phase10c_clock_event_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF session_user = 'workloop_migration' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'clock events are append-only' USING ERRCODE='42501';
END $$;
CREATE TRIGGER trg_phase10c_clock_events_append_only BEFORE UPDATE OR DELETE ON public.clock_events FOR EACH ROW EXECUTE FUNCTION public.phase10c_clock_event_append_only();
""")
    admin = """public.workloop_actor_kind() = 'human'
AND public.workloop_role() = 'admin'
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_employee_id() IS NULL
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()"""
    op.execute("ALTER TABLE public.attendance_import_batches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.attendance_import_row_outcomes ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY phase10c_import_batches_select_runtime ON public.attendance_import_batches "
        f"FOR SELECT TO workloop_runtime USING ({admin})"
    )
    op.execute(
        f"CREATE POLICY phase10c_import_batches_insert_runtime ON public.attendance_import_batches "
        f"FOR INSERT TO workloop_runtime WITH CHECK ({admin} "
        "AND submitted_by_app_user_id = public.workloop_app_user_id())"
    )
    outcome_scope = """company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND EXISTS (
  SELECT 1 FROM public.attendance_import_batches batch
  WHERE batch.id = attendance_import_row_outcomes.batch_id
    AND batch.company_id = attendance_import_row_outcomes.company_id
    AND batch.branch_id = attendance_import_row_outcomes.branch_id
)"""
    op.execute(
        "CREATE POLICY phase10c_import_outcomes_select_runtime "
        "ON public.attendance_import_row_outcomes FOR SELECT TO workloop_runtime "
        f"USING ({outcome_scope})"
    )
    op.execute(
        "CREATE POLICY phase10c_import_outcomes_insert_runtime "
        "ON public.attendance_import_row_outcomes FOR INSERT TO workloop_runtime "
        f"WITH CHECK ({outcome_scope})"
    )
    op.execute(
        "GRANT SELECT, INSERT ON TABLE public.attendance_import_batches, "
        "public.attendance_import_row_outcomes TO workloop_runtime"
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10C_REPLAY)
    _install_audit_wrapper()
    op.execute("""
CREATE FUNCTION public.phase10c_import_evidence_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF session_user = 'workloop_migration' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'attendance import evidence is append-only' USING ERRCODE='42501';
END $$;
CREATE TRIGGER trg_phase10c_import_batches_append_only BEFORE UPDATE OR DELETE ON public.attendance_import_batches FOR EACH ROW EXECUTE FUNCTION public.phase10c_import_evidence_append_only();
CREATE TRIGGER trg_phase10c_import_outcomes_append_only BEFORE UPDATE OR DELETE ON public.attendance_import_row_outcomes FOR EACH ROW EXECUTE FUNCTION public.phase10c_import_evidence_append_only();
""")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC, workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(f"ALTER FUNCTION {PRIVATE_AUDIT_SIGNATURE} RENAME TO append_audit_event")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10B_REPLAY)
    op.execute(
        "REVOKE SELECT, INSERT ON TABLE public.attendance_import_batches, "
        "public.attendance_import_row_outcomes FROM workloop_runtime"
    )
    op.execute(
        "DROP TRIGGER trg_phase10c_import_outcomes_append_only ON public.attendance_import_row_outcomes"
    )
    op.execute(
        "DROP TRIGGER trg_phase10c_import_batches_append_only ON public.attendance_import_batches"
    )
    op.execute("DROP FUNCTION public.phase10c_import_evidence_append_only()")
    op.execute("DROP TRIGGER trg_phase10c_clock_events_append_only ON public.clock_events")
    op.execute("DROP FUNCTION public.phase10c_clock_event_append_only()")
    op.drop_table("attendance_import_row_outcomes")
    op.drop_constraint("uq_clock_events_id_scope", "clock_events", type_="unique")
    op.drop_index("ix_biometric_mappings_scope_badge", table_name="biometric_mappings")
    op.drop_index("ix_clock_events_scope_employee_time", table_name="clock_events")
    op.drop_index("uq_clock_events_method_minute", table_name="clock_events")
    op.drop_index("uq_clock_events_fingerprint", table_name="clock_events")
    op.drop_constraint("phase10c_clock_event_provenance", "clock_events", type_="check")
    op.drop_constraint("fk_clock_events_import_batch_scope", "clock_events", type_="foreignkey")
    for column in (
        "source_device_name",
        "source_badge_no",
        "import_row_number",
        "import_batch_id",
        "event_fingerprint",
    ):
        op.drop_column("clock_events", column)
    op.drop_index(
        "ix_attendance_import_batches_scope_created", table_name="attendance_import_batches"
    )
    op.drop_table("attendance_import_batches")
