import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.domain.match import MatchResult
from app.domain.resume import ExtractedResume


class StructuredOutputError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def parse_structured_output[ModelT: BaseModel](raw: str, model: type[ModelT]) -> ModelT:
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise StructuredOutputError("INVALID_JSON", "LLM response is not valid JSON") from error
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise StructuredOutputError("SCHEMA_VALIDATION_FAILED", str(error)) from error


def validate_match_evidence(result: MatchResult, resume: ExtractedResume) -> MatchResult:
    for evidence in result.evidence:
        source_text = _resolve_source(evidence.source, resume)
        if source_text is None:
            raise StructuredOutputError(
                "EVIDENCE_SOURCE_NOT_FOUND", f"Unknown evidence source: {evidence.source}"
            )
        if evidence.quote not in source_text:
            raise StructuredOutputError(
                "EVIDENCE_QUOTE_NOT_FOUND", f"Evidence quote is not present in {evidence.source}"
            )
    return result


def _resolve_source(source: str, resume: ExtractedResume) -> str | None:
    skill_match = re.fullmatch(r"skills\[(\d+)\]", source)
    if skill_match:
        index = int(skill_match.group(1))
        return resume.skills[index] if index < len(resume.skills) else None
    experience_match = re.fullmatch(r"experience\[(\d+)\]\.(description|evidence)", source)
    if experience_match:
        index = int(experience_match.group(1))
        if index >= len(resume.experience):
            return None
        experience = resume.experience[index]
        return (
            experience.description
            if experience_match.group(2) == "description"
            else "\n".join(experience.evidence)
        )
    return None
