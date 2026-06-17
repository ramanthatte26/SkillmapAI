"""
SkillMap AI — User Pydantic Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request and response shapes for user-related endpoints.

Separation principle:
  UserCreate  → what the client sends to create a user
  UserResponse → what the API returns (NEVER includes hashed_password)
  UserUpdate  → partial update payload (all fields optional)
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """
    Internal schema used by the auth service to create a User ORM object.
    Mirrors RegisterRequest but accepts pre-validated data from the router.
    """

    email: EmailStr
    username: str
    password: str  # plaintext — hashed in the service before storing


class UserResponse(BaseModel):
    """
    Public user representation returned by all endpoints.

    Critical: hashed_password is intentionally absent.
    model_config with from_attributes=True enables constructing this
    schema directly from a SQLAlchemy ORM object.
    """

    id: uuid.UUID
    email: EmailStr
    username: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """
    Partial update schema for PATCH /users/me.
    All fields are optional — only provided fields will be updated.
    """

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=30,
        examples=["new_username"],
    )
    email: EmailStr | None = Field(
        default=None,
        examples=["newemail@example.com"],
    )

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str | None) -> str | None:
        import re
        if v is not None and not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "Username may only contain letters, numbers, and underscores."
            )
        return v.lower() if v else v


class UserWithToken(BaseModel):
    """
    Composite response returned after successful registration.
    Combines the user profile with the initial access token so the
    client doesn't need a second round-trip to login after signing up.
    """

    user: UserResponse
    access_token: str
    token_type: str = "bearer"
    expires_in: int
