import pytest

from app.domain.match import MatchResult, ModelMetadata
from app.matching.ranking import rank_matches


def match(candidate_id: str, score: int, coverage: float = 1.0) -> MatchResult:
    return MatchResult(
        candidate_id=candidate_id,
        score=score,
        required_coverage=coverage,
        preferred_coverage=0,
        strengths=[],
        gaps=[],
        evidence=[],
        uncertainty=[],
        model=ModelMetadata(provider="test", model="test", prompt_version="v1"),
    )


def test_ranks_by_score_then_coverage_then_candidate_id() -> None:
    results = rank_matches([match("b", 8, 0.8), match("a", 8, 0.8), match("c", 9)])

    assert [result.candidate_id for result in results] == ["c", "a", "b"]


def test_supports_threshold_and_top_n_shortlisting() -> None:
    results = [match("a", 9), match("b", 7), match("c", 5)]

    assert [item.candidate_id for item in rank_matches(results, threshold=7)] == ["a", "b"]
    assert [item.candidate_id for item in rank_matches(results, top_n=2)] == ["a", "b"]


def test_filters_score_coverage_and_location() -> None:
    results = [match("a", 9, 1), match("b", 8, 0.5), match("c", 7, 1)]
    metadata = {
        "a": {"location": "London", "required_skills_complete": True, "status": "scored"},
        "b": {"location": "New York", "required_skills_complete": False},
        "c": {"location": "London", "required_skills_complete": True},
    }

    filtered = rank_matches(
        results,
        filters={"min_score": 8, "min_required_coverage": 0.9, "location": "London"},
        metadata=metadata,
    )

    assert [item.candidate_id for item in filtered] == ["a"]


def test_supports_extended_filters_and_pagination() -> None:
    results = [match("a", 9), match("b", 8), match("c", 7)]
    metadata = {
        "a": {"experience_months": 12, "work_mode": "remote", "status": "scored"},
        "b": {"experience_months": 24, "work_mode": "remote", "status": "scored"},
        "c": {"experience_months": 36, "work_mode": "onsite", "status": "failed"},
    }

    filtered = rank_matches(
        results,
        filters={
            "min_experience_months": 24,
            "max_experience_months": 24,
            "work_mode": "remote",
            "status": "scored",
        },
        metadata=metadata,
        offset=0,
        limit=1,
    )

    assert [item.candidate_id for item in filtered] == ["b"]


def test_rejects_combining_threshold_and_top_n() -> None:
    with pytest.raises(ValueError, match="THRESHOLD_TOP_N_CONFLICT"):
        rank_matches([match("a", 8)], threshold=7, top_n=1)
