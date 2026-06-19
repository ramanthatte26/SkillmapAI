"""
SkillMap AI — Search Router
~~~~~~~~~~~~~~~~~~~~~~~~~~~
FastAPI router registering the semantic search endpoint.
"""

import logging
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search"])


def get_search_service() -> SearchService:
    """Provides a SearchService instance. Override in tests."""
    return SearchService()


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search concepts across an imported roadmap",
    description=(
        "Performs a semantic similarity search across knowledge documents of "
        "a specific roadmap. Returns matched videos, scores, and context snippets. "
        "Only searches within roadmaps owned by the authenticated user."
    ),
    responses={
        200: {"description": "Query processed successfully, results returned."},
        401: {"description": "Not authenticated."},
        403: {"description": "Roadmap belongs to another user."},
        404: {"description": "Roadmap not found."},
    },
)
def search_roadmap(
    payload: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Semantic search handler — delegates query processing to SearchService."""
    logger.info(
        "search_roadmap: User %s searching roadmap %s for query: %r",
        current_user.id,
        payload.roadmap_id,
        payload.query,
    )
    
    results = search_service.search(
        roadmap_id=payload.roadmap_id,
        query=payload.query,
        user_id=current_user.id,
        db=db,
    )
    
    return SearchResponse(results=results)
