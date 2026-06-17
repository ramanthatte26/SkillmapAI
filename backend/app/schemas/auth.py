"""
SkillMap AI — Auth Pydantic Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request and response shapes for the authentication endpoints.

Rule: NEVER include hashed_password in any response schema.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """
    Payload for POST /auth/register.

    Constraints:
    - email: validated as a real email address format
    - username: 3–30 chars, alphanumeric + underscores only
    - password: minimum 8 characters (enforced here + hashed in service)
    """

    email: EmailStr = Field(
        ...,
        description="Valid email address. Used as the login identifier.",
        examples=["user@example.com"],
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=30,
        description="Display handle. 3–30 chars, letters/numbers/underscores only.",
        examples=["john_doe"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plain-text password. Minimum 8 characters.",
        examples=["MySecureP@ss1"],
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Reject usernames with characters outside [a-z, A-Z, 0-9, _]."""
        import re
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "Username may only contain letters, numbers, and underscores."
            )
        return v.lower()  # normalise to lowercase for consistency

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce basic password complexity."""
        if v.isdigit():
            raise ValueError("Password cannot be entirely numeric.")
        return v


class LoginRequest(BaseModel):
    """
    Payload for POST /auth/login.
    """

    email: EmailStr = Field(
        ...,
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        examples=["MySecureP@ss1"],
    )


class TokenResponse(BaseModel):
    """
    Returned on successful login or token refresh.

    access_token: signed JWT — must be attached to protected requests as:
                  Authorization: Bearer <access_token>
    token_type:   Always "bearer" per OAuth2 spec.
    expires_in:   Seconds until the access token expires (for client-side timers).
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        description="Seconds until the access token expires."
    )


class TokenPayload(BaseModel):
    """
    The decoded contents of a JWT access token.

    sub:  Subject — the user's UUID as a string.
    exp:  Expiry unix timestamp (validated by python-jose automatically).
    type: Token type guard — prevents refresh tokens being used as access tokens.
    """

    sub: str                # user UUID
    exp: int                # unix timestamp
    type: str = "access"
