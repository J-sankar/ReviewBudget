"""Helpers for building small git repositories with a known history in tests."""

import os
import subprocess
from pathlib import Path

BASE_TS = 1_700_000_000


def git(repo: Path, *args: str, day: int = 0) -> str:
    date = f"{BASE_TS + day * 86400} +0000"
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def init(repo: Path) -> Path:
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    return repo


def commit(
    repo: Path,
    subject: str,
    day: int,
    files: dict[str, str] | None = None,
    body: str = "",
) -> str:
    for name, content in (files or {}).items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    git(repo, "add", "-A")
    message = ["-m", subject] + (["-m", body] if body else [])
    git(repo, "commit", "-q", *message, day=day)
    return git(repo, "rev-parse", "HEAD")


def timestamp(day: int) -> int:
    return BASE_TS + day * 86400
