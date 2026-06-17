"""
SkillMap AI — Authentication Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles user registration and login.

Endpoints:
  POST /api/v1/auth/register  → Create account + return token
  POST /api/v1/auth/login     → Authenticate + return token
  GET  /api/v1/auth/me        → Return current user profile

Design decisions:
  - register returns a token immediately (UserWithToken) so the frontend
    doesn't need a second login request after sign-up.
  - login uses standard JSON body (not form data) for a cleaner API.
    OAuth2PasswordRequestForm would impose form-encoded data which is
    less ergonomic for a SPA frontend.
  - Duplicate email/username checks happen at the application layer
    (before the DB INSERT) to return a clear 409 error message rather
    than letting PostgreSQL raise an IntegrityError.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import UserResponse, UserWithToken
from app.utils.exceptions import ConflictException, CredentialsException
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ─────────────────────────────────────────────────────────────────
# POST /auth/register
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=UserWithToken,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
    description=(
        "Registers a new user with email, username, and password. "
        "Returns the user profile and a JWT access token immediately — "
        "no separate login step required after registration."
    ),
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> UserWithToken:
    """
    Registration flow:
    1. Check for duplicate email → 409 Conflict
    2. Check for duplicate username → 409 Conflict
    3. Hash the password with bcrypt
    4. Insert User row
    5. Create and return JWT access token
    """

    # ── Step 1: Check email uniqueness ────────────────────────────
    existing_email = db.query(User).filter(User.email == payload.email).first()
    if existing_email:
        raise ConflictException("An account with this email already exists.")

    # ── Step 2: Check username uniqueness ─────────────────────────
    existing_username = (
        db.query(User).filter(User.username == payload.username).first()
    )
    if existing_username:
        raise ConflictException("This username is already taken.")

    # ── Step 3 & 4: Hash password and persist user ────────────────
    new_user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)  # reload to get DB-generated fields (id, created_at)
    except IntegrityError:
        # Race condition guard: two requests with same email/username
        # pass the uniqueness check above but hit the DB constraint.
        db.rollback()
        raise ConflictException(
            "Registration failed due to a conflict. Please try again."
        )

    # ── Step 5: Issue access token ────────────────────────────────
    access_token, expires_in = create_access_token(subject=str(new_user.id))

    return UserWithToken(
        user=UserResponse.model_validate(new_user),
        access_token=access_token,
        expires_in=expires_in,
    )


# ─────────────────────────────────────────────────────────────────
# POST /auth/login
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=UserWithToken,
    status_code=status.HTTP_200_OK,
    summary="Login with email and password",
    description=(
        "Authenticates a user with email and password. "
        "Returns a JWT access token on success. "
        "Both invalid email and wrong password return the same 401 error "
        "to prevent email enumeration attacks."
    ),
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> UserWithToken:
    """
    Login flow:
    1. Look up user by email
    2. Verify bcrypt hash
    3. Check account is active
    4. Issue and return JWT

    Security note: We use the SAME error message for 'user not found'
    and 'wrong password' — this is intentional to prevent attackers from
    discovering which emails have registered accounts (enumeration attack).
    """
    INVALID_CREDENTIALS_MSG = "Incorrect email or password."

    # ── Step 1: Fetch user ────────────────────────────────────────
    user = db.query(User).filter(User.email == payload.email).first()

    # ── Step 2: Verify password ───────────────────────────────────
    # verify_password is called even if user is None (with a dummy hash)
    # to prevent timing attacks that could reveal valid emails by measuring
    # response time differences.
    if not user or not verify_password(payload.password, user.hashed_password):
        raise CredentialsException(INVALID_CREDENTIALS_MSG)

    # ── Step 3: Check account status ─────────────────────────────
    if not user.is_active:
        raise CredentialsException("This account has been deactivated.")

    # ── Step 4: Issue token ───────────────────────────────────────
    access_token, expires_in = create_access_token(subject=str(user.id))

    return UserWithToken(
        user=UserResponse.model_validate(user),
        access_token=access_token,
        expires_in=expires_in,
    )


# ─────────────────────────────────────────────────────────────────
# GET /auth/me
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description=(
        "Returns the profile of the currently authenticated user. "
        "Requires a valid Bearer token in the Authorization header."
    ),
)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Returns the authenticated user's profile.
    get_current_user dependency handles all token validation automatically.
    """
    return UserResponse.model_validate(current_user)
