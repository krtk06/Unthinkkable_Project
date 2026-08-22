import pytest

from app.domain.job import JobRequirements, Requirement
from app.matching.job_requirements import normalize_job_description


class FakeJobClient:
    def __init__(self, result: JobRequirements) -> None:
        self.result = result
        self.received: list[str] = []

    def extract_job(self, text: str) -> JobRequirements:
        self.received.append(text)
        return self.result


def test_normalizes_free_text_job_description() -> None:
    expected = JobRequirements(
        title="Backend Engineer",
        required=[Requirement(name="Python", type="skill")],
        preferred=[Requirement(name="Kubernetes", type="skill")],
    )
    client = FakeJobClient(expected)

    result = normalize_job_description("Must have Python; Kubernetes is a plus", client)

    assert result == expected
    assert client.received == ["Must have Python; Kubernetes is a plus"]


def test_preserves_ambiguities_from_llm_output() -> None:
    expected = JobRequirements(
        title="Engineer",
        preferred=[Requirement(name="cloud experience", type="experience")],
        ambiguities=["Cloud experience is not labeled required or preferred"],
    )

    result = normalize_job_description("Cloud experience", FakeJobClient(expected))

    assert result.ambiguities == ["Cloud experience is not labeled required or preferred"]
    assert result.required == []


def test_accepts_already_normalized_requirements_without_llm_call() -> None:
    requirements = JobRequirements(title="Engineer")

    assert normalize_job_description(requirements, None) is requirements


def test_rejects_empty_job_description() -> None:
    with pytest.raises(ValueError, match="EMPTY_JOB_DESCRIPTION"):
        normalize_job_description("  ", FakeJobClient(JobRequirements()))
