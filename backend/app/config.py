"""
SkillMap AI — Pydantic Settings Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Uses pydantic-settings to load and validate all environment variables.
Settings are cached via @lru_cache so .env is read only once per process.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration object.

    All fields map 1-to-1 with environment variables (case-insensitive).
    Validation happens at application startup — misconfigured envs fail fast.
    """

    # ── Application ────────────────────────────────────────────────
    app_name: str = "SkillMap AI"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # ── Database ───────────────────────────────────────────────────
    database_url: str

    # ── JWT ────────────────────────────────────────────────────────
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    # ── CORS ───────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"

    # ── External APIs (populated later) ────────────────────────────
    youtube_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-chat"
    chroma_db_dir: str = "chroma_db"

    # ── Pydantic-settings config ────────────────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # silently drop unknown env vars
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is using the correct driver for SQLAlchemy."""
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v


    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Return allowed CORS origins based on environment."""
        origins = [self.frontend_url]
        for url in ["http://localhost:3000", "http://localhost:5173"]:
            if url not in origins:
                origins.append(url)
        return origins



@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    Using @lru_cache ensures the .env file is read exactly once
    for the lifetime of the process — no repeated disk I/O per request.
    """
    return Settings()
