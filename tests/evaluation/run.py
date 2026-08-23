"""Run the extraction and matching evaluation harness.

Usage:

    python -m tests.evaluation.run [--threshold 7]

The harness runs a deterministic offline proxy pipeline over an annotated
synthetic manifest and reports field-level precision/recall/F1, score
distance from two-reviewer consensus, shortlist false-positive/negative
rates, and processing latency. It never contacts a provider and contains no
real PII.

Dataset limitations: six synthetic resumes exercise the rubric bands and
missing-field rules but do not measure real-world parser variance, OCR
quality, or non-English text; reviewer consensus is encoded by annotation,
not independent human review. Swap `OfflinePipeline` for the production
`StructuredLLMClient` to benchmark the live path against the same metrics.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tests.evaluation.metrics import (
    LatencyReport,
    PrfReport,
    ShortlistReport,
    scalar_prf,
    score_distances,
    set_prf,
)
from tests.evaluation.pipeline import (
    experience_months_from_text,
    extract_fields,
    load_cases,
    score_against_requirements,
)

MANIFEST_PATH = Path(__file__).parent / "manifest.json"
DEFAULT_THRESHOLD = 7


def build_report(threshold: int) -> dict[str, object]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = load_cases(manifest)

    name_pairs: list[tuple[object, object]] = []
    email_pairs: list[tuple[object, object]] = []
    predicted_scores: list[int] = []
    consensus_scores: list[int] = []
    skill_reports: list[PrfReport] = []
    company_reports: list[PrfReport] = []
    latency = LatencyReport()

    for case in cases:
        started = time.perf_counter()
        prediction = extract_fields(case.resume_text)
        months = experience_months_from_text(case.resume_text)
        score = score_against_requirements(prediction, case.expected_requirements, months)
        elapsed = time.perf_counter() - started

        latency.add(elapsed)
        name_pairs.append((prediction.name, case.expected_fields["candidate.name"]))
        email_pairs.append((prediction.email, case.expected_fields["candidate.contact.email"]))
        expected_skills = {str(item).casefold() for item in case.expected_fields["skills"]}
        expected_companies = {
            str(item).casefold() for item in case.expected_fields["experience.companies"]
        }
        skill_reports.append(
            set_prf({s.casefold() for s in prediction.skills}, expected_skills, "skills")
        )
        company_reports.append(
            set_prf({c.casefold() for c in prediction.companies}, expected_companies, "companies")
        )
        predicted_scores.append(score)
        consensus_scores.append(round(sum(case.reviewer_scores) / 2))

    def merged_prf(reports: list[PrfReport], group: str) -> dict[str, object]:
        tp = sum(r.true_positives for r in reports)
        fp = sum(r.false_positives for r in reports)
        fn = sum(r.false_negatives for r in reports)
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall > 0
            else None
        )
        return {
            "group": group,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": None if f1 is None else round(f1, 4),
        }

    shortlist = ShortlistReport(
        threshold=threshold,
        predicted_shortlist=sum(1 for score in predicted_scores if score >= threshold),
        false_positives=sum(
            1
            for score, consensus in zip(predicted_scores, consensus_scores, strict=True)
            if score >= threshold and consensus < threshold
        ),
        consensus_shortlist=sum(1 for consensus in consensus_scores if consensus >= threshold),
        false_negatives=sum(
            1
            for score, consensus in zip(predicted_scores, consensus_scores, strict=True)
            if consensus >= threshold and score < threshold
        ),
    )

    within_one = sum(
        1
        for score, consensus in zip(predicted_scores, consensus_scores, strict=True)
        if abs(score - consensus) <= 1
    )
    agreement_rate = within_one / len(predicted_scores) if predicted_scores else 0.0

    return {
        "dataset_size": len(cases),
        "extraction": {
            "name": scalar_prf(name_pairs, "name").as_dict(),
            "email": scalar_prf(email_pairs, "email").as_dict(),
            "skills": merged_prf(skill_reports, "skills"),
            "experience.companies": merged_prf(company_reports, "experience.companies"),
        },
        "score_agreement": {
            **score_distances(predicted_scores, consensus_scores),
            "within_one_point_rate": round(agreement_rate, 4),
        },
        "shortlist": shortlist.as_dict(),
        "latency": latency.summary(),
        "predicted_vs_consensus": [
            {"resume_id": case.resume_id, "predicted": score, "consensus": consensus}
            for case, score, consensus in zip(
                cases, predicted_scores, consensus_scores, strict=True
            )
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()
    report = build_report(args.threshold)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
