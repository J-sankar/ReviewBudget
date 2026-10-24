"""Phase 0 feasibility spike: how much usable bug evidence does a repo's history hold?

Throwaway research script, not product code. For one repository it reports:
  - history profile (commits, span, authors, file/author history coverage)
  - revert labels (high confidence)
  - SZZ labels via PyDriller (medium confidence), with noise filters
  - label counts in the older 70% / newer 30% of the analysis window
  - runtime per stage

Usage:
  python spikes/phase0_feasibility.py REPO_PATH [--years 3] [--out results.json] [--sample 10]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

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
NON_CODE_DIRS = {
    "tests",
    "test",
    "testing",
    "docs",
    "doc",
    "examples",
    "example",
    "benchmarks",
    "docs_src",
}
NON_CODE_FILES = {
    "tests.py",
    "setup.py",
    "noxfile.py",
    "conftest.py",
    "tasks.py",
    "fabfile.py",
}

MAX_FIX_FILES = 10
MAX_CANDIDATE_AGE_DAYS = 730
FILE_HISTORY_MIN = 3
AUTHOR_HISTORY_MIN = 5
TRAIN_SHARE = 0.7
DAY = 86400


@dataclass
class Commit:
    sha: str
    author: str
    ts: int
    subject: str
    body: str
    files: list[str] = field(default_factory=list)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout


def is_code_file(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    parts = path.split("/")
    if any(p in NON_CODE_DIRS for p in parts[:-1]):
        return False
    name = parts[-1]
    return not (
        name.startswith("test_") or name.endswith("_test.py") or name in NON_CODE_FILES
    )


def load_commits(repo: Path) -> list[Commit]:
    """All non-merge commits on HEAD, oldest first."""
    out = git(
        repo,
        "log",
        "--no-merges",
        "--reverse",
        "--name-only",
        "--format=%x1e%H%x1f%ae%x1f%at%x1f%s%x1f%b%x1f",
    )
    commits = []
    for rec in out.split("\x1e")[1:]:
        sha, author, ts, subject, body, rest = rec.split("\x1f", 5)
        files = [f for f in rest.strip().splitlines() if f.strip()]
        commits.append(Commit(sha, author.lower(), int(ts), subject, body, files))
    return commits


def is_bug_fix(c: Commit) -> bool:
    # Subject only: squash-merge bodies list every sub-commit ("* Fix lint", "* Fix tests"),
    # which made feature PRs look like bug fixes in the phase 0 hand check.
    if REVERT_RE.search(c.body) or c.subject.lower().startswith("revert"):
        return False
    return bool(FIX_RE.search(c.subject)) and not NON_BUG_FIX_RE.search(c.subject)


def find_reverts(
    repo: Path, commits: list[Commit], known: set[str]
) -> dict[str, list[str]]:
    """reverted sha -> [reverting shas]"""
    labels: dict[str, list[str]] = {}
    for c in commits:
        for short in REVERT_RE.findall(c.body):
            try:
                full = git(
                    repo, "rev-parse", "--verify", "--quiet", f"{short}^{{commit}}"
                ).strip()
            except subprocess.CalledProcessError:
                continue
            if full in known:
                labels.setdefault(full, []).append(c.sha)
    return labels


def run_szz(
    repo: Path, fixes: list[Commit], by_sha: dict[str, Commit]
) -> tuple[dict[str, list[str]], dict]:
    """bug-introducing sha -> [fix shas], plus filter stats."""
    from pydriller import Git

    gr = Git(str(repo))
    ignore = repo / ".git-blame-ignore-revs"
    ignore_path = str(ignore) if ignore.exists() else None
    labels: dict[str, list[str]] = {}
    stats = {
        "fix_commits": len(fixes),
        "skipped_too_many_files": 0,
        "skipped_no_code": 0,
        "dropped_too_old": 0,
        "dropped_unknown": 0,
        "fixes_with_candidates": 0,
    }
    for fix in fixes:
        if len(fix.files) > MAX_FIX_FILES:
            stats["skipped_too_many_files"] += 1
            continue
        code_files = [f for f in fix.files if is_code_file(f)]
        if not code_files:
            stats["skipped_no_code"] += 1
            continue
        commit = gr.get_commit(fix.sha)
        mods = [
            m
            for m in commit.modified_files
            if is_code_file(m.old_path or m.new_path or "") and m.old_path
        ]
        if not mods:
            continue
        found = False
        for mod in mods:
            for shas in gr.get_commits_last_modified_lines(
                commit, mod, ignore_path
            ).values():
                for sha in shas:
                    cand = by_sha.get(sha)
                    if cand is None:
                        stats["dropped_unknown"] += 1
                        continue
                    if fix.ts - cand.ts > MAX_CANDIDATE_AGE_DAYS * DAY:
                        stats["dropped_too_old"] += 1
                        continue
                    labels.setdefault(sha, [])
                    if fix.sha not in labels[sha]:
                        labels[sha].append(fix.sha)
                    found = True
        stats["fixes_with_candidates"] += int(found)
    return labels, stats


def coverage(commits: list[Commit], window: list[Commit]) -> dict:
    """Share of window commits whose code files / author have enough *prior* history."""
    window_shas = {c.sha for c in window}
    file_seen: dict[str, int] = {}
    author_seen: dict[str, int] = {}
    file_ok = author_ok = eligible = 0
    for c in commits:
        code = [f for f in c.files if is_code_file(f)]
        if c.sha in window_shas and code:
            eligible += 1
            if all(file_seen.get(f, 0) >= FILE_HISTORY_MIN for f in code):
                file_ok += 1
            if author_seen.get(c.author, 0) >= AUTHOR_HISTORY_MIN:
                author_ok += 1
        for f in code:
            file_seen[f] = file_seen.get(f, 0) + 1
        author_seen[c.author] = author_seen.get(c.author, 0) + 1
    return {
        "code_commits": eligible,
        "file_history_coverage": round(file_ok / eligible, 3) if eligible else 0.0,
        "author_history_coverage": round(author_ok / eligible, 3) if eligible else 0.0,
    }


def analyse(repo: Path, years: float) -> dict:
    t0 = time.perf_counter()
    commits = load_commits(repo)
    by_sha = {c.sha: c for c in commits}
    end = commits[-1].ts
    start = end - int(years * 365 * DAY)
    window = [c for c in commits if c.ts >= start]
    window_shas = {c.sha for c in window}
    code_window = [c for c in window if any(is_code_file(f) for f in c.files)]
    t_log = time.perf_counter() - t0

    t0 = time.perf_counter()
    reverts = find_reverts(repo, window, set(by_sha))
    t_rev = time.perf_counter() - t0

    t0 = time.perf_counter()
    fixes = [c for c in window if is_bug_fix(c)]
    szz, szz_stats = run_szz(repo, fixes, by_sha)
    t_szz = time.perf_counter() - t0

    labels: dict[str, dict] = {}
    for sha, by in reverts.items():
        if sha in window_shas:
            labels[sha] = {"confidence": "high", "reverted_by": by, "fixed_by": []}
    for sha, by in szz.items():
        if sha in window_shas:
            entry = labels.setdefault(
                sha, {"confidence": "medium", "reverted_by": [], "fixed_by": []}
            )
            entry["fixed_by"] = by

    split = int(len(code_window) * TRAIN_SHARE)
    train = {c.sha for c in code_window[:split]}
    test = {c.sha for c in code_window[split:]}

    def count(shas: set[str], conf: str | None = None) -> int:
        return sum(
            1
            for s, v in labels.items()
            if s in shas and (conf is None or v["confidence"] == conf)
        )

    fix_delays = [
        (by_sha[f].ts - by_sha[s].ts) / DAY
        for s, v in labels.items()
        for f in v["fixed_by"]
    ]
    authors = {c.author for c in window}
    summary = {
        "repo": repo.name,
        "head": git(repo, "rev-parse", "HEAD").strip(),
        "window_years": years,
        "window_start": time.strftime("%Y-%m-%d", time.gmtime(start)),
        "window_end": time.strftime("%Y-%m-%d", time.gmtime(end)),
        "all_commits": len(commits),
        "window_commits": len(window),
        "authors": len(authors),
        **coverage(commits, window),
        "fix_commits": len(fixes),
        "revert_labels": count(window_shas, "high"),
        "szz_labels": count(window_shas, "medium"),
        "labelled_code_commits": count({c.sha for c in code_window}),
        "positive_rate": round(
            count({c.sha for c in code_window}) / len(code_window), 3
        )
        if code_window
        else 0.0,
        "train_commits": len(train),
        "test_commits": len(test),
        "train_labels": count(train),
        "test_labels": count(test),
        "train_positive_rate": round(count(train) / len(train), 3) if train else 0.0,
        "test_positive_rate": round(count(test) / len(test), 3) if test else 0.0,
        "median_days_to_fix": round(statistics.median(fix_delays), 1)
        if fix_delays
        else None,
        "szz_filters": szz_stats,
        "seconds": {
            "log": round(t_log, 1),
            "reverts": round(t_rev, 1),
            "szz": round(t_szz, 1),
        },
    }
    return {
        "summary": summary,
        "labels": labels,
        "subjects": {
            s: by_sha[s].subject
            for s in set(labels)
            | {f for v in labels.values() for f in v["fixed_by"] + v["reverted_by"]}
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo", type=Path)
    ap.add_argument("--years", type=float, default=3.0)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--sample",
        type=int,
        default=0,
        help="print N random SZZ labels for hand-checking",
    )
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    result = analyse(args.repo.resolve(), args.years)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result["summary"], indent=2))

    if args.sample:
        szz = sorted(s for s, v in result["labels"].items() if v["fixed_by"])
        rng = random.Random(args.seed)
        for sha in rng.sample(szz, min(args.sample, len(szz))):
            fix = result["labels"][sha]["fixed_by"][0]
            print(
                f"\nBUG {sha[:10]} {result['subjects'][sha]}\nFIX {fix[:10]} {result['subjects'][fix]}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
