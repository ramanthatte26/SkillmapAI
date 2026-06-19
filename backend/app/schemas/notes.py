"""
SkillMap AI — Video Notes Pydantic Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request and response shapes for per-video AI notes generation endpoints.

The notes are stored as a JSON blob in videos.ai_notes (Text column)
and deserialized here into a typed structure.
"""

import uuid

from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────
# Response schemas
# ─────────────────────────────────────────────────────────────────


class VideoNotesResponse(BaseModel):
    """
    Structured AI-generated study notes for a single video.

    Returned by both:
      POST /api/v1/videos/{video_id}/generate-notes  (fresh generation)
      GET  /api/v1/videos/{video_id}/notes           (cached retrieval)

    All list fields are guaranteed to be non-null (may be empty lists
    if the AI returns nothing useful or the fallback fires).
    """

    video_id: uuid.UUID
    ai_notes_status: str  # mirrors AINotesStatus enum value: "done" | "failed"
    summary: str
    key_concepts: list[str]
    important_terms: list[str]
    interview_questions: list[str]
