"""The synthetic fixture manifest as executable row specs.

This module is the version-controlled manifest: every row carries its target
table, its deterministic id, and its complete values. The runner upserts these
rows in list order, which is foreign-key safe. This first pass seeds the
identity and organization spine plus the load-bearing golden financial cases
from ``docs/migration/phase-0/SYNTHETIC_TEST_DATA.md``. Status-coverage rows for
every leave, attendance, document, incident, and appraisal state follow in a
later pass.

Retired legacy-only fixtures, impossible in the Phase 4 target schema:
- ``H-LEG-001`` and every ``company_id IS NULL`` employee: the target requires a
  company and a branch on every employee.
- ``storage.objects`` rows: the target keeps file metadata in domain tables and
  has no storage table; object keys move to FastAPI in a later phase.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, time
from decimal import Decimal
from typing import Any

from app.db.seed import constants as c


@dataclass(frozen=True)
class Row:
    table: str
    values: dict[str, Any]
    conflict: tuple[str, ...] = ("id",)


def _utc(year: int, month: int, day: int, hour: int = 8) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


# --- Companies (2 tenants) --------------------------------------------------

_COMPANIES = [
    Row(
        "companies",
        {
            "id": c.COMPANY_ID[c.HORIZON],
            "name": "Horizon Clinics LLC",
            "sector": "Healthcare",
            "nafis_quota_percent": Decimal("2.00"),
            "enable_nafis": True,
        },
    ),
    Row(
        "companies",
        {
            "id": c.COMPANY_ID[c.CEDAR],
            "name": "Cedar Medical Group LLC",
            "sector": "Healthcare",
            "nafis_quota_percent": Decimal("2.00"),
            "enable_nafis": True,
        },
    ),
]

# --- Branches (4) -----------------------------------------------------------

_BRANCHES = [
    Row(
        "branches",
        {
            "id": c.BRANCH_DXB,
            "company_id": c.COMPANY_ID[c.HORIZON],
            "name": "Horizon Dubai Main",
            "mol_employer_id": "9000000816726",
            "default_bank_routing_code": "999000001",
            "contact_email": "payroll@horizon.test",
            "default_salary_day": 25,
            "work_location_type": "Mainland",
            "enable_staffing_rules": True,
            "enable_biometric_import": True,
        },
    ),
    Row(
        "branches",
        {
            "id": c.BRANCH_AUH,
            "company_id": c.COMPANY_ID[c.HORIZON],
            "name": "Horizon Abu Dhabi",
            "mol_employer_id": "9000000816727",
            "default_bank_routing_code": "999000002",
            "contact_email": "auh-payroll@horizon.test",
            "default_salary_day": 27,
            "work_location_type": "Mainland",
            "enable_staffing_rules": True,
            "enable_biometric_import": False,
        },
    ),
    Row(
        "branches",
        {
            "id": c.BRANCH_SHJ,
            "company_id": c.COMPANY_ID[c.CEDAR],
            "name": "Cedar Sharjah",
            "mol_employer_id": "9000000910001",
            "default_bank_routing_code": "999000101",
            "contact_email": "payroll@cedar.test",
            "default_salary_day": 25,
            "work_location_type": "Mainland",
            "enable_staffing_rules": True,
            "enable_biometric_import": True,
        },
    ),
    Row(
        "branches",
        {
            "id": c.BRANCH_DHC,
            "company_id": c.COMPANY_ID[c.CEDAR],
            "name": "Cedar DHCC",
            "mol_employer_id": "9000000910002",
            "default_bank_routing_code": "999000102",
            "contact_email": "dhcc-payroll@cedar.test",
            "default_salary_day": 25,
            "work_location_type": "Free Zone",
            "free_zone_name": "Dubai Healthcare City",
            "enable_staffing_rules": False,
            "enable_biometric_import": True,
        },
    ),
]

# --- Employee specifications ------------------------------------------------
# Each row is (emp_no, id, company_key, branch_id, name, seq, role, manager_emp_no,
# status, active, contract_type, extra_overrides).

_BRANCH_ROUTING = {
    c.BRANCH_DXB: "999000001",
    c.BRANCH_AUH: "999000002",
    c.BRANCH_SHJ: "999000101",
    c.BRANCH_DHC: "999000102",
}

_EMP = uuid.UUID


def _empty_values() -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class EmpSpec:
    emp_no: str
    id: uuid.UUID
    company: str
    branch: uuid.UUID
    name: str
    seq: int
    role: str  # manager | employee | none
    manager: str | None
    status: str
    active: bool
    contract_type: str
    email: str
    app_user: uuid.UUID | None = None
    extra: dict[str, Any] = field(default_factory=_empty_values)


_EMPLOYEES: list[EmpSpec] = [
    # Horizon Dubai
    EmpSpec(
        "H-DXB-001",
        _EMP("21000000-0000-4000-8000-000000000001"),
        c.HORIZON,
        c.BRANCH_DXB,
        "Dr Aisha Test",
        1,
        "manager",
        None,
        "Active",
        True,
        "Unlimited",
        "aisha.manager@horizon.test",
        _EMP("11000000-0000-4000-8000-000000000001"),
        {
            "nationality": "United Arab Emirates",
            "department": "Clinical",
            "job_title": "Medical Director",
            "employment_start_date": "2017-01-01",
            "basic_salary": Decimal("30000.00"),
            "housing_allowance": Decimal("8000.00"),
            "transport_allowance": Decimal("2000.00"),
            "allowance": Decimal("1000.00"),
            "licence_authority": "DHA",
            "licence_number": "FAKE-DHA-0001",
            "licence_expiry": "2027-05-31",
        },
    ),
    EmpSpec(
        "H-DXB-002",
        _EMP("21000000-0000-4000-8000-000000000002"),
        c.HORIZON,
        c.BRANCH_DXB,
        "Ravi Test",
        2,
        "employee",
        "H-DXB-001",
        "Active",
        True,
        "Limited",
        "ravi.employee@horizon.test",
        _EMP("11000000-0000-4000-8000-000000000002"),
        {
            "nationality": "India",
            "department": "Nursing",
            "job_title": "Registered Nurse",
            "employment_start_date": "2022-03-15",
            "contract_end_date": "2027-03-14",
            "basic_salary": Decimal("12000.00"),
            "housing_allowance": Decimal("3000.00"),
            "transport_allowance": Decimal("1000.00"),
            "allowance": Decimal("500.00"),
        },
    ),
    EmpSpec(
        "H-DXB-003",
        _EMP("21000000-0000-4000-8000-000000000003"),
        c.HORIZON,
        c.BRANCH_DXB,
        "Maria Test",
        3,
        "employee",
        "H-DXB-001",
        "Probation",
        True,
        "Limited",
        "maria.employee@horizon.test",
        _EMP("11000000-0000-4000-8000-000000000003"),
        {
            "employment_start_date": "2026-03-05",
            "probation_end_date": "2026-09-03",
            "passport_expiry": "2026-09-10",
        },
    ),
    EmpSpec(
        "H-DXB-004",
        _EMP("21000000-0000-4000-8000-000000000004"),
        c.HORIZON,
        c.BRANCH_DXB,
        "Noor Test",
        4,
        "employee",
        "H-DXB-001",
        "On Leave",
        True,
        "Unlimited",
        "noor.employee@horizon.test",
        _EMP("11000000-0000-4000-8000-000000000004"),
    ),
    EmpSpec(
        "H-DXB-005",
        _EMP("21000000-0000-4000-8000-000000000005"),
        c.HORIZON,
        c.BRANCH_DXB,
        "Fatima Test",
        5,
        "employee",
        "H-DXB-001",
        "Active",
        True,
        "Unlimited",
        "fatima.employee@horizon.test",
        _EMP("11000000-0000-4000-8000-000000000005"),
        {"nationality": "United Arab Emirates"},
    ),
    EmpSpec(
        "H-DXB-006",
        _EMP("21000000-0000-4000-8000-000000000006"),
        c.HORIZON,
        c.BRANCH_DXB,
        "John Test",
        15,
        "none",
        "H-DXB-001",
        "Terminated",
        False,
        "Unlimited",
        "john.terminated@horizon.test",
        None,
        {
            "employment_start_date": "2019-02-01",
            "termination_date": "2026-08-20",
            "termination_reason": "Resignation",
        },
    ),
    # Horizon Abu Dhabi
    EmpSpec(
        "H-AUH-001",
        _EMP("22000000-0000-4000-8000-000000000001"),
        c.HORIZON,
        c.BRANCH_AUH,
        "Dr Omar Test",
        6,
        "manager",
        None,
        "Active",
        True,
        "Unlimited",
        "omar.manager@horizon.test",
        _EMP("12000000-0000-4000-8000-000000000001"),
    ),
    EmpSpec(
        "H-AUH-002",
        _EMP("22000000-0000-4000-8000-000000000002"),
        c.HORIZON,
        c.BRANCH_AUH,
        "Leila Test",
        7,
        "employee",
        "H-AUH-001",
        "Active",
        True,
        "Limited",
        "leila.employee@horizon.test",
        _EMP("12000000-0000-4000-8000-000000000002"),
    ),
    EmpSpec(
        "H-AUH-003",
        _EMP("22000000-0000-4000-8000-000000000003"),
        c.HORIZON,
        c.BRANCH_AUH,
        "Sara Test",
        8,
        "employee",
        "H-AUH-001",
        "Active",
        True,
        "Limited",
        "sara.employee@horizon.test",
        _EMP("12000000-0000-4000-8000-000000000003"),
    ),
    # Cedar Sharjah
    EmpSpec(
        "C-SHJ-001",
        _EMP("31000000-0000-4000-8000-000000000001"),
        c.CEDAR,
        c.BRANCH_SHJ,
        "Priya Test",
        10,
        "manager",
        None,
        "Active",
        True,
        "Unlimited",
        "priya.manager@cedar.test",
        _EMP("13000000-0000-4000-8000-000000000001"),
    ),
    EmpSpec(
        "C-SHJ-002",
        _EMP("31000000-0000-4000-8000-000000000002"),
        c.CEDAR,
        c.BRANCH_SHJ,
        "Ahmed Test",
        11,
        "employee",
        "C-SHJ-001",
        "Active",
        True,
        "Unlimited",
        "ahmed.employee@cedar.test",
        _EMP("13000000-0000-4000-8000-000000000002"),
    ),
    EmpSpec(
        "C-SHJ-003",
        _EMP("31000000-0000-4000-8000-000000000003"),
        c.CEDAR,
        c.BRANCH_SHJ,
        "Eva Test",
        12,
        "employee",
        "C-SHJ-001",
        "Probation",
        True,
        "Limited",
        "eva.employee@cedar.test",
        _EMP("13000000-0000-4000-8000-000000000003"),
        {"probation_end_date": "2026-09-30"},
    ),
    # Cedar DHCC
    EmpSpec(
        "C-DHC-001",
        _EMP("32000000-0000-4000-8000-000000000001"),
        c.CEDAR,
        c.BRANCH_DHC,
        "Dr Lina Test",
        13,
        "manager",
        None,
        "Active",
        True,
        "Unlimited",
        "lina.manager@cedar.test",
        _EMP("14000000-0000-4000-8000-000000000001"),
    ),
    EmpSpec(
        "C-DHC-002",
        _EMP("32000000-0000-4000-8000-000000000002"),
        c.CEDAR,
        c.BRANCH_DHC,
        "Bilal Test",
        14,
        "employee",
        "C-DHC-001",
        "Active",
        True,
        "Unlimited",
        "bilal.employee@cedar.test",
        _EMP("14000000-0000-4000-8000-000000000002"),
    ),
    EmpSpec(
        "C-DHC-003",
        _EMP("32000000-0000-4000-8000-000000000003"),
        c.CEDAR,
        c.BRANCH_DHC,
        "Grace Test",
        16,
        "none",
        "C-DHC-001",
        "Terminated",
        False,
        "Unlimited",
        "grace.terminated@cedar.test",
        None,
        {
            "employment_start_date": "2020-05-01",
            "termination_date": "2026-07-15",
            "termination_reason": "Resignation",
        },
    ),
]

_EMP_BY_NO = {e.emp_no: e for e in _EMPLOYEES}


def _admin_app_users() -> list[Row]:
    return [
        Row(
            "app_users",
            {
                "id": c.ADMIN_APP_USER[c.HORIZON],
                "identity_issuer": c.SEED_ISSUER,
                "identity_subject": "hr.admin@horizon.test",
                "status": "active",
            },
        ),
        Row(
            "app_users",
            {
                "id": c.ADMIN_APP_USER[c.CEDAR],
                "identity_issuer": c.SEED_ISSUER,
                "identity_subject": "hr.admin@cedar.test",
                "status": "active",
            },
        ),
    ]


def _employee_app_users() -> list[Row]:
    rows: list[Row] = []
    for e in _EMPLOYEES:
        if e.app_user is None:
            continue
        rows.append(
            Row(
                "app_users",
                {
                    "id": e.app_user,
                    "identity_issuer": c.SEED_ISSUER,
                    "identity_subject": e.email,
                    "status": "active",
                },
            )
        )
    return rows


def _employee_rows() -> list[Row]:
    # Managers first so a report's reporting_manager_id foreign key resolves.
    ordered = [e for e in _EMPLOYEES if e.role == "manager"]
    ordered += [e for e in _EMPLOYEES if e.role != "manager"]
    rows: list[Row] = []
    for e in ordered:
        ids = c.identifiers(e.seq)
        manager = _EMP_BY_NO[e.manager].id if e.manager else None
        values: dict[str, Any] = {
            "id": e.id,
            "company_id": c.COMPANY_ID[e.company],
            "branch_id": e.branch,
            "emp_no": e.emp_no,
            "name": e.name,
            "work_email": e.email,
            "bank_name": "Fake National Bank",
            "bank_account_holder": e.name,
            "bank_routing_code": _BRANCH_ROUTING[e.branch],
            "iban": ids["iban"],
            "mol_id": ids["mol_id"],
            "emirates_id": ids["emirates_id"],
            "visa_number": ids["visa_number"],
            "passport_number": ids["passport_number"],
            "labour_card_number": ids["labour_card_number"],
            "phone": ids["phone"],
            "employment_status": e.status,
            "active": e.active,
            "contract_type": e.contract_type,
            "reporting_manager_id": manager,
            "basic_salary": Decimal("10000.00"),
            "housing_allowance": Decimal("2500.00"),
            "transport_allowance": Decimal("800.00"),
            "allowance": Decimal("300.00"),
        }
        values.update(e.extra)
        rows.append(Row("employees", values))
    return rows


def _user_profiles() -> list[Row]:
    rows = [
        Row(
            "user_profiles",
            {
                "app_user_id": c.ADMIN_APP_USER[c.HORIZON],
                "company_id": c.COMPANY_ID[c.HORIZON],
                "employee_id": None,
                "role": "admin",
            },
            conflict=("app_user_id",),
        ),
        Row(
            "user_profiles",
            {
                "app_user_id": c.ADMIN_APP_USER[c.CEDAR],
                "company_id": c.COMPANY_ID[c.CEDAR],
                "employee_id": None,
                "role": "admin",
            },
            conflict=("app_user_id",),
        ),
    ]
    for e in _EMPLOYEES:
        if e.app_user is None:
            continue
        rows.append(
            Row(
                "user_profiles",
                {
                    "app_user_id": e.app_user,
                    "company_id": c.COMPANY_ID[e.company],
                    "employee_id": e.id,
                    "role": e.role,
                },
                conflict=("app_user_id",),
            )
        )
    return rows


# --- Departments and staffing (Horizon Dubai) -------------------------------


def _departments() -> list[Row]:
    def dept_id(name: str) -> uuid.UUID:
        return c.derive("departments", c.HORIZON, "dubai", None, name.lower())

    clinical = dept_id("Clinical")
    rows = [
        Row(
            "departments",
            {
                "id": clinical,
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "name": "Clinical",
                "head_employee_id": _EMP_BY_NO["H-DXB-001"].id,
                "sort_order": 0,
            },
        ),
    ]
    children = ["Nursing", "Laboratory", "Pharmacy"]
    standalone = ["Reception", "Administration"]
    order = 1
    for name in children:
        rows.append(
            Row(
                "departments",
                {
                    "id": dept_id(name),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "name": name,
                    "parent_id": clinical,
                    "sort_order": order,
                },
            )
        )
        order += 1
    for name in standalone:
        rows.append(
            Row(
                "departments",
                {
                    "id": dept_id(name),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "name": name,
                    "sort_order": order,
                },
            )
        )
        order += 1
    return rows


def _staffing_rules() -> list[Row]:
    def rule_id(dept: str, cat: str) -> uuid.UUID:
        return c.derive("department_staffing_rules", c.HORIZON, "dubai", None, f"{dept}-{cat}")

    specs = [("Nursing", "morning", 2), ("Nursing", "night", 1), ("Clinical", "morning", 1)]
    return [
        Row(
            "department_staffing_rules",
            {
                "id": rule_id(dept, cat),
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "department": dept,
                "shift_category": cat,
                "min_staff": n,
                "effective_from": "2026-08-01",
            },
        )
        for dept, cat, n in specs
    ]


# --- Shifts (Horizon Dubai) -------------------------------------------------


def _shifts() -> list[Row]:
    def shift_id(code: str) -> uuid.UUID:
        return c.derive("shifts", c.HORIZON, "dubai", None, code)

    specs = [
        ("M", "Morning", "fixed", "morning", time(8), time(17), 60, Decimal("8"), False, None),
        ("A", "Afternoon", "fixed", "afternoon", time(13), time(22), 60, Decimal("8"), False, None),
        ("N", "Night", "overnight", "night", time(20), time(8), 60, Decimal("11"), True, None),
        ("F", "Flexible", "flexible", "flexible", None, None, 0, Decimal("8"), False, Decimal("8")),
        ("S", "Split", "split", "split", time(8), time(12), 0, Decimal("8"), False, None),
    ]
    rows: list[Row] = []
    for code, name, stype, cat, start, end, brk, hours, overnight, flex in specs:
        values: dict[str, Any] = {
            "id": shift_id(code),
            "company_id": c.COMPANY_ID[c.HORIZON],
            "branch_id": c.BRANCH_DXB,
            "name": name,
            "code": code,
            "shift_type": stype,
            "shift_category": cat,
            "start_time": start,
            "end_time": end,
            "break_minutes": brk,
            "expected_hours": hours,
            "is_overnight": overnight,
            "min_hours_flexible": flex,
        }
        if code == "S":
            values["split_start_time"] = time(16)
            values["split_end_time"] = time(20)
        rows.append(Row("shifts", values))
    return rows


# --- Golden financial cases (Horizon Dubai) ---------------------------------

RUN_MAY = uuid.UUID("41000000-0000-4000-8000-000000000001")
RUN_JUN = uuid.UUID("41000000-0000-4000-8000-000000000002")
RUN_JUL = uuid.UUID("41000000-0000-4000-8000-000000000003")
RUN_AUG = uuid.UUID("41000000-0000-4000-8000-000000000004")

ADVANCE = {n: uuid.UUID(f"51000000-0000-4000-8000-00000000000{n}") for n in range(1, 7)}


def _payroll_runs() -> list[Row]:
    horizon = c.COMPANY_ID[c.HORIZON]
    base = {"company_id": horizon, "branch_id": c.BRANCH_DXB, "scr_bank_routing_code": "999000001"}
    admin = c.ADMIN_APP_USER[c.HORIZON]
    return [
        Row(
            "payroll_runs",
            {
                **base,
                "id": RUN_MAY,
                "period": "2026-05",
                "status": "generated",
                "approval_status": "approved",
                "wps_status": "confirmed",
                "submitted_by_app_user_id": admin,
                "submitted_for_approval_at": _utc(2026, 5, 24),
                "approved_by_app_user_id": admin,
                "approved_at": _utc(2026, 5, 25),
                "wps_submitted_at": _utc(2026, 5, 25),
                "wps_confirmed_at": _utc(2026, 5, 26),
                "payment_date": "2026-05-25",
            },
        ),
        Row(
            "payroll_runs",
            {
                **base,
                "id": RUN_JUN,
                "period": "2026-06",
                "status": "generated",
                "approval_status": "approved",
                "wps_status": "partial_rejection",
                "submitted_by_app_user_id": admin,
                "submitted_for_approval_at": _utc(2026, 6, 24),
                "approved_by_app_user_id": admin,
                "approved_at": _utc(2026, 6, 25),
                "wps_submitted_at": _utc(2026, 6, 25),
                "wps_confirmed_at": _utc(2026, 6, 26),
                "payment_date": "2026-06-25",
            },
        ),
        Row(
            "payroll_runs",
            {
                **base,
                "id": RUN_JUL,
                "period": "2026-07",
                "status": "draft",
                "approval_status": "pending_approval",
                "wps_status": "draft",
                "submitted_by_app_user_id": admin,
                "submitted_for_approval_at": _utc(2026, 7, 24),
            },
        ),
        Row(
            "payroll_runs",
            {
                **base,
                "id": RUN_AUG,
                "period": "2026-08",
                "status": "draft",
                "approval_status": "draft",
                "wps_status": "draft",
            },
        ),
    ]


def _payroll_entries() -> list[Row]:
    # Canonical payroll golden case for H-DXB-002 in the August draft run.
    additional = [
        {
            "label": "Expense Reimbursement",
            "amount": 350.00,
            "recurrence": "one_time",
            "source": "automatic",
        },
        {
            "label": "Overtime (Roster)",
            "amount": 288.46,
            "recurrence": "one_time",
            "source": "automatic",
        },
    ]
    deductions = [
        {
            "label": "Advance Repayment",
            "amount": 500.00,
            "recurrence": "one_time",
            "source": "automatic",
            "payrollPeriod": "2026-08",
            "advanceRepayments": [{"id": str(ADVANCE[2]), "amount": 500.00}],
        },
    ]
    return [
        Row(
            "payroll_entries",
            {
                "id": c.derive(
                    "payroll_entries", c.HORIZON, "dubai", "H-DXB-002", "golden-2026-08"
                ),
                "payroll_run_id": RUN_AUG,
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "employee_id": _EMP_BY_NO["H-DXB-002"].id,
                "basic_salary": Decimal("12000.00"),
                "housing_allowance": Decimal("3000.00"),
                "transport_allowance": Decimal("1000.00"),
                "allowance": Decimal("500.00"),
                "increment": Decimal("0.00"),
                "bonus": Decimal("1000.00"),
                "other_pay": Decimal("0.00"),
                "leave_deduction": Decimal("400.00"),
                "variable_allowance": Decimal("5238.46"),
                "additional_allowances": additional,
                "deductions": deductions,
                "excluded": False,
                "wps_payment_status": "pending",
            },
        )
    ]


def _advances() -> list[Row]:
    horizon = c.COMPANY_ID[c.HORIZON]
    e = _EMP_BY_NO
    specs = [
        # id, employee, branch, status, amount, outstanding, months, monthly, start, reason
        (ADVANCE[1], e["H-DXB-003"], "pending", "1000.00", "1000.00", 1, "1000.00", "2026-09", ""),
        (ADVANCE[2], e["H-DXB-002"], "active", "1500.00", "1000.00", 3, "500.00", "2026-08", ""),
        (ADVANCE[3], e["H-DXB-005"], "active", "900.00", "900.00", 3, "300.00", "2026-09", ""),
        (ADVANCE[4], e["H-AUH-002"], "settled", "1000.00", "0.00", 1, "1000.00", "2026-06", ""),
        (
            ADVANCE[5],
            e["H-AUH-003"],
            "cancelled",
            "1000.00",
            "0.00",
            1,
            "1000.00",
            "2026-07",
            "Insufficient tenure",
        ),
        (
            ADVANCE[6],
            e["H-DXB-004"],
            "cancelled",
            "500.00",
            "0.00",
            1,
            "500.00",
            "2026-08",
            "Withdrawn by employee",
        ),
    ]
    rows: list[Row] = []
    for aid, emp, status, amount, outstanding, months, monthly, start, reason in specs:
        rows.append(
            Row(
                "salary_advances",
                {
                    "id": aid,
                    "company_id": horizon,
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "amount": Decimal(amount),
                    "outstanding_balance": Decimal(outstanding),
                    "repayment_months": months,
                    "monthly_deduction": Decimal(monthly),
                    "repayment_start_month": f"{start}-01",
                    "status": status,
                    "rejection_reason": reason,
                    "disbursed_date": f"{start}-01",
                },
            )
        )
    return rows


def _advance_repayments() -> list[Row]:
    key = c.derive("advance_repayments", c.HORIZON, "dubai", "H-DXB-002", "aug-golden")
    return [
        Row(
            "advance_repayments",
            {
                "id": key,
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "advance_id": ADVANCE[2],
                "payroll_run_id": RUN_AUG,
                "idempotency_key": key,
                "amount": Decimal("500.00"),
                "paid_date": "2026-08-25",
            },
        )
    ]


def _expense_claims() -> list[Row]:
    return [
        Row(
            "expense_claims",
            {
                "id": c.derive(
                    "expense_claims", c.HORIZON, "dubai", "H-DXB-002", "golden-approved"
                ),
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "employee_id": _EMP_BY_NO["H-DXB-002"].id,
                "category": "travel",
                "amount": Decimal("350.00"),
                "expense_date": "2026-08-10",
                "description": "Client site visit taxi",
                "status": "approved",
                "approved_by_app_user_id": c.ADMIN_APP_USER[c.HORIZON],
                "approved_at": _utc(2026, 8, 12),
            },
        )
    ]


def _roster_assignments() -> list[Row]:
    # Golden roster overtime: planned 8, actual 12, four overtime hours.
    return [
        Row(
            "roster_assignments",
            {
                "id": c.derive(
                    "roster_assignments", c.HORIZON, "dubai", "H-DXB-002", "ot-2026-08-28"
                ),
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "employee_id": _EMP_BY_NO["H-DXB-002"].id,
                "shift_id": c.derive("shifts", c.HORIZON, "dubai", None, "M"),
                "date": "2026-08-28",
                "published": True,
                "planned_hours": Decimal("8.00"),
                "actual_hours": Decimal("12.00"),
            },
        )
    ]


def build_rows() -> list[Row]:
    """Return every fixture row in foreign-key-safe insert order."""
    rows: list[Row] = []
    rows += _COMPANIES
    rows += _BRANCHES
    rows += _admin_app_users()
    rows += _employee_app_users()
    rows += _employee_rows()
    rows += _user_profiles()
    rows += _departments()
    rows += _staffing_rules()
    rows += _shifts()
    rows += _payroll_runs()
    rows += _payroll_entries()
    rows += _advances()
    rows += _advance_repayments()
    rows += _expense_claims()
    rows += _roster_assignments()
    return rows


TENANT_COMPANY_IDS = tuple(c.COMPANY_ID.values())
