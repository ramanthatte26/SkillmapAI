"""
SkillMap AI — Module Pydantic Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Request and response shapes for learning module endpoints.
"""

import uuid
from pydantic import BaseModel
from app.schemas.roadmap import VideoResponse


class ModuleResponse(BaseModel):
    """
    Response schema for a single learning module,
    including the ordered list of videos belonging to it.
    """

    id: uuid.UUID
    name: str
    description: str | None
    position: int
    videos: list[VideoResponse] = []

    model_config = {"from_attributes": True}


class GenerateModulesResponse(BaseModel):
    """
    Response schema after successfully generating modules.
    Returns the total number of modules created.
    """

    modules_created: int
