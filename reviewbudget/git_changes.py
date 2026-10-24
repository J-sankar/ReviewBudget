"""Read the non-merge commits in a revision range from a local Git repository."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"


class GitError(RuntimeError):
    """A git command failed or the path is not a usable repository."""


@dataclass
class FileChange:
    path: str
    old_path: str | None = None
    binary: bool = False
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)

    @property
    def added(self) -> int:
        return len(self.added_lines)

    @property
    def deleted(self) -> int:
        return len(self.removed_lines)

    @property
    def is_pure_rename(self) -> bool:
        return (
            self.old_path is not None
            and not self.added_lines
            and not self.removed_lines
        )


@dataclass
class CommitChange:
    sha: str
    author: str
    timestamp: int
    subject: str
    files: list[FileChange]

    @property
    def added(self) -> int:
        return sum(f.added for f in self.files)

    @property
    def deleted(self) -> int:
        return sum(f.deleted for f in self.files)


@dataclass
class HistoryCommit:
    sha: str
    timestamp: int
    subject: str
    body: str
    files: list[str]


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotePath=false", *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def parse_diff(diff: str) -> list[FileChange]:
    """Parse `git show --unified=0` output into per-file added and removed lines."""
    files: list[FileChange] = []
    current: FileChange | None = None
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            paths = line[len("diff --git ") :]
            split = paths.rfind(" b/")
            current = FileChange(path=paths[split + 3 :] if split != -1 else paths)
            files.append(current)
            in_header = True
            continue
        if current is None:
            continue
        if in_header:
            if line.startswith("rename from "):
                current.old_path = line[len("rename from ") :]
            elif line.startswith("rename to "):
                current.path = line[len("rename to ") :]
            elif line.startswith("+++ b/"):
                current.path = line[len("+++ b/") :]
            elif line.startswith("Binary files "):
                current.binary = True
            elif line.startswith("@@"):
                in_header = False
            continue
        if line.startswith("+"):
            current.added_lines.append(line[1:])
        elif line.startswith("-"):
            current.removed_lines.append(line[1:])
    return files


def load_commits(repo: Path, revisions: list[str]) -> list[CommitChange]:
    """Return the non-merge commits selected by `revisions`, oldest first."""
    _require_repo(repo)
    log = git(
        repo,
        "log",
        "--no-merges",
        "--reverse",
        f"--format=%H{FIELD_SEP}%ae{FIELD_SEP}%at{FIELD_SEP}%s",
        *revisions,
        "--",
    )
    commits = []
    for line in log.splitlines():
        if not line:
            continue
        sha, author, ts, subject = line.split(FIELD_SEP, 3)
        diff = git(
            repo,
            "show",
            "--format=",
            "-M",
            "--unified=0",
            "--no-color",
            "--no-ext-diff",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            sha,
        )
        commits.append(CommitChange(sha, author, int(ts), subject, parse_diff(diff)))
    return commits


def _require_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise GitError(f"not a directory: {repo}")
    try:
        git(repo, "rev-parse", "--git-dir")
    except GitError:
        raise GitError(f"not a git repository: {repo}") from None


def head_sha(repo: Path) -> str:
    _require_repo(repo)
    try:
        return git(repo, "rev-parse", "--verify", "HEAD").strip()
    except GitError:
        raise GitError(f"repository has no commits: {repo}") from None


def load_history(repo: Path, rev: str = "HEAD") -> list[HistoryCommit]:
    """Every non-merge commit reachable from `rev`, oldest first, with the paths it touched."""
    _require_repo(repo)
    fmt = f"{RECORD_SEP}%H{FIELD_SEP}%at{FIELD_SEP}%s{FIELD_SEP}%b{FIELD_SEP}"
    log = git(
        repo,
        "log",
        "--no-merges",
        "--reverse",
        f"--format={fmt}",
        "--name-only",
        rev,
        "--",
    )
    commits = []
    for record in log.split(RECORD_SEP):
        if not record.strip():
            continue
        sha, ts, subject, body, rest = record.split(FIELD_SEP, 4)
        files = [line for line in rest.splitlines() if line.strip()]
        commits.append(HistoryCommit(sha, int(ts), subject, body, files))
    return commits
