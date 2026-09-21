# ruff: noqa: E501

"""Add Phase 10E exception workflow guards.

Revision ID: c9e5a7d1f642
Revises: f2d4a8c6b901
Created: 2026-09-21 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9e5a7d1f642"
down_revision: str | Sequence[str] | None = "f2d4a8c6b901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10E_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record','regularisation_request') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""
PHASE10D_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""


def upgrade() -> None:
    op.drop_index("uq_clock_events_method_minute", table_name="clock_events")
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
        postgresql_where=sa.text("method IN ('MANUAL','BIOMETRIC') AND superseded_by IS NULL"),
    )
    op.add_column(
        "regularisation_requests",
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "attendance_records", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "attendance_records", sa.Column("resolution_source_digest", sa.Text(), nullable=True)
    )
    op.add_column(
        "attendance_records",
        sa.Column("overtime_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "attendance_records", sa.Column("overtime_approval_source_digest", sa.Text(), nullable=True)
    )
    op.execute("""
UPDATE public.regularisation_requests
SET reason='Legacy request'
WHERE btrim(reason) = '';
UPDATE public.attendance_records
SET resolved_at=updated_at, resolution_source_digest=source_digest
WHERE resolution_type <> '';
UPDATE public.attendance_records
SET overtime_approved_at=updated_at, overtime_approval_source_digest=source_digest
WHERE overtime_approved;
""")
    op.create_check_constraint(
        "phase10e_regularisation_version", "regularisation_requests", "version >= 1"
    )
    op.create_check_constraint(
        "phase10e_regularisation_reason",
        "regularisation_requests",
        "char_length(btrim(reason)) BETWEEN 3 AND 500",
    )
    op.create_check_constraint(
        "phase10e_regularisation_span",
        "regularisation_requests",
        "correct_clock_out - correct_clock_in <= interval '24 hours'",
    )
    op.drop_constraint("decision_fields", "regularisation_requests", type_="check")
    op.drop_constraint("rejection_fields", "regularisation_requests", type_="check")
    op.create_check_constraint(
        "phase10e_decision_state",
        "regularisation_requests",
        "(status='Pending' AND approved_by_app_user_id IS NULL AND approved_at IS NULL "
        "AND rejection_reason='') OR (status='Approved' "
        "AND approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL "
        "AND rejection_reason='') OR (status='Rejected' "
        "AND approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL "
        "AND btrim(rejection_reason) <> '')",
    )
    op.create_index(
        "uq_regularisation_requests_pending_employee_date",
        "regularisation_requests",
        ["company_id", "branch_id", "employee_id", "attendance_date"],
        unique=True,
        postgresql_where=sa.text("status = 'Pending'"),
    )
    op.create_check_constraint(
        "phase10e_attendance_resolution_evidence",
        "attendance_records",
        "(resolution_type = '' AND resolved_by_app_user_id IS NULL AND resolved_at IS NULL AND resolution_source_digest IS NULL) OR (resolution_type <> '' AND resolved_by_app_user_id IS NOT NULL AND resolved_at IS NOT NULL AND btrim(resolution_source_digest) <> '')",
    )
    op.create_check_constraint(
        "phase10e_overtime_approval_evidence",
        "attendance_records",
        "(NOT overtime_approved AND overtime_approved_by_app_user_id IS NULL AND overtime_approved_at IS NULL AND overtime_approval_source_digest IS NULL) OR (overtime_approved AND overtime_approved_by_app_user_id IS NOT NULL AND overtime_approved_at IS NOT NULL AND btrim(overtime_approval_source_digest) <> '')",
    )
    op.create_check_constraint(
        "phase10e_attendance_audit_action",
        "attendance_audit_log",
        "action IN ('edit', 'Absence Resolved', 'REGULARISATION_APPROVED', "
        "'REGULARISATION_REJECTED', 'ABSENCE_RESOLVED', 'OVERTIME_APPROVED')",
    )
    op.create_check_constraint(
        "phase10e_clock_event_supersession",
        "clock_events",
        "is_superseded = (superseded_by IS NOT NULL)",
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10E_REPLAY)
    op.execute("""
CREATE OR REPLACE FUNCTION public.phase10c_clock_event_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user = 'workloop_migration' THEN
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'clock events are append-only' USING ERRCODE='42501';
END $$;
CREATE FUNCTION public.phase10e_attendance_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user = 'workloop_migration' THEN
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'attendance audit rows are append-only';
END $$;
CREATE TRIGGER trg_phase10e_attendance_audit_append_only
BEFORE UPDATE OR DELETE ON public.attendance_audit_log
FOR EACH ROW EXECUTE FUNCTION public.phase10e_attendance_audit_append_only();
REVOKE ALL ON FUNCTION public.phase10e_attendance_audit_append_only() FROM PUBLIC;
CREATE FUNCTION public.phase10e_regularisation_limits()
RETURNS TABLE(window_days integer, max_days integer)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp AS $$
BEGIN
  IF session_user <> 'workloop_runtime' OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_role() NOT IN ('manager','employee')
    OR public.workloop_company_id() IS NULL OR public.workloop_branch_id() IS NULL
    OR public.workloop_employee_id() IS NULL THEN
    RAISE EXCEPTION 'regularisation limits denied' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
  SELECT settings.regularisation_window_days, settings.regularisation_max_days_per_month
  FROM public.attendance_settings AS settings
  WHERE settings.company_id=public.workloop_company_id()
    AND settings.branch_id=public.workloop_branch_id()
  FOR UPDATE;
END $$;
ALTER FUNCTION public.phase10e_regularisation_limits() OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.phase10e_regularisation_limits() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.phase10e_regularisation_limits() TO workloop_runtime;
CREATE FUNCTION public.phase10e_prepare_regularisation_approval(
  p_request_id uuid, p_expected_version integer
) RETURNS TABLE(employee_id uuid, attendance_date date, source_digest text, calculation_version integer)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp AS $$
DECLARE request_row public.regularisation_requests%ROWTYPE;
DECLARE record_row public.attendance_records%ROWTYPE;
DECLARE period_status text;
DECLARE source_event_count integer;
BEGIN
  IF session_user <> 'workloop_runtime' OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_role() IS DISTINCT FROM 'admin' OR public.workloop_company_id() IS NULL
    OR public.workloop_branch_id() IS NULL OR public.workloop_app_user_id() IS NULL THEN
    RAISE EXCEPTION 'regularisation approval denied' USING ERRCODE = '42501';
  END IF;
  SELECT request.* INTO request_row FROM public.regularisation_requests AS request
  WHERE request.id=p_request_id AND request.company_id=public.workloop_company_id()
    AND request.branch_id=public.workloop_branch_id() FOR UPDATE;
  IF NOT FOUND OR request_row.status <> 'Pending' OR request_row.version <> p_expected_version THEN
    RAISE EXCEPTION 'regularisation state changed' USING ERRCODE = '40001';
  END IF;
  SELECT attendance_period.status INTO period_status
  FROM public.attendance_periods AS attendance_period
  WHERE attendance_period.company_id=request_row.company_id
    AND attendance_period.branch_id=request_row.branch_id
    AND attendance_period.period=to_char(request_row.attendance_date, 'YYYY-MM') FOR UPDATE;
  IF period_status = 'closed' THEN
    RAISE EXCEPTION 'attendance period is closed' USING ERRCODE = '40001';
  END IF;
  SELECT record.* INTO record_row FROM public.attendance_records AS record
  WHERE record.company_id=request_row.company_id AND record.branch_id=request_row.branch_id
    AND record.employee_id=request_row.employee_id
    AND record.date=request_row.attendance_date FOR UPDATE;
  IF NOT FOUND OR record_row.period_closed OR record_row.source_stale THEN
    RAISE EXCEPTION 'attendance record unavailable' USING ERRCODE = '40001';
  END IF;
  SELECT count(*) INTO source_event_count FROM public.clock_events AS event
  WHERE event.id = ANY(record_row.source_clock_event_ids)
    AND event.company_id=request_row.company_id AND event.branch_id=request_row.branch_id
    AND event.employee_id=request_row.employee_id AND event.superseded_by IS NULL;
  IF source_event_count <> cardinality(record_row.source_clock_event_ids) THEN
    RAISE EXCEPTION 'regularisation source changed' USING ERRCODE = '40001';
  END IF;
  PERFORM 1 FROM public.clock_events AS event
  WHERE event.id = ANY(record_row.source_clock_event_ids)
    AND event.company_id=request_row.company_id AND event.branch_id=request_row.branch_id
    AND event.employee_id=request_row.employee_id AND event.superseded_by IS NULL
  ORDER BY event.id FOR UPDATE;
  UPDATE public.clock_events AS event SET is_superseded=true, superseded_by=request_row.id
  WHERE event.id = ANY(record_row.source_clock_event_ids)
    AND event.company_id=request_row.company_id AND event.branch_id=request_row.branch_id
    AND event.employee_id=request_row.employee_id AND event.superseded_by IS NULL;
  INSERT INTO public.clock_events(company_id,branch_id,employee_id,event_type,event_time,method,entered_by_app_user_id,notes)
  VALUES
    (request_row.company_id,request_row.branch_id,request_row.employee_id,'CLOCK_IN',request_row.correct_clock_in,'MANUAL',public.workloop_app_user_id(),'regularisation:' || request_row.id::text),
    (request_row.company_id,request_row.branch_id,request_row.employee_id,'CLOCK_OUT',request_row.correct_clock_out,'MANUAL',public.workloop_app_user_id(),'regularisation:' || request_row.id::text);
  UPDATE public.regularisation_requests AS request
  SET status='Approved', approved_by_app_user_id=public.workloop_app_user_id(), approved_at=now(),
    original_clock_in=record_row.clock_in_time, original_clock_out=record_row.clock_out_time,
    version=request.version+1
  WHERE request.id=request_row.id;
  RETURN QUERY SELECT record_row.employee_id, record_row.date, record_row.source_digest, record_row.calculation_version;
END $$;
ALTER FUNCTION public.phase10e_prepare_regularisation_approval(uuid, integer) OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.phase10e_prepare_regularisation_approval(uuid, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.phase10e_prepare_regularisation_approval(uuid, integer) TO workloop_runtime;
""")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER trg_phase10e_attendance_audit_append_only ON public.attendance_audit_log"
    )
    op.execute("DROP FUNCTION public.phase10e_attendance_audit_append_only()")
    op.execute(
        "REVOKE ALL ON FUNCTION public.phase10e_regularisation_limits() FROM workloop_runtime"
    )
    op.execute("DROP FUNCTION public.phase10e_regularisation_limits()")
    op.execute(
        "REVOKE ALL ON FUNCTION public.phase10e_prepare_regularisation_approval(uuid, integer) FROM workloop_runtime"
    )
    op.execute("DROP FUNCTION public.phase10e_prepare_regularisation_approval(uuid, integer)")
    op.execute("""
CREATE OR REPLACE FUNCTION public.phase10c_clock_event_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF session_user = 'workloop_migration' THEN RETURN OLD; END IF;
  RAISE EXCEPTION 'clock events are append-only' USING ERRCODE='42501';
END $$;
""")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10D_REPLAY)
    op.drop_constraint("phase10e_clock_event_supersession", "clock_events", type_="check")
    op.drop_constraint("phase10e_attendance_audit_action", "attendance_audit_log", type_="check")
    op.drop_constraint("phase10e_overtime_approval_evidence", "attendance_records", type_="check")
    op.drop_constraint(
        "phase10e_attendance_resolution_evidence", "attendance_records", type_="check"
    )
    op.drop_index(
        "uq_regularisation_requests_pending_employee_date", table_name="regularisation_requests"
    )
    op.drop_constraint("phase10e_decision_state", "regularisation_requests", type_="check")
    op.create_check_constraint(
        "decision_fields",
        "regularisation_requests",
        "status = 'Pending' OR (approved_by_app_user_id IS NOT NULL AND approved_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "rejection_fields",
        "regularisation_requests",
        "status <> 'Rejected' OR btrim(rejection_reason) <> ''",
    )
    op.drop_constraint("phase10e_regularisation_span", "regularisation_requests", type_="check")
    op.drop_constraint("phase10e_regularisation_reason", "regularisation_requests", type_="check")
    op.drop_constraint("phase10e_regularisation_version", "regularisation_requests", type_="check")
    op.drop_column("attendance_records", "overtime_approval_source_digest")
    op.drop_column("attendance_records", "overtime_approved_at")
    op.drop_column("attendance_records", "resolution_source_digest")
    op.drop_column("attendance_records", "resolved_at")
    op.drop_column("regularisation_requests", "version")
    op.drop_index("uq_clock_events_method_minute", table_name="clock_events")
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
