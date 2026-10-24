"""H1: history-aware heuristic, ranked by risk per line to review.

Risk is H0's signals without its size points, plus history points: files with
earlier bugs, frequently changed files, and an author new to the files. Commits are
ranked by risk per 100 changed code lines, because the review budget limits lines
read, not commits: a small risky change comes before a large one with the same risk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from reviewbudget import h0
from reviewbudget.git_changes import CommitChange
from reviewbudget.h0 import Reason, code_lines
from reviewbudget.history import AUTHOR_HISTORY_MIN_COMMITS, History

# All hand-set weights live here. They were set once and not tuned on evaluation results.
WEIGHTS = {
    "file_bug": 1.0,
    "file_bug_cap": 3.0,
    "churn_per_log2_change": 0.25,
    "churn_cap": 1.5,
    "author_new_to_files": 1.0,
    "author_inexperienced": 1.0,
}
LINES_PER_UNIT = 100


@dataclass
class H1Score:
    commit: CommitChange
    risk: float
    lines: int
    reasons: list[Reason]

    @property
    def score(self) -> float:
        """Risk points per 100 changed code lines; every commit costs at least one line."""
        return round(self.risk * LINES_PER_UNIT / max(1, self.lines), 2)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def history_reasons(history: History) -> list[Reason]:
    w = WEIGHTS
    reasons = []
    if history.file_bugs:
        points = min(w["file_bug_cap"], w["file_bug"] * history.file_bugs)
        text = f"files had {_plural(history.file_bugs, 'earlier bug-linked commit')}"
        reasons.append(Reason(points, text))
    if history.file_changes:
        points = min(
            w["churn_cap"],
            w["churn_per_log2_change"] * math.log2(1 + history.file_changes),
        )
        text = f"files changed {_plural(history.file_changes, 'time')} before"
        reasons.append(Reason(round(points, 2), text))
    if not history.author_knows_files:
        reasons.append(
            Reason(w["author_new_to_files"], "author's first change to these files")
        )
    if history.author_commits < AUTHOR_HISTORY_MIN_COMMITS:
        text = f"author has {_plural(history.author_commits, 'earlier commit')}"
        reasons.append(Reason(w["author_inexperienced"], text))
    return reasons


def score_commit(
    commit: CommitChange, history: History, h0_scored: h0.ScoredCommit | None = None
) -> H1Score:
    h0_scored = h0_scored or h0.score_commit(commit)
    reasons = [r for r in h0_scored.reasons if r.key != "size"]
    lines = code_lines(commit)
    if lines:  # history only matters for commits that change program code
        reasons += history_reasons(history)
    # Without program code, the effort is reading whatever changed (config, docs).
    effort_lines = lines or commit.added + commit.deleted
    reasons.sort(key=lambda r: -r.points)
    risk = round(sum(r.points for r in reasons), 2)
    return H1Score(commit, risk, effort_lines, reasons)


def rank(scored: list[H1Score]) -> list[H1Score]:
    """Highest risk per line first; ties go to higher risk, then the newer commit."""
    return sorted(
        scored, key=lambda s: (-s.score, -s.risk, -s.commit.timestamp, s.commit.sha)
    )
