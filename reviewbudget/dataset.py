"""The evaluation dataset: one row per code commit with its scores and bug label.

Rows are split by time: the older TRAIN_SHARE of code commits are for training and
the rest for testing. A training row only counts as buggy if its bug evidence appeared
before the split, so nothing is learned from bugs that were discovered later.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reviewbudget import h1
from reviewbudget.git_changes import CommitChange, load_commits
from reviewbudget.h0 import ScoredCommit, code_lines, file_kind, score_commit
from reviewbudget.history import compute_history
from reviewbudget.labels import Label, LabelSet, load_labels

TRAIN_SHARE = 0.7
CSV_COLUMNS = [
    "sha",
    "date",
    "window",
    "subject",
    "code_lines",
    "h0_score",
    "h0_reasons",
    "buggy",
    "hidden_from_training",
    "label_source",
    "label_confidence",
    "evidence_date",
    "evidence",
    "h1_risk",
    "h1_score",
    "h1_reasons",
    "file_changes_before",
    "file_bugs_before",
    "author_commits_before",
]


@dataclass
class Row:
    sha: str
    timestamp: int
    subject: str
    code_lines: int
    h0_score: float
    window: str = "test"
    buggy: int = 0  # 1 if labelled buggy and the label is usable in this window
    h0_reasons: str = ""
    label_source: str = ""
    label_confidence: str = ""
    evidence_found_at: int | None = None
    evidence: str = ""
    hidden_from_training: int = (
        0  # 1 if a training row's bug was only found after the split
    )
    h1_risk: float = 0.0
    h1_score: float = 0.0  # H1 risk per 100 changed code lines
    h1_reasons: str = ""
    file_changes_before: int = 0
    file_bugs_before: int = 0
    author_commits_before: int = 0


@dataclass
class Dataset:
    head: str
    split_time: int | None
    rows: list[Row]

    @property
    def train(self) -> list[Row]:
        return [r for r in self.rows if r.window == "train"]

    @property
    def test(self) -> list[Row]:
        return [r for r in self.rows if r.window == "test"]


def count_buggy(rows: list[Row]) -> int:
    return sum(r.buggy for r in rows)


def iso_date(timestamp: int | None) -> str:
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d")


def is_code_commit(commit: CommitChange) -> bool:
    return any(file_kind(f.path) == "code" for f in commit.files)


def make_rows(
    scored: list[ScoredCommit],
    labels: dict[str, Label],
    train_share: float = TRAIN_SHARE,
) -> tuple[list[Row], int | None]:
    """Rows for the code commits (oldest first) and the timestamp where the test window starts."""
    code = [s for s in scored if is_code_commit(s.commit)]
    n_train = int(len(code) * train_share)
    split_time = code[n_train].commit.timestamp if n_train < len(code) else None
    history = compute_history([s.commit for s in scored], labels)
    rows = []
    for i, s in enumerate(code):
        c = s.commit
        label = labels.get(c.sha)
        past = history[c.sha]
        h1_scored = h1.score_commit(c, past, s)
        window = "train" if i < n_train else "test"
        hidden = (
            window == "train"
            and label is not None
            and split_time is not None
            and label.found_at >= split_time
        )
        rows.append(
            Row(
                sha=c.sha,
                timestamp=c.timestamp,
                subject=c.subject,
                code_lines=code_lines(c),
                h0_score=s.score,
                window=window,
                buggy=int(label is not None and not hidden),
                h0_reasons="; ".join(r.text for r in s.reasons[:3]),
                label_source=label.source if label else "",
                label_confidence=label.confidence if label else "",
                evidence_found_at=label.found_at if label else None,
                evidence=" ".join(label.evidence) if label else "",
                hidden_from_training=int(hidden),
                h1_risk=h1_scored.risk,
                h1_score=h1_scored.score,
                h1_reasons="; ".join(r.text for r in h1_scored.reasons[:3]),
                file_changes_before=past.file_changes,
                file_bugs_before=past.file_bugs,
                author_commits_before=past.author_commits,
            )
        )
    return rows, split_time


def build_dataset(
    repo: Path, cache_dir: Path | None = None, use_cache: bool = True
) -> Dataset:
    label_set, _ = load_labels(repo, cache_dir, use_cache)
    return dataset_from_commits(load_commits(repo, [label_set.head]), label_set)


def dataset_from_commits(commits: list[CommitChange], label_set: LabelSet) -> Dataset:
    """Dataset from commits given oldest first, with labels computed at label_set.head."""
    rows, split_time = make_rows([score_commit(c) for c in commits], label_set.labels)
    return Dataset(label_set.head, split_time, rows)


def write_csv(dataset: Dataset, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for r in dataset.rows:
            writer.writerow(
                [
                    r.sha,
                    iso_date(r.timestamp),
                    r.window,
                    r.subject,
                    r.code_lines,
                    r.h0_score,
                    r.h0_reasons,
                    r.buggy,
                    r.hidden_from_training,
                    r.label_source,
                    r.label_confidence,
                    iso_date(r.evidence_found_at),
                    r.evidence,
                    r.h1_risk,
                    r.h1_score,
                    r.h1_reasons,
                    r.file_changes_before,
                    r.file_bugs_before,
                    r.author_commits_before,
                ]
            )
