import json
from typing import cast

from tests.evaluation.metrics import (
    LatencyReport,
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
from tests.evaluation.run import MANIFEST_PATH, build_report

RESUME = """Sample Candidate One
Email: one@example.com
Phone: 555-0100
Skills: Python, REST APIs, SQL
Experience:
- Backend Engineer at Sample Logistics GmbH, 2021-03 to present (48 months).
Built Python REST services.
"""


def test_set_prf_counts_overlap() -> None:
    report = set_prf({"python", "sql"}, {"python", "kafka"}, "skills")
    assert (report.true_positives, report.false_positives, report.false_negatives) == (1, 1, 1)
    assert report.f1 is not None and abs(report.f1 - 0.5) < 1e-9


def test_scalar_prf_excludes_none_predictions() -> None:
    # (None, None) pairs are excluded entirely when ignore_none is set;
    # predicting an email where none is annotated counts as a false positive.
    report = scalar_prf([("a@x.com", "a@x.com"), (None, None), ("b@x.com", None)], "email")
    assert report.true_positives == 1
    assert report.false_positives == 1
    assert report.false_negatives == 0


def test_score_distances() -> None:
    assert score_distances([8, 5], [8, 6]) == {"mean_distance": 0.5, "max_distance": 1}
    assert score_distances([], []) == {"mean_distance": 0.0, "max_distance": 0}


def test_shortlist_rates_use_matching_denominators() -> None:
    report = ShortlistReport(
        threshold=7,
        predicted_shortlist=4,
        false_positives=1,
        consensus_shortlist=2,
        false_negatives=1,
    )
    assert report.false_positive_rate == 0.25
    assert report.false_negative_rate == 0.5


def test_latency_summary_percentile() -> None:
    latency = LatencyReport()
    assert latency.summary() == {"count": 0, "mean_seconds": 0.0, "p95_seconds": 0.0}
    for value in [1.0, 2.0, 3.0]:
        latency.add(value)
    summary = latency.summary()
    assert summary["count"] == 3
    assert summary["mean_seconds"] == 2.0
    assert summary["p95_seconds"] == 3.0


def test_extract_fields_parses_annotated_text() -> None:
    prediction = extract_fields(RESUME)
    assert prediction.name == "Sample Candidate One"
    assert prediction.email == "one@example.com"
    assert prediction.skills == ["Python", "REST APIs", "SQL"]
    assert prediction.companies == ["Sample Logistics GmbH"]


def test_extract_fields_handles_null_contact() -> None:
    text = (
        "Sample Candidate Four\nEmail: null\nSkills: Python\nExperience:\n"
        "- Dev at Acme Ltd, 2020-01 to present (68 months). Work.\n"
    )
    prediction = extract_fields(text)
    assert prediction.email is None
    assert experience_months_from_text(text) == 68


def test_rubric_band_mapping_matches_prd() -> None:
    requirements = {"required": ["python", "rest apis"], "preferred": ["sql"]}
    none_required = extract_fields("X\nSkills: Java\n")
    partial = extract_fields("X\nSkills: Python\n")
    full = extract_fields("X\nSkills: Python, REST APIs\n")
    full_plus_preferred = extract_fields("X\nSkills: Python, REST APIs, SQL, Kubernetes\n")

    assert score_against_requirements(none_required, requirements, 10) == 1
    assert score_against_requirements(partial, requirements, 10) == 5
    assert score_against_requirements(full, requirements, 10) == 7
    assert score_against_requirements(full, requirements, 60) == 8
    assert score_against_requirements(full_plus_preferred, requirements, 60) == 10


def test_manifest_loads_and_validates_reviewer_panel() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cases = load_cases(manifest)
    assert len(cases) >= 5
    for case in cases:
        assert len(case.reviewer_scores) == 2


def test_build_report_meets_prd_targets_on_synthetic_set() -> None:
    report = build_report(threshold=7)
    extraction = cast(dict[str, dict[str, object]], report["extraction"])
    for group in ["name", "email", "skills", "experience.companies"]:
        f1_val = cast(float | int | None, extraction[group]["f1"])
        assert f1_val is not None and float(f1_val) >= 0.9, group
    agreement = cast(dict[str, float], report["score_agreement"])
    assert agreement["within_one_point_rate"] >= 0.8
    shortlist = cast(dict[str, float | int | None], report["shortlist"])
    fp_val = shortlist["false_positive_rate"]
    fn_val = shortlist["false_negative_rate"]
    assert fp_val is not None and float(fp_val) <= 0.15
    assert fn_val is not None and float(fn_val) <= 0.15
