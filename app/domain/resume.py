from typing import Annotated, Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

DateValue = Annotated[str, StringConstraints(pattern=r"^\d{4}(-\d{2})?$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Contact(StrictModel):
    email: EmailStr | None
    phone: str | None
    url: AnyUrl | None


class Candidate(StrictModel):
    name: str | None
    contact: Contact
    location: str | None


class Experience(StrictModel):
    company: str | None
    role: str | None
    start_date: DateValue | None
    end_date: str | None
    duration_months: int | None = Field(ge=0)
    description: str
    evidence: list[str] = Field(default_factory=list)

class Education(StrictModel):
    institution: str | None
    degree: str | None
    field: str | None
    graduation_date: str | None


class Certification(StrictModel):
    name: str
    issuer: str | None
    date: str | None


class ExtractedResume(StrictModel):
    schema_version: Literal["1.0"]
    candidate: Candidate
    skills: list[str]
    experience: list[Experience]
    education: list[Education]
    certifications: list[Certification]
    languages: list[str] = Field(default_factory=list)
    warnings: list[str]
