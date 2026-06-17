"""
SkillMap AI — JWT Utility Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles creation and validation of JWT access tokens using python-jose.

Algorithm: HS256 (HMAC-SHA256)
  - Symmetric: same key signs and verifies
  - Appropriate for a single-server API where the backend is both issuer
    and verifier
  - RS256 (asymmetric) would be needed for multi-service auth (e.g. microservices)

Token lifetime: configured via ACCESS_TOKEN_EXPIRE_MINUTES in Settings.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from app.config import get_settings
from app.schemas.auth import TokenPayload

settings = get_settings()


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, int]:
    """
    Create and sign a JWT access token.

    Args:
        subject:      The token subject — typically the user's UUID as string.
        extra_claims: Optional additional claims to embed in the payload.

    Returns:
        A tuple of (encoded_jwt_string, expires_in_seconds).

    The expiry is embedded in the token itself (the 'exp' claim) AND
    returned separately so the client can set client-side timers without
    parsing the JWT.
    """
    expire_minutes = settings.access_token_expire_minutes
    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expires_at,
        "iat": datetime.now(tz=timezone.utc),
        "type": "access",  # type guard — prevents reusing refresh tokens
    }

    if extra_claims:
        payload.update(extra_claims)

    encoded = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return encoded, expire_minutes * 60


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.

    Args:
        token: The raw JWT string from the Authorization header.

    Returns:
        A TokenPayload with the decoded claims.

    Raises:
        JWTError: If the token is expired, tampered with, or otherwise invalid.
                  Callers should convert this to an HTTP 401 response.

    Validation performed by python-jose:
    - Signature verification (HMAC-SHA256)
    - Expiry check ('exp' claim)
    - Algorithm verification (prevents algorithm-confusion attacks)
    """
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

    # Enforce the type guard — reject refresh tokens if/when they're added
    if payload.get("type") != "access":
        raise JWTError("Invalid token type.")

    return TokenPayload(
        sub=payload["sub"],
        exp=int(payload["exp"].timestamp()) if hasattr(payload["exp"], "timestamp") else payload["exp"],
        type=payload["type"],
    )
