"""
SkillMap AI — Roadmap Pydantic Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request and response shapes for roadmap and import endpoints.

Separation principle:
  PlaylistImportRequest  → what the client sends to import a playlist
  RoadmapImportResponse  → lightweight confirmation after import
  VideoResponse          → per-video shape embedded in RoadmapDetailResponse
  RoadmapDetailResponse  → full roadmap with nested video list
  RoadmapSummary         → lightweight shape used in list endpoints (no videos)
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.roadmap import RoadmapStatus
from app.models.video import AINotesStatus


# ─────────────────────────────────────────────────────────────────
# Request schemas
# ─────────────────────────────────────────────────────────────────


class PlaylistImportRequest(BaseModel):
    """
    Payload for POST /api/v1/roadmaps/import.

    Accepts any valid YouTube playlist URL format:
      - https://www.youtube.com/playlist?list=PLxxxxx
      - https://youtube.com/playlist?list=PLxxxxx
      - https://www.youtube.com/watch?v=xxx&list=PLxxxxx  (share URLs)
    """

    playlist_url: str = Field(
        ...,
        description="Full YouTube playlist URL.",
        examples=["https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxx"],
    )

    @field_validator("playlist_url")
    @classmethod
    def must_be_youtube_url(cls, v: str) -> str:
        """Reject obviously non-YouTube URLs early before hitting the API."""
        v = v.strip()
        if not v:
            raise ValueError("playlist_url cannot be empty.")
        allowed_hosts = ("youtube.com", "www.youtube.com", "youtu.be")
        try:
            from urllib.parse import urlparse
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https"):
                raise ValueError("URL must start with http:// or https://")
            if parsed.netloc not in allowed_hosts:
                raise ValueError(
                    f"URL must be a YouTube URL. Got host: {parsed.netloc!r}"
                )
        except Exception as exc:
            raise ValueError(f"Invalid URL: {exc}") from exc
        return v


# ─────────────────────────────────────────────────────────────────
# Response schemas
# ─────────────────────────────────────────────────────────────────


class RoadmapImportResponse(BaseModel):
    """
    Lightweight response returned immediately after a successful import.

    Why lightweight?
    The frontend doesn't need the full video list at import time —
    it can fetch the detail view separately. Keeping this small
    reduces response payload and serialisation time.
    """

    roadmap_id: uuid.UUID
    title: str
    total_videos: int
    status: RoadmapStatus
    message: str = "Playlist imported successfully."


class VideoResponse(BaseModel):
    """Per-video shape embedded inside RoadmapDetailResponse."""

    id: uuid.UUID
    youtube_id: str
    title: str
    thumbnail_url: str | None
    duration_seconds: int | None
    position: int
    ai_notes: str | None = None
    ai_notes_status: AINotesStatus
    is_completed: bool = False

    model_config = {"from_attributes": True}


class RoadmapDetailResponse(BaseModel):
    """
    Full roadmap shape including nested video list.
    Used by GET /roadmaps/{id}.
    """

    id: uuid.UUID
    title: str
    description: str | None
    playlist_url: str
    playlist_id: str
    thumbnail_url: str | None
    total_videos: int
    completed_videos: int
    status: RoadmapStatus
    completion_percentage: float
    created_at: datetime
    updated_at: datetime
    videos: list[VideoResponse] = []

    model_config = {"from_attributes": True}


class RoadmapSummary(BaseModel):
    """
    Lightweight roadmap shape used in list endpoints.
    Does NOT include the videos list to prevent N+1 serialisation.
    """

    id: uuid.UUID
    title: str
    thumbnail_url: str | None
    total_videos: int
    completed_videos: int
    status: RoadmapStatus
    completion_percentage: float
    created_at: datetime

    model_config = {"from_attributes": True}
