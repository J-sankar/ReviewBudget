"""Score rankings of the test window against bug labels.

Headline measure: the share of buggy test commits a reviewer finds when reviewing in
ranked order and stopping at 20% of the window's changed code lines (effort-aware recall).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from reviewbudget.dataset import Dataset, Row, count_buggy

EFFORT_SHARE = 0.2
TOP_K = 10
RANDOM_RUNS = 100
SEED = 0
MIN_TEST_LABELS = 10  # the same bar as the phase 0 rule for evaluating H1


@dataclass
class Result:
    name: str
    recall_at_effort: float
    precision_at_k: float


def effort(row: Row) -> int:
    # Every commit costs at least one line, so pure renames are not free to review.
    return max(1, row.code_lines)


def recall_at_effort(ranked: list[Row], share: float = EFFORT_SHARE) -> float | None:
    """Share of buggy commits found before the next commit would exceed the effort budget."""
    bugs = count_buggy(ranked)
    if not bugs:
        return None
    budget = share * sum(effort(r) for r in ranked)
    spent = found = 0
    for r in ranked:
        spent += effort(r)
        if spent > budget:
            break
        found += r.buggy
    return found / bugs


def precision_at_k(ranked: list[Row], k: int = TOP_K) -> float | None:
    top = ranked[:k]
    return count_buggy(top) / len(top) if top else None


def by_h0(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda r: (-r.h0_score, -r.timestamp, r.sha))


def by_h1(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda r: (-r.h1_score, -r.h1_risk, -r.timestamp, r.sha))


def largest_first(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda r: (-r.code_lines, -r.timestamp, r.sha))


def smallest_first(rows: list[Row]) -> list[Row]:
    return sorted(rows, key=lambda r: (effort(r), -r.timestamp, r.sha))


STRATEGIES = {
    "H0 (change-only heuristic)": by_h0,
    "H1 (history-aware, per line)": by_h1,
    "largest first": largest_first,
    "smallest first": smallest_first,
}


def random_baseline(
    rows: list[Row], runs: int = RANDOM_RUNS, seed: int = SEED
) -> Result:
    rng = random.Random(seed)
    recalls, precisions = [], []
    for _ in range(runs):
        order = rows[:]
        rng.shuffle(order)
        recalls.append(recall_at_effort(order) or 0.0)
        precisions.append(precision_at_k(order) or 0.0)
    return Result(
        f"random order ({runs} runs)", sum(recalls) / runs, sum(precisions) / runs
    )


def evaluate(dataset: Dataset, window: str = "test") -> list[Result] | None:
    """Results for each strategy on one window, or None if it has too few labels."""
    rows = dataset.test if window == "test" else dataset.train
    if count_buggy(rows) < max(1, MIN_TEST_LABELS):
        return None
    results = []
    for name, order in STRATEGIES.items():
        ranked = order(rows)
        results.append(Result(name, recall_at_effort(ranked), precision_at_k(ranked)))
    results.append(random_baseline(rows))
    return results
