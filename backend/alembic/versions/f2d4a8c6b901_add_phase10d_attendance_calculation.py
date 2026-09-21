"""Add Phase 10D attendance derivation evidence.

Revision ID: f2d4a8c6b901
Revises: b7d9e1f3a5c6
Created: 2026-09-20 11:00:00.000000
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f2d4a8c6b901"
down_revision: str | Sequence[str] | None = "b7d9e1f3a5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE10D_REPLAY = """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch','attendance_record') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL"""


def upgrade() -> None:
    op.add_column(
        "attendance_records",
        sa.Column(
            "source_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("jsonb_build_object('legacy', true)"),
        ),
    )
    op.add_column(
        "attendance_records",
        sa.Column(
            "source_digest",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'legacy-unverified'"),
        ),
    )
    op.add_column(
        "attendance_records",
        sa.Column("calculation_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "attendance_records",
        sa.Column(
            "source_clock_event_ids",
            sa.ARRAY(sa.UUID()),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
    )
    op.add_column(
        "attendance_records",
        sa.Column(
            "evidence_flags",
            sa.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )
    op.add_column(
        "attendance_records",
        sa.Column("source_stale", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.execute("""
UPDATE public.attendance_records
SET source_snapshot = jsonb_build_object('legacyRecordId', id::text, 'migration', 'phase10d'),
    source_digest = 'legacy-unverified:' || id::text,
    source_stale = true
WHERE source_digest = 'legacy-unverified'
""")
    op.create_check_constraint(
        "phase10d_attendance_derivation",
        "attendance_records",
        "calculation_version >= 1 AND btrim(source_digest) <> '' AND jsonb_typeof(source_snapshot) = 'object'",
    )
    op.create_index(
        "ix_attendance_records_scope_stale",
        "attendance_records",
        ["company_id", "branch_id", "source_stale", "date", "employee_id"],
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint("replay_resource", "idempotency_records", PHASE10D_REPLAY)
    op.execute("""
CREATE FUNCTION public.phase10d_mark_attendance_stale() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE attendance_day date;
BEGIN
  attendance_day := (NEW.event_time AT TIME ZONE 'Asia/Dubai')::date;
  UPDATE public.attendance_records
  SET source_stale = true, updated_at = now()
  WHERE company_id=NEW.company_id AND branch_id=NEW.branch_id AND employee_id=NEW.employee_id
    AND date IN (attendance_day, attendance_day - 1) AND NOT period_closed AND NOT source_stale;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_phase10d_clock_events_stale AFTER INSERT ON public.clock_events
FOR EACH ROW EXECUTE FUNCTION public.phase10d_mark_attendance_stale();
""")


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_phase10d_clock_events_stale ON public.clock_events")
    op.execute("DROP FUNCTION public.phase10d_mark_attendance_stale()")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        """(replay_resource_kind IN ('branch','employee','department','user_profile','leave_request','expense_claim','salary_advance','payroll_run','compliance_override','nafis_snapshot','attendance_settings','shift','shift_assignment','clock_event','biometric_mapping','attendance_import_batch') AND replay_resource_id IS NOT NULL) OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) OR replay_resource_kind IS NULL""",
    )
    op.drop_index("ix_attendance_records_scope_stale", table_name="attendance_records")
    op.drop_constraint("phase10d_attendance_derivation", "attendance_records", type_="check")
    op.drop_column("attendance_records", "source_stale")
    op.drop_column("attendance_records", "evidence_flags")
    op.drop_column("attendance_records", "source_clock_event_ids")
    op.drop_column("attendance_records", "calculation_version")
    op.drop_column("attendance_records", "source_digest")
    op.drop_column("attendance_records", "source_snapshot")
