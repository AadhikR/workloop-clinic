"""Static guarantees for the Phase 4E synthetic fixtures.

These need no database. They prove the manifest is deterministic, references only
real columns, keeps managers ahead of their reports, carries the golden financial
values, and holds no real personal data or credentials.
"""

import importlib
from collections import Counter
from decimal import Decimal
from pathlib import Path

from app.db.base import Base
from app.db.seed import constants as c
from app.db.seed.fixtures import (
    NEGATIVE_CONTROL_MATRIX,
    NON_PERSISTED_SCENARIOS,
    RETIRED_OR_REPLACED_SCENARIOS,
    build_rows,
)

importlib.import_module("app.models")

EXPECTED_COUNTS = {
    "advance_repayments": 1,
    "appraisal_cycles": 5,
    "appraisal_sections": 9,
    "appraisals": 8,
    "companies": 2,
    "branches": 4,
    "app_users": 15,
    "asset_assignments": 2,
    "assets": 6,
    "attendance_periods": 2,
    "attendance_records": 13,
    "attendance_settings": 4,
    "biometric_mappings": 1,
    "certifications": 8,
    "clock_events": 6,
    "cme_requirements": 4,
    "department_staffing_rules": 3,
    "departments": 6,
    "employee_contracts": 4,
    "employee_documents": 9,
    "employee_insurance": 1,
    "employees": 15,
    "expense_claims": 7,
    "incident_reports": 9,
    "insurance_dependants": 1,
    "insurance_policies": 1,
    "leave_approval_delegates": 2,
    "leave_balances": 3,
    "leave_requests": 12,
    "leave_settings": 4,
    "leave_types": 36,
    "letter_requests": 6,
    "notifications": 12,
    "offboarding_checklists": 4,
    "offboarding_task_templates": 16,
    "offboarding_tasks": 5,
    "payroll_approval_log": 4,
    "payroll_entries": 8,
    "payroll_runs": 16,
    "payslips": 1,
    "public_holidays": 4,
    "regularisation_requests": 3,
    "roster_assignments": 9,
    "salary_advances": 7,
    "shift_swap_requests": 3,
    "shifts": 8,
    "training_records": 10,
    "user_profiles": 15,
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
    assert len(build_rows()) == 334
    assert len(EXPECTED_COUNTS) == 48


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
    entries = [
        r
        for r in build_rows()
        if r.table == "payroll_entries" and r.values.get("leave_deduction") == Decimal("400.00")
    ]
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


def _values(table: str) -> list[dict[str, object]]:
    return [row.values for row in build_rows() if row.table == table]


def test_leave_catalogue_coverage_is_exact() -> None:
    assert {row["status"] for row in _values("leave_requests")} == {
        "Pending",
        "ManagerApproved",
        "ManagerRejected",
        "Approved",
        "Rejected",
        "Cancelled",
    }
    assert {row["code"] for row in _values("leave_types")} == {
        "ANNUAL",
        "SICK",
        "MATERNITY",
        "PATERNITY",
        "BEREAVEMENT",
        "STUDY",
        "HAJJ",
        "UNPAID",
        "CUSTOM_COMPASSIONATE",
    }
    assert Counter(row["code"] for row in _values("leave_types")) == Counter(
        {
            code: 4
            for code in {
                "ANNUAL",
                "SICK",
                "MATERNITY",
                "PATERNITY",
                "BEREAVEMENT",
                "STUDY",
                "HAJJ",
                "UNPAID",
                "CUSTOM_COMPASSIONATE",
            }
        }
    )
    sick = next(row for row in _values("leave_balances") if row["sick_full_pay_used"])
    assert sick["used_days"] == Decimal("50")
    assert sick["sick_full_pay_used"] == Decimal("15")
    assert sick["sick_half_pay_used"] == Decimal("30")
    assert sick["sick_unpaid_used"] == Decimal("5")


def test_attendance_and_roster_catalogue_coverage_is_exact() -> None:
    attendance = _values("attendance_records")
    assert {row["status"] for row in attendance} == {
        "PRESENT",
        "ABSENT",
        "ON_LEAVE",
        "PUBLIC_HOLIDAY",
        "WEEKEND",
        "LATE",
        "EARLY_DEPARTURE",
        "HALF_DAY",
        "OVERTIME",
        "UNEXPLAINED_ABSENCE",
        "PRESENT_REMOTE",
        "MISSING_CLOCK_OUT",
    }
    assert Counter(row["status"] for row in attendance)["OVERTIME"] == 2
    assert {row.get("resolution_type", "") for row in attendance} >= {
        "UNAUTHORISED",
        "LEAVE_LINKED",
        "WFH",
    }
    assert {row["status"] for row in _values("regularisation_requests")} == {
        "Pending",
        "Approved",
        "Rejected",
    }
    assert {row["status"] for row in _values("shift_swap_requests")} == {
        "pending",
        "approved",
        "rejected",
    }
    assert {row["method"] for row in _values("clock_events")} == {"WEB", "MANUAL", "BIOMETRIC"}
    assert len({row["branch_id"] for row in _values("roster_assignments")}) == 4


def test_financial_status_and_branch_coverage_is_exact() -> None:
    runs = _values("payroll_runs")
    assert Counter(row["period"] for row in runs) == Counter(
        {"2026-05": 4, "2026-06": 4, "2026-07": 4, "2026-08": 4}
    )
    assert len({row["branch_id"] for row in runs}) == 4
    assert {row["status"] for row in runs} == {"draft", "generated"}
    assert {row["approval_status"] for row in runs} == {
        "draft",
        "pending_approval",
        "approved",
    }
    assert {row["wps_status"] for row in runs} == {
        "draft",
        "confirmed",
        "partial_rejection",
    }
    entries = _values("payroll_entries")
    assert {row["wps_payment_status"] for row in entries} == {"pending", "paid", "rejected"}
    assert any(row.get("excluded") is True for row in entries)
    assert any(row.get("variable_allowance") == Decimal("-50.00") for row in entries)
    assert {row["action"] for row in _values("payroll_approval_log")} == {
        "submitted",
        "recalled",
        "approved",
        "rejected",
    }
    assert {row["status"] for row in _values("expense_claims")} == {
        "pending",
        "manager_approved",
        "manager_rejected",
        "approved",
        "paid",
        "rejected",
    }


def test_document_certification_and_notification_coverage_is_exact() -> None:
    documents = _values("employee_documents")
    certifications = _values("certifications")
    assert {row["status"] for row in documents} == {
        "pending_verification",
        "verified",
        "rejected",
    }
    assert {row["status"] for row in certifications} == {
        "pending_review",
        "verified",
        "rejected",
    }
    expiry_values = {row.get("expiry_date") for row in documents + certifications}
    assert expiry_values >= {
        None,
        "2026-08-26",
        "2026-09-03",
        "2026-09-10",
        "2026-09-26",
        "2026-10-26",
        "2026-11-25",
        "2028-01-01",
    }
    notifications = _values("notifications")
    assert {row["type"] for row in notifications} == {
        "document_expiry",
        "clinical_credential_expiry",
        "insurance_expiry",
        "probation_ending",
        "contract_expiry",
        "cert_expiry",
        "clinical_licence_expiry",
        "policy_renewal",
        "leave_approved",
        "leave_rejected",
        "payslip_available",
        "roster_published",
    }
    assert {row["read_at"] is None for row in notifications} == {True, False}


def test_training_cme_and_appraisal_coverage_is_exact() -> None:
    training = _values("training_records")
    assert {row["status"] for row in training} == {
        "planned",
        "in_progress",
        "completed",
        "cancelled",
    }
    assert {row["training_type"] for row in training} == {
        "internal",
        "external",
        "online",
        "conference",
    }
    completed = [row for row in training if row["status"] == "completed"]
    assert {row["passed"] for row in completed} == {True, False}
    cme: dict[tuple[object, str], Decimal] = {}
    for row in training:
        if row.get("is_cme"):
            year = str(row["start_date"])[:4]
            hours = row["duration_hours"]
            assert isinstance(hours, Decimal)
            key = (row["employee_id"], year)
            cme[key] = cme.get(key, Decimal("0")) + hours
    assert sorted(cme.values()) == [
        Decimal("8.00"),
        Decimal("12.00"),
        Decimal("25.00"),
        Decimal("30.00"),
    ]
    assert {row["status"] for row in _values("appraisal_cycles")} == {
        "draft",
        "active",
        "closed",
    }
    assert {row["status"] for row in _values("appraisals")} == {
        "pending",
        "reviewed",
        "calibrated",
    }
    golden = [row for row in _values("appraisal_sections") if row.get("rating") is not None]
    weighted_sum = Decimal("0")
    total_weight = Decimal("0")
    for row in golden[:5]:
        rating = row["rating"]
        weight = row["weight"]
        assert isinstance(rating, Decimal)
        assert isinstance(weight, Decimal)
        weighted_sum += rating * weight
        total_weight += weight
    assert weighted_sum == Decimal("28.5")
    assert weighted_sum / total_weight == Decimal("3.8")


def test_people_operations_coverage_is_exact() -> None:
    assert {row["status"] for row in _values("assets")} == {
        "available",
        "assigned",
        "under_repair",
        "retired",
        "lost",
    }
    incidents = _values("incident_reports")
    assert {row["incident_type"] for row in incidents} == {
        "patient_safety",
        "medication_error",
        "injury",
        "needlestick",
        "infection",
        "equipment",
        "near_miss",
        "workplace",
        "other",
    }
    assert {row["severity"] for row in incidents} == {"low", "moderate", "high", "critical"}
    assert {row["status"] for row in incidents} == {"open", "investigating", "closed"}
    assert len({row["branch_id"] for row in incidents}) == 4
    assert {row["action"] for row in _values("employee_contracts")} == {
        "new",
        "renewed",
        "converted",
        "not_renewed",
    }
    assert {row["status"] for row in _values("offboarding_checklists")} == {
        "in_progress",
        "completed",
    }
    assert {row["visa_cancellation_status"] for row in _values("offboarding_checklists")} == {
        "not_started",
        "initiated",
        "submitted_gdrfa",
        "cancelled",
    }
    requests = _values("letter_requests")
    assert {row["status"] for row in requests} == {"pending", "completed", "rejected"}
    assert {row["request_kind"] for row in requests} == {"letter", "custom"}
    assert {row["letter_type"] for row in requests} >= {
        "salary_certificate_bank",
        "salary_certificate_embassy",
        "noc",
        "salary_transfer_letter",
        "employment_confirmation",
    }


def test_cross_scope_controls_have_distinct_tenant_and_branch_rows() -> None:
    for table in ("employees", "roster_assignments", "incident_reports", "assets"):
        rows = _values(table)
        assert {row["company_id"] for row in rows} == set(c.COMPANY_ID.values())
        assert len({row["branch_id"] for row in rows}) == 4


def test_seed_and_migrations_have_no_supabase_database_dependency() -> None:
    root = Path(__file__).resolve().parents[2]
    paths = list((root / "app" / "db" / "seed").glob("*.py"))
    paths += list((root / "alembic" / "versions").glob("*.py"))
    forbidden = (
        "auth.users",
        "auth.uid",
        "auth.email",
        "auth.role",
        "storage.objects",
        "storage.foldername",
        "service_role",
        "authenticated role",
        "anon role",
    )
    corpus = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    for marker in forbidden:
        assert marker not in corpus


def test_non_persisted_and_replaced_phase0_cases_are_explicit() -> None:
    assert len(NON_PERSISTED_SCENARIOS) == 26
    assert len(set(NON_PERSISTED_SCENARIOS)) == len(NON_PERSISTED_SCENARIOS)
    assert len(NEGATIVE_CONTROL_MATRIX) == 19
    assert len(set(NEGATIVE_CONTROL_MATRIX)) == len(NEGATIVE_CONTROL_MATRIX)
    assert RETIRED_OR_REPLACED_SCENARIOS == {
        "legacy-null-company-employee": "omitted: employees require company and branch scope",
        "legacy-storage-object-row": (
            "replaced: domain metadata only; private object storage is later work"
        ),
        "biometric-api-clock-method": "replaced: BIOMETRIC is the approved target value",
        "stale-task-doc-type": "replaced: employee_documents.document_type",
        "stale-task-eid-expiry": "replaced: employees.emirates_id_expiry",
        "stale-task-payroll-month-year": "replaced: payroll_runs.period",
    }
    forbidden_columns = {"doc_type", "eid_expiry", "month", "year"}
    for row in build_rows():
        if row.table in {"employee_documents", "employees", "payroll_runs"}:
            assert not forbidden_columns.intersection(row.values)
