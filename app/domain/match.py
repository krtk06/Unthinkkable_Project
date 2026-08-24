from pydantic import Field

from app.domain.resume import StrictModel


class ModelMetadata(StrictModel):
    provider: str
    model: str
    prompt_version: str


class MatchBreakdown(StrictModel):
    """LLM-produced scoring breakdown (returned by the scoring prompt)."""

    score: float = Field(ge=0, le=10)
    skills_score: float = Field(ge=0, le=10)
    experience_score: float = Field(ge=0, le=10)
    education_score: float = Field(ge=0, le=10)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    analysis: str


class MatchResult(StrictModel):
    """Persisted match: LLM breakdown plus app-computed fields."""

    candidate_id: str
    score: float = Field(ge=0, le=10)
    skills_score: float = Field(ge=0, le=10)
    experience_score: float = Field(ge=0, le=10)
    education_score: float = Field(ge=0, le=10)
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    semantic_similarity: float = Field(ge=0, le=10)
    analysis: str
    shortlisted: bool
    model: ModelMetadata
