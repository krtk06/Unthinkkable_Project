import pytest
from pydantic import ValidationError

from app.domain.job import JobRequirements, Requirement
from app.domain.match import MatchResult, ModelMetadata
from app.domain.resume import Candidate, Contact, Education, Experience, ExtractedResume


def test_resume_schema_accepts_complete_candidate() -> None:
    resume = ExtractedResume(
        candidate=Candidate(
            name="Ada Lovelace",
            contact=Contact.model_validate(
                {"email": "ada@example.com", "phone": None, "url": "https://example.com/ada"}
            ),
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


def test_resume_schema_requires_nested_fields_and_fixed_version() -> None:
    schema = ExtractedResume.model_json_schema()

    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert schema["$defs"]["Education"]["required"] == [
        "institution",
        "degree",
        "field",
        "graduation_date",
    ]
    assert schema["$defs"]["Certification"]["required"] == ["name", "issuer", "date"]
    assert "languages" not in schema["required"]


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
            skills_score=8,
            experience_score=8,
            education_score=8,
            matching_skills=[],
            missing_skills=[],
            semantic_similarity=6.0,
            analysis="",
            shortlisted=True,
            model=ModelMetadata(provider="test", model="test", prompt_version="test-v1"),
        )


def test_job_schema_requires_explicit_requirement_type() -> None:
    requirement = Requirement(name="Python", type="skill")
    job = JobRequirements(title="Engineer", required=[requirement])

    assert job.required[0].type == "skill"


def test_match_schema_requires_explanation_fields() -> None:
    schema = MatchResult.model_json_schema()

    assert schema["required"] == [
        "candidate_id",
        "score",
        "skills_score",
        "experience_score",
        "education_score",
        "semantic_similarity",
        "analysis",
        "shortlisted",
        "model",
    ]
