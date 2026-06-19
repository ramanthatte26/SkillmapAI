"""
SkillMap AI — Progress Pydantic Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request and response shapes for progress tracking endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Request schemas
# ─────────────────────────────────────────────────────────────────


class ProgressUpdateRequest(BaseModel):
    """
    Payload for PUT /api/v1/progress/video/{video_id}.

    All fields except is_completed are optional — clients may update
    only the fields they care about without clobbering the rest.

    is_completed is required because it's the core state toggle.
    Ambiguity here (omitting it) would be a bug.
    """

    is_completed: bool = Field(
        ...,
        description="Mark the video as completed (true) or not completed (false).",
    )
    watch_time_seconds: int = Field(
        default=0,
        ge=0,
        description="How many seconds of the video the user has watched. "
                    "Stored for future analytics. Defaults to 0.",
    )
    user_notes: str | None = Field(
        default=None,
        max_length=5000,
        description="User's personal notes for this video. Optional. Max 5000 chars.",
    )


# ─────────────────────────────────────────────────────────────────
# Response schemas
# ─────────────────────────────────────────────────────────────────


class ProgressResponse(BaseModel):
    """
    Returned after a successful progress upsert.
    Reflects the complete current state of the progress record.
    """

    id: uuid.UUID
    video_id: uuid.UUID
    roadmap_id: uuid.UUID
    is_completed: bool
    watch_time_seconds: int
    user_notes: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProgressStatsResponse(BaseModel):
    """
    Aggregate progress statistics returned by
    GET /api/v1/progress/roadmap/{roadmap_id}.

    roadmap_id and title are included so the client doesn't need
    a second request to know which roadmap these stats belong to.
    """

    roadmap_id: uuid.UUID
    title: str
    total_videos: int
    completed_videos: int
    remaining_videos: int
    completion_percentage: float = Field(
        description="Percentage of videos completed. Range: 0.0 – 100.0."
    )
