import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

DateValue = Annotated[str, StringConstraints(pattern=r"^\d{4}(-\d{2})?$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Contact(StrictModel):
    email: str | None = None
    phone: str | None = None
    url: str | None = None


class Candidate(StrictModel):
    name: str | None = None
    contact: Contact = Field(default_factory=Contact)
    location: str | None = None


class Experience(StrictModel):
    company: str | None = None
    role: str | None = None
    start_date: DateValue | None = None
    end_date: str | None = None
    duration_months: int | None = Field(default=None, ge=0)
    description: str = ""
    evidence: list[str] = Field(default_factory=list)

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, value: str | None) -> str | None:
        if value is None or value == "present":
            return value
        if not re.fullmatch(r"\d{4}(-\d{2})?", value):
            raise ValueError("end_date must be YYYY, YYYY-MM, or present")
        return value


class Education(StrictModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    graduation_date: str | None = None


class Certification(StrictModel):
    name: str
    issuer: str | None = None
    date: str | None = None


class ExtractedResume(StrictModel):
    schema_version: str = "1.0"
    candidate: Candidate = Field(default_factory=Candidate)
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
