"""
SkillMap AI — Roadmaps Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
All roadmap-related HTTP endpoints.

Endpoints:
  POST /api/v1/roadmaps/import        → Import a YouTube playlist
  GET  /api/v1/roadmaps               → List authenticated user's roadmaps
  GET  /api/v1/roadmaps/{roadmap_id}  → Roadmap detail with full video list

Design:
  - Router is thin — all business logic lives in the service layer.
  - Ordering of routes matters: /import must be declared BEFORE /{roadmap_id}
    or FastAPI will try to parse "import" as a UUID and return a 422.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.dependencies.db import get_db
from app.models.user import User
from app.schemas.roadmap import (
    PlaylistImportRequest,
    RoadmapDetailResponse,
    RoadmapImportResponse,
    RoadmapSummary,
)
from app.schemas.module import GenerateModulesResponse, ModuleResponse
from app.schemas.insight import RoadmapInsightsResponse
from app.services.roadmap_service import RoadmapService
from app.services.youtube_service import YouTubeService
from app.services.module_service import ModuleService
from app.services.insights_service import InsightsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roadmaps", tags=["Roadmaps"])


# ── Service dependencies ──────────────────────────────────────────

def get_youtube_service() -> YouTubeService:
    """Provides a YouTubeService instance. Override in tests."""
    return YouTubeService()


def get_roadmap_service() -> RoadmapService:
    """Provides a RoadmapService instance. Override in tests."""
    return RoadmapService()


def get_module_service() -> ModuleService:
    """Provides a ModuleService instance. Override in tests."""
    return ModuleService()


def get_insights_service() -> InsightsService:
    """Provides an InsightsService instance. Override in tests."""
    return InsightsService()


# ─────────────────────────────────────────────────────────────────
# POST /roadmaps/import
# NOTE: Must come BEFORE /{roadmap_id} to avoid routing conflicts.
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/import",
    response_model=RoadmapImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import a YouTube playlist as a roadmap",
    description=(
        "Fetches all video metadata from the YouTube Data API v3 "
        "and persists a new Roadmap + Video records. "
        "Requires authentication."
    ),
    responses={
        201: {"description": "Playlist imported successfully."},
        400: {"description": "Invalid URL, quota exceeded, or rate limited."},
        401: {"description": "Not authenticated."},
        404: {"description": "Playlist not found or is private."},
    },
)
def import_playlist(
    payload: PlaylistImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    youtube_service: YouTubeService = Depends(get_youtube_service),
) -> RoadmapImportResponse:
    """Import pipeline — delegates entirely to YouTubeService."""
    logger.info("User %s importing playlist: %s", current_user.id, payload.playlist_url)

    result = youtube_service.import_playlist(
        playlist_url=payload.playlist_url,
        user_id=current_user.id,
        db=db,
    )

    from app.services.youtube_service import run_background_pipeline
    background_tasks.add_task(
        run_background_pipeline,
        roadmap_id=result.roadmap_id,
        user_id=current_user.id
    )

    logger.info(
        "Import started: roadmap_id=%s title=%r",
        result.roadmap_id, result.title,
    )
    return result


# ─────────────────────────────────────────────────────────────────
# GET /roadmaps
# ─────────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=list[RoadmapSummary],
    status_code=status.HTTP_200_OK,
    summary="List all roadmaps for the authenticated user",
    description=(
        "Returns a paginated list of roadmaps belonging to the current user. "
        "Ordered by newest first. Does not include video lists — "
        "use the detail endpoint for that."
    ),
    responses={
        200: {"description": "List of roadmap summaries."},
        401: {"description": "Not authenticated."},
    },
)
def list_roadmaps(
    skip: int = Query(default=0, ge=0, description="Number of records to skip."),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
) -> list[RoadmapSummary]:
    """
    Returns lightweight RoadmapSummary objects (no nested videos).

    Why no videos here?
    Returning videos in a list endpoint would:
      - Multiply the response payload by N videos per roadmap
      - Require N+1 queries or a complex JOIN
    Use GET /roadmaps/{id} to get the full video list for one roadmap.
    """
    logger.info(
        "User %s listing roadmaps (skip=%d limit=%d)",
        current_user.id, skip, limit,
    )
    return roadmap_service.get_user_roadmaps(
        user_id=current_user.id,
        db=db,
        skip=skip,
        limit=limit,
    )


# ─────────────────────────────────────────────────────────────────
# GET /roadmaps/{roadmap_id}
# NOTE: This must come AFTER /import — see module docstring.
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/{roadmap_id}",
    response_model=RoadmapDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get roadmap detail with all videos",
    description=(
        "Returns full roadmap information including all videos ordered "
        "by their playlist position. Only the owner can access their roadmaps."
    ),
    responses={
        200: {"description": "Roadmap detail with video list."},
        401: {"description": "Not authenticated."},
        403: {"description": "Roadmap belongs to a different user."},
        404: {"description": "Roadmap not found."},
    },
)
def get_roadmap(
    roadmap_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
):
    """
    Fetch a single roadmap + all its videos.
    Raises 404 if not found, 403 if it belongs to a different user.
    """
    logger.info("[ROUTERS_TRACE] User %s fetching roadmap %s", current_user.id, roadmap_id)

    try:
        result = roadmap_service.get_roadmap_detail(
            roadmap_id=roadmap_id,
            user_id=current_user.id,
            db=db,
        )

        logger.info(
            "[ROUTERS_TRACE] Roadmap detail: id=%s title=%r videos=%d",
            result.id, result.title, len(result.videos),
        )
        return result
    except Exception as e:
        import traceback
        tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        logger.error("[ROUTERS_TRACE_ERROR] Exception in get_roadmap: %s\n%s", e, tb_str)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Internal Error: {e} | Traceback: {tb_str}"
            }
        )



# ─────────────────────────────────────────────────────────────────
# DELETE /roadmaps/{roadmap_id}
# ─────────────────────────────────────────────────────────────────
@router.delete(
    "/{roadmap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a roadmap and all associated resources",
    description=(
        "Deletes the roadmap, its videos, progress records, modules, "
        "and removes all corresponding vector embeddings from ChromaDB. "
        "Only the owner can delete a roadmap."
    ),
    responses={
        204: {"description": "Roadmap deleted successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Roadmap belongs to a different user."},
        404: {"description": "Roadmap not found."},
    },
)
def delete_roadmap(
    roadmap_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    roadmap_service: RoadmapService = Depends(get_roadmap_service),
) -> None:
    """Deletes a roadmap and its associated vectors and database records."""
    logger.info("User %s requested deletion of roadmap %s", current_user.id, roadmap_id)
    roadmap_service.delete_roadmap(
        roadmap_id=roadmap_id,
        user_id=current_user.id,
        db=db,
    )


# ─────────────────────────────────────────────────────────────────
# POST /roadmaps/{roadmap_id}/generate-modules
# ─────────────────────────────────────────────────────────────────
@router.post(
    "/{roadmap_id}/generate-modules",
    response_model=GenerateModulesResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate learning modules for a roadmap",
    description=(
        "Uses AI to group videos in the roadmap into logical learning modules. "
        "Replaces any existing modules for this roadmap."
    ),
    responses={
        200: {"description": "Modules successfully generated and saved."},
        401: {"description": "Not authenticated."},
        403: {"description": "Roadmap belongs to a different user."},
        404: {"description": "Roadmap not found."},
    },
)
def generate_roadmap_modules(
    roadmap_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    module_service: ModuleService = Depends(get_module_service),
) -> GenerateModulesResponse:
    """Invokes AI Service to group roadmap videos into modules."""
    logger.info(
        "User %s generating modules for roadmap %s",
        current_user.id,
        roadmap_id,
    )
    count = module_service.generate_and_store_modules(
        roadmap_id=roadmap_id,
        user_id=current_user.id,
        db=db,
    )
    return GenerateModulesResponse(modules_created=count)


# ─────────────────────────────────────────────────────────────────
# GET /roadmaps/{roadmap_id}/modules
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/{roadmap_id}/modules",
    response_model=list[ModuleResponse],
    status_code=status.HTTP_200_OK,
    summary="Get learning modules for a roadmap",
    description="Returns all modules and their associated videos for a roadmap.",
    responses={
        200: {"description": "List of modules with nested videos."},
        401: {"description": "Not authenticated."},
        403: {"description": "Roadmap belongs to a different user."},
        404: {"description": "Roadmap not found."},
    },
)
def get_roadmap_modules(
    roadmap_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    module_service: ModuleService = Depends(get_module_service),
) -> list[ModuleResponse]:
    """Fetch all modules + nested videos for a single roadmap."""
    logger.info(
        "User %s fetching modules for roadmap %s",
        current_user.id,
        roadmap_id,
    )
    return module_service.get_roadmap_modules(
        roadmap_id=roadmap_id,
        user_id=current_user.id,
        db=db,
    )


# ─────────────────────────────────────────────────────────────────
# GET /roadmaps/{roadmap_id}/insights
# ─────────────────────────────────────────────────────────────────
@router.get(
    "/{roadmap_id}/insights",
    response_model=RoadmapInsightsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get learning insights for a roadmap",
    description="Returns personalized AI-powered study insights and recommendations based on progress.",
    responses={
        200: {"description": "Learning insights generated successfully."},
        401: {"description": "Not authenticated."},
        403: {"description": "Roadmap belongs to a different user."},
        404: {"description": "Roadmap not found."},
    },
)
def get_roadmap_insights(
    roadmap_id: uuid.UUID,
    force_refresh: bool = Query(default=False, description="Force refresh the cached insights."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    insights_service: InsightsService = Depends(get_insights_service),
) -> RoadmapInsightsResponse:
    """Fetch learning insights for a single roadmap."""
    logger.info(
        "User %s fetching insights for roadmap %s (force_refresh=%s)",
        current_user.id,
        roadmap_id,
        force_refresh,
    )
    from app.models.roadmap import Roadmap
    from app.utils.exceptions import ForbiddenException, NotFoundException
    import json

    roadmap = db.query(Roadmap).filter(Roadmap.id == roadmap_id).first()
    if not roadmap:
        raise NotFoundException("Roadmap")
    if roadmap.user_id != current_user.id:
        raise ForbiddenException("You do not have permission to access this roadmap.")

    if not force_refresh and roadmap.insights_json:
        try:
            return json.loads(roadmap.insights_json)
        except Exception as exc:
            logger.warning("Failed to decode cached insights: %s. Regenerating.", exc)

    insights = insights_service.get_roadmap_insights(
        roadmap_id=roadmap_id,
        user_id=current_user.id,
        db=db,
    )

    roadmap.insights_json = json.dumps(insights)
    db.commit()

    return insights
