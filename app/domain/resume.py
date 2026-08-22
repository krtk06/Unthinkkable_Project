import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

DateValue = Annotated[str, StringConstraints(pattern=r"^\d{4}(-\d{2})?$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Contact(StrictModel):
    email: EmailStr | None
    phone: str | None
    url: str | None


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
    schema_version: str = Field(pattern=r"^1\.0$")
    candidate: Candidate
    skills: list[str]
    experience: list[Experience]
    education: list[Education]
    certifications: list[Certification]
    languages: list[str]
    warnings: list[str]
