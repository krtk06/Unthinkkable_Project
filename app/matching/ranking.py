from typing import Any

from app.domain.match import MatchResult


def rank_matches(
    matches: list[MatchResult],
    threshold: int | None = None,
    top_n: int | None = None,
    filters: dict[str, Any] | None = None,
    metadata: dict[str, str] | None = None,
) -> list[MatchResult]:
    if threshold is not None and top_n is not None:
        raise ValueError("THRESHOLD_TOP_N_CONFLICT")
    if threshold is not None and not 1 <= threshold <= 10:
        raise ValueError("INVALID_THRESHOLD")
    if top_n is not None and top_n < 0:
        raise ValueError("INVALID_TOP_N")

    selected = [item for item in matches if _matches_filters(item, filters or {}, metadata or {})]
    if threshold is not None:
        selected = [item for item in selected if item.score >= threshold]
    selected.sort(key=lambda item: (-item.score, -item.required_coverage, item.candidate_id))
    return selected[:top_n] if top_n is not None else selected


def _matches_filters(
    item: MatchResult, filters: dict[str, Any], metadata: dict[str, str]
) -> bool:
    if "min_score" in filters and item.score < filters["min_score"]:
        return False
    if "max_score" in filters and item.score > filters["max_score"]:
        return False
    if (
        "min_required_coverage" in filters
        and item.required_coverage < filters["min_required_coverage"]
    ):
        return False
    if "location" in filters and metadata.get(item.candidate_id) != filters["location"]:
        return False
    return True
