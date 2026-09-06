import uuid
from datetime import date
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import ClauseElement

from app.auth.application_user import AuthorizationPrincipal
from app.auth.scopes import (
    AuthorizationScopeError,
    active_leave_delegate_authorization_scope,
    active_leave_delegate_scope_predicate,
    branch_authorization_scope,
    branch_scope_predicate,
    direct_report_authorization_scope,
    direct_report_scope_predicate,
    employee_self_authorization_scope,
    employee_self_scope_predicate,
    expiry_processing_authorization_scope,
    expiry_processing_scope_predicate,
    tenant_authorization_scope,
    tenant_scope_predicate,
)
from app.db.seed import constants as fixture_ids
from app.models.identity import AccountStatus, AppRole, Employee
from app.models.leave import LeaveRequest

HORIZON_MANAGER_ID = uuid.UUID("21000000-0000-4000-8000-000000000001")
HORIZON_EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
HORIZON_DELEGATE_ID = uuid.UUID("21000000-0000-4000-8000-000000000005")


def principal(
    role: AppRole,
    *,
    company_id: uuid.UUID = fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
    employee_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=uuid.uuid4(),
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=company_id,
        employee_id=employee_id,
        branch_id=branch_id,
    )


def compiled_parameters(statement: ClauseElement) -> dict[str, object]:
    compiled = statement.compile(dialect=postgresql.dialect())
    return cast(dict[str, object], compiled.params)


def compiled_sql(statement: ClauseElement) -> str:
    compiled = statement.compile(dialect=postgresql.dialect())
    return str(compiled)


def test_tenant_and_admin_branch_scopes_use_database_derived_company() -> None:
    admin = principal(AppRole.ADMIN)
    tenant_scope = tenant_authorization_scope(admin)
    branch_scope = branch_authorization_scope(
        admin,
        verified_admin_branch_id=fixture_ids.BRANCH_DXB,
    )
    statement = select(LeaveRequest.__table__.c.id).where(
        tenant_scope_predicate(LeaveRequest.__table__.c.company_id, tenant_scope),
        branch_scope_predicate(
            LeaveRequest.__table__.c.company_id,
            LeaveRequest.__table__.c.branch_id,
            branch_scope,
        ),
    )

    parameters = compiled_parameters(statement)
    assert fixture_ids.COMPANY_ID[fixture_ids.HORIZON] in parameters.values()
    assert fixture_ids.BRANCH_DXB in parameters.values()


def test_admin_branch_scope_fails_closed_without_verified_selector() -> None:
    with pytest.raises(AuthorizationScopeError):
        branch_authorization_scope(principal(AppRole.ADMIN))


def test_staff_cannot_replace_linked_branch_with_admin_selector() -> None:
    manager = principal(
        AppRole.MANAGER,
        employee_id=HORIZON_MANAGER_ID,
        branch_id=fixture_ids.BRANCH_DXB,
    )
    with pytest.raises(AuthorizationScopeError):
        branch_authorization_scope(
            manager,
            verified_admin_branch_id=fixture_ids.BRANCH_AUH,
        )


def test_employee_self_scope_matches_company_branch_and_employee() -> None:
    employee = principal(
        AppRole.EMPLOYEE,
        employee_id=HORIZON_EMPLOYEE_ID,
        branch_id=fixture_ids.BRANCH_DXB,
    )
    scope = employee_self_authorization_scope(employee)
    statement = select(LeaveRequest.__table__.c.id).where(
        employee_self_scope_predicate(
            LeaveRequest.__table__.c.company_id,
            LeaveRequest.__table__.c.branch_id,
            LeaveRequest.__table__.c.employee_id,
            scope,
        )
    )

    parameters = compiled_parameters(statement)
    assert fixture_ids.COMPANY_ID[fixture_ids.HORIZON] in parameters.values()
    assert fixture_ids.BRANCH_DXB in parameters.values()
    assert HORIZON_EMPLOYEE_ID in parameters.values()


def test_direct_report_scope_rechecks_the_current_relationship() -> None:
    manager = principal(
        AppRole.MANAGER,
        employee_id=HORIZON_MANAGER_ID,
        branch_id=fixture_ids.BRANCH_DXB,
    )
    scope = direct_report_authorization_scope(manager)
    statement = select(LeaveRequest.__table__.c.id).where(
        direct_report_scope_predicate(LeaveRequest.__table__.c.employee_id, scope)
    )

    sql = compiled_sql(statement)
    parameters = compiled_parameters(statement)
    assert "EXISTS" in sql
    assert "scope_direct_report.reporting_manager_id" in sql
    assert "scope_direct_report.id = leave_requests.employee_id" in sql
    assert HORIZON_MANAGER_ID in parameters.values()
    assert HORIZON_EMPLOYEE_ID not in parameters.values()


def test_non_manager_cannot_receive_direct_report_scope() -> None:
    employee = principal(
        AppRole.EMPLOYEE,
        employee_id=HORIZON_EMPLOYEE_ID,
        branch_id=fixture_ids.BRANCH_DXB,
    )
    with pytest.raises(AuthorizationScopeError):
        direct_report_authorization_scope(employee)


def test_leave_delegate_scope_rechecks_dates_approver_and_current_report() -> None:
    delegate = principal(
        AppRole.EMPLOYEE,
        employee_id=HORIZON_DELEGATE_ID,
        branch_id=fixture_ids.BRANCH_DXB,
    )
    scope = active_leave_delegate_authorization_scope(
        delegate,
        business_date=fixture_ids.TODAY,
    )
    statement = select(LeaveRequest.__table__.c.id).where(
        active_leave_delegate_scope_predicate(LeaveRequest.__table__.c.employee_id, scope)
    )

    sql = compiled_sql(statement)
    parameters = compiled_parameters(statement)
    assert "scope_leave_delegation.from_date <=" in sql
    assert "scope_leave_delegation.to_date >=" in sql
    assert "scope_delegated_report.reporting_manager_id = scope_leave_approver.id" in sql
    assert "scope_leave_approver_user.status" in sql
    assert "scope_leave_approver_profile.role" in sql
    assert "scope_leave_delegate_user.status" in sql
    assert "scope_leave_delegate_profile.role" in sql
    assert "scope_leave_delegate.active IS true" in sql
    assert fixture_ids.TODAY in parameters.values()
    assert HORIZON_DELEGATE_ID in parameters.values()


@pytest.mark.parametrize(
    "business_date",
    [date(2025, 1, 1), date(2027, 1, 1)],
)
def test_delegate_business_date_is_always_a_bound_value(business_date: date) -> None:
    delegate = principal(
        AppRole.EMPLOYEE,
        employee_id=HORIZON_DELEGATE_ID,
        branch_id=fixture_ids.BRANCH_DXB,
    )
    scope = active_leave_delegate_authorization_scope(delegate, business_date=business_date)
    statement = select(LeaveRequest.__table__.c.id).where(
        active_leave_delegate_scope_predicate(LeaveRequest.__table__.c.employee_id, scope)
    )

    assert business_date in compiled_parameters(statement).values()
    assert business_date.isoformat() not in compiled_sql(statement)


def test_expiry_scope_requires_the_dedicated_database_actor() -> None:
    with pytest.raises(AuthorizationScopeError):
        expiry_processing_authorization_scope(
            database_actor="workloop_runtime",
            company_id=fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
            branch_id=fixture_ids.BRANCH_DXB,
            business_date=fixture_ids.TODAY,
        )


def test_expiry_scope_is_limited_to_one_company_and_branch() -> None:
    scope = expiry_processing_authorization_scope(
        database_actor="workloop_expiry_processing",
        company_id=fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
        branch_id=fixture_ids.BRANCH_DXB,
        business_date=fixture_ids.TODAY,
    )
    statement = select(Employee.__table__.c.id).where(
        expiry_processing_scope_predicate(
            Employee.__table__.c.company_id,
            scope,
            branch_column=Employee.__table__.c.branch_id,
        )
    )

    parameters = compiled_parameters(statement)
    assert fixture_ids.COMPANY_ID[fixture_ids.HORIZON] in parameters.values()
    assert fixture_ids.BRANCH_DXB in parameters.values()
    assert fixture_ids.COMPANY_ID[fixture_ids.CEDAR] not in parameters.values()


def test_tenant_only_expiry_scope_rejects_branch_owned_rows() -> None:
    scope = expiry_processing_authorization_scope(
        database_actor="workloop_expiry_processing",
        company_id=fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
        branch_id=None,
        business_date=fixture_ids.TODAY,
    )
    statement = select(Employee.__table__.c.id).where(
        expiry_processing_scope_predicate(
            Employee.__table__.c.company_id,
            scope,
            branch_column=Employee.__table__.c.branch_id,
        )
    )

    assert "employees.branch_id IS NULL" in compiled_sql(statement)
