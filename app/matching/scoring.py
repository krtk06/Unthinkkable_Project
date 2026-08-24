import random
import re
from collections.abc import Callable
from typing import Protocol

from app.domain.job import JobRequirements
from app.domain.match import MatchBreakdown, MatchResult, ModelMetadata
from app.domain.resume import ExtractedResume
from app.llm.client import LLMError


class ScoringClient(Protocol):
    def score_match(
        self, requirements: JobRequirements, resume: ExtractedResume, embedding_context: str
    ) -> MatchBreakdown: ...


def score_candidate(
    requirements: JobRequirements,
    resume: ExtractedResume,
    embedding_context: str,
    client: ScoringClient,
    *,
    model: ModelMetadata,
    shortlist_threshold: float = 7.0,
    sleeper: Callable[[float], None] | None = None,
    jitter: Callable[[float, float], float] | None = None,
) -> MatchResult:
    """Run LLM scoring with retries and assemble the persisted MatchResult.

    The LLM returns the breakdown (scores, skills, analysis); the semantic
    similarity and shortlist flag are computed here, not by the model.
    """
    wait = sleeper or _sleep
    add_jitter = jitter or random.uniform
    for attempt in range(3):
        try:
            breakdown = client.score_match(requirements, resume, embedding_context)
            return MatchResult(
                candidate_id="",
                score=breakdown.score,
                skills_score=breakdown.skills_score,
                experience_score=breakdown.experience_score,
                education_score=breakdown.education_score,
                matching_skills=breakdown.matching_skills,
                missing_skills=breakdown.missing_skills,
                semantic_similarity=_semantic_similarity(embedding_context),
                analysis=breakdown.analysis,
                shortlisted=breakdown.score >= shortlist_threshold,
                model=model,
            )
        except LLMError as error:
            if not error.retryable or attempt == 2:
                raise
            wait(0.5 * (2**attempt) + add_jitter(0, 0.1))
    raise RuntimeError("unreachable")


def _semantic_similarity(embedding_context: str) -> float:
    """Extract a 0-10 similarity from the embedding context string.

    The context is expected to carry a numeric similarity; when absent or
    malformed, fall back to 0.0 so the UI never renders a blank value.
    """
    match = re.search(r"similarity[:=]\s*([\d.]+)", embedding_context)
    if match is None:
        return 0.0
    try:
        value = float(match.group(1))
    except ValueError:
        return 0.0
    return max(0.0, min(10.0, value))


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
