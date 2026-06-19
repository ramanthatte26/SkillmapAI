"""
SkillMap AI — Learning Insights Pydantic Schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Response shape for the AI learning insights retrieval endpoint.
"""

from pydantic import BaseModel


class RoadmapInsightsResponse(BaseModel):
    """
    Response model containing AI-generated learning metrics,
    personalized strengths, weak areas, and actionable study recommendations.
    """

    summary: str
    strengths: list[str]
    weak_areas: list[str]
    recommended_next_module: str
    estimated_completion_days: int
    study_recommendation: str
