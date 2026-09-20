import uuid
from datetime import date as date_type
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AttendanceSettings(Base):
    __tablename__ = "attendance_settings"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("branch_id", name="uq_attendance_settings_branch_id"),
        CheckConstraint(
            "default_hours_per_day >= 0 AND late_grace_minutes >= 0 "
            "AND early_departure_grace_minutes >= 0 AND max_daily_overtime_hours >= 0 "
            "AND regularisation_max_days_per_month >= 0 AND regularisation_window_days >= 0",
            name="nonnegative",
        ),
        CheckConstraint(
            "cardinality(working_days) > 0 AND cardinality(weekend_days) > 0 "
            "AND cardinality(working_days) + cardinality(weekend_days) = 7 "
            "AND NOT working_days && weekend_days "
            "AND working_days <@ ARRAY['Sun','Mon','Tue','Wed','Thu','Fri','Sat']::text[] "
            "AND weekend_days <@ ARRAY['Sun','Mon','Tue','Wed','Thu','Fri','Sat']::text[] "
            "AND ARRAY['Sun','Mon','Tue','Wed','Thu','Fri','Sat']::text[] "
            "<@ (working_days || weekend_days)",
            name="phase10b_attendance_settings_days",
        ),
        CheckConstraint(
            "default_hours_per_day BETWEEN 0.25 AND 24 "
            "AND late_grace_minutes BETWEEN 0 AND 240 "
            "AND early_departure_grace_minutes BETWEEN 0 AND 240 "
            "AND max_daily_overtime_hours BETWEEN 0 AND 12 "
            "AND regularisation_max_days_per_month BETWEEN 0 AND 31 "
            "AND regularisation_window_days BETWEEN 0 AND 365",
            name="phase10b_attendance_settings_bounds",
        ),
        CheckConstraint(
            "octet_length(biometric_api_key) <= 512 "
            "AND (NOT biometric_api_enabled "
            "OR octet_length(btrim(biometric_api_key)) BETWEEN 16 AND 512)",
            name="phase10b_attendance_settings_secret",
        ),
        CheckConstraint("late_deduction_amount >= 0", name="late_deduction_amount"),
        CheckConstraint(
            "late_deduction_policy IN ('none', 'per_minute', 'per_occurrence')",
            name="late_deduction_policy",
        ),
        Index("ix_attendance_settings_company_id_branch_id", "company_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    working_days: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default=text("ARRAY['Sun','Mon','Tue','Wed','Thu']")
    )
    weekend_days: Mapped[list[str]] = mapped_column(
        ARRAY(Text()), nullable=False, server_default=text("ARRAY['Fri', 'Sat']")
    )
    default_hours_per_day: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default=text("8")
    )
    late_grace_minutes: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("10")
    )
    early_departure_grace_minutes: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("10")
    )
    overtime_requires_approval: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("true")
    )
    max_daily_overtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default=text("2")
    )
    late_deduction_policy: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'none'")
    )
    late_deduction_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    wfh_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    regularisation_max_days_per_month: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("2")
    )
    regularisation_window_days: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("7")
    )
    biometric_api_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    biometric_api_key: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("''")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "company_id", "branch_id", name="uq_shifts_id_company_id_branch_id"),
        UniqueConstraint("branch_id", "name", name="uq_shifts_branch_id_name"),
        CheckConstraint(
            "break_minutes >= 0 AND expected_hours >= 0 AND late_grace_minutes >= 0 "
            "AND early_departure_grace_minutes >= 0 "
            "AND (min_hours_flexible IS NULL OR min_hours_flexible >= 0) "
            "AND min_staff >= 0",
            name="nonnegative",
        ),
        CheckConstraint(
            "octet_length(btrim(name)) BETWEEN 1 AND 80 "
            "AND color ~ '^#[0-9A-F]{6}$' "
            "AND (code IS NULL OR code ~ '^[A-Z0-9]([A-Z0-9-]{0,10}[A-Z0-9])?$')",
            name="phase10b_shifts_text",
        ),
        CheckConstraint(
            "break_minutes BETWEEN 0 AND 240 AND expected_hours BETWEEN 0.25 AND 24 "
            "AND late_grace_minutes BETWEEN 0 AND 240 "
            "AND early_departure_grace_minutes BETWEEN 0 AND 240 "
            "AND (min_hours_flexible IS NULL "
            "OR min_hours_flexible BETWEEN 0.25 AND expected_hours) "
            "AND min_staff BETWEEN 0 AND 999",
            name="phase10b_shifts_bounds",
        ),
        CheckConstraint(
            "(shift_type='fixed' AND start_time IS NOT NULL AND end_time IS NOT NULL "
            "AND start_time < end_time AND NOT is_overnight "
            "AND split_start_time IS NULL AND split_end_time IS NULL "
            "AND min_hours_flexible IS NULL "
            "AND shift_category IN ('morning','afternoon','night')) "
            "OR (shift_type='overnight' AND start_time IS NOT NULL AND end_time IS NOT NULL "
            "AND end_time <= start_time AND is_overnight "
            "AND split_start_time IS NULL AND split_end_time IS NULL "
            "AND min_hours_flexible IS NULL AND shift_category='night') "
            "OR (shift_type='split' AND start_time IS NOT NULL AND end_time IS NOT NULL "
            "AND split_start_time IS NOT NULL AND split_end_time IS NOT NULL "
            "AND start_time < end_time AND end_time <= split_start_time "
            "AND split_start_time < split_end_time AND NOT is_overnight "
            "AND min_hours_flexible IS NULL AND shift_category='split') "
            "OR (shift_type='flexible' AND start_time IS NULL AND end_time IS NULL "
            "AND split_start_time IS NULL AND split_end_time IS NULL "
            "AND NOT is_overnight AND break_minutes=0 "
            "AND min_hours_flexible IS NOT NULL AND shift_category='flexible')",
            name="phase10b_shifts_shape",
        ),
        CheckConstraint(
            "shift_type IN ('fixed', 'flexible', 'split', 'overnight')", name="shift_type"
        ),
        CheckConstraint(
            "shift_category IN ('morning', 'afternoon', 'night', 'flexible', 'split')",
            name="shift_category",
        ),
        Index("ix_shifts_branch_id_active", "branch_id", "is_active"),
        Index(
            "uq_shifts_branch_id_code_nonempty",
            "branch_id",
            "code",
            unique=True,
            postgresql_where=text("code IS NOT NULL AND btrim(code) <> ''"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text(), nullable=False)
    shift_type: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'fixed'"))
    start_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    break_minutes: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("60"))
    expected_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default=text("8")
    )
    late_grace_minutes: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("10")
    )
    early_departure_grace_minutes: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("10")
    )
    split_start_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    split_end_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    is_overnight: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    min_hours_flexible: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("true"))
    color: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'#6366F1'"))
    code: Mapped[str | None] = mapped_column(Text(), nullable=True)
    shift_category: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'morning'")
    )
    min_staff: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shift_id", "company_id", "branch_id"],
            ["shifts.id", "shifts.company_id", "shifts.branch_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="dates"),
        ExcludeConstraint(
            ("company_id", "="),
            ("branch_id", "="),
            ("employee_id", "="),
            (text("daterange(effective_from, effective_to, '[]')"), "&&"),
            name="shift_assignments_no_overlap",
            using="gist",
        ),
        Index(
            "ix_shift_assignments_employee_id_effective_from",
            "employee_id",
            text("effective_from DESC"),
        ),
        Index(
            "ix_shift_assignments_scope_employee_effective",
            "company_id",
            "branch_id",
            "employee_id",
            text("effective_from DESC"),
            "id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    effective_from: Mapped[date_type] = mapped_column(Date(), nullable=False)
    effective_to: Mapped[date_type | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RegularisationRequest(Base):
    __tablename__ = "regularisation_requests"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["approved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "id",
            "company_id",
            "branch_id",
            name="uq_regularisation_requests_id_company_id_branch_id",
        ),
        UniqueConstraint(
            "id",
            "employee_id",
            "company_id",
            "branch_id",
            name="uq_regularisation_requests_id_employee_id_company_id_branch_id",
        ),
        CheckConstraint("correct_clock_out > correct_clock_in", name="clock_order"),
        CheckConstraint("status IN ('Pending', 'Approved', 'Rejected')", name="status"),
        CheckConstraint(
            "status = 'Pending' OR (approved_by_app_user_id IS NOT NULL "
            "AND approved_at IS NOT NULL)",
            name="decision_fields",
        ),
        CheckConstraint(
            "status <> 'Rejected' OR btrim(rejection_reason) <> ''", name="rejection_fields"
        ),
        Index(
            "ix_regularisation_requests_employee_id_attendance_date",
            "employee_id",
            "attendance_date",
        ),
        Index("ix_regularisation_requests_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attendance_date: Mapped[date_type] = mapped_column(Date(), nullable=False)
    correct_clock_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correct_clock_out: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'Pending'"))
    approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    original_clock_in: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    original_clock_out: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ClockEvent(Base):
    __tablename__ = "clock_events"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["entered_by_app_user_id"], ["app_users.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(
            ["superseded_by", "employee_id", "company_id", "branch_id"],
            [
                "regularisation_requests.id",
                "regularisation_requests.employee_id",
                "regularisation_requests.company_id",
                "regularisation_requests.branch_id",
            ],
            name="fk_clock_events_superseded_by_regularisation_requests",
            ondelete="SET NULL (superseded_by)",
        ),
        CheckConstraint("event_type IN ('CLOCK_IN', 'CLOCK_OUT')", name="event_type"),
        CheckConstraint(
            "method IN ('WEB', 'MOBILE', 'MANUAL', 'BIOMETRIC', 'EMPLOYEE_APP')", name="method"
        ),
        CheckConstraint("gps_lat IS NULL OR gps_lat BETWEEN -90 AND 90", name="latitude"),
        CheckConstraint("gps_lng IS NULL OR gps_lng BETWEEN -180 AND 180", name="longitude"),
        UniqueConstraint("id", "company_id", "branch_id", name="uq_clock_events_id_scope"),
        Index("ix_clock_events_employee_id_event_time", "employee_id", "event_time"),
        Index("ix_clock_events_event_time", "event_time"),
        Index("ix_clock_events_branch_id", "branch_id"),
        Index(
            "uq_clock_events_fingerprint",
            "company_id",
            "branch_id",
            "event_fingerprint",
            unique=True,
            postgresql_where=text("event_fingerprint IS NOT NULL"),
        ),
        Index(
            "uq_clock_events_method_minute",
            "employee_id",
            "event_type",
            "method",
            text("date_trunc('minute'::text, (event_time AT TIME ZONE 'UTC'::text))"),
            unique=True,
            postgresql_where=text("method = ANY (ARRAY['MANUAL'::text, 'BIOMETRIC'::text])"),
        ),
        Index(
            "ix_clock_events_scope_employee_time",
            "company_id",
            "branch_id",
            "employee_id",
            text("event_time DESC"),
            "id",
        ),
        ForeignKeyConstraint(
            ["import_batch_id", "company_id", "branch_id"],
            [
                "attendance_import_batches.id",
                "attendance_import_batches.company_id",
                "attendance_import_batches.branch_id",
            ],
            name="fk_clock_events_import_batch_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "(import_batch_id IS NULL AND import_row_number IS NULL AND source_badge_no IS NULL "
            "AND source_device_name IS NULL AND event_fingerprint IS NULL) OR "
            "(method='BIOMETRIC' AND import_batch_id IS NOT NULL AND import_row_number IS NOT NULL "
            "AND source_badge_no IS NOT NULL AND source_device_name IS NOT NULL "
            "AND event_fingerprint IS NOT NULL)",
            name="phase10c_clock_event_provenance",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text(), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'WEB'"))
    ip_address: Mapped[str | None] = mapped_column(Text(), nullable=True)
    gps_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    gps_lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    entered_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    is_superseded: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    event_fingerprint: Mapped[str | None] = mapped_column(Text(), nullable=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    import_row_number: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    source_badge_no: Mapped[str | None] = mapped_column(Text(), nullable=True)
    source_device_name: Mapped[str | None] = mapped_column(Text(), nullable=True)


class AttendanceImportBatch(Base):
    __tablename__ = "attendance_import_batches"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"], ["branches.id", "branches.company_id"], ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(["submitted_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint(
            "company_id",
            "branch_id",
            "batch_fingerprint",
            name="uq_attendance_import_batches_scope_fingerprint",
        ),
        UniqueConstraint(
            "id", "company_id", "branch_id", name="uq_attendance_import_batches_id_scope"
        ),
        CheckConstraint("row_count BETWEEN 1 AND 5000", name="row_count"),
        CheckConstraint("byte_count BETWEEN 1 AND 2097152", name="byte_count"),
        Index(
            "ix_attendance_import_batches_scope_created",
            "company_id",
            "branch_id",
            text("created_at DESC"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    submitted_by_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    batch_fingerprint: Mapped[str] = mapped_column(Text(), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    byte_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AttendanceImportRowOutcome(Base):
    __tablename__ = "attendance_import_row_outcomes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "company_id", "branch_id"],
            [
                "attendance_import_batches.id",
                "attendance_import_batches.company_id",
                "attendance_import_batches.branch_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["clock_event_id", "company_id", "branch_id"],
            ["clock_events.id", "clock_events.company_id", "clock_events.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "batch_id", "row_number", name="uq_attendance_import_row_outcomes_batch_row"
        ),
        CheckConstraint("row_number >= 1", name="row_number"),
        CheckConstraint(
            "outcome IN ('accepted','duplicate','unknown_badge','invalid')", name="outcome"
        ),
        CheckConstraint(
            "(outcome='accepted') = (clock_event_id IS NOT NULL)", name="event_for_accepted_only"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    outcome: Mapped[str] = mapped_column(Text(), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(Text(), nullable=True)
    clock_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shift_id", "company_id", "branch_id"],
            ["shifts.id", "shifts.company_id", "shifts.branch_id"],
            ondelete="SET NULL (shift_id)",
        ),
        ForeignKeyConstraint(
            ["overtime_approved_by_app_user_id"],
            ["app_users.id"],
            name="fk_attendance_records_ot_approved_by_app_users",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["resolved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint("employee_id", "date", name="uq_attendance_records_employee_id_date"),
        CheckConstraint(
            "status IN ('PRESENT', 'ABSENT', 'ON_LEAVE', 'PUBLIC_HOLIDAY', 'WEEKEND', 'LATE', "
            "'EARLY_DEPARTURE', 'HALF_DAY', 'OVERTIME', 'UNEXPLAINED_ABSENCE', 'PRESENT_REMOTE', "
            "'MISSING_CLOCK_OUT')",
            name="status",
        ),
        CheckConstraint(
            "resolution_type IN ('', 'LEAVE_LINKED', 'UNAUTHORISED', 'WFH')",
            name="resolution_type",
        ),
        CheckConstraint(
            "overtime_type IS NULL OR overtime_type IN ('STANDARD', 'REST_DAY_NO_SUB', "
            "'REST_DAY_WITH_SUB', 'NIGHT_SHIFT')",
            name="overtime_type",
        ),
        CheckConstraint(
            "total_hours >= 0 AND late_minutes >= 0 AND early_departure_minutes >= 0 "
            "AND overtime_hours >= 0",
            name="nonnegative",
        ),
        CheckConstraint("overtime_amount >= 0", name="overtime_amount"),
        CheckConstraint("absence_deduction >= 0", name="absence_deduction"),
        CheckConstraint("late_deduction >= 0", name="late_deduction"),
        CheckConstraint(
            "NOT overtime_approved OR overtime_approved_by_app_user_id IS NOT NULL",
            name="overtime_actor",
        ),
        CheckConstraint(
            "resolution_type = '' OR resolved_by_app_user_id IS NOT NULL", name="resolution_actor"
        ),
        Index("ix_attendance_records_employee_id_date", "employee_id", "date"),
        Index("ix_attendance_records_branch_id_date", "branch_id", "date"),
        Index("ix_attendance_records_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date: Mapped[date_type] = mapped_column(Date(), nullable=False)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    clock_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clock_out_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'ABSENT'"))
    late_minutes: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    early_departure_minutes: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default=text("0")
    )
    overtime_hours: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    overtime_type: Mapped[str | None] = mapped_column(Text(), nullable=True)
    overtime_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    overtime_approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    overtime_approved: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    worked_on_rest_day: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    rest_day_substitute: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    missing_clock_out: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    is_ramadan_day: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    absence_deduction: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    late_deduction: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    period_closed: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    resolved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    resolution_type: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    resolution_notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AttendancePeriod(Base):
    __tablename__ = "attendance_periods"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["closed_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        UniqueConstraint("branch_id", "period", name="uq_attendance_periods_branch_id_period"),
        CheckConstraint("status IN ('open', 'closed')", name="status"),
        CheckConstraint("open_items >= 0", name="open_items"),
        CheckConstraint(
            "status <> 'closed' OR (closed_by_app_user_id IS NOT NULL AND closed_at IS NOT NULL)",
            name="closed_fields",
        ),
        Index("ix_attendance_periods_branch_id_period", "branch_id", "period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    period: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'open'"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    payroll_ready: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default=text("false")
    )
    open_items: Mapped[int] = mapped_column(Integer(), nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class AttendanceAuditLog(Base):
    __tablename__ = "attendance_audit_log"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(["actor_app_user_id"], ["app_users.id"], ondelete="RESTRICT"),
        Index("ix_attendance_audit_log_employee_id_date", "employee_id", "attendance_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    attendance_date: Mapped[date_type | None] = mapped_column(Date(), nullable=True)
    action: Mapped[str] = mapped_column(Text(), nullable=False)
    actor_app_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    old_value: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    new_value: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RosterAssignment(Base):
    __tablename__ = "roster_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["shift_id", "company_id", "branch_id"],
            ["shifts.id", "shifts.company_id", "shifts.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("employee_id", "date", name="uq_roster_assignments_employee_id_date"),
        CheckConstraint(
            "(planned_hours IS NULL OR planned_hours >= 0) "
            "AND (actual_hours IS NULL OR actual_hours >= 0) AND co_hours >= 0",
            name="hours",
        ),
        Index("ix_roster_assignments_employee_id", "employee_id"),
        Index("ix_roster_assignments_date", "date"),
        Index("ix_roster_assignments_branch_id", "branch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    date: Mapped[date_type] = mapped_column(Date(), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("false"))
    notes: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    planned_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    co_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ShiftSwapRequest(Base):
    __tablename__ = "shift_swap_requests"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requester_employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_shift_swap_requests_requester_employee_id_employees",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["target_employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            name="fk_shift_swap_requests_target_employee_id_employees",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["admin_approved_by_app_user_id"], ["app_users.id"], ondelete="RESTRICT"
        ),
        CheckConstraint("requester_employee_id <> target_employee_id", name="distinct_employees"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')", name="status"
        ),
        CheckConstraint(
            "status <> 'approved' OR (admin_approved_by_app_user_id IS NOT NULL "
            "AND admin_approved_at IS NOT NULL)",
            name="approved_fields",
        ),
        CheckConstraint(
            "status <> 'rejected' OR (admin_approved_by_app_user_id IS NOT NULL "
            "AND admin_approved_at IS NOT NULL AND btrim(rejection_reason) <> '')",
            name="rejected_fields",
        ),
        Index("ix_shift_swap_requests_branch_id", "branch_id"),
        Index("ix_shift_swap_requests_status", "status"),
        Index("ix_shift_swap_requests_requester_employee_id", "requester_employee_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requester_employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requester_date: Mapped[date_type] = mapped_column(Date(), nullable=False)
    target_date: Mapped[date_type | None] = mapped_column(Date(), nullable=True)
    reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("'pending'"))
    admin_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    admin_approved_by_app_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    rejection_reason: Mapped[str] = mapped_column(Text(), nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class BiometricMapping(Base):
    __tablename__ = "biometric_mappings"
    __table_args__ = (
        ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("branch_id", "badge_no", name="uq_biometric_mappings_branch_id_badge_no"),
        Index("ix_biometric_mappings_employee_id", "employee_id"),
        Index(
            "ix_biometric_mappings_scope_badge",
            "company_id",
            "branch_id",
            "badge_no",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    badge_no: Mapped[str] = mapped_column(Text(), nullable=False)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    device_name: Mapped[str] = mapped_column(
        Text(), nullable=False, server_default=text("'Default'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
