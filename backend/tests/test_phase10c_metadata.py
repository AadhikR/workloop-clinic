from sqlalchemy import CheckConstraint

from app.models import Base


def test_phase10c_clock_event_metadata_matches_the_migration() -> None:
    table = Base.metadata.tables["clock_events"]
    indexes = {index.name: index for index in table.indexes}

    assert {
        "ix_clock_events_scope_employee_time",
        "uq_clock_events_fingerprint",
        "uq_clock_events_method_minute",
    } <= indexes.keys()
    assert indexes["uq_clock_events_fingerprint"].unique
    assert (
        str(indexes["uq_clock_events_fingerprint"].dialect_options["postgresql"]["where"])
        == "event_fingerprint IS NOT NULL"
    )
    assert indexes["uq_clock_events_method_minute"].unique
    assert str(indexes["uq_clock_events_method_minute"].expressions[-1]) == (
        "date_trunc('minute'::text, (event_time AT TIME ZONE 'UTC'::text))"
    )
    assert (
        str(indexes["uq_clock_events_method_minute"].dialect_options["postgresql"]["where"])
        == "method = ANY (ARRAY['MANUAL'::text, 'BIOMETRIC'::text])"
    )
    assert str(indexes["ix_clock_events_scope_employee_time"].expressions[-2]) == (
        "event_time DESC"
    )

    check_names = {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_clock_events_phase10c_clock_event_provenance" in check_names


def test_phase10c_biometric_mapping_metadata_matches_the_migration() -> None:
    table = Base.metadata.tables["biometric_mappings"]
    index = next(
        index for index in table.indexes if index.name == "ix_biometric_mappings_scope_badge"
    )

    assert [expression.name for expression in index.expressions] == [
        "company_id",
        "branch_id",
        "badge_no",
    ]
