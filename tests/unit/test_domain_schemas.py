import pytest
from pydantic import ValidationError

from app.domain.job import JobRequirements, Requirement
from app.domain.match import Evidence, MatchResult, ModelMetadata
from app.domain.resume import Candidate, Contact, Education, Experience, ExtractedResume


def test_resume_schema_accepts_complete_candidate() -> None:
    resume = ExtractedResume(
        candidate=Candidate(
            name="Ada Lovelace",
            contact=Contact(email="ada@example.com", phone=None, url=None),
            location="London",
        ),
        skills=["Python"],
        experience=[
            Experience(
                company="Analytical Engines",
                role="Engineer",
                start_date="2020-01",
                end_date="2024-01",
                duration_months=48,
                description="Built numerical systems.",
                evidence=["Built numerical systems."],
            )
        ],
            education=[
            Education(
                institution="University",
                degree="BSc",
                field="Math",
                graduation_date="2019",
            )
        ],
        certifications=[],
        languages=[],
        warnings=[],
        schema_version="1.0",
    )

    assert resume.schema_version == "1.0"
    assert resume.candidate.name == "Ada Lovelace"


def test_resume_schema_preserves_missing_sections() -> None:
    resume = ExtractedResume(
        candidate=Candidate(
            name=None,
            contact=Contact(email=None, phone=None, url=None),
            location=None,
        ),
        skills=[],
        experience=[],
        education=[],
        certifications=[],
        languages=[],
        warnings=[],
        schema_version="1.0",
    )

    assert resume.candidate.name is None
    assert resume.experience == []
    assert resume.education == []
    assert resume.warnings == []


def test_resume_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ExtractedResume.model_validate({"unexpected": "value"})


def test_experience_rejects_invalid_date() -> None:
    with pytest.raises(ValidationError):
        Experience(
            company=None,
            role=None,
            start_date="January 2020",
            end_date=None,
            duration_months=None,
            description="Worked",
        )


def test_match_schema_rejects_score_outside_rubric() -> None:
    with pytest.raises(ValidationError):
        MatchResult(
            candidate_id="candidate-1",
            score=11,
            required_coverage=1,
            preferred_coverage=0,
            evidence=[Evidence(claim="Python", source="skills[0]", quote="Python")],
            model=ModelMetadata(provider="test", model="test", prompt_version="test-v1"),
        )


def test_job_schema_requires_explicit_requirement_type() -> None:
    requirement = Requirement(name="Python", type="skill", required=True)
    job = JobRequirements(title="Engineer", required=[requirement])

    assert job.required[0].required is True
