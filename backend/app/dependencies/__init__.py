"""SkillMap AI — Dependencies Package"""

from app.dependencies.db import get_db
from app.dependencies.auth import get_current_user, get_current_active_user

__all__ = ["get_db", "get_current_user", "get_current_active_user"]
