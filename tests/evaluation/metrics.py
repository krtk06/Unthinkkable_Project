"""Evaluation metrics for extraction quality and shortlist calibration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PrfReport:
    """Precision/recall/F1 for one comparable field group."""

    group: str
    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float | None:
        denominator = self.true_positives + self.false_positives
        return None if denominator == 0 else self.true_positives / denominator

    @property
    def recall(self) -> float | None:
        denominator = self.true_positives + self.false_negatives
        return None if denominator == 0 else self.true_positives / denominator

    @property
    def f1(self) -> float | None:
        precision = self.precision
        recall = self.recall
        if precision is None or recall is None or precision + recall == 0:
            return None
        return 2 * precision * recall / (precision + recall)

    def as_dict(self) -> dict[str, object]:
        return {
            "group": self.group,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": _rounded(self.precision),
            "recall": _rounded(self.recall),
            "f1": _rounded(self.f1),
        }


def _rounded(value: float | int | None, digits: int = 4) -> float | int | None:
    if value is None:
        return None
    return round(float(value), digits)


def set_prf(predicted: set[str], expected: set[str], group: str) -> PrfReport:
    """Precision/recall/F1 over unordered sets such as skills."""
    return PrfReport(
        group=group,
        true_positives=len(predicted & expected),
        false_positives=len(predicted - expected),
        false_negatives=len(expected - predicted),
    )


def scalar_prf(
    pairs: list[tuple[object, object]], group: str, *, ignore_none: bool = True
) -> PrfReport:
    """Precision/recall/F1 over scalar fields compared pairwise by position.

    Each pair is (predicted, expected). A prediction counts as a true positive
    when it equals the expectation; ``None`` predictions are excluded from
    precision denominators when ``ignore_none`` is set, matching the PRD rule
    that absent contact fields are excluded rather than penalized.
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    for predicted, expected in pairs:
        if predicted == expected:
            if expected is not None or not ignore_none:
                true_positives += 1
            continue
        if predicted is None and ignore_none:
            false_negatives += 1
            continue
        false_positives += 1
        if expected is not None:
            false_negatives += 1
    return PrfReport(
        group=group,
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
    )


@dataclass
class ShortlistReport:
    """False-positive/negative rates for the shortlist at a threshold.

    False-positive rate uses predicted-shortlist size as the denominator;
    false-negative rate uses the reviewer-consensus shortlist size.
    """

    threshold: int
    predicted_shortlist: int
    false_positives: int
    consensus_shortlist: int
    false_negatives: int

    @property
    def false_positive_rate(self) -> float | None:
        if self.predicted_shortlist == 0:
            return None
        return self.false_positives / self.predicted_shortlist

    @property
    def false_negative_rate(self) -> float | None:
        if self.consensus_shortlist == 0:
            return None
        return self.false_negatives / self.consensus_shortlist

    def as_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "predicted_shortlist": self.predicted_shortlist,
            "false_positives": self.false_positives,
            "false_positive_rate": _rounded(self.false_positive_rate),
            "consensus_shortlist": self.consensus_shortlist,
            "false_negatives": self.false_negatives,
            "false_negative_rate": _rounded(self.false_negative_rate),
        }


def score_distances(predicted: list[int], consensus: list[int]) -> dict[str, float]:
    """Mean and max absolute distance between predicted and consensus scores."""
    if len(predicted) != len(consensus):
        raise ValueError("SCORE_LIST_LENGTH_MISMATCH")
    if not predicted:
        return {"mean_distance": 0.0, "max_distance": 0}
    distances = [abs(a - b) for a, b in zip(predicted, consensus, strict=True)]
    return {
        "mean_distance": round(sum(distances) / len(distances), 4),
        "max_distance": max(distances),
    }


@dataclass
class LatencyReport:
    """Processing latency samples in seconds."""

    samples: list[float] = field(default_factory=list)

    def add(self, seconds: float) -> None:
        self.samples.append(seconds)

    def summary(self) -> dict[str, float]:
        if not self.samples:
            return {"count": 0, "mean_seconds": 0.0, "p95_seconds": 0.0}
        ordered = sorted(self.samples)
        index = min(len(ordered) - 1, max(0, round(0.95 * len(ordered)) - 1))
        return {
            "count": len(ordered),
            "mean_seconds": round(sum(ordered) / len(ordered), 4),
            "p95_seconds": round(ordered[index], 4),
        }
