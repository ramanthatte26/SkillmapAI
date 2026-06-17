"""
SkillMap AI — Password Hashing Utilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Uses passlib with bcrypt as the hashing scheme.

Why bcrypt?
- Adaptive: the cost factor can be increased as hardware improves
- Built-in salt: each hash includes a unique random salt — identical
  passwords produce different hashes
- OWASP recommended for password storage

Cost factor 12 targets ~250ms on modern hardware — fast enough for
UX but expensive enough to make brute-force attacks impractical.
"""

from passlib.context import CryptContext

# CryptContext manages scheme selection and hash verification.
# deprecated="auto" means old schemes (e.g. md5_crypt) are recognised
# but new hashes always use bcrypt.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # cost factor — increase to 13/14 in production if hardware allows
)


def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Args:
        plain_password: The user's raw password string.

    Returns:
        A bcrypt hash string safe to store in the database.

    Note:
        This function is intentionally slow (~250ms). Never call it in
        a hot loop or on every request — only on registration and password change.
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.

    Args:
        plain_password:  The password the user typed during login.
        hashed_password: The bcrypt hash stored in the database.

    Returns:
        True if the password matches, False otherwise.

    Note:
        passlib uses a constant-time comparison internally to prevent
        timing attacks — do NOT use a simple == comparison.
    """
    return pwd_context.verify(plain_password, hashed_password)
