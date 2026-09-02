from app.db.base import NAMING_CONVENTION, Base
from app.models.identity import AccountStatus, AppRole

PHASE_4_TARGET_TABLES = frozenset(
    {
        # Phase 4B identity and organization
        "companies",
        "branches",
        "employees",
        "app_users",
        "user_profiles",
        # Phase 4C people and organization
        "employee_job_history",
        "departments",
        "department_staffing_rules",
        # Phase 4C payroll, finance, and compliance
        "payroll_runs",
        "payroll_entries",
        "payslips",
        "payroll_approval_log",
        "nafis_reports",
        "salary_advances",
        "advance_repayments",
        "expense_claims",
        "compliance_overrides",
        # Phase 4C leave
        "leave_settings",
        "leave_types",
        "public_holidays",
        "leave_requests",
        "leave_audit_log",
        "leave_balances",
        "leave_approval_delegates",
        # Phase 4C attendance and roster
        "attendance_settings",
        "shifts",
        "shift_assignments",
        "clock_events",
        "attendance_records",
        "attendance_periods",
        "regularisation_requests",
        "attendance_audit_log",
        "roster_assignments",
        "shift_swap_requests",
        "biometric_mappings",
        # Phase 4C documents, benefits, people operations, and clinical
        "employee_documents",
        "insurance_policies",
        "employee_insurance",
        "insurance_dependants",
        "notifications",
        "employee_contracts",
        "offboarding_checklists",
        "offboarding_tasks",
        "offboarding_task_templates",
        "assets",
        "asset_assignments",
        "training_records",
        "certifications",
        "appraisal_cycles",
        "appraisals",
        "appraisal_sections",
        "cme_requirements",
        "incident_reports",
        "letter_requests",
    }
)


def test_metadata_contains_exactly_the_phase_4_target_tables() -> None:
    assert len(PHASE_4_TARGET_TABLES) == 54
    assert set(Base.metadata.tables) == PHASE_4_TARGET_TABLES


def test_foundation_metadata_has_deterministic_constraint_names() -> None:
    assert NAMING_CONVENTION == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }


def test_identity_enums_match_the_approved_design() -> None:
    assert [status.value for status in AccountStatus] == [
        "pending_identity",
        "active",
        "disabled",
    ]
    assert [role.value for role in AppRole] == ["admin", "manager", "employee"]
