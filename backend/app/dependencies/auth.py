"""
SkillMap AI — Auth Dependency (get_current_user)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The single source of truth for protecting endpoints.

How it works:
1. FastAPI extracts the JWT from the Authorization: Bearer <token> header
   via the oauth2_scheme (OAuth2PasswordBearer).
2. decode_access_token validates the token signature and expiry.
3. The user UUID from the token payload is used to load the User from DB.
4. The loaded User object is returned and injected into the route handler.

Usage in any protected route:
    @router.get("/protected")
    def my_route(current_user: User = Depends(get_current_user)):
        ...

If the token is missing, expired, or the user is inactive, FastAPI
automatically returns a 401 Unauthorized response before the route
handler is called.
"""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.models.user import User
from app.utils.exceptions import CredentialsException
from app.utils.jwt import decode_access_token

# oauth2_scheme tells FastAPI's OpenAPI schema where to look for the token.
# tokenUrl points to the login endpoint — used by Swagger UI's Authorize button.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT and return the authenticated User from the database.

    Args:
        token: Raw JWT string extracted from Authorization header.
        db:    Database session from get_db().

    Returns:
        The authenticated User ORM object.

    Raises:
        CredentialsException (HTTP 401): If the token is invalid/expired,
            or if no user matches the token's subject claim.
        CredentialsException (HTTP 401): If the user account is deactivated.
    """
    try:
        payload = decode_access_token(token)
        user_id: str = payload.sub
    except Exception as exc:
        logger.error("JWT decoding failed: %s", exc)
        raise CredentialsException("Token is invalid or has expired.")

    user = db.get(User, user_id)
    if user is None:
        raise CredentialsException("User not found.")

    if not user.is_active:
        raise CredentialsException("User account is deactivated.")

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Convenience dependency — alias for get_current_user.
    Kept separate to allow future role-based access control (RBAC)
    without changing every router that uses it.
    """
    return current_user
