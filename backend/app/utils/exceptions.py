"""
SkillMap AI — Custom HTTP Exceptions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centralised exception definitions with consistent error response shapes.

Using a single module for custom exceptions ensures:
- Consistent error message format across the entire API
- Easy to add global exception handlers in main.py
- Interviewers can see deliberate error handling design
"""

from fastapi import HTTPException, status


class CredentialsException(HTTPException):
    """Raised when JWT is missing, invalid, or expired."""

    def __init__(self, detail: str = "Could not validate credentials."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class NotFoundException(HTTPException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found.",
        )


class ConflictException(HTTPException):
    """Raised when a create/update would violate a uniqueness constraint."""

    def __init__(self, detail: str = "A conflict occurred."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class ForbiddenException(HTTPException):
    """Raised when an authenticated user tries to access someone else's resource."""

    def __init__(self, detail: str = "You do not have permission to access this resource."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class BadRequestException(HTTPException):
    """Raised for malformed requests that pass Pydantic validation but fail business rules."""

    def __init__(self, detail: str = "Bad request."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )
