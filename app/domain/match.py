from pydantic import Field

from app.domain.resume import StrictModel


class Evidence(StrictModel):
    claim: str
    source: str
    quote: str


class ModelMetadata(StrictModel):
    provider: str
    model: str
    prompt_version: str


class MatchResult(StrictModel):
    candidate_id: str
    score: int = Field(ge=1, le=10)
    required_coverage: float = Field(ge=0, le=1)
    preferred_coverage: float = Field(ge=0, le=1)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list, max_length=5)
    uncertainty: list[str] = Field(default_factory=list)
    model: ModelMetadata
