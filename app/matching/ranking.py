from typing import Any

from app.domain.match import MatchResult


def rank_matches(
    matches: list[MatchResult],
    threshold: int | None = None,
    top_n: int | None = None,
    filters: dict[str, Any] | None = None,
    metadata: dict[str, dict[str, Any]] | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> list[MatchResult]:
    if threshold is not None and top_n is not None:
        raise ValueError("THRESHOLD_TOP_N_CONFLICT")
    if threshold is not None and not 1 <= threshold <= 10:
        raise ValueError("INVALID_THRESHOLD")
    if top_n is not None and top_n < 0:
        raise ValueError("INVALID_TOP_N")
    if offset < 0 or (limit is not None and limit < 0):
        raise ValueError("INVALID_PAGINATION")

    selected = [item for item in matches if _matches_filters(item, filters or {}, metadata or {})]
    if threshold is not None:
        selected = [item for item in selected if item.score >= threshold]
    selected.sort(key=lambda item: (-item.score, -item.required_coverage, item.candidate_id))
    if top_n is not None:
        selected = selected[:top_n]
    return selected[offset:] if limit is None else selected[offset : offset + limit]


def _matches_filters(
    item: MatchResult, filters: dict[str, Any], metadata: dict[str, dict[str, Any]]
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
    candidate_metadata = metadata.get(item.candidate_id, {})
    if (
        "min_preferred_coverage" in filters
        and item.preferred_coverage < filters["min_preferred_coverage"]
    ):
        return False
    if (
        "required_skills_complete" in filters
        and candidate_metadata.get("required_skills_complete")
        != filters["required_skills_complete"]
    ):
        return False
    if (
        "min_experience_months" in filters
        and candidate_metadata.get("experience_months", 0) < filters["min_experience_months"]
    ):
        return False
    if "work_mode" in filters and candidate_metadata.get("work_mode") != filters["work_mode"]:
        return False
    if "status" in filters and candidate_metadata.get("status") != filters["status"]:
        return False
    if "location" in filters and candidate_metadata.get("location") != filters["location"]:
        return False
    return True
