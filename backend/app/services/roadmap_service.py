"""
SkillMap AI — Roadmap Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Business logic for roadmap retrieval.

Responsibilities:
  - Fetch all roadmaps belonging to the authenticated user
  - Fetch a single roadmap by ID with its videos (ordered by position)
  - Enforce ownership: users can only access their own roadmaps
  - Enrich roadmap summaries with per-user completion counts

Design pattern:
  Pure Python class — no FastAPI concerns inside.
  The router handles HTTP, this handles data access and ownership.
"""

import logging
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.roadmap import Roadmap
from app.models.video import Video
from app.models.progress import VideoProgress
from app.schemas.roadmap import RoadmapDetailResponse, RoadmapSummary, VideoResponse
from app.utils.exceptions import ForbiddenException, NotFoundException

logger = logging.getLogger(__name__)


class RoadmapService:
    """
    Encapsulates all roadmap read/query operations.

    Why a service class?
    - Centralises ownership-check logic in one place
    - Keeps routers thin and focused on HTTP
    - Makes unit testing straightforward (just inject a mock Session)
    """

    # ─────────────────────────────────────────────────────────────
    # List user's roadmaps
    # ─────────────────────────────────────────────────────────────

    def get_user_roadmaps(
        self,
        user_id: uuid.UUID,
        db: Session,
        skip: int = 0,
        limit: int = 20,
    ) -> list[RoadmapSummary]:
        """
        Return all roadmaps belonging to user_id, paginated.

        Args:
            user_id: UUID of the authenticated user.
            db:      SQLAlchemy session.
            skip:    Number of records to skip (offset). Default 0.
            limit:   Max records to return. Default 20, max 100.

        Returns:
            List of RoadmapSummary (lightweight — no nested videos).

        Query strategy:
          - Filter by user_id (indexed column) first
          - Order by created_at DESC so newest roadmaps appear first
          - No JOIN to videos needed — total_videos is denormalized on Roadmap
          - completed_videos is kept in sync by the progress service
        """
        limit = min(limit, 100)  # hard cap — prevent runaway queries

        roadmaps = (
            db.query(Roadmap)
            .filter(Roadmap.user_id == user_id)
            .order_by(Roadmap.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        logger.debug(
            "get_user_roadmaps: user_id=%s returned %d roadmaps",
            user_id, len(roadmaps),
        )

        return [RoadmapSummary.model_validate(r) for r in roadmaps]

    # ─────────────────────────────────────────────────────────────
    # Get single roadmap detail
    # ─────────────────────────────────────────────────────────────

    def get_roadmap_detail(
        self,
        roadmap_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session,
    ) -> RoadmapDetailResponse:
        """
        Fetch a single roadmap with its full video list.

        Args:
            roadmap_id: UUID of the requested roadmap.
            user_id:    UUID of the requesting user (for ownership check).
            db:         SQLAlchemy session.

        Returns:
            RoadmapDetailResponse with nested VideoResponse list.

        Raises:
            NotFoundException:  If the roadmap_id doesn't exist.
            ForbiddenException: If the roadmap belongs to a different user.

        Query strategy:
          - selectinload(Roadmap.videos) fires a second query:
              SELECT * FROM videos WHERE roadmap_id IN (...)
            This avoids the N+1 problem and does NOT use a JOIN that
            would produce duplicate Roadmap columns for each video.
          - Videos are pre-ordered by position at the model level
            (order_by="Video.position" on the relationship definition).
        """
        logger.info("[TRACE] get_roadmap_detail start: roadmap_id=%s, user_id=%s", roadmap_id, user_id)
        
        try:
            logger.info("[TRACE] Querying database for Roadmap and videos...")
            roadmap = (
                db.query(Roadmap)
                .options(selectinload(Roadmap.videos))
                .filter(Roadmap.id == roadmap_id)
                .first()
            )

            if roadmap is None:
                logger.warning("[TRACE] get_roadmap_detail: roadmap_id=%s not found", roadmap_id)
                raise NotFoundException("Roadmap")

            logger.info("[TRACE] Loaded roadmap from DB: title=%r, status=%s, owner=%s", roadmap.title, roadmap.status, roadmap.user_id)

            # Ownership check — never leak other users' roadmaps
            if roadmap.user_id != user_id:
                logger.warning(
                    "[TRACE] get_roadmap_detail: user %s attempted to access roadmap %s owned by %s",
                    user_id, roadmap_id, roadmap.user_id,
                )
                raise ForbiddenException(
                    "You do not have permission to access this roadmap."
                )

            logger.info("[TRACE] Modules count: %d", len(roadmap.modules) if roadmap.modules else 0)

            # Query completed video IDs for this user & roadmap
            logger.info("[TRACE] Querying completed video progress records...")
            completed_video_ids = {
                r[0] for r in db.query(VideoProgress.video_id)
                .filter(
                    VideoProgress.user_id == user_id,
                    VideoProgress.roadmap_id == roadmap_id,
                    VideoProgress.is_completed == True
                )
                .all()
            }
            logger.info("[TRACE] Completed video IDs retrieved: %d", len(completed_video_ids))

            # Dynamically set is_completed attribute on each video ORM model
            logger.info("[TRACE] Setting is_completed attribute on videos...")
            for video in roadmap.videos:
                video.is_completed = video.id in completed_video_ids
            logger.info("[TRACE] is_completed flags set on %d videos", len(roadmap.videos))

            # Filter out segment videos from the main videos list of the roadmap detail
            logger.info("[TRACE] Filtering out segment videos...")
            roadmap.videos = [v for v in roadmap.videos if not v.is_segment]
            logger.info("[TRACE] Remaining videos count: %d", len(roadmap.videos))

            # Insights check
            logger.info("[TRACE] Insights JSON length: %s", len(roadmap.insights_json) if roadmap.insights_json else "None")

            logger.info("[TRACE] Attempting response DTO serialization (model_validate)...")
            response_dto = RoadmapDetailResponse.model_validate(roadmap)
            logger.info("[TRACE] Response DTO serialization succeeded.")
            return response_dto
            
        except Exception as e:
            import traceback
            tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.error("[TRACE_ERROR] Exception in get_roadmap_detail: %s\n%s", e, tb_str)
            raise e


    # ─────────────────────────────────────────────────────────────
    # Delete roadmap
    # ─────────────────────────────────────────────────────────────

    def delete_roadmap(
        self,
        roadmap_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session,
    ) -> None:
        """
        Verify roadmap ownership, delete search vectors from ChromaDB, and
        delete the SQL Roadmap record (cascading deletes handle related SQL tables).
        """
        roadmap = (
            db.query(Roadmap)
            .filter(Roadmap.id == roadmap_id)
            .first()
        )

        if roadmap is None:
            logger.warning("delete_roadmap: roadmap_id=%s not found", roadmap_id)
            raise NotFoundException("Roadmap")

        # Ownership check
        if roadmap.user_id != user_id:
            logger.warning(
                "delete_roadmap: user %s attempted to delete roadmap %s owned by %s",
                user_id, roadmap_id, roadmap.user_id,
            )
            raise ForbiddenException(
                "You do not have permission to delete this roadmap."
            )

        logger.info("delete_roadmap: deleting roadmap %s (%r)", roadmap_id, roadmap.title)

        # 1. Clear ChromaDB vectors
        from app.services.search_service import SearchService
        try:
            search_service = SearchService()
            search_service.vector_service.delete_by_roadmap(str(roadmap_id))
        except Exception as exc:
            logger.error("delete_roadmap: ChromaDB vector deletion failed: %s", exc)

        # 2. Delete from PostgreSQL
        db.delete(roadmap)
        db.commit()
        logger.info("delete_roadmap: SQL roadmap %s deleted successfully", roadmap_id)

