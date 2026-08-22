from typing import Literal

from pydantic import Field

from app.domain.resume import StrictModel

RequirementType = Literal["skill", "experience", "education", "certification", "constraint"]


class Requirement(StrictModel):
    name: str
    type: RequirementType
    minimum: str | None = None
    required: bool = False


class JobRequirements(StrictModel):
    title: str | None = None
    summary: str | None = None
    required: list[Requirement] = Field(default_factory=list)
    preferred: list[Requirement] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
