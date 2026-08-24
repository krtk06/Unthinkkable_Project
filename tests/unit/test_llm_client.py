import json
from typing import Any

import pytest

from app.domain.resume import ExtractedResume
from app.llm.client import StructuredLLMClient
from app.llm.validation import StructuredOutputError


def valid_resume_payload() -> dict[str, Any]:
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


def test_parse_tolerates_markdown_fences() -> None:
    from app.llm.validation import parse_structured_output

    fenced = f"```json\n{json.dumps(valid_resume_payload())}\n```"
    result = parse_structured_output(fenced, ExtractedResume)
    assert result.candidate.name == "Ada"


def test_parse_extracts_json_from_surrounding_prose() -> None:
    from app.llm.validation import parse_structured_output

    prose = f"Here is the result:\n{json.dumps(valid_resume_payload())}\nHope this helps!"
    result = parse_structured_output(prose, ExtractedResume)
    assert result.skills == ["Python"]


def test_parse_drops_unknown_extra_keys() -> None:
    from app.llm.validation import parse_structured_output

    payload = {**valid_resume_payload(), "confidence": 0.9, "notes": "extra"}
    payload["candidate"] = {**payload["candidate"], "nickname": "Ada"}
    result = parse_structured_output(json.dumps(payload), ExtractedResume)
    assert result.candidate.name == "Ada"
    assert result.skills == ["Python"]


def test_parse_coerces_null_list_fields_to_defaults() -> None:
    from app.llm.validation import parse_structured_output

    payload = valid_resume_payload()
    payload["languages"] = None
    result = parse_structured_output(json.dumps(payload), ExtractedResume)
    assert result.languages == []
    assert result.skills == ["Python"]


def test_parse_still_fails_on_missing_required_fields() -> None:
    from app.llm.validation import parse_structured_output

    with pytest.raises(StructuredOutputError, match="SCHEMA_VALIDATION_FAILED"):
        parse_structured_output(json.dumps({"schema_version": "1.0"}), ExtractedResume)

