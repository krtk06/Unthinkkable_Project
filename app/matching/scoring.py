from collections.abc import Callable
from typing import Protocol

from app.domain.job import JobRequirements
from app.domain.match import MatchResult
from app.domain.resume import ExtractedResume


class ScoringClient(Protocol):
    def score_match(
        self, requirements: JobRequirements, resume: ExtractedResume, embedding_context: str
    ) -> MatchResult: ...


def score_candidate(
    requirements: JobRequirements,
    resume: ExtractedResume,
    embedding_context: str,
    client: ScoringClient,
    *,
    sleeper: Callable[[float], None] | None = None,
) -> MatchResult:
    wait = sleeper or _sleep
    for attempt in range(3):
        try:
            return client.score_match(requirements, resume, embedding_context)
        except (TimeoutError, ConnectionError):
            if attempt == 2:
                raise
            wait(0.5 * (2**attempt))
    raise RuntimeError("unreachable")


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)
