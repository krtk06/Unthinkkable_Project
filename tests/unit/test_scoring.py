import pytest

from app.domain.job import JobRequirements
from app.domain.match import MatchResult, ModelMetadata
from app.domain.resume import ExtractedResume
from app.matching.scoring import score_candidate


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


def make_result() -> MatchResult:
    return MatchResult(
        candidate_id="candidate-1",
        score=8,
        required_coverage=1,
        preferred_coverage=0,
        strengths=["Python"],
        gaps=[],
        evidence=[],
        uncertainty=[],
        model=ModelMetadata(provider="fake", model="fake", prompt_version="v1"),
    )


class FakeScoringClient:
    def __init__(self, responses: list[MatchResult | Exception]) -> None:
        self.responses = responses
        self.calls = 0

    def score_match(
        self, requirements: JobRequirements, resume: ExtractedResume, embedding_context: str
    ) -> MatchResult:
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_score_candidate_returns_validated_match() -> None:
    client = FakeScoringClient([make_result()])

    result = score_candidate(JobRequirements(title="Engineer"), make_resume(), "context", client)

    assert result.score == 8
    assert client.calls == 1


def test_score_candidate_retries_transient_provider_failures() -> None:
    client = FakeScoringClient([TimeoutError(), TimeoutError(), make_result()])
    sleeps: list[float] = []

    result = score_candidate(
        JobRequirements(title="Engineer"),
        make_resume(),
        "context",
        client,
        sleeper=sleeps.append,
    )

    assert result.score == 8
    assert client.calls == 3
    assert sleeps == [0.5, 1.0]


def test_score_candidate_raises_after_three_provider_failures() -> None:
    client = FakeScoringClient([TimeoutError(), TimeoutError(), TimeoutError()])

    with pytest.raises(TimeoutError):
        score_candidate(JobRequirements(title="Engineer"), make_resume(), "context", client)
