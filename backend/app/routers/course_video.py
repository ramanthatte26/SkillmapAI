"""
SkillMap AI — Course Video Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Router implementing the single course video import endpoint.
"""

import logging
import uuid
from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.user import User
from app.models.roadmap import Roadmap, RoadmapStatus
from app.schemas.roadmap import RoadmapImportResponse
from app.services.youtube_service import YouTubeService, run_course_video_background_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/course-video", tags=["Course Video"])


class CourseVideoImportRequest(BaseModel):
    """
    Payload for POST /api/v1/course-video/import.
    """

    video_url: str = Field(
        ...,
        description="Full YouTube watch or share URL of the single course video.",
        examples=["https://www.youtube.com/watch?v=rfscVS0vtbw"],
    )

    @field_validator("video_url")
    @classmethod
    def must_be_youtube_url(cls, v: str) -> str:
        """Validate that the input is a valid YouTube URL."""
        v = v.strip()
        if not v:
            raise ValueError("video_url cannot be empty.")
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


@router.post(
    "/import",
    response_model=RoadmapImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a single YouTube video as a structured roadmap",
    description=(
        "Extracts metadata and the transcript of a single YouTube video, "
        "detects curriculum boundaries using AI, and creates a learning roadmap. "
        "Runs asynchronously in the background."
    ),
    responses={
        201: {"description": "Video import started successfully."},
        400: {"description": "Invalid URL or YouTube API quota exceeded."},
        401: {"description": "Not authenticated."},
        404: {"description": "Video not found or is private."},
    },
)
def import_course_video(
    payload: CourseVideoImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RoadmapImportResponse:
    """Import course video — delegates extraction and AI pipeline to background tasks."""
    logger.info("User %s importing course video: %s", current_user.id, payload.video_url)

    yt_service = YouTubeService()
    
    # 1. Extract video ID
    video_id = yt_service.extract_video_id(payload.video_url)
    
    # 2. Fetch basic metadata synchronously (proactive validation)
    metadata = yt_service.fetch_video_metadata(video_id)
    logger.info("Fetched single video metadata: title=%r duration=%s", metadata["title"], metadata["duration_seconds"])

    # 3. Create skeleton roadmap (status = IMPORTING)
    roadmap = Roadmap(
        user_id=current_user.id,
        title=metadata["title"],
        description="Generating course overview from transcript...",
        playlist_url=payload.video_url,
        playlist_id=video_id,
        thumbnail_url=metadata.get("thumbnail_url"),
        total_videos=0,
        completed_videos=0,
        status=RoadmapStatus.IMPORTING,
    )
    db.add(roadmap)
    db.commit()
    db.refresh(roadmap)

    # 4. Trigger background processing pipeline
    background_tasks.add_task(
        run_course_video_background_pipeline,
        roadmap_id=roadmap.id,
        user_id=current_user.id,
        video_id=video_id,
        metadata=metadata
    )

    logger.info(
        "Course video import started: roadmap_id=%s title=%r",
        roadmap.id, roadmap.title,
    )
    
    return RoadmapImportResponse(
        roadmap_id=roadmap.id,
        title=roadmap.title,
        total_videos=0,
        status=roadmap.status,
        message="Course video import and curriculum generation started in the background."
    )
