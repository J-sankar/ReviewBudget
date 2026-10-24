"""Bug labels from repository history: reverts (high confidence) and SZZ (medium).

Labels are evidence, not ground truth: in the phase 0 hand check roughly half to
two thirds of SZZ labels looked plausible.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from reviewbudget.git_changes import HistoryCommit, head_sha, load_history
from reviewbudget.h0 import file_kind

LABELS_VERSION = 1
REVERT_RE = re.compile(r"This reverts commit ([0-9a-f]{7,40})", re.IGNORECASE)
FIX_RE = re.compile(
    r"\b(fix|fixes|fixed|fixing|bug|bugs|bugfix|regression|crash|crashes)\b",
    re.IGNORECASE,
)
NON_BUG_FIX_RE = re.compile(
    r"\b(typos?|docs?|documentation|docstrings?|lint|linting|flake8|mypy|typing|type hints?|"
    r"changelog|readme|ci|style|formatting|pep8|spelling|grammar|links?)\b",
    re.IGNORECASE,
)
MAX_FIX_FILES = 10
MAX_SUSPECT_AGE_DAYS = 730
DAY = 86400
STAT_KEYS = (
    "fix_commits",
    "skipped_too_many_files",
    "skipped_no_code",
    "dropped_too_old",
    "dropped_unknown",
)


@dataclass
class Label:
    sha: str
    confidence: str  # "high" (revert) or "medium" (SZZ)
    source: str
    evidence: list[str]  # reverting or fixing commits
    found_at: int  # timestamp of the earliest evidence; later phases must not use it before then
    note: str


@dataclass
class LabelSet:
    head: str
    code_commits: int
    labels: dict[str, Label]
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def positive_rate(self) -> float:
        return len(self.labels) / self.code_commits if self.code_commits else 0.0


def is_bug_fix(commit: HistoryCommit) -> bool:
    # Subject only: squash-merge bodies list sub-commits ("* Fix lint"), which made
    # feature PRs look like bug fixes in the phase 0 hand check.
    if REVERT_RE.search(commit.body) or commit.subject.lower().startswith("revert"):
        return False
    return bool(FIX_RE.search(commit.subject)) and not NON_BUG_FIX_RE.search(
        commit.subject
    )


def touches_code(commit: HistoryCommit) -> bool:
    return any(file_kind(path) == "code" for path in commit.files)


def find_reverts(
    commits: list[HistoryCommit], by_sha: dict[str, HistoryCommit]
) -> dict[str, list[str]]:
    """Reverted sha -> reverting shas."""
    reverted: dict[str, list[str]] = {}
    for commit in commits:
        for short in REVERT_RE.findall(commit.body):
            matches = [sha for sha in by_sha if sha.startswith(short.lower())]
            if len(matches) == 1 and commit.sha not in reverted.get(matches[0], []):
                reverted.setdefault(matches[0], []).append(commit.sha)
    return reverted


def run_szz(
    repo: Path,
    commits: list[HistoryCommit],
    by_sha: dict[str, HistoryCommit],
    stats: dict[str, int],
) -> dict[str, list[str]]:
    """Suspected bug-introducing sha -> fixing shas. Updates `stats` with filter counts."""
    from pydriller import Git

    gr = Git(str(repo))
    ignore = repo / ".git-blame-ignore-revs"
    ignore_path = str(ignore) if ignore.is_file() else None
    suspects: dict[str, list[str]] = {}
    try:
        for fix in commits:
            if not is_bug_fix(fix):
                continue
            stats["fix_commits"] += 1
            if len(fix.files) > MAX_FIX_FILES:
                stats["skipped_too_many_files"] += 1
                continue
            if not touches_code(fix):
                stats["skipped_no_code"] += 1
                continue
            commit = gr.get_commit(fix.sha)
            for mod in commit.modified_files:
                if not mod.old_path or file_kind(mod.old_path) != "code":
                    continue
                for shas in gr.get_commits_last_modified_lines(
                    commit, mod, ignore_path
                ).values():
                    for sha in shas:
                        suspect = by_sha.get(sha)
                        if suspect is None:
                            stats["dropped_unknown"] += 1
                        elif (
                            fix.timestamp - suspect.timestamp
                            > MAX_SUSPECT_AGE_DAYS * DAY
                        ):
                            stats["dropped_too_old"] += 1
                        elif fix.sha not in suspects.setdefault(sha, []):
                            suspects[sha].append(fix.sha)
    finally:
        gr.clear()
    return suspects


def _first(shas: list[str], by_sha: dict[str, HistoryCommit]) -> HistoryCommit:
    return min((by_sha[s] for s in shas), key=lambda c: (c.timestamp, c.sha))


def combine(
    reverts: dict[str, list[str]],
    szz: dict[str, list[str]],
    by_sha: dict[str, HistoryCommit],
) -> dict[str, Label]:
    """Merge both sources; revert evidence wins the confidence when a commit has both."""
    labels: dict[str, Label] = {}
    for sha, fixes in szz.items():
        first = _first(fixes, by_sha)
        note = f'fixed by {first.sha[:8]} "{first.subject}"'
        labels[sha] = Label(sha, "medium", "szz", sorted(fixes), first.timestamp, note)
    for sha, reverters in reverts.items():
        first = _first(reverters, by_sha)
        found_at = (
            min(first.timestamp, labels[sha].found_at)
            if sha in labels
            else first.timestamp
        )
        note = f'reverted by {first.sha[:8]} "{first.subject}"'
        labels[sha] = Label(sha, "high", "revert", sorted(reverters), found_at, note)
    return dict(sorted(labels.items()))


def compute_labels(repo: Path, head: str) -> LabelSet:
    commits = load_history(repo, head)
    by_sha = {c.sha: c for c in commits}
    stats = dict.fromkeys(STAT_KEYS, 0)
    reverts = find_reverts(commits, by_sha)
    szz = run_szz(repo, commits, by_sha, stats)
    code_commits = sum(1 for c in commits if touches_code(c))
    return LabelSet(head, code_commits, combine(reverts, szz, by_sha), stats)


def default_cache_dir() -> Path:
    return (
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        / "reviewbudget"
    )


def cache_path(repo: Path, head: str, cache_dir: Path) -> Path:
    key = hashlib.sha256(str(repo.resolve()).encode()).hexdigest()[:12]
    return cache_dir / f"labels-v{LABELS_VERSION}-{key}-{head[:12]}.json"


def _from_json(data: dict) -> LabelSet:
    labels = {sha: Label(**label) for sha, label in data["labels"].items()}
    return LabelSet(data["head"], data["code_commits"], labels, data["stats"])


def load_labels(
    repo: Path, cache_dir: Path | None = None, use_cache: bool = True
) -> tuple[LabelSet, bool]:
    """Labels for the repository's current HEAD and whether they came from the cache."""
    head = head_sha(repo)
    path = cache_path(repo, head, cache_dir or default_cache_dir())
    if use_cache and path.is_file():
        try:
            return _from_json(json.loads(path.read_text())), True
        except (ValueError, KeyError, TypeError):
            pass  # unreadable cache: recompute and overwrite it
    label_set = compute_labels(repo, head)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(label_set), indent=1))
    return label_set, False
