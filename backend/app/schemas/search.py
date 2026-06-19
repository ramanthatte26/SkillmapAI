"""
SkillMap AI — Search Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pydantic schemas validating input and output for semantic search endpoint.
"""

import uuid
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Payload to perform semantic search within a roadmap."""
    roadmap_id: uuid.UUID = Field(..., description="The ID of the roadmap to search within.")
    query: str = Field(..., min_length=1, description="The query string to match concepts for.")


class SearchResultItem(BaseModel):
    """A matched segment representing a video context alignment."""
    video_id: uuid.UUID = Field(..., description="The ID of the matched video.")
    video_title: str = Field(..., description="The title of the video.")
    module_name: str | None = Field(default=None, description="The name of the module containing this video.")
    similarity_score: float = Field(..., description="The match confidence score (0.0 to 1.0).")
    matched_content_preview: str = Field(..., description="A snippet preview of the matching context.")


class SearchResponse(BaseModel):
    """The structured list of relevant matched videos."""
    results: list[SearchResultItem] = Field(..., description="Top relevant matches ranked by similarity score.")
