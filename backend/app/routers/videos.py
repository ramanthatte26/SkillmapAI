"""
SkillMap AI — Videos Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Per-video endpoints, specifically AI notes generation and retrieval.

Endpoints:
  POST /api/v1/videos/{video_id}/generate-notes  → Generate + persist AI notes
  GET  /api/v1/videos/{video_id}/notes           → Retrieve cached AI notes

Design:
  - Ownership is enforced via the parent roadmap's user_id.
  - Notes are stored as a JSON blob in videos.ai_notes (Text column).
  - ai_notes_status tracks the generation lifecycle:
      pending   → not yet requested
      generating → AI call in-flight (set immediately before API call)
      done      → successfully generated and persisted
      failed    → generation failed (endpoint still returns fallback notes)
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.user import User
from app.models.video import Video, AINotesStatus
from app.models.roadmap import Roadmap
from app.schemas.notes import VideoNotesResponse
from app.services.ai_service import AIService
from app.services.module_service import ModuleService
from app.utils.exceptions import ForbiddenException, NotFoundException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/videos", tags=["Videos"])


# ── Service dependencies ──────────────────────────────────────────

def get_ai_service() -> AIService:
    """Provides an AIService instance. Override in tests."""
    return AIService()


def get_module_service() -> ModuleService:
    """Provides a ModuleService instance. Override in tests."""
    return ModuleService()


# ── Helper ────────────────────────────────────────────────────────

def _get_video_and_verify_ownership(
    video_id: uuid.UUID,
    current_user: User,
    db: Session,
) -> Video:
    """
    Fetch a Video by its primary key and verify the calling user owns
    the parent Roadmap. Raises 404 or 403 as appropriate.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        logger.warning("Video %s not found", video_id)
        raise NotFoundException("Video")

    roadmap = db.query(Roadmap).filter(Roadmap.id == video.roadmap_id).first()
    if not roadmap:
        logger.warning("Roadmap %s for video %s not found", video.roadmap_id, video_id)
        raise NotFoundException("Roadmap")

    if roadmap.user_id != current_user.id:
        logger.warning(
            "User %s attempted to access video %s owned by user %s",
            current_user.id,
            video_id,
            roadmap.user_id,
        )
        raise ForbiddenException("You do not have permission to access this video.")

    return video


# ─────────────────────────────────────────────────────────────────
# POST /videos/{video_id}/generate-notes
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/{video_id}/generate-notes",
    response_model=VideoNotesResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI study notes for a video",
    description=(
        "Calls the OpenRouter AI API to generate structured study notes for the specified video. "
        "Notes include a summary, key concepts, important terms, and interview questions. "
        "Results are persisted in the database and returned immediately. "
        "Only the roadmap owner can generate notes for their videos."
    ),
    responses={
        200: {"description": "AI notes generated and saved successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Video belongs to a roadmap owned by a different user."},
        404: {"description": "Video not found."},
    },
)
def generate_video_notes(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
    module_service: ModuleService = Depends(get_module_service),
) -> VideoNotesResponse:
    """
    Generate AI-powered study notes for a single video.

    Pipeline:
      1. Verify video exists and is owned by the requesting user.
      2. Mark ai_notes_status = 'generating' immediately (optimistic update).
      3. Resolve the module name this video belongs to (for richer AI context).
      4. Call AIService.generate_video_notes() → structured dict.
      5. Serialize dict to JSON and save to video.ai_notes.
      6. Set ai_notes_status = 'done' (or 'failed' on error).
      7. Return the notes.
    """
    logger.info("User %s generating notes for video %s", current_user.id, video_id)

    video = _get_video_and_verify_ownership(video_id, current_user, db)

    # Fetch the parent roadmap for title context
    roadmap = db.query(Roadmap).filter(Roadmap.id == video.roadmap_id).first()

    # Resolve module name for richer AI context (best-effort, not required)
    module_name: str | None = None
    try:
        modules = module_service.get_roadmap_modules(
            roadmap_id=roadmap.id,
            user_id=current_user.id,
            db=db,
        )
        for mod in modules:
            if any(mv.id == video_id or str(mv.id) == str(video_id) for mv in mod.videos):
                module_name = mod.name
                break
    except Exception as exc:
        logger.warning("Could not resolve module name for video %s: %s", video_id, exc)

    # Mark as generating immediately so the UI can show a spinner
    video.ai_notes_status = AINotesStatus.GENERATING
    db.add(video)
    db.flush()

    try:
        notes_dict = ai_service.generate_video_notes(
            video_title=video.title,
            roadmap_title=roadmap.title,
            module_name=module_name,
            video_description=video.description,
        )

        # Persist the notes as a JSON blob
        video.ai_notes = json.dumps(notes_dict)
        video.ai_notes_status = AINotesStatus.DONE
        db.add(video)
        db.commit()
        db.refresh(video)

        logger.info(
            "Notes persisted for video %s (status=done, roadmap=%s)",
            video_id,
            roadmap.id,
        )

        # Trigger semantic indexing to update index with the generated notes
        try:
            from app.services.search_service import SearchService
            SearchService().index_video(video.id, db)
        except Exception as exc:
            logger.error("Failed to run search indexing for video %s after note generation: %s", video.id, exc)

        return VideoNotesResponse(
            video_id=video.id,
            ai_notes_status=video.ai_notes_status.value,
            **notes_dict,
        )

    except Exception as exc:
        logger.error("Failed to generate notes for video %s: %s", video_id, exc)
        video.ai_notes_status = AINotesStatus.FAILED
        db.add(video)
        db.commit()
        raise


# ─────────────────────────────────────────────────────────────────
# GET /videos/{video_id}/notes
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/{video_id}/notes",
    response_model=VideoNotesResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve cached AI notes for a video",
    description=(
        "Returns previously generated AI study notes for the specified video. "
        "Returns 404 if notes have not been generated yet. "
        "Call POST /generate-notes first to trigger generation."
    ),
    responses={
        200: {"description": "Cached notes returned successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Video belongs to a roadmap owned by a different user."},
        404: {"description": "Video not found, or notes have not been generated yet."},
    },
)
def get_video_notes(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VideoNotesResponse:
    """
    Return cached AI notes for a single video.

    Raises 404 if no notes have been generated yet (ai_notes is NULL
    or ai_notes_status is still 'pending').
    """
    logger.info("User %s fetching notes for video %s", current_user.id, video_id)

    video = _get_video_and_verify_ownership(video_id, current_user, db)

    if video.ai_notes_status != AINotesStatus.DONE or not video.ai_notes:
        logger.info(
            "Notes not ready for video %s (status=%s)",
            video_id,
            video.ai_notes_status.value,
        )
        raise NotFoundException("Video notes")

    try:
        notes_dict = json.loads(video.ai_notes)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Could not parse stored notes JSON for video %s: %s", video_id, exc)
        raise NotFoundException("Video notes")

    logger.info("Returning cached notes for video %s", video_id)

    return VideoNotesResponse(
        video_id=video.id,
        ai_notes_status=video.ai_notes_status.value,
        summary=notes_dict.get("summary", ""),
        key_concepts=notes_dict.get("key_concepts", []),
        important_terms=notes_dict.get("important_terms", []),
        interview_questions=notes_dict.get("interview_questions", []),
    )
