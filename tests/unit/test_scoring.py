import pytest

from app.domain.job import JobRequirements
from app.domain.match import MatchBreakdown, ModelMetadata
from app.domain.resume import ExtractedResume
from app.llm.client import LLMError
from app.matching.scoring import score_candidate

MODEL = ModelMetadata(provider="fake", model="fake", prompt_version="v1")


def make_resume() -> ExtractedResume:
    return ExtractedResume.model_validate(
        {
            "schema_version": "1.0",
            "candidate": {
                "name": "Ada",
                "contact": {"email": None, "phone": None, "url": None},
                "location": None,
            },
            "skills": ["Python"],
            "experience": [],
            "education": [],
            "certifications": [],
            "languages": [],
            "warnings": [],
        }
    )


def make_breakdown() -> MatchBreakdown:
    return MatchBreakdown(
        score=8,
        skills_score=8,
        experience_score=10,
        education_score=4,
        matching_skills=["Python"],
        missing_skills=["REST"],
        analysis="The candidate is a strong fit.",
    )


class FakeScoringClient:
    def __init__(self, responses: list[MatchBreakdown | Exception]) -> None:
        self.responses = responses
        self.calls = 0

    def score_match(
        self, requirements: JobRequirements, resume: ExtractedResume, embedding_context: str
    ) -> MatchBreakdown:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_score_candidate_returns_validated_match() -> None:
    client = FakeScoringClient([make_breakdown()])

    result = score_candidate(
        JobRequirements(title="Engineer"),
        make_resume(),
        "similarity:6.4",
        client,
        model=MODEL,
    )

    assert result.score == 8
    assert result.semantic_similarity == 6.4
    assert result.shortlisted is True
    assert result.skills_score == 8
    assert client.calls == 1


def test_score_candidate_retries_transient_provider_failures() -> None:
    client = FakeScoringClient([
            LLMError('API_TIMEOUT', 'timeout', retryable=True),
            LLMError('API_TIMEOUT', 'timeout', retryable=True),
            make_breakdown(),
        ])
    sleeps: list[float] = []

    result = score_candidate(
        JobRequirements(title="Engineer"),
        make_resume(),
        "similarity:6.4",
        client,
        model=MODEL,
        sleeper=sleeps.append,
        jitter=lambda _start, _end: 0.0,
    )

    assert result.score == 8
    assert client.calls == 3
    assert sleeps == [0.5, 1.0]


def test_score_candidate_raises_after_three_provider_failures() -> None:
    client = FakeScoringClient([
            LLMError('API_TIMEOUT', 'timeout', retryable=True),
            LLMError('API_TIMEOUT', 'timeout', retryable=True),
            LLMError('API_TIMEOUT', 'timeout', retryable=True),
        ])

    with pytest.raises(LLMError):
        score_candidate(
            JobRequirements(title="Engineer"),
            make_resume(),
            "similarity:6.4",
            client,
            model=MODEL,
        )
