import enum
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import ColumnElement, and_, exists, literal, or_, select
from sqlalchemy.sql.elements import SQLColumnExpression

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole, AppUser, Employee, UserProfile
from app.models.leave import LeaveApprovalDelegate

ELIGIBLE_EMPLOYMENT_STATUSES = ("Active", "Probation", "On Leave")


class AuthorizationScopeError(ValueError):
    pass


class SystemActor(enum.StrEnum):
    EXPIRY_PROCESSING = "workloop_expiry_processing"


@dataclass(frozen=True, slots=True)
class TenantAuthorizationScope:
    company_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class BranchAuthorizationScope:
    company_id: uuid.UUID
    branch_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class EmployeeSelfAuthorizationScope:
    company_id: uuid.UUID
    branch_id: uuid.UUID
    employee_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class DirectReportAuthorizationScope:
    manager_app_user_id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    manager_employee_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ActiveLeaveDelegateAuthorizationScope:
    delegate_app_user_id: uuid.UUID
    company_id: uuid.UUID
    branch_id: uuid.UUID
    delegate_employee_id: uuid.UUID
    business_date: date


@dataclass(frozen=True, slots=True)
class ExpiryProcessingAuthorizationScope:
    actor: SystemActor
    company_id: uuid.UUID
    branch_id: uuid.UUID | None
    business_date: date


def _require_active_principal(principal: AuthorizationPrincipal) -> None:
    if principal.account_status is not AccountStatus.ACTIVE:
        raise AuthorizationScopeError("authorization principal is not active")


def tenant_authorization_scope(
    principal: AuthorizationPrincipal,
) -> TenantAuthorizationScope:
    _require_active_principal(principal)
    return TenantAuthorizationScope(company_id=principal.company_id)


def branch_authorization_scope(
    principal: AuthorizationPrincipal,
    *,
    verified_admin_branch_id: uuid.UUID | None = None,
) -> BranchAuthorizationScope:
    _require_active_principal(principal)
    if principal.role is AppRole.ADMIN:
        if verified_admin_branch_id is None:
            raise AuthorizationScopeError("an admin branch scope requires a verified branch")
        return BranchAuthorizationScope(
            company_id=principal.company_id,
            branch_id=verified_admin_branch_id,
        )
    if verified_admin_branch_id is not None:
        raise AuthorizationScopeError("staff cannot select an admin branch")
    if (
        principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
        or principal.employee_id is None
        or principal.branch_id is None
    ):
        raise AuthorizationScopeError("the principal has no staff branch scope")
    return BranchAuthorizationScope(
        company_id=principal.company_id,
        branch_id=principal.branch_id,
    )


def employee_self_authorization_scope(
    principal: AuthorizationPrincipal,
) -> EmployeeSelfAuthorizationScope:
    branch_scope = branch_authorization_scope(principal)
    if principal.employee_id is None:
        raise AuthorizationScopeError("the principal has no employee identity")
    return EmployeeSelfAuthorizationScope(
        company_id=branch_scope.company_id,
        branch_id=branch_scope.branch_id,
        employee_id=principal.employee_id,
    )


def direct_report_authorization_scope(
    principal: AuthorizationPrincipal,
) -> DirectReportAuthorizationScope:
    if principal.role is not AppRole.MANAGER:
        raise AuthorizationScopeError("direct-report scope requires a manager")
    branch_scope = branch_authorization_scope(principal)
    if principal.employee_id is None:
        raise AuthorizationScopeError("the manager has no employee identity")
    return DirectReportAuthorizationScope(
        manager_app_user_id=principal.app_user_id,
        company_id=branch_scope.company_id,
        branch_id=branch_scope.branch_id,
        manager_employee_id=principal.employee_id,
    )


def active_leave_delegate_authorization_scope(
    principal: AuthorizationPrincipal,
    *,
    business_date: date,
) -> ActiveLeaveDelegateAuthorizationScope:
    if principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}:
        raise AuthorizationScopeError("leave delegation requires a staff principal")
    branch_scope = branch_authorization_scope(principal)
    if principal.employee_id is None:
        raise AuthorizationScopeError("the delegate has no employee identity")
    return ActiveLeaveDelegateAuthorizationScope(
        delegate_app_user_id=principal.app_user_id,
        company_id=branch_scope.company_id,
        branch_id=branch_scope.branch_id,
        delegate_employee_id=principal.employee_id,
        business_date=business_date,
    )


def expiry_processing_authorization_scope(
    *,
    database_actor: str,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    business_date: date,
) -> ExpiryProcessingAuthorizationScope:
    try:
        actor = SystemActor(database_actor)
    except ValueError:
        raise AuthorizationScopeError("unapproved system actor") from None
    return ExpiryProcessingAuthorizationScope(
        actor=actor,
        company_id=company_id,
        branch_id=branch_id,
        business_date=business_date,
    )


def tenant_scope_predicate(
    company_column: SQLColumnExpression[uuid.UUID],
    scope: TenantAuthorizationScope,
) -> ColumnElement[bool]:
    return company_column == scope.company_id


def branch_scope_predicate(
    company_column: SQLColumnExpression[uuid.UUID],
    branch_column: SQLColumnExpression[uuid.UUID],
    scope: BranchAuthorizationScope,
) -> ColumnElement[bool]:
    return and_(
        company_column == scope.company_id,
        branch_column == scope.branch_id,
    )


def employee_self_scope_predicate(
    company_column: SQLColumnExpression[uuid.UUID],
    branch_column: SQLColumnExpression[uuid.UUID],
    employee_column: SQLColumnExpression[uuid.UUID],
    scope: EmployeeSelfAuthorizationScope,
) -> ColumnElement[bool]:
    return and_(
        company_column == scope.company_id,
        branch_column == scope.branch_id,
        employee_column == scope.employee_id,
    )


def direct_report_scope_predicate(
    employee_column: SQLColumnExpression[uuid.UUID],
    scope: DirectReportAuthorizationScope,
) -> ColumnElement[bool]:
    reports = Employee.__table__.alias("scope_direct_report")
    managers = Employee.__table__.alias("scope_current_manager")
    profiles = UserProfile.__table__.alias("scope_current_manager_profile")
    app_users = AppUser.__table__.alias("scope_current_manager_user")
    source = (
        reports.join(
            managers,
            and_(
                managers.c.id == reports.c.reporting_manager_id,
                managers.c.company_id == reports.c.company_id,
                managers.c.branch_id == reports.c.branch_id,
            ),
        )
        .join(
            profiles,
            and_(
                profiles.c.employee_id == managers.c.id,
                profiles.c.company_id == managers.c.company_id,
                profiles.c.role == AppRole.MANAGER,
            ),
        )
        .join(
            app_users,
            and_(
                app_users.c.id == profiles.c.app_user_id,
                app_users.c.id == scope.manager_app_user_id,
                app_users.c.status == AccountStatus.ACTIVE,
            ),
        )
    )
    return exists(
        select(literal(1))
        .select_from(source)
        .where(
            reports.c.id == employee_column,
            reports.c.company_id == scope.company_id,
            reports.c.branch_id == scope.branch_id,
            reports.c.reporting_manager_id == scope.manager_employee_id,
            managers.c.active.is_(True),
            managers.c.employment_status.in_(ELIGIBLE_EMPLOYMENT_STATUSES),
        )
    )


def active_leave_delegate_scope_predicate(
    employee_column: SQLColumnExpression[uuid.UUID],
    scope: ActiveLeaveDelegateAuthorizationScope,
) -> ColumnElement[bool]:
    delegations = LeaveApprovalDelegate.__table__.alias("scope_leave_delegation")
    approvers = Employee.__table__.alias("scope_leave_approver")
    reports = Employee.__table__.alias("scope_delegated_report")
    delegates = Employee.__table__.alias("scope_leave_delegate")
    profiles = UserProfile.__table__.alias("scope_leave_approver_profile")
    app_users = AppUser.__table__.alias("scope_leave_approver_user")
    delegate_profiles = UserProfile.__table__.alias("scope_leave_delegate_profile")
    delegate_users = AppUser.__table__.alias("scope_leave_delegate_user")

    source = (
        delegations.join(
            approvers,
            and_(
                approvers.c.id == delegations.c.approver_employee_id,
                approvers.c.company_id == delegations.c.company_id,
                approvers.c.branch_id == delegations.c.branch_id,
            ),
        )
        .join(
            reports,
            and_(
                reports.c.id == employee_column,
                reports.c.company_id == delegations.c.company_id,
                reports.c.branch_id == delegations.c.branch_id,
                reports.c.reporting_manager_id == approvers.c.id,
            ),
        )
        .join(
            delegates,
            and_(
                delegates.c.id == delegations.c.delegate_employee_id,
                delegates.c.company_id == delegations.c.company_id,
                delegates.c.branch_id == delegations.c.branch_id,
            ),
        )
        .join(
            profiles,
            and_(
                profiles.c.employee_id == approvers.c.id,
                profiles.c.company_id == delegations.c.company_id,
                profiles.c.role == AppRole.MANAGER,
            ),
        )
        .join(
            app_users,
            and_(
                app_users.c.id == profiles.c.app_user_id,
                app_users.c.status == AccountStatus.ACTIVE,
            ),
        )
        .join(
            delegate_profiles,
            and_(
                delegate_profiles.c.employee_id == delegates.c.id,
                delegate_profiles.c.company_id == delegations.c.company_id,
                delegate_profiles.c.role.in_((AppRole.MANAGER, AppRole.EMPLOYEE)),
            ),
        )
        .join(
            delegate_users,
            and_(
                delegate_users.c.id == delegate_profiles.c.app_user_id,
                delegate_users.c.id == scope.delegate_app_user_id,
                delegate_users.c.status == AccountStatus.ACTIVE,
            ),
        )
    )
    return exists(
        select(literal(1))
        .select_from(source)
        .where(
            delegations.c.company_id == scope.company_id,
            delegations.c.branch_id == scope.branch_id,
            delegations.c.delegate_employee_id == scope.delegate_employee_id,
            delegations.c.from_date <= scope.business_date,
            delegations.c.to_date >= scope.business_date,
            approvers.c.active.is_(True),
            approvers.c.employment_status.in_(ELIGIBLE_EMPLOYMENT_STATUSES),
            delegates.c.active.is_(True),
            delegates.c.employment_status.in_(ELIGIBLE_EMPLOYMENT_STATUSES),
        )
    )


def manager_or_delegate_scope_predicate(
    employee_column: SQLColumnExpression[uuid.UUID],
    manager_scope: DirectReportAuthorizationScope,
    delegate_scope: ActiveLeaveDelegateAuthorizationScope,
) -> ColumnElement[bool]:
    if (
        manager_scope.company_id != delegate_scope.company_id
        or manager_scope.branch_id != delegate_scope.branch_id
        or manager_scope.manager_employee_id != delegate_scope.delegate_employee_id
        or manager_scope.manager_app_user_id != delegate_scope.delegate_app_user_id
    ):
        raise AuthorizationScopeError("manager and delegate scopes name different principals")
    return or_(
        direct_report_scope_predicate(employee_column, manager_scope),
        active_leave_delegate_scope_predicate(employee_column, delegate_scope),
    )


def expiry_processing_scope_predicate(
    company_column: SQLColumnExpression[uuid.UUID],
    scope: ExpiryProcessingAuthorizationScope,
    *,
    branch_column: SQLColumnExpression[uuid.UUID | None] | None = None,
) -> ColumnElement[bool]:
    predicates: list[ColumnElement[bool]] = [company_column == scope.company_id]
    if branch_column is not None:
        if scope.branch_id is None:
            predicates.append(branch_column.is_(None))
        else:
            predicates.append(branch_column == scope.branch_id)
    return and_(*predicates)
