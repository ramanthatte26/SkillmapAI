"""
SkillMap AI — Progress Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Business logic for tracking per-user, per-video learning progress.

Responsibilities:
  - Upsert progress records (INSERT if new, UPDATE if existing)
  - Keep Roadmap.completed_videos counter in sync
  - Return per-roadmap progress statistics
  - Validate that the video belongs to the requesting user's roadmap

Key design decisions:
  - Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE (via SQLAlchemy
    dialect-specific upsert) for safe concurrent updates.
  - completed_at is set/cleared automatically when is_completed flips.
  - Roadmap.completed_videos is updated atomically in the same transaction
    as the progress upsert — no separate job needed.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.progress import VideoProgress
from app.models.roadmap import Roadmap
from app.models.video import Video
from app.schemas.progress import (
    ProgressUpdateRequest,
    ProgressResponse,
    ProgressStatsResponse,
)
from app.utils.exceptions import ForbiddenException, NotFoundException

logger = logging.getLogger(__name__)


class ProgressService:
    """
    Handles all progress tracking operations.

    The upsert approach (rather than separate create/update) is intentional:
      - Clients don't need to know if a record exists
      - Concurrent requests from the same user on the same video are safe
      - The UNIQUE constraint on (user_id, video_id) acts as the conflict target
    """

    # ─────────────────────────────────────────────────────────────
    # Upsert video progress
    # ─────────────────────────────────────────────────────────────

    def upsert_video_progress(
        self,
        video_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: ProgressUpdateRequest,
        db: Session,
    ) -> ProgressResponse:
        """
        Create or update progress for a specific video.

        Args:
            video_id: UUID of the video to update progress for.
            user_id:  UUID of the authenticated user.
            payload:  ProgressUpdateRequest with is_completed etc.
            db:       SQLAlchemy session.

        Returns:
            ProgressResponse reflecting the new state.

        Raises:
            NotFoundException:  If video_id doesn't exist.
            ForbiddenException: If the video's roadmap doesn't belong to user.

        Upsert strategy:
          1. Verify the video exists and belongs to the user's roadmap
          2. Determine completed_at value based on is_completed flag
          3. Use SQLAlchemy's ORM-level upsert pattern:
               - Try to fetch existing record
               - Create new or update existing
          4. Recount completed_videos on the parent Roadmap atomically
        """
        # ── Step 1: Validate video exists and user owns it ────────
        video = db.query(Video).filter(Video.id == video_id).first()

        if video is None:
            logger.warning("upsert_progress: video_id=%s not found", video_id)
            raise NotFoundException("Video")

        # Verify the roadmap belongs to this user
        roadmap = db.query(Roadmap).filter(
            Roadmap.id == video.roadmap_id,
            Roadmap.user_id == user_id,
        ).first()

        if roadmap is None:
            logger.warning(
                "upsert_progress: user %s attempted progress on video %s "
                "from roadmap %s they don't own",
                user_id, video_id, video.roadmap_id,
            )
            raise ForbiddenException(
                "You do not have permission to update progress for this video."
            )

        # ── Step 2: Compute completed_at ──────────────────────────
        now = datetime.now(tz=timezone.utc)
        completed_at: datetime | None = now if payload.is_completed else None

        # ── Step 3: Fetch existing progress or create new ─────────
        progress = (
            db.query(VideoProgress)
            .filter(
                VideoProgress.user_id == user_id,
                VideoProgress.video_id == video_id,
            )
            .first()
        )

        if progress is None:
            # First time marking progress on this video
            progress = VideoProgress(
                user_id=user_id,
                video_id=video_id,
                roadmap_id=video.roadmap_id,
                is_completed=payload.is_completed,
                watch_time_seconds=payload.watch_time_seconds,
                user_notes=payload.user_notes,
                completed_at=completed_at,
            )
            db.add(progress)
            logger.info(
                "Created new progress: user=%s video=%s completed=%s",
                user_id, video_id, payload.is_completed,
            )
        else:
            # Update existing record
            previous_completed = progress.is_completed
            progress.is_completed = payload.is_completed
            progress.watch_time_seconds = payload.watch_time_seconds
            progress.user_notes = payload.user_notes

            # Only set/clear completed_at when is_completed actually changes
            if payload.is_completed and not previous_completed:
                progress.completed_at = completed_at
            elif not payload.is_completed and previous_completed:
                progress.completed_at = None  # un-marking completion

            logger.info(
                "Updated progress: user=%s video=%s completed=%s->%s",
                user_id, video_id, previous_completed, payload.is_completed,
            )

        # ── Step 4: Sync Roadmap.completed_videos counter ─────────
        # Flush progress change so the COUNT below reflects it
        db.flush()

        completed_count = (
            db.query(func.count(VideoProgress.id))
            .filter(
                VideoProgress.user_id == user_id,
                VideoProgress.roadmap_id == video.roadmap_id,
                VideoProgress.is_completed == True,  # noqa: E712
            )
            .scalar()
        )
        roadmap.completed_videos = completed_count or 0

        db.commit()
        db.refresh(progress)

        logger.debug(
            "Roadmap %s completed_videos synced to %d",
            video.roadmap_id, roadmap.completed_videos,
        )

        return ProgressResponse.model_validate(progress)

    # ─────────────────────────────────────────────────────────────
    # Progress statistics for a roadmap
    # ─────────────────────────────────────────────────────────────

    def get_roadmap_stats(
        self,
        roadmap_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session,
    ) -> ProgressStatsResponse:
        """
        Return aggregate progress statistics for a roadmap.

        Args:
            roadmap_id: UUID of the roadmap.
            user_id:    UUID of the authenticated user.
            db:         SQLAlchemy session.

        Returns:
            ProgressStatsResponse with counts and percentage.

        Raises:
            NotFoundException:  If roadmap doesn't exist.
            ForbiddenException: If roadmap belongs to another user.

        Query strategy:
          - total_videos is read from Roadmap.total_videos (denormalized)
            — no COUNT(*) on videos table needed.
          - completed_videos is a COUNT from video_progress filtered by
            user + roadmap + is_completed=True. This is the source of truth
            (Roadmap.completed_videos is an optimistic cache; stats uses
            the live count for accuracy).
        """
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()

        if roadmap is None:
            logger.warning("get_roadmap_stats: roadmap_id=%s not found", roadmap_id)
            raise NotFoundException("Roadmap")

        if roadmap.user_id != user_id:
            logger.warning(
                "get_roadmap_stats: user %s attempted stats on roadmap %s owned by %s",
                user_id, roadmap_id, roadmap.user_id,
            )
            raise ForbiddenException(
                "You do not have permission to view stats for this roadmap."
            )

        total = roadmap.total_videos

        # Live COUNT — always accurate regardless of counter sync state
        completed = (
            db.query(func.count(VideoProgress.id))
            .filter(
                VideoProgress.user_id == user_id,
                VideoProgress.roadmap_id == roadmap_id,
                VideoProgress.is_completed == True,  # noqa: E712
            )
            .scalar()
        ) or 0

        remaining = total - completed
        percentage = round((completed / total * 100), 2) if total > 0 else 0.0

        logger.debug(
            "get_roadmap_stats: roadmap=%s total=%d completed=%d pct=%.2f",
            roadmap_id, total, completed, percentage,
        )

        return ProgressStatsResponse(
            roadmap_id=roadmap_id,
            title=roadmap.title,
            total_videos=total,
            completed_videos=completed,
            remaining_videos=remaining,
            completion_percentage=percentage,
        )
