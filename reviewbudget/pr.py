"""Analyze a GitHub pull request from an already checked-out local repository."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from reviewbudget.git_changes import (
    CommitChange,
    GitError,
    git,
    load_commits,
    parse_diff,
)

_GITHUB_PR = re.compile(r"^/([^/]+)/([^/]+)/pull/(\d+)/?$")


@dataclass(frozen=True)
class PullRequest:
    owner: str
    repository: str
    number: int
    url: str


@dataclass(frozen=True)
class LocalPR:
    pull_request: PullRequest
    repo: Path
    base_ref: str
    base_sha: str
    branch: str
    remote: str
    commits: list[CommitChange]
    working_tree: CommitChange
    # Kept for callers that previously consumed the aggregate local change.
    change: CommitChange


def parse_pull_request_url(url: str) -> PullRequest:
    """Parse a GitHub pull-request URL without contacting GitHub."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        raise ValueError(
            "PR URL must be an https://github.com/<owner>/<repo>/pull/<number> URL"
        )
    match = _GITHUB_PR.fullmatch(parsed.path)
    if not match:
        raise ValueError("PR URL must end with /pull/<number>")
    owner, repository, number = match.groups()
    return PullRequest(owner, repository.removesuffix(".git"), int(number), url.strip())


def load_local_pr(repo: Path, url: str, base_ref: str = "main") -> LocalPR:
    """Load committed PR changes and pending tracked edits from a local checkout."""
    pull_request = parse_pull_request_url(url)
    remote = _matching_remote(repo, pull_request)
    base_sha = git(repo, "rev-parse", "--verify", base_ref).strip()
    branch = git(repo, "branch", "--show-current").strip() or "detached HEAD"
    commits = load_commits(repo, [f"{base_ref}..HEAD"])
    diff = git(
        repo,
        "diff",
        "--no-ext-diff",
        "--unified=0",
        "--no-color",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "HEAD",
        "--",
    )
    files = parse_diff(diff)
    change = CommitChange(
        sha="WORKTREE",
        author=git(repo, "config", "user.email").strip() or "local reviewer",
        timestamp=0,
        subject=f"working tree changes for PR #{pull_request.number}",
        files=files,
    )
    return LocalPR(
        pull_request,
        repo,
        base_ref,
        base_sha,
        branch,
        remote,
        commits,
        change,
        change,
    )


def _matching_remote(repo: Path, pull_request: PullRequest) -> str:
    remotes = git(repo, "remote").splitlines()
    expected = f"github.com/{pull_request.owner}/{pull_request.repository}".lower()
    for name in remotes:
        for remote_url in git(repo, "remote", "get-url", name).splitlines():
            normalized = (
                remote_url.strip().removesuffix("/").removesuffix(".git").lower()
            )
            if normalized.endswith(expected):
                return remote_url.strip()
    raise GitError(
        f"local repository remotes do not match {pull_request.owner}/{pull_request.repository}"
    )


def has_tracked_changes(change: CommitChange) -> bool:
    """Return whether the local diff contains anything ReviewBudget can score."""
    return bool(change.files)
