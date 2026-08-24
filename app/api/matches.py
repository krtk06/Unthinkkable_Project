from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException


@dataclass
class MatchFilters:
    threshold: float | None = None
    min_score: float | None = None
    max_score: float | None = None
    min_skills_score: float | None = None
    shortlisted: bool | None = None
    required_skills_complete: bool | None = None
    min_experience_months: int | None = None


def _get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
        if cur is default:
            return default
    return cur


def _build_matches(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **candidate["match"],
            "_metadata": {
                "status": candidate["resume"].get("status"),
                "location": _get_nested(candidate, "resume", "parsed_json", "candidate", "location"),
                "work_mode": _get_nested(candidate, "resume", "parsed_json", "work_mode"),
                "required_skills_complete": _get_nested(
                    candidate, "resume", "parsed_json", "required_skills_complete"
                ),
                "experience_months": _get_nested(
                    candidate, "resume", "parsed_json", "experience_months", default=0
                ),
            },
        }
        for candidate in candidates
        if candidate.get("match")
    ]


def _apply_filters(
    matches: list[dict[str, Any]],
    filters: MatchFilters,
) -> list[dict[str, Any]]:
    if filters.threshold is not None:
        matches = [m for m in matches if m.get("score", 0) >= filters.threshold]
    if filters.min_score is not None:
        matches = [m for m in matches if m.get("score", 0) >= filters.min_score]
    if filters.max_score is not None:
        matches = [m for m in matches if m.get("score", 0) <= filters.max_score]
    if filters.min_skills_score is not None:
        matches = [m for m in matches if m.get("skills_score", 0) >= filters.min_skills_score]
    if filters.shortlisted is not None:
        matches = [m for m in matches if m.get("shortlisted", False) == filters.shortlisted]
    if filters.required_skills_complete is not None:
        matches = [
            m for m in matches if m["_metadata"].get("required_skills_complete") == filters.required_skills_complete
        ]
    if filters.min_experience_months is not None:
        matches = [
            m for m in matches if m["_metadata"].get("experience_months", 0) >= filters.min_experience_months
        ]
    return matches


def _apply_metadata_filters(
    matches: list[dict[str, Any]],
    status: str | None,
    location: str | None,
    work_mode: str | None,
) -> list[dict[str, Any]]:
    if status is not None:
        matches = [m for m in matches if m["_metadata"].get("status") == status]
    if location is not None:
        matches = [m for m in matches if m["_metadata"].get("location") == location]
    if work_mode is not None:
        matches = [m for m in matches if m["_metadata"].get("work_mode") == work_mode]
    return matches


def _sort_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches.sort(
        key=lambda m: (
            -m.get("score", 0),
            -m.get("skills_score", 0),
            m["candidate_id"],
        )
    )
    return matches


def _paginate(
    matches: list[dict[str, Any]],
    limit: int,
    cursor: str | None,
    top_n: int | None,
    threshold: float | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if threshold is not None and top_n is not None:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "THRESHOLD_TOP_N_CONFLICT", "message": "Choose threshold or top_n", "details": {}}},
        )
    if top_n is not None:
        matches = matches[:top_n]
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_LIMIT", "message": "limit must be between 1 and 100", "details": {}}},
        )
    if cursor is not None:
        try:
            cursor_score, cursor_skills, cursor_id = cursor.split(":", 2)
            cursor_key = (-float(cursor_score), -float(cursor_skills), cursor_id)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_CURSOR", "message": "Cursor is malformed", "details": {}}},
            ) from error
        matches = [
            m
            for m in matches
            if (-m.get("score", 0), -m.get("skills_score", 0), m["candidate_id"]) > cursor_key
        ]
    page = matches[:limit]
    next_cursor = None
    if len(matches) > limit:
        last = page[-1]
        next_cursor = f"{last['score']}:{last.get('skills_score', 0)}:{last['candidate_id']}"
    for m in page:
        m.pop("_metadata", None)
    return page, next_cursor
