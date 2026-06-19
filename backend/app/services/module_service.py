"""
SkillMap AI — Module Service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Coordinates AI module generation, applies validation (healing),
saves module configurations to the database, and retrieves them.
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


class ModuleService:
    """
    Handles business logic for learning modules and database interaction.
    """

    def __init__(self, ai_service: AIService | None = None):
        self.ai_service = ai_service or AIService()

    def generate_and_store_modules(
        self,
        roadmap_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session,
    ) -> int:
        """
        Organize roadmap videos into learning modules:
          1. Retrieve roadmap and verify user ownership.
          2. Retrieve videos sorted by position.
          3. Call the AI service to get the module groupings.
          4. Heal and validate the AI output.
          5. Replace any existing modules in a transaction.
          6. Commit and return the count of modules created.
        """
        # 1. Fetch roadmap and verify ownership
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            logger.warning("generate_and_store_modules: Roadmap %s not found", roadmap_id)
            raise NotFoundException("Roadmap")

        if roadmap.user_id != user_id:
            logger.warning(
                "generate_and_store_modules: User %s attempted to modify roadmap %s owned by %s",
                user_id,
                roadmap_id,
                roadmap.user_id,
            )
            raise ForbiddenException("You do not have permission to modify this roadmap.")

        # 2. Fetch all videos for this roadmap ordered by position
        videos = (
            db.query(Video)
            .filter(Video.roadmap_id == roadmap_id)
            .order_by(Video.position)
            .all()
        )
        total_videos = len(videos)

        if total_videos == 0:
            logger.warning(
                "generate_and_store_modules: Roadmap %s has 0 videos. Cannot generate modules.",
                roadmap_id,
            )
            return 0

        video_titles = [v.title for v in videos]

        # 3. Call AI Service
        raw_modules = self.ai_service.generate_learning_modules(roadmap.title, video_titles)

        # 4. Heal the modules list to ensure database safety and complete coverage
        healed_modules = self._heal_modules(raw_modules, total_videos)

        try:
            # 5. Clear existing modules (foreign key cascade deletes module_videos)
            db.query(Module).filter(Module.roadmap_id == roadmap_id).delete()
            db.flush()

            # 6. Save new modules
            for mod_pos, raw_mod in enumerate(healed_modules):
                module = Module(
                    roadmap_id=roadmap_id,
                    name=raw_mod["name"],
                    description=raw_mod["description"],
                    position=mod_pos,
                )
                db.add(module)
                db.flush()  # Populate module.id for foreign keys

                for item_pos, vid_pos in enumerate(raw_mod["video_positions"]):
                    video = videos[vid_pos]
                    mv = ModuleVideo(
                        module_id=module.id,
                        video_id=video.id,
                        position=item_pos,
                    )
                    db.add(mv)

            db.commit()
            logger.info(
                "generate_and_store_modules: Successfully stored %d modules for roadmap %s",
                len(healed_modules),
                roadmap_id,
            )
            return len(healed_modules)

        except Exception as exc:
            db.rollback()
            logger.error(
                "generate_and_store_modules: Database save failed for roadmap %s: %s",
                roadmap_id,
                exc,
            )
            raise

    def get_roadmap_modules(
        self,
        roadmap_id: uuid.UUID,
        user_id: uuid.UUID,
        db: Session,
    ) -> list[Module]:
        """
        Fetch all modules with their associated videos (populated with completion status).
        """
        # 1. Fetch roadmap and check ownership
        roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
        if not roadmap:
            logger.warning("get_roadmap_modules: Roadmap %s not found", roadmap_id)
            raise NotFoundException("Roadmap")

        if roadmap.user_id != user_id:
            logger.warning(
                "get_roadmap_modules: User %s attempted to access roadmap %s owned by %s",
                user_id,
                roadmap_id,
                roadmap.user_id,
            )
            raise ForbiddenException("You do not have permission to access this roadmap.")

        # 2. Fetch modules with nested relationships using selectinload to avoid N+1 queries
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

        # 3. Query completed video IDs for this user & roadmap
        completed_video_ids = {
            r[0]
            for r in db.query(VideoProgress.video_id)
            .filter(
                VideoProgress.user_id == user_id,
                VideoProgress.roadmap_id == roadmap_id,
                VideoProgress.is_completed == True,
            )
            .all()
        }

        # 4. Attach dynamic is_completed attribute to video ORM models
        for module in modules:
            for mv in module.module_videos:
                mv.video.is_completed = mv.video.id in completed_video_ids

        return modules

    def _heal_modules(self, modules_list: list[dict], total_videos: int) -> list[dict]:
        """
        Validation parser to heal the module lists returned by the AI service.
        Guarantees that:
          - Every video in the roadmap (0 to total_videos-1) is assigned exactly once.
          - No positions are duplicated or out of bounds.
          - Empty modules are discarded.
        """
        # 1. Strip out of bounds indexes
        for m in modules_list:
            m["video_positions"] = [p for p in m.get("video_positions", []) if 0 <= p < total_videos]

        # 2. Prevent duplicate video assignments across modules (first assignment wins)
        assigned = set()
        for m in modules_list:
            unique_positions = []
            for p in m["video_positions"]:
                if p not in assigned:
                    unique_positions.append(p)
                    assigned.add(p)
            m["video_positions"] = unique_positions

        # 3. Handle unassigned video positions
        unassigned = [p for p in range(total_videos) if p not in assigned]
        if unassigned:
            if not modules_list:
                modules_list.append({
                    "name": "General Fundamentals",
                    "description": "Core concepts and general introductory material.",
                    "video_positions": unassigned,
                })
            else:
                # Append unassigned videos to the last module and sort positions
                modules_list[-1]["video_positions"].extend(unassigned)
                modules_list[-1]["video_positions"].sort()

        # 4. Filter out any modules that contain no videos
        if len(modules_list) > 1:
            modules_list = [m for m in modules_list if len(m["video_positions"]) > 0]

        return modules_list
