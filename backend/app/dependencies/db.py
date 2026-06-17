"""
SkillMap AI — Database Dependency
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Re-exports get_db from database.py as the canonical FastAPI dependency.
Keeping this in the dependencies/ package allows test overrides via
app.dependency_overrides without touching the core database module.
"""

from app.database import get_db

__all__ = ["get_db"]
