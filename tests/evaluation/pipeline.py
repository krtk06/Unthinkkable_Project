"""Deterministic offline pipeline used by the evaluation harness.

The proxy extractor/scorer derives predictions from annotated synthetic text
with explicit rules so `python -m tests.evaluation.run` needs no network,
API keys, or provider account. Swap `OfflinePipeline` for a real
`StructuredLLMClient` to measure the production path on the same manifest;
the metric code is provider-independent.

Dataset limitations are documented in `run.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+")
_JOB_LINE_PATTERN = re.compile(r"^-\s+.+?\s+at\s+(?P<company>.+?),")


@dataclass
class ExtractionPrediction:
    name: str | None
    email: str | None
    skills: list[str]
    companies: list[str]


@dataclass
class EvaluationCase:
    resume_id: str
    resume_text: str
    expected_fields: dict[str, Any]
    expected_requirements: dict[str, list[str]]
    reviewer_scores: tuple[int, int]


def extract_fields(text: str) -> ExtractionPrediction:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = lines[0] if lines else None
    email_match = _EMAIL_PATTERN.search(text)
    email = email_match.group(0) if email_match else None
    skills: list[str] = []
    companies: list[str] = []
    for line in lines:
        if line.lower().startswith("skills:"):
            raw = line.split(":", 1)[1].strip()
            skills = [item.strip() for item in raw.split(",") if item.strip()]
        job_match = _JOB_LINE_PATTERN.match(line)
        if job_match:
            companies.append(job_match.group("company").strip())
    return ExtractionPrediction(name=name, email=email, skills=skills, companies=companies)


def score_against_requirements(
    prediction: ExtractionPrediction, requirements: dict[str, list[str]], experience_months: int
) -> int:
    """Rubric-band score from required/preferred coverage and evidence depth."""
    skill_set = {skill.casefold() for skill in prediction.skills}
    required = [item.casefold() for item in requirements.get("required", [])]
    preferred = [item.casefold() for item in requirements.get("preferred", [])]
    if not required:
        return 1
    required_hit = sum(1 for item in required if item in skill_set)
    preferred_hit = sum(1 for item in preferred if item in skill_set)
    coverage = required_hit / len(required)

    deep_experience = experience_months >= 48
    if coverage == 0:
        return 2 if deep_experience or preferred_hit else 1
    if coverage < 0.5:
        return 4 if deep_experience else 3
    if coverage < 1.0:
        return 6 if deep_experience else 5
    if preferred_hit == len(preferred):
        return 10 if len(prediction.skills) > len(required) + len(preferred) else 9
    return 8 if deep_experience or preferred_hit else 7


def experience_months_from_text(text: str) -> int:
    """Extract the longest '(N months)' span mentioned in the resume text."""
    months = re.findall(r"\((\d+)\s*months\)", text)
    return max((int(value) for value in months), default=0)


def load_cases(manifest: list[dict[str, Any]]) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for entry in manifest:
        scores = entry["reviewer_scores"]
        if len(scores) != 2:
            raise ValueError(f"REVIEWER_PANEL_INVALID:{entry['resume_id']}")
        cases.append(
            EvaluationCase(
                resume_id=entry["resume_id"],
                resume_text=entry["resume_text"],
                expected_fields=entry["expected_fields"],
                expected_requirements=entry["expected_requirements"],
                reviewer_scores=(scores[0], scores[1]),
            )
        )
    return cases
