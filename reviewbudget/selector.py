"""Pick a ranking strategy from the quality of a repository's bug evidence.

Uses the phase 0 rules. Repository size is deliberately not an input: repositories
with similar commit counts can have very different amounts of usable evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from reviewbudget.dataset import Dataset, Row, count_buggy
from reviewbudget.evaluate import EFFORT_SHARE, by_h0, by_h1, recall_at_effort
from reviewbudget.history import AUTHOR_HISTORY_MIN_COMMITS, FILE_HISTORY_MIN_CHANGES

MODEL_MIN_TRAIN_LABELS = 50
MODEL_MIN_TEST_LABELS = 20
MODEL_MIN_RATE = 0.03
MODEL_MAX_RATE = 0.30
H1_MIN_TEST_LABELS = 10
H1_MIN_COVERAGE = 0.6


@dataclass
class Evidence:
    train_labels: int
    test_labels: int
    positive_rate: float  # share of code commits with a bug label
    file_coverage: float  # share of newer commits whose files have history
    author_coverage: float  # share of newer commits whose author has history


@dataclass
class Choice:
    strategy: str  # "H0" or "H1"
    model_eligible: bool
    reasons: list[str]


def _share(rows: list[Row], condition) -> float:
    return sum(1 for r in rows if condition(r)) / len(rows) if rows else 0.0


def gather_evidence(dataset: Dataset) -> Evidence:
    test = dataset.test
    return Evidence(
        train_labels=count_buggy(dataset.train),
        test_labels=count_buggy(test),
        positive_rate=_share(dataset.rows, lambda r: bool(r.label_source)),
        file_coverage=_share(
            test, lambda r: r.file_changes_before >= FILE_HISTORY_MIN_CHANGES
        ),
        author_coverage=_share(
            test, lambda r: r.author_commits_before >= AUTHOR_HISTORY_MIN_COMMITS
        ),
    )


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def choose(
    evidence: Evidence, h0_recall: float | None, h1_recall: float | None
) -> Choice:
    """Apply the phase 0 rules, then keep H1 only if it beat H0 on the newer commits."""
    e = evidence
    reasons = [
        (
            f"bug labels: {e.train_labels} older, {e.test_labels} newer; "
            f"{e.positive_rate:.0%} of code commits labelled"
        ),
        (
            f"history coverage of newer commits: files {e.file_coverage:.2f}, "
            f"authors {e.author_coverage:.2f}"
        ),
    ]
    model_eligible = (
        e.train_labels >= MODEL_MIN_TRAIN_LABELS
        and e.test_labels >= MODEL_MIN_TEST_LABELS
        and MODEL_MIN_RATE <= e.positive_rate <= MODEL_MAX_RATE
    )
    if model_eligible:
        reasons.append(
            f"learning model eligible (at least {MODEL_MIN_TRAIN_LABELS} older and "
            f"{MODEL_MIN_TEST_LABELS} newer labels, {MODEL_MIN_RATE:.0%}-"
            f"{MODEL_MAX_RATE:.0%} labelled); it is not built yet, so H1 is considered"
        )
    missing = []
    if e.test_labels < H1_MIN_TEST_LABELS:
        missing.append(
            f"only {e.test_labels} newer labels to check history signals against "
            f"(need {H1_MIN_TEST_LABELS})"
        )
    for name, value in (("file", e.file_coverage), ("author", e.author_coverage)):
        if value < H1_MIN_COVERAGE:
            missing.append(
                f"{name} history coverage {value:.2f} (need {H1_MIN_COVERAGE})"
            )
    if missing and not model_eligible:
        reasons.append("H0: " + "; ".join(missing))
        return Choice("H0", model_eligible, reasons)

    measure = f"bugs found in {EFFORT_SHARE:.0%} effort"
    if h0_recall is None or h1_recall is None or h1_recall <= h0_recall:
        reasons.append(
            f"H0: H1 did not beat H0 on newer commits ({measure}: H1 "
            f"{_pct(h1_recall)}, H0 {_pct(h0_recall)})"
        )
        return Choice("H0", model_eligible, reasons)
    reasons.append(
        f"H1: enough evidence, and it beat H0 on newer commits ({measure}: H1 "
        f"{_pct(h1_recall)}, H0 {_pct(h0_recall)})"
    )
    return Choice("H1", model_eligible, reasons)


def select(dataset: Dataset) -> Choice:
    test = dataset.test
    return choose(
        gather_evidence(dataset),
        recall_at_effort(by_h0(test)),
        recall_at_effort(by_h1(test)),
    )
