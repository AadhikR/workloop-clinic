"""Static guarantees for the Phase 4E synthetic fixtures.

These need no database. They prove the manifest is deterministic, references only
real columns, keeps managers ahead of their reports, carries the golden financial
values, and holds no real personal data or credentials.
"""

from collections import Counter

import app.models  # noqa: F401  # register every table on Base.metadata
from app.db.base import Base
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows

EXPECTED_COUNTS = {
    "companies": 2,
    "branches": 4,
    "app_users": 15,
    "employees": 15,
    "user_profiles": 15,
    "departments": 6,
    "department_staffing_rules": 3,
    "shifts": 5,
    "payroll_runs": 4,
    "payroll_entries": 1,
    "salary_advances": 6,
    "advance_repayments": 1,
    "expense_claims": 1,
    "roster_assignments": 1,
}


def test_manifest_is_deterministic() -> None:
    first = [(r.table, r.conflict, tuple(sorted(map(str, r.values.items())))) for r in build_rows()]
    second = [
        (r.table, r.conflict, tuple(sorted(map(str, r.values.items())))) for r in build_rows()
    ]
    assert first == second


def test_no_duplicate_primary_keys() -> None:
    seen: set[tuple[str, tuple[object, ...]]] = set()
    for row in build_rows():
        pk = (row.table, tuple(row.values[k] for k in row.conflict))
        assert pk not in seen, f"duplicate {pk}"
        seen.add(pk)


def test_every_value_targets_a_real_column() -> None:
    tables = Base.metadata.tables
    for row in build_rows():
        assert row.table in tables, f"unknown table {row.table}"
        columns = set(tables[row.table].columns.keys())
        unknown = set(row.values) - columns
        assert not unknown, f"{row.table} has unknown columns {unknown}"


def test_per_table_counts() -> None:
    assert Counter(row.table for row in build_rows()) == Counter(EXPECTED_COUNTS)


def test_managers_precede_their_reports() -> None:
    seen_employees: set[object] = set()
    for row in build_rows():
        if row.table != "employees":
            continue
        manager = row.values.get("reporting_manager_id")
        if manager is not None:
            assert manager in seen_employees, f"{row.values['emp_no']} precedes its manager"
        seen_employees.add(row.values["id"])


def test_identifier_formats_match_phase0_example() -> None:
    # H-DXB-002 is sequence 2; Phase 0 pins its exact identifiers.
    ids = c.identifiers(2)
    assert ids["mol_id"] == "90000000000002"
    assert ids["iban"] == "AE000000000000000000002"
    assert ids["emirates_id"] == "784-1990-0000000-2"
    assert ids["visa_number"] == "999/2026/0000002"
    assert ids["passport_number"] == "TESTP000002"
    assert ids["labour_card_number"] == "TESTLC000002"
    assert ids["phone"] == "+971500000002"


def test_golden_payroll_entry_values() -> None:
    entries = [r for r in build_rows() if r.table == "payroll_entries"]
    assert len(entries) == 1
    entry = entries[0].values
    assert str(entry["leave_deduction"]) == "400.00"
    assert str(entry["variable_allowance"]) == "5238.46"
    labels = {item["label"] for item in entry["additional_allowances"]}
    assert labels == {"Expense Reimbursement", "Overtime (Roster)"}


def test_identities_are_inert_and_active() -> None:
    rows = build_rows()
    app_users = [r for r in rows if r.table == "app_users"]
    assert all(r.values["identity_issuer"] == c.SEED_ISSUER for r in app_users)
    assert all(r.values["status"] == "active" for r in app_users)
    # A synthetic issuer that is not the live Keycloak issuer keeps seeded rows
    # from ever resolving against a real token.
    assert "keycloak" not in c.SEED_ISSUER and ":8080" not in c.SEED_ISSUER


def test_profiles_respect_the_role_link_rule() -> None:
    for row in build_rows():
        if row.table != "user_profiles":
            continue
        if row.values["role"] == "admin":
            assert row.values["employee_id"] is None
        else:
            assert row.values["employee_id"] is not None


def test_no_real_personal_data_or_credentials() -> None:
    for row in build_rows():
        for key, value in row.values.items():
            if not isinstance(value, str):
                continue
            assert "password" not in key.lower()
            if "email" in key:
                assert value.endswith(".test"), f"{row.table}.{key}={value} is not a .test email"
