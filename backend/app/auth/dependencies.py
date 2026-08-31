import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.auth.access_token import AccessTokenClaims, AccessTokenError, AccessTokenVerifier
from app.auth.application_user import (
    ApplicationUser,
    ApplicationUserLookupError,
    ApplicationUserResolver,
    ApplicationUserUnavailableError,
)

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


async def require_application_user(
    request: Request,
    claims: VerifiedAccessToken,
) -> ApplicationUser:
    resolver: ApplicationUserResolver = request.app.state.application_user_resolver
    try:
        return await resolver.resolve(issuer=claims.issuer, subject=claims.subject)
    except ApplicationUserUnavailableError:
        raise application_account_error() from None
    except ApplicationUserLookupError:
        logger.warning("application_user_lookup_failed")
        raise application_account_lookup_error() from None


VerifiedApplicationUser = Annotated[ApplicationUser, Depends(require_application_user)]
