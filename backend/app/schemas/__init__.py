"""
SkillMap AI — Schemas Package
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    TokenPayload,
)
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithToken,
)
from app.schemas.roadmap import (
    PlaylistImportRequest,
    RoadmapImportResponse,
    VideoResponse,
    RoadmapDetailResponse,
    RoadmapSummary,
)
from app.schemas.progress import (
    ProgressUpdateRequest,
    ProgressResponse,
    ProgressStatsResponse,
)

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "TokenPayload",
    "UserCreate",
    "UserResponse",
    "UserUpdate",
    "UserWithToken",
    "PlaylistImportRequest",
    "RoadmapImportResponse",
    "VideoResponse",
    "RoadmapDetailResponse",
    "RoadmapSummary",
    "ProgressUpdateRequest",
    "ProgressResponse",
    "ProgressStatsResponse",
]

