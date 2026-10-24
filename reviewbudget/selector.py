"""Pick a ranking strategy from the quality of a repository's bug evidence.

Uses the phase 0 rules to decide which strategies the evidence can support, then picks
the one that found the most bugs within the effort budget on older commits. The newer
commits are only reported, as an honest check of that choice. When the learned model
L is eligible, the older commits are split again by time: L learns from the first part
and every strategy is compared on the rest, so L is never judged on rows it learned
from. Repository size is deliberately not an input: repositories with similar commit
counts can have very different amounts of usable evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from reviewbudget import model
from reviewbudget.dataset import Dataset, Row, count_buggy
from reviewbudget.evaluate import (
    EFFORT_SHARE,
    by_h0,
    by_h1,
    recall_at_effort,
    smallest_first,
)
from reviewbudget.history import AUTHOR_HISTORY_MIN_COMMITS, FILE_HISTORY_MIN_CHANGES

MODEL_MIN_TRAIN_LABELS = 50
MODEL_MIN_TEST_LABELS = 20
MODEL_MIN_RATE = 0.03
MODEL_MAX_RATE = 0.30
H1_MIN_TEST_LABELS = 10
H1_MIN_COVERAGE = 0.6
INNER_TRAIN_SHARE = 0.7
RULE_BASED = {"H0": by_h0, "S": smallest_first, "H1": by_h1}
ORDER = ["H0", "S", "H1", "L"]  # simplest first: on a tie the simpler strategy wins
OLDER = "the older commits"
OLDER_SLICE = "the newest 30% of the older commits, after L learned from the rest"


@dataclass
class Evidence:
    train_labels: int
    test_labels: int
    positive_rate: float  # share of code commits with a bug label
    file_coverage: float  # share of newer commits whose files have history
    author_coverage: float  # share of newer commits whose author has history

    @property
    def model_eligible(self) -> bool:
        return (
            self.train_labels >= MODEL_MIN_TRAIN_LABELS
            and self.test_labels >= MODEL_MIN_TEST_LABELS
            and MODEL_MIN_RATE <= self.positive_rate <= MODEL_MAX_RATE
        )


@dataclass
class Choice:
    strategy: str  # "H0", "S", "H1" or "L"
    model_eligible: bool
    reasons: list[str]


Recalls = dict[str, float | None]


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


def _summary(names: list[str], recalls: Recalls) -> str:
    return ", ".join(f"{name} {_pct(recalls.get(name))}" for name in names)


def choose(
    evidence: Evidence, older: Recalls, newer: Recalls, basis: str = OLDER
) -> Choice:
    """Apply the phase 0 rules, then pick the best strategy on the older commits.

    `older` and `newer` map strategy names to bugs found within the effort budget;
    only `older` (measured on `basis`) decides. L only competes when model-eligible.
    """
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
    if e.model_eligible:
        reasons.append(
            f"learning model eligible (at least {MODEL_MIN_TRAIN_LABELS} older and "
            f"{MODEL_MIN_TEST_LABELS} newer labels, {MODEL_MIN_RATE:.0%}-"
            f"{MODEL_MAX_RATE:.0%} labelled), so L competes"
        )
    missing = []
    if e.test_labels < H1_MIN_TEST_LABELS:
        missing.append(
            f"only {e.test_labels} newer labels to check other strategies against "
            f"(need {H1_MIN_TEST_LABELS})"
        )
    for name, value in (("file", e.file_coverage), ("author", e.author_coverage)):
        if value < H1_MIN_COVERAGE:
            missing.append(
                f"{name} history coverage {value:.2f} (need {H1_MIN_COVERAGE})"
            )
    if missing and not e.model_eligible:
        reasons.append("H0: " + "; ".join(missing))
        return Choice("H0", e.model_eligible, reasons)

    names = [n for n in ORDER if n in older and (n != "L" or e.model_eligible)]
    scored = {n: older[n] for n in names if older[n] is not None}
    if not scored:
        reasons.append(f"H0: no usable bug labels in {basis} to compare on")
        return Choice("H0", e.model_eligible, reasons)
    best = max(scored, key=lambda n: (scored[n], -ORDER.index(n)))
    measure = f"bugs found in {EFFORT_SHARE:.0%} effort"
    reasons.append(
        f"{best}: best on {basis} ({measure}: {_summary(names, older)}); "
        f"check on the newer commits: {_summary(names, newer)}"
    )
    return Choice(best, e.model_eligible, reasons)


def inner_split(rows: list[Row]) -> tuple[list[Row], list[Row]]:
    """Split older rows by time; the first part hides bugs found after the cut."""
    n = int(len(rows) * INNER_TRAIN_SHARE)
    if n >= len(rows):
        return rows, []
    cut = rows[n].timestamp

    def known(r: Row) -> int:
        return int(
            bool(r.buggy)
            and r.evidence_found_at is not None
            and r.evidence_found_at < cut
        )

    return [replace(r, buggy=known(r)) for r in rows[:n]], rows[n:]


def _recalls(rows: list[Row], learned: model.Model | None = None) -> Recalls:
    recalls = {n: recall_at_effort(order(rows)) for n, order in RULE_BASED.items()}
    if learned is not None:
        recalls["L"] = recall_at_effort(model.order(learned, rows))
    return recalls


def select(dataset: Dataset) -> Choice:
    evidence = gather_evidence(dataset)
    if not evidence.model_eligible:
        return choose(evidence, _recalls(dataset.train), _recalls(dataset.test))
    fit, check = inner_split(dataset.train)
    return choose(
        evidence,
        _recalls(check, model.train(fit)),
        _recalls(dataset.test, model.train(dataset.train)),
        OLDER_SLICE,
    )
