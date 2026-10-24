"""History features for each commit, using only what was known before that commit.

One pass over the commits, oldest first. An earlier bug in a file only counts once
its evidence (the fix or revert) had appeared before the commit, so nothing is taken
from the future.
"""

from __future__ import annotations

from dataclasses import dataclass

from reviewbudget.git_changes import CommitChange
from reviewbudget.h0 import file_kind
from reviewbudget.labels import Label

# Phase 0 coverage rules: a commit has file history if one of its code files was
# changed at least 3 times before, and author history if its author made at least
# 5 earlier commits.
FILE_HISTORY_MIN_CHANGES = 3
AUTHOR_HISTORY_MIN_COMMITS = 5


@dataclass
class History:
    file_changes: int  # most earlier changes to any one of the commit's code files
    file_bugs: (
        int  # earlier bug-labelled commits on these files, evidence already known
    )
    author_commits: int  # the author's earlier commits
    author_knows_files: bool  # the author changed one of these files before

    @property
    def has_file_history(self) -> bool:
        return self.file_changes >= FILE_HISTORY_MIN_CHANGES

    @property
    def has_author_history(self) -> bool:
        return self.author_commits >= AUTHOR_HISTORY_MIN_COMMITS


def compute_history(
    commits: list[CommitChange], labels: dict[str, Label]
) -> dict[str, History]:
    """History features for each commit (given oldest first), keyed by sha."""
    changes: dict[str, int] = {}
    buggy_commits: dict[str, list[str]] = {}  # file -> earlier bug-labelled commits
    authors: dict[str, set[str]] = {}
    author_commits: dict[str, int] = {}
    result = {}
    for c in commits:
        for f in c.files:  # a renamed file keeps its history
            if f.old_path and f.old_path != f.path:
                for by_file in (changes, buggy_commits, authors):
                    if f.old_path in by_file:
                        by_file[f.path] = by_file.pop(f.old_path)

        paths = [f.path for f in c.files if file_kind(f.path) == "code"]
        earlier_bugs = {
            sha
            for p in paths
            for sha in buggy_commits.get(p, [])
            if labels[sha].found_at < c.timestamp
        }
        result[c.sha] = History(
            file_changes=max((changes.get(p, 0) for p in paths), default=0),
            file_bugs=len(earlier_bugs),
            author_commits=author_commits.get(c.author, 0),
            author_knows_files=any(c.author in authors.get(p, ()) for p in paths),
        )

        for f in c.files:
            changes[f.path] = changes.get(f.path, 0) + 1
            authors.setdefault(f.path, set()).add(c.author)
            if c.sha in labels:
                buggy_commits.setdefault(f.path, []).append(c.sha)
        author_commits[c.author] = author_commits.get(c.author, 0) + 1
    return result
