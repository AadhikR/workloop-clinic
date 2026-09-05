"""The synthetic fixture manifest as executable row specs.

This module is the version-controlled manifest. Every row carries its target
table, deterministic id, and fixed values. The runner inserts these rows in
foreign-key-safe order and treats an existing fixture id as a no-op.

Retired legacy-only fixtures, impossible in the Phase 4 target schema:
- ``H-LEG-001`` and every ``company_id IS NULL`` employee: the target requires a
  company and a branch on every employee.
- Legacy object-storage rows: the target keeps file metadata in domain tables and
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


def _financial_status_rows() -> list[Row]:
    rows: list[Row] = []
    periods = [
        ("2026-05", "generated", "approved", "confirmed"),
        ("2026-06", "generated", "approved", "partial_rejection"),
        ("2026-07", "draft", "pending_approval", "draft"),
        ("2026-08", "draft", "draft", "draft"),
    ]
    run_ids: dict[tuple[str, str], uuid.UUID] = {}
    for branch_key in ("abu-dhabi", "sharjah", "dhcc"):
        tenant, branch_id = _BRANCHES_BY_KEY[branch_key]
        for period, status, approval, wps in periods:
            run_id = _id("payroll_runs", tenant, branch_key, "none", period)
            run_ids[(branch_key, period)] = run_id
            values: dict[str, Any] = {
                "id": run_id,
                "company_id": c.COMPANY_ID[tenant],
                "branch_id": branch_id,
                "period": period,
                "status": status,
                "approval_status": approval,
                "wps_status": wps,
            }
            if approval == "pending_approval":
                values["submitted_by_app_user_id"] = c.ADMIN_APP_USER[tenant]
                values["submitted_for_approval_at"] = c.CLOCK_TIMESTAMP
            if approval == "approved":
                values["approved_by_app_user_id"] = c.ADMIN_APP_USER[tenant]
                values["approved_at"] = c.CLOCK_TIMESTAMP
                values["submitted_by_app_user_id"] = c.ADMIN_APP_USER[tenant]
                values["submitted_for_approval_at"] = c.CLOCK_TIMESTAMP
            if wps in {"confirmed", "partial_rejection"}:
                values["wps_submitted_at"] = c.CLOCK_TIMESTAMP
                values["wps_confirmed_at"] = c.CLOCK_TIMESTAMP
            rows.append(Row("payroll_runs", values))

    entry_specs: list[
        tuple[str, str, str, bool, str, list[dict[str, object]], list[dict[str, object]]]
    ] = [
        (
            "H-DXB-001",
            "fixed-only",
            "pending",
            False,
            "0.00",
            [
                {
                    "label": "Synthetic recurring allowance",
                    "amount": 100.00,
                    "recurrence": "recurring",
                }
            ],
            [],
        ),
        ("H-DXB-003", "legacy-signed-variable", "paid", False, "-50.00", [], []),
        ("H-DXB-004", "excluded", "pending", True, "0.00", [], []),
        ("H-DXB-005", "expired-warning", "rejected", False, "0.00", [], []),
        (
            "H-DXB-006",
            "named-deductions-capacity",
            "paid",
            False,
            "0.00",
            [],
            [{"label": "Synthetic deduction", "amount": 9000.00}],
        ),
    ]
    for employee, scenario, wps_status, excluded, variable, additions, deductions in entry_specs:
        emp = _EMP_BY_NO[employee]
        values = {
            "id": _id("payroll_entries", c.HORIZON, "dubai", employee, scenario),
            "payroll_run_id": RUN_AUG,
            "company_id": c.COMPANY_ID[c.HORIZON],
            "branch_id": c.BRANCH_DXB,
            "employee_id": emp.id,
            "basic_salary": emp.extra.get("basic_salary", Decimal("10000.00")),
            "variable_allowance": Decimal(variable),
            "additional_allowances": additions,
            "deductions": deductions,
            "excluded": excluded,
            "wps_payment_status": wps_status,
        }
        if wps_status == "rejected":
            values["wps_rejection_reason"] = "Expired synthetic compliance document"
        rows.append(Row("payroll_entries", values))

    may_entry = _id("payroll_entries", c.HORIZON, "dubai", "H-DXB-005", "paid-expense")
    rows.extend(
        [
            Row(
                "payroll_entries",
                {
                    "id": may_entry,
                    "payroll_run_id": RUN_MAY,
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "employee_id": _EMP_BY_NO["H-DXB-005"].id,
                    "basic_salary": Decimal("10000.00"),
                    "variable_allowance": Decimal("350.00"),
                    "additional_allowances": [{"label": "Expense Reimbursement", "amount": 350.00}],
                    "wps_payment_status": "paid",
                },
            ),
            Row(
                "payslips",
                {
                    "id": _id("payslips", c.HORIZON, "dubai", "H-DXB-005", "2026-05"),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "payroll_run_id": RUN_MAY,
                    "employee_id": _EMP_BY_NO["H-DXB-005"].id,
                    "period": "2026-05",
                    "payment_date": "2026-05-25",
                    "gross_pay": Decimal("10350.00"),
                    "net_pay": Decimal("10350.00"),
                    "data_snapshot": {"synthetic": True, "grossPay": 10350.00, "netPay": 10350.00},
                    "issued_at": c.CLOCK_TIMESTAMP,
                },
            ),
        ]
    )
    for action, run_id in (
        ("submitted", RUN_JUL),
        ("recalled", RUN_JUL),
        ("approved", RUN_MAY),
        ("rejected", RUN_JUN),
    ):
        rows.append(
            Row(
                "payroll_approval_log",
                {
                    "id": _id("payroll_approval_log", c.HORIZON, "dubai", "admin", action),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "payroll_run_id": run_id,
                    "action": action,
                    "performed_by_app_user_id": c.ADMIN_APP_USER[c.HORIZON],
                    "notes": f"Synthetic payroll action {action}",
                },
            )
        )

    expense_specs = [
        ("H-DXB-003", "dubai", "pending", "", None),
        ("H-DXB-004", "dubai", "manager_approved", "fixtures/receipts/fake-receipt.jpg", None),
        ("H-DXB-005", "dubai", "manager_rejected", "", None),
        ("H-DXB-005", "dubai", "paid", "fixtures/receipts/fake-receipt.jpg", RUN_MAY),
        ("H-AUH-003", "abu-dhabi", "rejected", "", None),
        ("C-SHJ-002", "sharjah", "pending", "fixtures/receipts/fake-receipt.jpg", None),
    ]
    for employee, branch_key, status, receipt, payroll_run_id in expense_specs:
        emp = _EMP_BY_NO[employee]
        values = {
            "id": _id("expense_claims", emp.company, branch_key, employee, status),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "category": "other",
            "amount": Decimal("125.00" if status != "paid" else "350.00"),
            "expense_date": "2026-08-10",
            "description": f"Synthetic {status} expense",
            "receipt_url": receipt,
            "status": status,
            "payroll_run_id": payroll_run_id,
        }
        if status == "manager_approved":
            values["manager_approved_at"] = c.CLOCK_TIMESTAMP
            values["manager_approved_by_app_user_id"] = _EMP_BY_NO["H-DXB-001"].app_user
        if status == "manager_rejected":
            values["manager_approved_at"] = c.CLOCK_TIMESTAMP
            values["manager_approved_by_app_user_id"] = _EMP_BY_NO["H-DXB-001"].app_user
            values["manager_rejection_reason"] = "The expense is outside policy"
        if status in {"paid", "rejected"}:
            values["approved_at"] = c.CLOCK_TIMESTAMP
            values["approved_by_app_user_id"] = c.ADMIN_APP_USER[emp.company]
        if status == "rejected":
            values["rejection_reason"] = "The receipt does not support the claim"
        rows.append(Row("expense_claims", values))

    rows.append(
        Row(
            "salary_advances",
            {
                "id": _id("salary_advances", c.CEDAR, "sharjah", "C-SHJ-002", "scope-control"),
                "company_id": c.COMPANY_ID[c.CEDAR],
                "branch_id": c.BRANCH_SHJ,
                "employee_id": _EMP_BY_NO["C-SHJ-002"].id,
                "amount": Decimal("600.00"),
                "repayment_start_month": "2026-09-01",
                "repayment_months": 3,
                "monthly_deduction": Decimal("200.00"),
                "outstanding_balance": Decimal("600.00"),
                "status": "active",
            },
        )
    )
    rows.append(
        Row(
            "payroll_entries",
            {
                "id": _id("payroll_entries", c.CEDAR, "sharjah", "C-SHJ-002", "scope-control"),
                "payroll_run_id": run_ids[("sharjah", "2026-08")],
                "company_id": c.COMPANY_ID[c.CEDAR],
                "branch_id": c.BRANCH_SHJ,
                "employee_id": _EMP_BY_NO["C-SHJ-002"].id,
                "basic_salary": Decimal("10000.00"),
                "wps_payment_status": "pending",
            },
        )
    )
    return rows


# --- Phase 0 status catalogue ------------------------------------------------


def _id(table: str, tenant: str, branch: str, actor: str, scenario: str) -> uuid.UUID:
    return c.derive(table, tenant, branch, actor, scenario)


_BRANCHES_BY_KEY = {
    "dubai": (c.HORIZON, c.BRANCH_DXB),
    "abu-dhabi": (c.HORIZON, c.BRANCH_AUH),
    "sharjah": (c.CEDAR, c.BRANCH_SHJ),
    "dhcc": (c.CEDAR, c.BRANCH_DHC),
}


def _leave_foundation() -> list[Row]:
    rows: list[Row] = []
    type_specs = [
        ("ANNUAL", "Annual Leave", True, False, False, 30, "monthly", "calendar", False),
        ("SICK", "Sick Leave", True, True, True, 90, "fixed", "calendar", True),
        ("MATERNITY", "Maternity Leave", True, True, False, 60, "fixed", "calendar", True),
        ("PATERNITY", "Parental Leave", True, False, False, 5, "fixed", "working", True),
        ("BEREAVEMENT", "Bereavement Leave", True, False, True, 5, "fixed", "working", True),
        ("STUDY", "Study Leave", True, True, True, 10, "fixed", "working", False),
        ("HAJJ", "Hajj Leave", False, False, False, 30, "once_per_career", "calendar", False),
        ("UNPAID", "Unpaid Leave", False, False, True, 0, "none", "calendar", True),
        (
            "CUSTOM_COMPASSIONATE",
            "Compassionate Leave",
            True,
            False,
            True,
            3,
            "fixed",
            "working",
            True,
        ),
    ]
    for branch_key, (tenant, branch_id) in _BRANCHES_BY_KEY.items():
        rows.append(
            Row(
                "leave_settings",
                {
                    "id": _id("leave_settings", tenant, branch_key, "none", "default"),
                    "company_id": c.COMPANY_ID[tenant],
                    "branch_id": branch_id,
                    "approval_chain": "2-level" if branch_id == c.BRANCH_AUH else "1-level",
                    "weekend_definition": "fri-sat",
                },
            )
        )
        rows.append(
            Row(
                "public_holidays",
                {
                    "id": _id("public_holidays", tenant, branch_key, "none", "national-day"),
                    "company_id": c.COMPANY_ID[tenant],
                    "branch_id": branch_id,
                    "date": "2026-12-02",
                    "name": "UAE National Day",
                    "type": "federal",
                    "year": 2026,
                },
            )
        )
        for order, spec in enumerate(type_specs):
            code, name, paid, attachment, reason, entitlement, accrual, day_count, probation = spec
            rows.append(
                Row(
                    "leave_types",
                    {
                        "id": _id("leave_types", tenant, branch_key, "none", code.lower()),
                        "company_id": c.COMPANY_ID[tenant],
                        "branch_id": branch_id,
                        "code": code,
                        "name": name,
                        "is_paid": paid,
                        "requires_attachment": attachment,
                        "requires_reason": reason,
                        "annual_entitlement_days": Decimal(entitlement),
                        "accrual_type": accrual,
                        "day_count_type": day_count,
                        "probation_eligible": probation,
                        "is_unlimited": code == "UNPAID",
                        "once_per_career": code == "HAJJ",
                        "not_deducted_from_annual": code == "BEREAVEMENT",
                        "affects_payroll": code == "UNPAID",
                        "sort_order": order,
                    },
                )
            )
    return rows


def _leave_type_id(branch_key: str, code: str) -> uuid.UUID:
    tenant, _ = _BRANCHES_BY_KEY[branch_key]
    return _id("leave_types", tenant, branch_key, "none", code.lower())


def _leave_rows() -> list[Row]:
    h = c.COMPANY_ID[c.HORIZON]
    aisha = _EMP_BY_NO["H-DXB-001"].app_user
    omar = _EMP_BY_NO["H-AUH-001"].app_user
    cedar_admin = c.ADMIN_APP_USER[c.CEDAR]
    assert aisha is not None and omar is not None

    def request(
        branch_key: str,
        employee: str,
        scenario: str,
        leave_code: str,
        start: str,
        end: str,
        days: str,
        status: str,
        **extra: Any,
    ) -> Row:
        emp = _EMP_BY_NO[employee]
        values: dict[str, Any] = {
            "id": _id("leave_requests", emp.company, branch_key, employee, scenario),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "leave_type_id": _leave_type_id(branch_key, leave_code),
            "start_date": start,
            "end_date": end,
            "days_requested": Decimal(days),
            "status": status,
            "reason": f"Synthetic {scenario}",
            "submitted_at": c.CLOCK_TIMESTAMP,
        }
        values.update(extra)
        return Row("leave_requests", values)

    rows = [
        request(
            "dubai",
            "H-DXB-002",
            "pending-annual-half-day",
            "ANNUAL",
            "2026-09-01",
            "2026-09-01",
            "0.50",
            "Pending",
            is_half_day=True,
            half_day_period="AM",
        ),
        request(
            "abu-dhabi",
            "H-AUH-002",
            "manager-approved-annual",
            "ANNUAL",
            "2026-09-06",
            "2026-09-07",
            "2.00",
            "ManagerApproved",
            approval_level_required=2,
            manager_approved_by_app_user_id=omar,
            manager_approved_at=c.CLOCK_TIMESTAMP,
        ),
        request(
            "dubai",
            "H-DXB-003",
            "manager-rejected-study",
            "STUDY",
            "2026-09-08",
            "2026-09-08",
            "1.00",
            "ManagerRejected",
            manager_approved_by_app_user_id=aisha,
            manager_approved_at=c.CLOCK_TIMESTAMP,
            manager_rejection_reason="Probation eligibility not met",
            institution_name="Synthetic Training Institute",
            exam_dates="2026-09-08",
            warnings=["probation_ineligible"],
        ),
        request(
            "dubai",
            "H-DXB-004",
            "approved-current-annual",
            "ANNUAL",
            "2026-08-26",
            "2026-08-28",
            "3.00",
            "Approved",
            approved_by_app_user_id=c.ADMIN_APP_USER[c.HORIZON],
            approved_at=c.CLOCK_TIMESTAMP,
        ),
        request(
            "abu-dhabi",
            "H-AUH-003",
            "rejected-sick-attachment",
            "SICK",
            "2026-09-02",
            "2026-09-03",
            "2.00",
            "Rejected",
            attachment_url="fixtures/documents/fake-document.pdf",
            approved_by_app_user_id=c.ADMIN_APP_USER[c.HORIZON],
            approved_at=c.CLOCK_TIMESTAMP,
            rejection_reason="Medical certificate details are incomplete",
        ),
        request(
            "sharjah",
            "C-SHJ-002",
            "cancelled-unpaid",
            "UNPAID",
            "2026-09-15",
            "2026-09-16",
            "2.00",
            "Cancelled",
        ),
        request(
            "dubai",
            "H-DXB-005",
            "approved-maternity",
            "MATERNITY",
            "2026-10-01",
            "2026-11-29",
            "60.00",
            "Approved",
            approved_by_app_user_id=c.ADMIN_APP_USER[c.HORIZON],
            approved_at=c.CLOCK_TIMESTAMP,
            child_name="Baby Test",
            expected_due_date="2026-10-01",
            attachment_url="fixtures/documents/fake-document.pdf",
        ),
        request(
            "dubai",
            "H-DXB-002",
            "approved-bereavement",
            "BEREAVEMENT",
            "2026-07-20",
            "2026-07-22",
            "3.00",
            "Approved",
            approved_by_app_user_id=c.ADMIN_APP_USER[c.HORIZON],
            approved_at=c.CLOCK_TIMESTAMP,
            relationship="Parent",
            deceased_name="Relative Test",
            date_of_death="2026-07-19",
        ),
        request(
            "dubai",
            "H-DXB-002",
            "approved-study",
            "STUDY",
            "2026-06-14",
            "2026-06-15",
            "2.00",
            "Approved",
            approved_by_app_user_id=c.ADMIN_APP_USER[c.HORIZON],
            approved_at=c.CLOCK_TIMESTAMP,
            institution_name="Synthetic Training Institute",
            exam_dates="2026-06-14,2026-06-15",
            attachment_url="fixtures/documents/fake-document.pdf",
        ),
        request(
            "dubai",
            "H-DXB-001",
            "approved-hajj",
            "HAJJ",
            "2026-05-01",
            "2026-05-30",
            "30.00",
            "Approved",
            approved_by_app_user_id=c.ADMIN_APP_USER[c.HORIZON],
            approved_at=c.CLOCK_TIMESTAMP,
        ),
        request(
            "dubai",
            "H-DXB-002",
            "approved-weekend-span",
            "ANNUAL",
            "2026-07-24",
            "2026-07-26",
            "3.00",
            "Approved",
            approved_by_app_user_id=c.ADMIN_APP_USER[c.HORIZON],
            approved_at=c.CLOCK_TIMESTAMP,
            warnings=["weekend_span"],
        ),
        request(
            "dhcc",
            "C-DHC-002",
            "approved-public-holiday-span",
            "ANNUAL",
            "2026-12-01",
            "2026-12-03",
            "3.00",
            "Approved",
            approved_by_app_user_id=cedar_admin,
            approved_at=c.CLOCK_TIMESTAMP,
            warnings=["public_holiday_span"],
        ),
    ]
    balance_specs = [
        ("H-DXB-002", "dubai", "SICK", "sick-50-used", "90", "50", "40", "15", "30", "5", False),
        ("H-DXB-001", "dubai", "HAJJ", "hajj-taken", "30", "30", "0", "0", "0", "0", True),
        ("H-DXB-003", "dubai", "ANNUAL", "insufficient", "5", "4", "1", "0", "0", "0", False),
    ]
    for (
        employee,
        branch_key,
        code,
        scenario,
        entitled,
        used,
        remaining,
        full,
        half,
        unpaid,
        hajj,
    ) in balance_specs:
        emp = _EMP_BY_NO[employee]
        rows.append(
            Row(
                "leave_balances",
                {
                    "id": _id("leave_balances", emp.company, branch_key, employee, scenario),
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "leave_type_id": _leave_type_id(branch_key, code),
                    "leave_year": 2026,
                    "entitled_days": Decimal(entitled),
                    "accrued_days": Decimal(entitled),
                    "used_days": Decimal(used),
                    "remaining_days": Decimal(remaining),
                    "sick_full_pay_used": Decimal(full),
                    "sick_half_pay_used": Decimal(half),
                    "sick_unpaid_used": Decimal(unpaid),
                    "hajj_taken": hajj,
                },
            )
        )
    for scenario, end in (("active", "2026-08-31"), ("expired", "2026-07-31")):
        rows.append(
            Row(
                "leave_approval_delegates",
                {
                    "id": _id(
                        "leave_approval_delegates", c.HORIZON, "dubai", "H-DXB-001", scenario
                    ),
                    "company_id": h,
                    "branch_id": c.BRANCH_DXB,
                    "approver_employee_id": _EMP_BY_NO["H-DXB-001"].id,
                    "delegate_employee_id": _EMP_BY_NO["H-DXB-005"].id,
                    "from_date": "2026-08-01" if scenario == "active" else "2026-07-01",
                    "to_date": end,
                },
            )
        )
    return rows


def _attendance_rows() -> list[Row]:
    rows: list[Row] = []
    for branch_key, (tenant, branch_id) in _BRANCHES_BY_KEY.items():
        rows.append(
            Row(
                "attendance_settings",
                {
                    "id": _id("attendance_settings", tenant, branch_key, "none", "default"),
                    "company_id": c.COMPANY_ID[tenant],
                    "branch_id": branch_id,
                    "wfh_enabled": True,
                    "biometric_api_enabled": branch_id != c.BRANCH_AUH,
                    "biometric_api_key": "synthetic-not-a-secret",
                },
            )
        )

    dxb_shift = c.derive("shifts", c.HORIZON, "dubai", None, "M")
    status_specs: list[tuple[str, str, str, dict[str, Any]]] = [
        ("PRESENT", "H-DXB-001", "2026-08-01", {}),
        (
            "ABSENT",
            "H-DXB-002",
            "2026-08-02",
            {"resolution_type": "UNAUTHORISED", "absence_deduction": Decimal("400.00")},
        ),
        ("ON_LEAVE", "H-DXB-003", "2026-08-03", {"resolution_type": "LEAVE_LINKED"}),
        ("PUBLIC_HOLIDAY", "H-DXB-004", "2026-08-04", {}),
        ("WEEKEND", "H-DXB-005", "2026-08-05", {}),
        ("LATE", "H-DXB-001", "2026-08-06", {"late_minutes": 20}),
        ("EARLY_DEPARTURE", "H-DXB-002", "2026-08-07", {"early_departure_minutes": 30}),
        ("HALF_DAY", "H-DXB-003", "2026-08-08", {"total_hours": Decimal("4.00")}),
        (
            "OVERTIME",
            "H-DXB-004",
            "2026-08-09",
            {
                "overtime_hours": Decimal("2.00"),
                "overtime_type": "STANDARD",
                "overtime_amount": Decimal("144.23"),
            },
        ),
        ("UNEXPLAINED_ABSENCE", "H-DXB-005", "2026-08-10", {}),
        ("PRESENT_REMOTE", "H-DXB-001", "2026-08-11", {"resolution_type": "WFH"}),
        (
            "MISSING_CLOCK_OUT",
            "H-DXB-002",
            "2026-08-26",
            {"missing_clock_out": True, "clock_in_time": _utc(2026, 8, 26, 8)},
        ),
        (
            "OVERTIME",
            "H-DXB-003",
            "2026-08-12",
            {
                "overtime_hours": Decimal("2.00"),
                "overtime_type": "REST_DAY_NO_SUB",
                "overtime_amount": Decimal("173.08"),
                "overtime_approved": True,
            },
        ),
    ]
    for status, employee, day, extra in status_specs:
        emp = _EMP_BY_NO[employee]
        values: dict[str, Any] = {
            "id": _id(
                "attendance_records", emp.company, "dubai", employee, f"{status.lower()}-{day}"
            ),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "date": day,
            "shift_id": dxb_shift,
            "status": status,
            "total_hours": Decimal("8.00")
            if status
            not in {"ABSENT", "ON_LEAVE", "PUBLIC_HOLIDAY", "WEEKEND", "UNEXPLAINED_ABSENCE"}
            else Decimal("0.00"),
        }
        if extra.get("resolution_type"):
            values["resolved_by_app_user_id"] = c.ADMIN_APP_USER[c.HORIZON]
        if extra.get("overtime_approved"):
            values["overtime_approved_by_app_user_id"] = c.ADMIN_APP_USER[c.HORIZON]
        values.update(extra)
        rows.append(Row("attendance_records", values))

    clock_specs = [
        ("H-DXB-002", "CLOCK_IN", "2026-08-27T04:00:00+00:00", "WEB", "web-in"),
        ("H-DXB-002", "CLOCK_OUT", "2026-08-27T12:00:00+00:00", "WEB", "web-out"),
        ("H-DXB-003", "CLOCK_IN", "2026-08-27T04:05:00+00:00", "MANUAL", "manual-in"),
        ("H-DXB-003", "CLOCK_OUT", "2026-08-27T12:05:00+00:00", "MANUAL", "manual-out"),
        ("H-DXB-004", "CLOCK_IN", "2026-08-27T04:01:00+00:00", "BIOMETRIC", "biometric-in"),
        ("H-DXB-002", "CLOCK_IN", "2026-08-26T04:00:00+00:00", "WEB", "missing-out"),
    ]
    for employee, event_type, event_time, method, scenario in clock_specs:
        emp = _EMP_BY_NO[employee]
        rows.append(
            Row(
                "clock_events",
                {
                    "id": _id("clock_events", emp.company, "dubai", employee, scenario),
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "event_type": event_type,
                    "event_time": event_time,
                    "method": method,
                    "entered_by_app_user_id": emp.app_user,
                },
            )
        )
    for status, employee, day in (
        ("Pending", "H-DXB-002", "2026-08-20"),
        ("Approved", "H-DXB-003", "2026-08-21"),
        ("Rejected", "H-DXB-004", "2026-08-22"),
    ):
        emp = _EMP_BY_NO[employee]
        values = {
            "id": _id("regularisation_requests", emp.company, "dubai", employee, status.lower()),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "attendance_date": day,
            "correct_clock_in": f"{day}T04:00:00+00:00",
            "correct_clock_out": f"{day}T12:00:00+00:00",
            "reason": "Synthetic clock correction",
            "status": status,
            "submitted_at": c.CLOCK_TIMESTAMP,
        }
        if status != "Pending":
            values["approved_by_app_user_id"] = c.ADMIN_APP_USER[c.HORIZON]
            values["approved_at"] = c.CLOCK_TIMESTAMP
        if status == "Rejected":
            values["rejection_reason"] = "Times do not match the source record"
        rows.append(Row("regularisation_requests", values))
    rows.extend(
        [
            Row(
                "attendance_periods",
                {
                    "id": _id("attendance_periods", c.HORIZON, "dubai", "none", "2026-07-closed"),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "period": "2026-07",
                    "status": "closed",
                    "closed_at": c.CLOCK_TIMESTAMP,
                    "closed_by_app_user_id": c.ADMIN_APP_USER[c.HORIZON],
                    "payroll_ready": True,
                    "open_items": 0,
                },
            ),
            Row(
                "attendance_periods",
                {
                    "id": _id("attendance_periods", c.HORIZON, "dubai", "none", "2026-08-open"),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "period": "2026-08",
                    "status": "open",
                    "payroll_ready": False,
                    "open_items": 2,
                },
            ),
            Row(
                "biometric_mappings",
                {
                    "id": _id(
                        "biometric_mappings", c.HORIZON, "dubai", "H-DXB-002", "matched-badge"
                    ),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "badge_no": "SYNTH-0002",
                    "employee_id": _EMP_BY_NO["H-DXB-002"].id,
                    "device_name": "Synthetic terminal",
                },
            ),
        ]
    )
    return rows


def _document_and_benefit_rows() -> list[Row]:
    rows: list[Row] = []
    document_specs = [
        ("H-DXB-002", "dubai", "visa", "2026-08-26", "pending_verification"),
        ("H-DXB-003", "dubai", "passport", "2026-09-03", "verified"),
        ("H-DXB-004", "dubai", "emirates_id", "2026-09-10", "rejected"),
        ("H-DXB-005", "dubai", "labour_card", "2026-09-26", "verified"),
        ("H-AUH-002", "abu-dhabi", "work_permit", "2026-10-26", "pending_verification"),
        ("H-AUH-003", "abu-dhabi", "medical_fitness", "2026-11-25", "verified"),
        ("C-SHJ-002", "sharjah", "educational_certificate", "2028-01-01", "verified"),
        ("C-SHJ-003", "sharjah", "noc", None, "pending_verification"),
        ("C-DHC-002", "dhcc", "other", "2027-12-31", "verified"),
    ]
    for index, (employee, branch_key, doc_type, expiry, status) in enumerate(document_specs):
        emp = _EMP_BY_NO[employee]
        values: dict[str, Any] = {
            "id": _id("employee_documents", emp.company, branch_key, employee, doc_type),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "document_type": doc_type,
            "document_number": f"SYNTH-DOC-{index + 1:03d}",
            "file_name": "fake-document.pdf",
            "file_size": 512,
            "storage_path": f"fixtures/{emp.company}/{employee}/{doc_type}/fake-document.pdf",
            "expiry_date": expiry,
            "status": status,
            "submitted_by": "employee" if status == "pending_verification" else "hr",
            "uploaded_at": c.CLOCK_TIMESTAMP,
        }
        if status != "pending_verification":
            values["reviewed_by_app_user_id"] = c.ADMIN_APP_USER[emp.company]
            values["reviewed_at"] = c.CLOCK_TIMESTAMP
        if status == "rejected":
            values["rejection_reason"] = "The uploaded copy is unreadable"
        if doc_type == "other":
            values["storage_path"] = "fixtures/missing-object/fake-document.pdf"
            values["notes"] = "Metadata-only missing-object control"
        rows.append(Row("employee_documents", values))

    certification_specs = [
        ("H-DXB-001", "dubai", "DHA licence", "2026-08-26", "verified"),
        ("H-AUH-001", "abu-dhabi", "DOH licence", "2026-09-03", "pending_review"),
        ("C-SHJ-001", "sharjah", "MOH licence", "2026-09-10", "rejected"),
        ("H-DXB-002", "dubai", "BLS", "2026-09-26", "verified"),
        ("H-DXB-003", "dubai", "ACLS", "2026-10-26", "pending_review"),
        ("H-DXB-004", "dubai", "PALS", "2026-11-25", "verified"),
        ("C-DHC-001", "dhcc", "NRP", "2028-01-01", "verified"),
        ("C-DHC-002", "dhcc", "CME certificate", None, "pending_review"),
    ]
    for index, (employee, branch_key, name, expiry, status) in enumerate(certification_specs):
        emp = _EMP_BY_NO[employee]
        values = {
            "id": _id(
                "certifications", emp.company, branch_key, employee, name.lower().replace(" ", "-")
            ),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "certification_name": name,
            "issuing_body": "Synthetic Credential Board",
            "certificate_no": f"SYNTH-CERT-{index + 1:03d}",
            "issued_date": "2025-01-01",
            "expiry_date": expiry,
            "storage_path": f"fixtures/{emp.company}/certs/{employee}/fake-credential.png",
            "file_name": "fake-credential.png",
            "status": status,
        }
        if status != "pending_review":
            values["reviewed_by_app_user_id"] = c.ADMIN_APP_USER[emp.company]
            values["reviewed_at"] = c.CLOCK_TIMESTAMP
        if status == "rejected":
            values["notes"] = "Issuer could not be verified"
        rows.append(Row("certifications", values))

    policy_id = _id("insurance_policies", c.HORIZON, "dubai", "none", "renewal-plus-30")
    rows.extend(
        [
            Row(
                "insurance_policies",
                {
                    "id": policy_id,
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "insurer_name": "Synthetic Health Cover",
                    "policy_number": "SYNTH-POLICY-001",
                    "tier_name": "Test Gold",
                    "annual_premium": Decimal("1200.00"),
                    "renewal_date": "2026-09-26",
                    "broker_contact": "broker@insurance.test",
                },
            ),
            Row(
                "employee_insurance",
                {
                    "id": _id(
                        "employee_insurance", c.HORIZON, "dubai", "H-DXB-002", "expiry-plus-60"
                    ),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "employee_id": _EMP_BY_NO["H-DXB-002"].id,
                    "policy_id": policy_id,
                    "member_id": "SYNTH-MEMBER-002",
                    "card_number": "SYNTH-CARD-002",
                    "effective_date": "2025-10-27",
                    "expiry_date": "2026-10-26",
                    "tier_name": "Test Gold",
                },
            ),
            Row(
                "insurance_dependants",
                {
                    "id": _id("insurance_dependants", c.HORIZON, "dubai", "H-DXB-002", "no-expiry"),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "employee_id": _EMP_BY_NO["H-DXB-002"].id,
                    "name": "Dependant Test",
                    "relationship": "Child",
                    "date_of_birth": "2018-01-01",
                    "card_number": "SYNTH-DEPENDANT-002",
                },
            ),
        ]
    )
    return rows


def _notification_rows() -> list[Row]:
    types = [
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
    ]
    recipient = _EMP_BY_NO["H-DXB-002"].app_user
    assert recipient is not None
    rows: list[Row] = []
    for index, notification_type in enumerate(types):
        values: dict[str, Any] = {
            "id": _id("notifications", c.HORIZON, "dubai", "H-DXB-002", notification_type),
            "company_id": c.COMPANY_ID[c.HORIZON],
            "branch_id": c.BRANCH_DXB,
            "created_by_app_user_id": c.ADMIN_APP_USER[c.HORIZON],
            "recipient_app_user_id": recipient,
            "type": notification_type,
            "title": f"Synthetic {notification_type.replace('_', ' ')}",
            "body": "Synthetic notification body",
            "related_entity_type": "fixture",
            "related_entity_id": f"SYNTH-{index + 1:02d}",
            "created_at": c.CLOCK_TIMESTAMP,
            "read_at": c.CLOCK_TIMESTAMP if index % 2 else None,
        }
        rows.append(Row("notifications", values))
    return rows


def _training_and_cme_rows() -> list[Row]:
    rows: list[Row] = []
    training_specs = [
        ("H-DXB-002", "dubai", "planned", "internal", None, None, "planned-internal"),
        ("H-DXB-003", "dubai", "in_progress", "external", None, None, "progress-external"),
        ("H-DXB-004", "dubai", "completed", "online", True, "2026-08-20", "completed-pass"),
        ("H-DXB-005", "dubai", "completed", "conference", False, "2026-08-21", "completed-fail"),
        ("H-AUH-002", "abu-dhabi", "cancelled", "internal", None, None, "cancelled"),
        ("C-SHJ-002", "sharjah", "planned", "online", None, None, "tenant-control"),
    ]
    for employee, branch_key, status, training_type, passed, end_date, scenario in training_specs:
        emp = _EMP_BY_NO[employee]
        rows.append(
            Row(
                "training_records",
                {
                    "id": _id("training_records", emp.company, branch_key, employee, scenario),
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "training_title": f"Synthetic {scenario}",
                    "training_type": training_type,
                    "provider": "Synthetic Training Institute",
                    "start_date": "2026-08-20",
                    "end_date": end_date,
                    "duration_hours": Decimal("2.00"),
                    "status": status,
                    "passed": passed,
                },
            )
        )
    cme_specs = [
        ("H-DXB-001", "dubai", 2026, "30.00"),
        ("H-DXB-002", "dubai", 2026, "12.00"),
        ("H-DXB-005", "dubai", 2026, "8.00"),
        ("H-DXB-001", "dubai", 2025, "25.00"),
    ]
    for employee, branch_key, year, hours in cme_specs:
        emp = _EMP_BY_NO[employee]
        rows.append(
            Row(
                "training_records",
                {
                    "id": _id("training_records", emp.company, branch_key, employee, f"cme-{year}"),
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "training_title": f"Synthetic CME {year}",
                    "training_type": "conference",
                    "provider": "Synthetic Medical Council",
                    "start_date": f"{year}-05-01",
                    "end_date": f"{year}-05-01",
                    "duration_hours": Decimal(hours),
                    "status": "completed",
                    "passed": True,
                    "is_cme": True,
                },
            )
        )
    for employee, branch_key, year in (
        ("H-DXB-001", "dubai", 2026),
        ("H-DXB-002", "dubai", 2026),
        ("H-DXB-003", "dubai", 2026),
        ("H-DXB-001", "dubai", 2025),
    ):
        emp = _EMP_BY_NO[employee]
        rows.append(
            Row(
                "cme_requirements",
                {
                    "id": _id("cme_requirements", emp.company, branch_key, employee, str(year)),
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "year": year,
                    "required_hours": Decimal("25.0"),
                },
            )
        )
    return rows


def _appraisal_rows() -> list[Row]:
    rows: list[Row] = []
    cycle_specs = [
        ("dubai", "2026 draft", "draft"),
        ("dubai", "2026 active", "active"),
        ("dubai", "2025 closed", "closed"),
        ("abu-dhabi", "2026 active", "active"),
        ("sharjah", "2026 active", "active"),
    ]
    cycles: dict[tuple[str, str], uuid.UUID] = {}
    for branch_key, name, status in cycle_specs:
        tenant, branch_id = _BRANCHES_BY_KEY[branch_key]
        cycle_id = _id("appraisal_cycles", tenant, branch_key, "none", name.replace(" ", "-"))
        cycles[(branch_key, name)] = cycle_id
        values: dict[str, Any] = {
            "id": cycle_id,
            "company_id": c.COMPANY_ID[tenant],
            "branch_id": branch_id,
            "name": name,
            "review_from": "2026-01-01" if name.startswith("2026") else "2025-01-01",
            "review_to": "2026-12-31" if name.startswith("2026") else "2025-12-31",
            "status": status,
        }
        if status == "closed":
            values["closed_by_app_user_id"] = c.ADMIN_APP_USER[tenant]
            values["closed_at"] = c.CLOCK_TIMESTAMP
        rows.append(Row("appraisal_cycles", values))

    appraisal_specs = [
        ("H-DXB-002", "dubai", "2026 draft", "pending", "unrated"),
        ("H-DXB-003", "dubai", "2026 active", "pending", "partially-rated"),
        ("H-DXB-004", "dubai", "2026 active", "reviewed", "golden-reviewed"),
        ("H-DXB-005", "dubai", "2026 active", "reviewed", "waiting-calibration"),
        ("H-DXB-006", "dubai", "2025 closed", "calibrated", "calibrated"),
        ("H-DXB-001", "dubai", "2026 active", "pending", "manager-own"),
        ("H-AUH-002", "abu-dhabi", "2026 active", "pending", "other-manager-report"),
        ("C-SHJ-002", "sharjah", "2026 active", "pending", "tenant-control"),
    ]
    appraisal_ids: dict[str, uuid.UUID] = {}
    for employee, branch_key, cycle_name, status, scenario in appraisal_specs:
        emp = _EMP_BY_NO[employee]
        appraisal_id = _id("appraisals", emp.company, branch_key, employee, scenario)
        appraisal_ids[scenario] = appraisal_id
        values: dict[str, Any] = {
            "id": appraisal_id,
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "cycle_id": cycles[(branch_key, cycle_name)],
            "employee_id": emp.id,
            "status": status,
        }
        if status != "pending":
            values["reviewed_by_app_user_id"] = c.ADMIN_APP_USER[emp.company]
            values["reviewed_at"] = c.CLOCK_TIMESTAMP
            values["overall_rating"] = (
                Decimal("3.8") if scenario == "golden-reviewed" else Decimal("4.0")
            )
        rows.append(Row("appraisals", values))

    golden_sections = [
        ("Clinical Competency", "4", "2.0"),
        ("Patient Care Quality", "5", "2.0"),
        ("Communication and Teamwork", "3", "1.5"),
        ("Punctuality and Attendance", "4", "1.0"),
        ("Professional Development", "2", "1.0"),
    ]
    for order, (name, rating, weight) in enumerate(golden_sections):
        rows.append(
            Row(
                "appraisal_sections",
                {
                    "id": _id(
                        "appraisal_sections",
                        c.HORIZON,
                        "dubai",
                        "H-DXB-004",
                        name.lower().replace(" ", "-"),
                    ),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "appraisal_id": appraisal_ids["golden-reviewed"],
                    "section_name": name,
                    "rating": Decimal(rating),
                    "weight": Decimal(weight),
                    "sort_order": order,
                },
            )
        )
    for scenario, employee, ratings in (
        ("unrated", "H-DXB-002", (None, None)),
        ("partially-rated", "H-DXB-003", ("4", None)),
    ):
        for order, rating in enumerate(ratings):
            values = {
                "id": _id(
                    "appraisal_sections", c.HORIZON, "dubai", employee, f"{scenario}-{order}"
                ),
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "appraisal_id": appraisal_ids[scenario],
                "section_name": f"Synthetic section {order + 1}",
                "weight": Decimal("1.0"),
                "sort_order": order,
            }
            if rating is not None:
                values["rating"] = Decimal(rating)
            rows.append(Row("appraisal_sections", values))
    return rows


def _asset_rows() -> list[Row]:
    specs = [
        (c.HORIZON, "dubai", "available", "DXB-AVAILABLE"),
        (c.HORIZON, "dubai", "assigned", "DXB-ASSIGNED"),
        (c.HORIZON, "abu-dhabi", "under_repair", "AUH-REPAIR"),
        (c.CEDAR, "sharjah", "retired", "SHJ-RETIRED"),
        (c.CEDAR, "dhcc", "lost", "DHC-LOST"),
        (c.CEDAR, "sharjah", "available", "SHJ-CONTROL"),
    ]
    rows: list[Row] = []
    ids: dict[str, uuid.UUID] = {}
    for tenant, branch_key, status, code in specs:
        _, branch_id = _BRANCHES_BY_KEY[branch_key]
        asset_id = _id("assets", tenant, branch_key, "none", code.lower())
        ids[code] = asset_id
        rows.append(
            Row(
                "assets",
                {
                    "id": asset_id,
                    "company_id": c.COMPANY_ID[tenant],
                    "branch_id": branch_id,
                    "name": f"Synthetic asset {code}",
                    "asset_code": code,
                    "category": "equipment",
                    "brand": "Test Brand",
                    "model": "Test Model",
                    "serial_number": f"SYNTH-{code}",
                    "purchase_cost": Decimal("1000.00"),
                    "status": status,
                },
            )
        )
    rows.extend(
        [
            Row(
                "asset_assignments",
                {
                    "id": _id("asset_assignments", c.HORIZON, "dubai", "H-DXB-002", "open"),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "asset_id": ids["DXB-ASSIGNED"],
                    "employee_id": _EMP_BY_NO["H-DXB-002"].id,
                    "assigned_date": "2026-08-01",
                    "condition_at_handover": "Good",
                    "assigned_by_app_user_id": c.ADMIN_APP_USER[c.HORIZON],
                },
            ),
            Row(
                "asset_assignments",
                {
                    "id": _id("asset_assignments", c.HORIZON, "dubai", "H-DXB-003", "returned"),
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_DXB,
                    "asset_id": ids["DXB-AVAILABLE"],
                    "employee_id": _EMP_BY_NO["H-DXB-003"].id,
                    "assigned_date": "2026-07-01",
                    "return_date": "2026-08-01",
                    "condition_at_handover": "Good",
                    "condition_at_return": "Good",
                    "assigned_by_app_user_id": c.ADMIN_APP_USER[c.HORIZON],
                },
            ),
        ]
    )
    return rows


def _incident_rows() -> list[Row]:
    incident_types = [
        "patient_safety",
        "medication_error",
        "injury",
        "needlestick",
        "infection",
        "equipment",
        "near_miss",
        "workplace",
        "other",
    ]
    branch_actors = [
        (c.HORIZON, "dubai", "H-DXB-001", "H-DXB-002"),
        (c.HORIZON, "abu-dhabi", "H-AUH-001", "H-AUH-002"),
        (c.CEDAR, "sharjah", "C-SHJ-001", "C-SHJ-002"),
        (c.CEDAR, "dhcc", "C-DHC-001", "C-DHC-002"),
    ]
    rows: list[Row] = []
    for index, incident_type in enumerate(incident_types):
        tenant, branch_key, reporter, involved = branch_actors[index % len(branch_actors)]
        _, branch_id = _BRANCHES_BY_KEY[branch_key]
        status = ("open", "investigating", "closed")[index % 3]
        severity = ("low", "moderate", "high", "critical")[index % 4]
        values: dict[str, Any] = {
            "id": _id("incident_reports", tenant, branch_key, reporter, incident_type),
            "company_id": c.COMPANY_ID[tenant],
            "branch_id": branch_id,
            "incident_date": f"2026-08-{index + 1:02d}",
            "incident_time": time(9, index),
            "location": "Synthetic clinic area",
            "department": "Clinical",
            "incident_type": incident_type,
            "severity": severity,
            "description": f"Synthetic {incident_type} incident",
            "reported_by_id": _EMP_BY_NO[reporter].id,
            "status": status,
        }
        if index % 2:
            values["involved_emp_id"] = _EMP_BY_NO[involved].id
        if status == "closed":
            values.update(
                {
                    "root_cause": "Synthetic root cause",
                    "corrective_action": "Synthetic corrective action",
                    "closed_date": "2026-08-20",
                    "closed_by_app_user_id": c.ADMIN_APP_USER[tenant],
                }
            )
        rows.append(Row("incident_reports", values))
    return rows


def _contract_offboarding_and_request_rows() -> list[Row]:
    rows: list[Row] = []
    for action, employee, branch_key in (
        ("new", "H-DXB-002", "dubai"),
        ("renewed", "H-DXB-003", "dubai"),
        ("converted", "H-AUH-002", "abu-dhabi"),
        ("not_renewed", "C-SHJ-002", "sharjah"),
    ):
        emp = _EMP_BY_NO[employee]
        rows.append(
            Row(
                "employee_contracts",
                {
                    "id": _id("employee_contracts", emp.company, branch_key, employee, action),
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "contract_type": "Limited" if action != "converted" else "Unlimited",
                    "start_date": "2026-01-01",
                    "end_date": None if action == "converted" else "2026-12-31",
                    "renewed_at": c.CLOCK_TIMESTAMP,
                    "renewed_by_app_user_id": c.ADMIN_APP_USER[emp.company],
                    "action": action,
                    "notes": f"Synthetic contract action {action}",
                },
            )
        )

    checklist_specs = [
        ("H-DXB-006", "dubai", "in_progress", "not_started"),
        ("H-DXB-005", "dubai", "completed", "cancelled"),
        ("H-AUH-003", "abu-dhabi", "in_progress", "initiated"),
        ("C-DHC-003", "dhcc", "in_progress", "submitted_gdrfa"),
    ]
    checklist_ids: dict[str, uuid.UUID] = {}
    for employee, branch_key, status, visa_status in checklist_specs:
        emp = _EMP_BY_NO[employee]
        checklist_id = _id("offboarding_checklists", emp.company, branch_key, employee, status)
        checklist_ids[employee] = checklist_id
        values: dict[str, Any] = {
            "id": checklist_id,
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "status": status,
            "visa_cancellation_status": visa_status,
        }
        if status == "completed":
            values["completed_at"] = c.CLOCK_TIMESTAMP
            values["completed_by_app_user_id"] = c.ADMIN_APP_USER[emp.company]
            values["visa_cancellation_date"] = "2026-08-20"
        rows.append(Row("offboarding_checklists", values))
    default_tasks = [
        "Return company property",
        "Cancel system access",
        "Settle payroll",
        "Cancel visa",
    ]
    for branch_key, (tenant, branch_id) in _BRANCHES_BY_KEY.items():
        for order, name in enumerate(default_tasks):
            rows.append(
                Row(
                    "offboarding_task_templates",
                    {
                        "id": _id(
                            "offboarding_task_templates",
                            tenant,
                            branch_key,
                            "none",
                            name.lower().replace(" ", "-"),
                        ),
                        "company_id": c.COMPANY_ID[tenant],
                        "branch_id": branch_id,
                        "task_name": name,
                        "default_order": order,
                    },
                )
            )
    task_specs = [
        ("H-DXB-006", "Return company property", True, 0),
        ("H-DXB-006", "Cancel system access", False, 1),
        ("H-DXB-006", "Synthetic custom exit interview", False, 2),
        ("H-DXB-005", "Return company property", True, 0),
        ("H-DXB-005", "Cancel system access", True, 1),
    ]
    for employee, name, completed, order in task_specs:
        emp = _EMP_BY_NO[employee]
        values = {
            "id": _id(
                "offboarding_tasks", emp.company, "dubai", employee, name.lower().replace(" ", "-")
            ),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "checklist_id": checklist_ids[employee],
            "task_name": name,
            "completed": completed,
            "sort_order": order,
        }
        if completed:
            values["completed_at"] = c.CLOCK_TIMESTAMP
            values["completed_by_app_user_id"] = c.ADMIN_APP_USER[emp.company]
        rows.append(Row("offboarding_tasks", values))

    letter_specs = [
        ("H-DXB-002", "dubai", "letter", "salary_certificate_bank", "pending"),
        ("H-DXB-003", "dubai", "letter", "salary_certificate_embassy", "completed"),
        ("H-DXB-004", "dubai", "letter", "noc", "rejected"),
        ("H-AUH-002", "abu-dhabi", "letter", "salary_transfer_letter", "completed"),
        ("C-SHJ-002", "sharjah", "letter", "employment_confirmation", "pending"),
        ("C-DHC-002", "dhcc", "custom", "Custom shift confirmation", "pending"),
    ]
    for employee, branch_key, request_kind, letter_type, status in letter_specs:
        emp = _EMP_BY_NO[employee]
        values = {
            "id": _id(
                "letter_requests",
                emp.company,
                branch_key,
                employee,
                letter_type.lower().replace(" ", "-"),
            ),
            "company_id": c.COMPANY_ID[emp.company],
            "branch_id": emp.branch,
            "employee_id": emp.id,
            "request_kind": request_kind,
            "letter_type": letter_type,
            "purpose": "Synthetic bank application"
            if request_kind == "letter"
            else "Confirm the synthetic shift arrangement",
            "status": status,
            "requested_at": c.CLOCK_TIMESTAMP,
        }
        if status in {"completed", "rejected"}:
            values["actioned_at"] = c.CLOCK_TIMESTAMP
            values["actioned_by_app_user_id"] = c.ADMIN_APP_USER[emp.company]
        if status == "completed":
            values["completed_at"] = c.CLOCK_TIMESTAMP
        if status == "rejected":
            values["rejection_reason"] = "The request needs a revised purpose"
        rows.append(Row("letter_requests", values))
    return rows


def _roster_and_swap_rows() -> list[Row]:
    rows: list[Row] = []
    for branch_key, employee in (
        ("abu-dhabi", "H-AUH-001"),
        ("sharjah", "C-SHJ-001"),
        ("dhcc", "C-DHC-001"),
    ):
        emp = _EMP_BY_NO[employee]
        shift_id = _id("shifts", emp.company, branch_key, "none", "M")
        rows.append(
            Row(
                "shifts",
                {
                    "id": shift_id,
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "name": "Morning",
                    "code": "M",
                    "shift_type": "fixed",
                    "shift_category": "morning",
                    "start_time": time(8),
                    "end_time": time(17),
                    "break_minutes": 60,
                    "expected_hours": Decimal("8.00"),
                },
            )
        )
    roster_specs = [
        ("H-DXB-001", "dubai", "2026-08-29", True, "published-same-code"),
        ("H-DXB-005", "dubai", "2026-08-30", False, "unpublished-edit"),
        ("H-AUH-001", "abu-dhabi", "2026-08-29", True, "published-same-code"),
        ("H-AUH-002", "abu-dhabi", "2026-08-30", True, "leave-conflict"),
        ("C-SHJ-001", "sharjah", "2026-08-29", True, "published-same-code"),
        ("C-SHJ-002", "sharjah", "2026-08-30", True, "swap-source"),
        ("C-DHC-001", "dhcc", "2026-08-29", True, "published-same-code"),
        ("C-DHC-002", "dhcc", "2026-08-30", True, "swap-source"),
    ]
    for employee, branch_key, day, published, scenario in roster_specs:
        emp = _EMP_BY_NO[employee]
        shift_id = (
            c.derive("shifts", c.HORIZON, "dubai", None, "M")
            if branch_key == "dubai"
            else _id("shifts", emp.company, branch_key, "none", "M")
        )
        rows.append(
            Row(
                "roster_assignments",
                {
                    "id": _id("roster_assignments", emp.company, branch_key, employee, scenario),
                    "company_id": c.COMPANY_ID[emp.company],
                    "branch_id": emp.branch,
                    "employee_id": emp.id,
                    "shift_id": shift_id,
                    "date": day,
                    "published": published,
                    "planned_hours": Decimal("8.00"),
                    "notes": scenario.replace("-", " "),
                },
            )
        )
    swap_specs = [
        ("H-DXB-002", "H-DXB-005", "dubai", "pending", None),
        ("H-AUH-002", "H-AUH-001", "abu-dhabi", "approved", None),
        ("C-SHJ-002", "C-SHJ-001", "sharjah", "rejected", "Staffing coverage is insufficient"),
    ]
    for requester, target, branch_key, status, rejection in swap_specs:
        req = _EMP_BY_NO[requester]
        values: dict[str, Any] = {
            "id": _id("shift_swap_requests", req.company, branch_key, requester, status),
            "company_id": c.COMPANY_ID[req.company],
            "branch_id": req.branch,
            "requester_employee_id": req.id,
            "target_employee_id": _EMP_BY_NO[target].id,
            "requester_date": "2026-08-30" if requester != "H-DXB-002" else "2026-08-28",
            "target_date": "2026-08-29",
            "reason": "Synthetic shift swap",
            "status": status,
        }
        if status in {"approved", "rejected"}:
            values["admin_approved_at"] = c.CLOCK_TIMESTAMP
            values["admin_approved_by_app_user_id"] = c.ADMIN_APP_USER[req.company]
        if rejection:
            values["rejection_reason"] = rejection
        rows.append(Row("shift_swap_requests", values))
    return rows


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
    rows += _roster_and_swap_rows()
    rows += _payroll_runs()
    rows += _payroll_entries()
    rows += _advances()
    rows += _advance_repayments()
    rows += _expense_claims()
    rows += _financial_status_rows()
    rows += _roster_assignments()
    rows += _leave_foundation()
    rows += _leave_rows()
    rows += _attendance_rows()
    rows += _document_and_benefit_rows()
    rows += _training_and_cme_rows()
    rows += _appraisal_rows()
    rows += _asset_rows()
    rows += _incident_rows()
    rows += _contract_offboarding_and_request_rows()
    rows += _notification_rows()
    return rows


TENANT_COMPANY_IDS = tuple(c.COMPANY_ID.values())

# Phase 0 cases that are payloads or calculations, not database rows.
NON_PERSISTED_SCENARIOS = (
    "leave.overlap",
    "leave.insufficient-balance",
    "leave.probation-ineligible",
    "attendance.unknown-biometric-badge",
    "attendance.duplicate-biometric-punch",
    "payroll.missing-mol-id",
    "payroll.invalid-iban",
    "expense.future-dated-request",
    "files.oversize-rejected",
    "files.executable-extension-rejected",
    "letter.custom-subject-invalid-low",
    "letter.custom-subject-valid-low",
    "letter.custom-subject-valid-high",
    "letter.custom-subject-invalid-high",
    "letter.custom-details-invalid-low",
    "letter.custom-details-valid-low",
    "letter.custom-details-valid-high",
    "letter.custom-details-invalid-high",
    "offboarding.gratuity-under-one-year",
    "offboarding.gratuity-two-years-termination",
    "offboarding.gratuity-four-years-termination",
    "offboarding.gratuity-six-years-termination",
    "offboarding.gratuity-two-years-resignation",
    "offboarding.gratuity-four-years-resignation",
    "offboarding.gratuity-cap",
    "offboarding.final-settlement",
)

# These controls have persisted rows on both sides. Phase 5 will execute the
# authenticated authorization attempts; Phase 4E verifies scoped query inputs
# and composite foreign-key rejection.
NEGATIVE_CONTROL_MATRIX = (
    "horizon-admin.cedar-employee",
    "horizon-admin.cedar-payroll",
    "horizon-admin.replace-cedar-payroll",
    "horizon-admin.repay-cedar-advance",
    "horizon-admin.approve-cedar-swap",
    "aisha.approve-omar-report-leave",
    "aisha.act-on-priya-report-expense",
    "aisha.rate-leila-or-cedar-appraisal",
    "ravi.other-employee-records",
    "ravi.other-employee-storage-folder",
    "ravi.delete-approved-expense",
    "ravi.cancel-active-or-settled-advance",
    "ravi.request-cedar-swap",
    "dubai-view.abu-dhabi-core",
    "dubai-view.abu-dhabi-supporting",
    "leila.explicit-abu-dhabi-company-resolution",
    "caller.expired-signed-url",
    "horizon-user.cedar-object-path",
    "aisha.manager-reassignment",
)

RETIRED_OR_REPLACED_SCENARIOS = {
    "legacy-null-company-employee": "omitted: employees require company and branch scope",
    "legacy-storage-object-row": (
        "replaced: domain metadata only; private object storage is later work"
    ),
    "biometric-api-clock-method": "replaced: BIOMETRIC is the approved target value",
    "stale-task-doc-type": "replaced: employee_documents.document_type",
    "stale-task-eid-expiry": "replaced: employees.emirates_id_expiry",
    "stale-task-payroll-month-year": "replaced: payroll_runs.period",
}
