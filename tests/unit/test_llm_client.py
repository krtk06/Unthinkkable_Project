import json

import pytest

from app.domain.match import MatchResult
from app.domain.resume import ExtractedResume
from app.llm.client import StructuredLLMClient
from app.llm.validation import StructuredOutputError, validate_match_evidence


def valid_resume_payload() -> dict[str, object]:
    return {
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


class FakeTransport:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


def test_client_returns_schema_valid_resume() -> None:
    transport = FakeTransport([json.dumps(valid_resume_payload())])
    client = StructuredLLMClient(transport, prompt_version="resume-extraction-v1")

    result = client.extract_resume("Ada\nPython")

    assert isinstance(result, ExtractedResume)
    assert result.skills == ["Python"]
    assert "resume-extraction-v1" in transport.prompts[0]


def test_client_repairs_one_malformed_response() -> None:
    transport = FakeTransport(["not json", json.dumps(valid_resume_payload())])
    client = StructuredLLMClient(transport, prompt_version="resume-extraction-v1")

    result = client.extract_resume("Ada\nPython")

    assert result.candidate.name == "Ada"
    assert len(transport.prompts) == 2
    assert "repair" in transport.prompts[1].lower()


def test_client_fails_after_repair_is_invalid() -> None:
    transport = FakeTransport(["not json", "still not json"])
    client = StructuredLLMClient(transport, prompt_version="resume-extraction-v1")

    with pytest.raises(StructuredOutputError, match="INVALID_JSON"):
        client.extract_resume("Ada\nPython")


def test_evidence_validation_rejects_unknown_source() -> None:
    resume = ExtractedResume.model_validate(valid_resume_payload())
    result = MatchResult.model_validate(
        {
            "candidate_id": "candidate-1",
            "score": 8,
            "required_coverage": 1,
            "preferred_coverage": 0,
            "strengths": [],
            "gaps": [],
            "evidence": [{"claim": "Python", "source": "skills[4]", "quote": "Python"}],
            "uncertainty": [],
            "model": {"provider": "test", "model": "test", "prompt_version": "v1"},
        }
    )

    with pytest.raises(StructuredOutputError, match="EVIDENCE_SOURCE_NOT_FOUND"):
        validate_match_evidence(result, resume)
