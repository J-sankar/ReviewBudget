"""S: smallest changes first.

Ranks commits that change program code by the lines a reviewer must read, fewest
first, so a fixed review budget covers as many commits as possible. Commits without
program code go last. H0's risk reasons are shown for context but do not affect order.
"""

from __future__ import annotations

from dataclasses import dataclass

from reviewbudget import h0
from reviewbudget.git_changes import CommitChange
from reviewbudget.h0 import Reason, code_lines, file_kind


@dataclass
class SizeScore:
    commit: CommitChange
    lines: int
    has_code: bool
    reasons: list[Reason]

    @property
    def score(self) -> float:
        """Lines of program code to review (shown in the score column)."""
        return float(self.lines)


def score_commit(commit: CommitChange) -> SizeScore:
    lines = code_lines(commit)
    has_code = any(file_kind(f.path) == "code" for f in commit.files)
    first = (
        Reason(0.0, f"{lines} lines of code to review")
        if has_code
        else Reason(0.0, "no program code changed")
    )
    context = [r for r in h0.score_commit(commit).reasons if r.key != "size"]
    return SizeScore(commit, lines, has_code, [first, *context])


def rank(scored: list[SizeScore]) -> list[SizeScore]:
    """Fewest code lines first (every code commit costs at least one line); ties go to the newer commit."""
    return sorted(
        scored,
        key=lambda s: (
            not s.has_code,
            max(1, s.lines),
            -s.commit.timestamp,
            s.commit.sha,
        ),
    )
