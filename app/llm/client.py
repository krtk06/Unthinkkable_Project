from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from app.config import get_settings
from app.domain.job import JobRequirements
from app.domain.match import MatchResult
from app.domain.resume import ExtractedResume
from app.llm.validation import (
    StructuredOutputError,
    parse_structured_output,
    validate_match_evidence,
)


class LLMError(Exception):
    """Base class for retryable LLM provider errors."""

    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMTransport(Protocol):
    def complete(self, prompt: str) -> str:
        """Return a provider response for a prompt."""


class OpenAITransport:
    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        settings = get_settings()
        self.client = OpenAI(api_key=api_key, timeout=settings.llm_timeout)
        self.model = model

    def complete(self, prompt: str) -> str:
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
        except (APIConnectionError, APITimeoutError, RateLimitError) as error:
            raise LLMError(type(error).__name__, str(error)) from error
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("EMPTY_LLM_RESPONSE")
        return content


class LLMClient(Protocol):
    def extract_resume(self, text: str) -> ExtractedResume: ...

    def extract_job(self, text: str) -> JobRequirements: ...

    def score_match(
        self, requirements: JobRequirements, resume: ExtractedResume, embedding_context: str
    ) -> MatchResult: ...


class StructuredLLMClient:
    def __init__(
        self,
        transport: LLMTransport,
        *,
        prompt_version: str,
        prompt_directory: Path = Path("prompts"),
    ) -> None:
        self.transport = transport
        self.prompt_version = prompt_version
        self.prompt_directory = prompt_directory

    def extract_resume(self, text: str) -> ExtractedResume:
        prompt = self._load_prompt("resume_extraction_v1.txt").format(resume_text=text)
        return self._complete_with_repair(prompt, ExtractedResume)

    def extract_job(self, text: str) -> JobRequirements:
        prompt = self._load_prompt("jd_extraction_v1.txt").format(jd_text=text)
        return self._complete_with_repair(prompt, JobRequirements)

    def score_match(
        self, requirements: JobRequirements, resume: ExtractedResume, embedding_context: str
    ) -> MatchResult:
        prompt = self._load_prompt("match_scoring_v1.txt").format(
            requirements_json=requirements.model_dump_json(),
            extracted_resume_json=resume.model_dump_json(),
            embedding_context=embedding_context,
        )
        return self._complete_with_repair(
            prompt, MatchResult, validator=lambda result: validate_match_evidence(result, resume)
        )

    def _complete_with_repair(
        self,
        prompt: str,
        model: type[ModelT],
        validator: Callable[[ModelT], ModelT] | None = None,
    ) -> ModelT:
        raw = self.transport.complete(f"{prompt}\nPROMPT_VERSION: {self.prompt_version}")
        try:
            result = parse_structured_output(raw, model)
            return validator(result) if validator is not None else result
        except StructuredOutputError as error:
            repair_prompt = (
                "REPAIR: Return only valid JSON matching the requested schema. "
                f"The previous response failed with {error.code}.\n"
                f"{prompt}\nPREVIOUS_RESPONSE:\n{raw}"
            )
            repaired = self.transport.complete(repair_prompt)
            result = parse_structured_output(repaired, model)
            return validator(result) if validator is not None else result

    def _load_prompt(self, filename: str) -> str:
        return (self.prompt_directory / filename).read_text(encoding="utf-8")
