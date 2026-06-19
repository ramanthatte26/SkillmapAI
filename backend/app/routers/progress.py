"""
SkillMap AI — Progress Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles all learning-progress tracking endpoints.

Endpoints:
  PUT /api/v1/progress/video/{video_id}        → Upsert video progress
  GET /api/v1/progress/roadmap/{roadmap_id}    → Roadmap progress statistics

Design:
  - PUT is semantically correct for upsert: calling it multiple times
    with the same payload produces the same result (idempotent).
  - All ownership checks live in ProgressService — the router only
    handles HTTP request/response shaping.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.user import User
from app.schemas.progress import (
    ProgressUpdateRequest,
    ProgressResponse,
    ProgressStatsResponse,
)
from app.services.progress_service import ProgressService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/progress", tags=["Progress"])


# ── Service dependency ────────────────────────────────────────────

def get_progress_service() -> ProgressService:
    """Provides a ProgressService instance. Override in tests."""
    return ProgressService()


# ─────────────────────────────────────────────────────────────────
# PUT /progress/video/{video_id}
# ─────────────────────────────────────────────────────────────────
@router.put(
    "/video/{video_id}",
    response_model=ProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark a video as completed or not completed",
    description=(
        "Creates a progress record if none exists for this user/video pair, "
        "or updates the existing one. "
        "Setting is_completed=false un-marks a previously completed video. "
        "Requires authentication. "
        "Only the owner of the roadmap containing this video may update its progress."
    ),
    responses={
        200: {"description": "Progress upserted successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Video belongs to another user's roadmap."},
        404: {"description": "Video not found."},
    },
)
def update_progress(
    video_id: uuid.UUID,
    payload: ProgressUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    progress_service: ProgressService = Depends(get_progress_service),
) -> ProgressResponse:
    """
    Upsert progress for a single video.

    Behaviour:
      - First call: creates a new VideoProgress row.
      - Subsequent calls: updates the existing row.
      - completed_at is set automatically when is_completed=True,
        and cleared when is_completed=False.
      - Roadmap.completed_videos counter is kept in sync atomically.
    """
    logger.info(
        "User %s updating progress: video=%s completed=%s",
        current_user.id, video_id, payload.is_completed,
    )

    result = progress_service.upsert_video_progress(
        video_id=video_id,
        user_id=current_user.id,
        payload=payload,
        db=db,
    )

    logger.info(
        "Progress upserted: id=%s video=%s completed=%s",
        result.id, result.video_id, result.is_completed,
    )
    return result


# ─────────────────────────────────────────────────────────────────
# GET /progress/roadmap/{roadmap_id}
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/roadmap/{roadmap_id}",
    response_model=ProgressStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get progress statistics for a roadmap",
    description=(
        "Returns aggregate completion statistics for the given roadmap: "
        "total videos, completed, remaining, and percentage. "
        "Only the roadmap's owner can view their stats."
    ),
    responses={
        200: {"description": "Progress statistics returned."},
        401: {"description": "Not authenticated."},
        403: {"description": "Roadmap belongs to a different user."},
        404: {"description": "Roadmap not found."},
    },
)
def get_progress_stats(
    roadmap_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    progress_service: ProgressService = Depends(get_progress_service),
) -> ProgressStatsResponse:
    """
    Returns live completion stats for a roadmap.

    Uses a COUNT query on video_progress (not the cached counter)
    for guaranteed accuracy.
    """
    logger.info(
        "User %s requesting stats for roadmap %s",
        current_user.id, roadmap_id,
    )

    result = progress_service.get_roadmap_stats(
        roadmap_id=roadmap_id,
        user_id=current_user.id,
        db=db,
    )

    logger.info(
        "Stats: roadmap=%s %d/%d (%.2f%%)",
        roadmap_id, result.completed_videos,
        result.total_videos, result.completion_percentage,
    )
    return result
