from sqlalchemy import CheckConstraint

from app.models import Base


def test_phase10d_attendance_record_metadata_matches_the_migration() -> None:
    table = Base.metadata.tables["attendance_records"]
    assert {
        "source_snapshot",
        "source_digest",
        "calculation_version",
        "source_clock_event_ids",
        "evidence_flags",
        "source_stale",
    } <= set(table.c.keys())
    indexes = {str(index.name): index for index in table.indexes if index.name is not None}
    stale = indexes["ix_attendance_records_scope_stale"]
    assert [str(expression) for expression in stale.expressions] == [
        "attendance_records.company_id",
        "attendance_records.branch_id",
        "attendance_records.source_stale",
        "attendance_records.date",
        "attendance_records.employee_id",
    ]
    checks = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_attendance_records_phase10d_attendance_derivation" in checks
