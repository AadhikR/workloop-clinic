import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.auth.access_token import AccessTokenClaims, AccessTokenError, AccessTokenVerifier
from app.auth.application_user import (
    ApplicationUserLookupError,
    ApplicationUserResolver,
    ApplicationUserUnavailableError,
    AuthorizationPrincipal,
    BranchUnavailableError,
)
from app.models.identity import AppRole

logger = logging.getLogger(__name__)


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_access_token",
            "message": "Authentication required",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_access_token(request: Request) -> AccessTokenClaims:
    authorization_values = request.headers.getlist("authorization")
    if len(authorization_values) != 1:
        raise authentication_error()
    authorization = authorization_values[0]
    if authorization.count(" ") != 1:
        raise authentication_error()
    scheme, token = authorization.split(" ", maxsplit=1)
    if scheme.lower() != "bearer" or not token or any(character.isspace() for character in token):
        raise authentication_error()

    verifier: AccessTokenVerifier = request.app.state.access_token_verifier
    try:
        return await verifier.verify(token)
    except AccessTokenError:
        raise authentication_error() from None


VerifiedAccessToken = Annotated[AccessTokenClaims, Depends(require_access_token)]


def application_account_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "application_account_unavailable",
            "message": "Application account unavailable",
        },
    )


def application_account_lookup_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "application_account_lookup_unavailable",
            "message": "Service temporarily unavailable",
        },
    )


def operation_not_permitted_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "operation_not_permitted",
            "message": "Operation not permitted",
        },
    )


def branch_required_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "branch_required",
            "message": "Branch selection required",
        },
    )


def invalid_branch_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "code": "invalid_branch",
            "message": "Invalid branch selection",
        },
    )


def resource_not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "resource_not_found",
            "message": "Resource not found",
        },
    )


async def require_authorization_principal(
    request: Request,
    claims: VerifiedAccessToken,
) -> AuthorizationPrincipal:
    resolver: ApplicationUserResolver = request.app.state.application_user_resolver
    try:
        return await resolver.resolve(issuer=claims.issuer, subject=claims.subject)
    except ApplicationUserUnavailableError:
        raise application_account_error() from None
    except ApplicationUserLookupError:
        logger.warning("application_user_lookup_failed")
        raise application_account_lookup_error() from None


require_application_user = require_authorization_principal
AuthenticatedAuthorizationPrincipal = Annotated[
    AuthorizationPrincipal, Depends(require_authorization_principal)
]
VerifiedApplicationUser = AuthenticatedAuthorizationPrincipal


def require_roles(
    *allowed_roles: AppRole,
) -> Callable[[AuthenticatedAuthorizationPrincipal], Awaitable[AuthorizationPrincipal]]:
    approved_roles = frozenset(allowed_roles)
    if not approved_roles or not approved_roles.issubset(set(AppRole)):
        raise ValueError("allowed_roles must contain approved Workloop roles")

    async def require_approved_role(
        principal: AuthenticatedAuthorizationPrincipal,
    ) -> AuthorizationPrincipal:
        if principal.role not in approved_roles:
            raise operation_not_permitted_error()
        return principal

    return require_approved_role


require_staff_principal = require_roles(AppRole.MANAGER, AppRole.EMPLOYEE)
require_manager_principal = require_roles(AppRole.MANAGER)
require_admin_principal = require_roles(AppRole.ADMIN)

StaffAuthorizationPrincipal = Annotated[AuthorizationPrincipal, Depends(require_staff_principal)]
ManagerAuthorizationPrincipal = Annotated[
    AuthorizationPrincipal, Depends(require_manager_principal)
]
AdminAuthorizationPrincipal = Annotated[AuthorizationPrincipal, Depends(require_admin_principal)]


async def require_tenant_scope(principal: AuthenticatedAuthorizationPrincipal) -> uuid.UUID:
    return principal.company_id


async def require_employee_self_identity(principal: StaffAuthorizationPrincipal) -> uuid.UUID:
    if principal.employee_id is None or principal.branch_id is None:
        raise operation_not_permitted_error()
    return principal.employee_id


async def require_manager_identity(principal: ManagerAuthorizationPrincipal) -> uuid.UUID:
    if principal.employee_id is None or principal.branch_id is None:
        raise operation_not_permitted_error()
    return principal.employee_id


async def require_admin_selected_branch(
    request: Request,
    principal: AdminAuthorizationPrincipal,
) -> uuid.UUID:
    header_values = request.headers.getlist("x-workloop-branch-id")
    if not header_values:
        raise branch_required_error()
    if len(header_values) != 1:
        raise invalid_branch_error()
    raw_branch_id = header_values[0]
    if not raw_branch_id or raw_branch_id != raw_branch_id.strip():
        raise invalid_branch_error()
    try:
        branch_id = uuid.UUID(raw_branch_id)
    except (AttributeError, ValueError):
        raise invalid_branch_error() from None

    resolver: ApplicationUserResolver = request.app.state.application_user_resolver
    try:
        return await resolver.resolve_admin_branch(
            company_id=principal.company_id,
            branch_id=branch_id,
        )
    except BranchUnavailableError:
        raise resource_not_found_error() from None
    except ApplicationUserLookupError:
        logger.warning("authorization_scope_lookup_failed")
        raise application_account_lookup_error() from None


TenantScope = Annotated[uuid.UUID, Depends(require_tenant_scope)]
EmployeeSelfIdentity = Annotated[uuid.UUID, Depends(require_employee_self_identity)]
ManagerIdentity = Annotated[uuid.UUID, Depends(require_manager_identity)]
AdminSelectedBranch = Annotated[uuid.UUID, Depends(require_admin_selected_branch)]
