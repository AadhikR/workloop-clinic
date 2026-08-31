from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.auth.access_token import AccessTokenClaims, AccessTokenError, AccessTokenVerifier


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
