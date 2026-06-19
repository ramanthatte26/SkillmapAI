"""
SkillMap AI — Insights Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gathers database state (completed videos, progress metrics, modules, user notes)
and coordinates with AIService to produce learning insights.
"""

import logging
import uuid

from sqlalchemy.orm import Session, selectinload

from app.models.module import Module, ModuleVideo
from app.models.progress import VideoProgress
from app.models.roadmap import Roadmap
from app.models.video import Video
from app.services.ai_service import AIService
from app.utils.exceptions import ForbiddenException, NotFoundException

logger = logging.getLogger(__name__)


class InsightsService:
    """
    Coordinates gathering data to feed into the AI insights generator.
    """

    def __init__(self, ai_service: AIService | None = None):
        self.ai_service = ai_service or AIService()

    def get_roadmap_insights(
        self,
        roadmap_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session,
    ) -> dict:
        """
        Gathers roadmap context, progress stats, module listings, and study notes,
        and requests learning insights from the AI service.
        """
        # 1. Fetch roadmap and check ownership
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            logger.warning("get_roadmap_insights: Roadmap %s not found", roadmap_id)
            raise NotFoundException("Roadmap")

        if roadmap.user_id != user_id:
            logger.warning(
                "get_roadmap_insights: User %s attempted to read insights for roadmap %s owned by %s",
                user_id,
                roadmap_id,
                roadmap.user_id,
            )
            raise ForbiddenException("You do not have permission to access these insights.")

        # 2. Fetch all modules with nested videos to build progress mapping
        modules = (
            db.query(Module)
            .options(
                selectinload(Module.module_videos)
                .selectinload(ModuleVideo.video)
            )
            .filter(Module.roadmap_id == roadmap_id)
            .order_by(Module.position)
            .all()
        )

        # 3. Query completed video IDs & notes for this user
        progress_records = (
            db.query(VideoProgress)
            .filter(
                VideoProgress.user_id == user_id,
                VideoProgress.roadmap_id == roadmap_id,
            )
            .all()
        )

        completed_video_ids = {p.video_id for p in progress_records if p.is_completed}
        notes_by_video_id = {p.video_id: p.user_notes for p in progress_records if p.user_notes}

        # 4. Compile modules summary
        modules_summary = []
        for m in modules:
            total_count = len(m.module_videos)
            completed_count = sum(1 for mv in m.module_videos if mv.video_id in completed_video_ids)
            modules_summary.append({
                "name": m.name,
                "description": m.description,
                "total_count": total_count,
                "completed_count": completed_count,
            })

        # If no modules exist yet, compile a mock summary from videos
        if not modules_summary:
            videos = db.query(Video).filter(Video.roadmap_id == roadmap_id).all()
            modules_summary.append({
                "name": "General Fundamentals",
                "description": "Unsorted roadmap videos.",
                "total_count": len(videos),
                "completed_count": len(completed_video_ids),
            })

        # 5. Compile completed video details (with user notes)
        completed_videos = []
        for p in progress_records:
            if p.is_completed:
                # Find the video details
                video = db.query(Video).filter(Video.id == p.video_id).first()
                if video:
                    completed_videos.append({
                        "title": video.title,
                        "description": video.description,
                        "user_notes": p.user_notes,
                    })

        # 6. Call AI service to generate study insights
        insights = self.ai_service.generate_learning_insights(
            roadmap_title=roadmap.title,
            modules_summary=modules_summary,
            completed_videos=completed_videos,
        )

        return insights


def run_background_insights_refresh(roadmap_id: uuid.UUID, user_id: uuid.UUID):
    """
    Asynchronously regenerates study insights and updates the database cache.
    """
    from app.database import SessionLocal
    from app.services.insights_service import InsightsService
    from app.models.roadmap import Roadmap
    import json

    logger.info("Starting background insights refresh for roadmap %s", roadmap_id)
    db = SessionLocal()
    try:
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            logger.error("Background insights: Roadmap %s not found in DB", roadmap_id)
            return

        # Generate insights
        insights_service = InsightsService()
        insights = insights_service.get_roadmap_insights(
            roadmap_id=roadmap_id,
            user_id=user_id,
            db=db,
        )

        # Cache them
        roadmap.insights_json = json.dumps(insights)
        db.commit()
        logger.info("Background insights refresh completed successfully for roadmap %s", roadmap_id)
    except Exception as exc:
        logger.error("Background insights refresh failed for roadmap %s: %s", roadmap_id, exc)
    finally:
        db.close()

