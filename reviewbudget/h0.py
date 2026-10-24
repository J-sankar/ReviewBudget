"""H0: change-only heuristic ranking.

Scores a commit from its diff alone: never from the commit message or repository
history. Every point of score comes with a reason, so the ranking is explainable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from reviewbudget.git_changes import CommitChange, FileChange

CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala",
}  # fmt: skip
DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
TEST_DIRS = {"tests", "test", "testing", "__tests__"}
NON_PRODUCTION_DIRS = {"docs", "doc", "examples", "example", "benchmarks", "docs_src"}
TEST_FILE_NAMES = {"conftest.py", "tests.py"}
# Build and task scripts, not shipped program code (same list as the phase 0 spike).
BUILD_FILE_NAMES = {"setup.py", "noxfile.py", "tasks.py", "fabfile.py"}
COMMENT_PREFIXES = ("#", "//", "/*", "*")

# All hand-set weights live here.
WEIGHTS = {
    "size_per_log2_line": 0.5,
    "size_cap": 3.0,
    "extra_file": 0.5,
    "extra_file_cap": 1.5,
    "extra_dir": 0.5,
    "extra_dir_cap": 1.0,
    "error_handling": 2.0,
    "security": 2.0,
    "concurrency": 1.5,
    "no_test_change": 1.0,
    "non_code_only": 0.5,
    "whitespace_only": 0.1,
    "rename_only": 0.1,
    "docs_or_tests_only": 0.0,
}

RISK_PATTERNS = {
    "error_handling": (
        "error handling changed",
        re.compile(r"\b(try|except|raise|finally|catch|throw)\b"),
    ),
    "security": (
        "security-sensitive code changed",
        re.compile(
            r"\b(auth|authenticat\w*|authoriz\w*|oauth\w*|token\w*|password\w*|passwd"
            r"|secret\w*|credential\w*"
            r"|permission\w*|ssl|tls|cert\w*)\b",
            re.IGNORECASE,
        ),
    ),
    "concurrency": (
        "concurrency code changed",
        re.compile(
            r"\b(lock\w*|mutex\w*|thread\w*|semaphore\w*|race)\b", re.IGNORECASE
        ),
    ),
}


@dataclass
class Reason:
    points: float
    text: str
    key: str = ""  # names the signal; "size" marks the size points, which H1 leaves out


@dataclass
class ScoredCommit:
    commit: CommitChange
    score: float
    reasons: list[Reason]


def file_kind(path: str) -> str:
    """Classify a path as "code", "test", "docs" or "other"."""
    p = PurePosixPath(path)
    dirs = {part.lower() for part in p.parts[:-1]}
    name = p.name.lower()
    if name in BUILD_FILE_NAMES:
        return "other"
    if p.suffix.lower() in CODE_EXTENSIONS:
        if (
            dirs & TEST_DIRS
            or name in TEST_FILE_NAMES
            or name.startswith("test_")
            or p.stem.lower().endswith("_test")
            or ".test." in name
            or ".spec." in name
        ):
            return "test"
        if dirs & NON_PRODUCTION_DIRS:
            return "docs"
        return "code"
    if p.suffix.lower() in DOC_EXTENSIONS or dirs & {"docs", "doc"}:
        return "docs"
    return "other"


def code_lines(commit: CommitChange) -> int:
    """Lines added plus deleted in production code: the effort to review a commit."""
    return sum(
        f.added + f.deleted
        for f in commit.files
        if file_kind(f.path) == "code" and not f.binary
    )


def _normalise(lines: list[str]) -> list[str]:
    return sorted(n for n in ("".join(line.split()) for line in lines) if n)


def _is_whitespace_only(files: list[FileChange]) -> bool:
    return all(_normalise(f.added_lines) == _normalise(f.removed_lines) for f in files)


def _is_comment(line: str) -> bool:
    return line.strip().startswith(COMMENT_PREFIXES)


def _scored(commit: CommitChange, reasons: list[Reason]) -> ScoredCommit:
    reasons = sorted(reasons, key=lambda r: -r.points)
    return ScoredCommit(commit, round(sum(r.points for r in reasons), 2), reasons)


def score_commit(commit: CommitChange) -> ScoredCommit:
    w = WEIGHTS
    kinds = {f.path: file_kind(f.path) for f in commit.files}
    code = [f for f in commit.files if kinds[f.path] == "code" and not f.binary]
    changed = [f for f in code if not f.is_pure_rename]
    tests_changed = any(kind == "test" for kind in kinds.values())

    if not changed:
        if code:
            return _scored(
                commit,
                [Reason(w["rename_only"], "only renames code files", "low_value")],
            )
        if all(kind in ("docs", "test") for kind in kinds.values()):
            return _scored(
                commit,
                [Reason(w["docs_or_tests_only"], "docs or tests only", "low_value")],
            )
        return _scored(
            commit,
            [
                Reason(
                    w["non_code_only"],
                    "non-code files only (config, build, data)",
                    "low_value",
                )
            ],
        )
    if _is_whitespace_only(changed):
        return _scored(
            commit,
            [Reason(w["whitespace_only"], "whitespace-only code change", "low_value")],
        )

    reasons = []
    lines = sum(f.added + f.deleted for f in changed)
    size = min(w["size_cap"], w["size_per_log2_line"] * math.log2(1 + lines))
    reasons.append(Reason(round(size, 2), f"{lines} lines of code changed", "size"))

    if len(changed) > 1:
        points = min(w["extra_file_cap"], w["extra_file"] * (len(changed) - 1))
        reasons.append(Reason(points, f"{len(changed)} code files changed"))
    dirs = {str(PurePosixPath(f.path).parent) for f in changed}
    if len(dirs) > 1:
        points = min(w["extra_dir_cap"], w["extra_dir"] * (len(dirs) - 1))
        reasons.append(Reason(points, f"spread over {len(dirs)} folders"))

    text = [
        line
        for f in changed
        for line in f.added_lines + f.removed_lines
        if not _is_comment(line)
    ]
    for key, (label, pattern) in RISK_PATTERNS.items():
        hits = sorted(
            {m.group(0).lower() for line in text for m in pattern.finditer(line)}
        )
        if hits:
            reasons.append(Reason(w[key], f"{label} ({', '.join(hits[:3])})", key))

    if tests_changed:
        reasons.append(Reason(0.0, "tests updated"))
    else:
        reasons.append(
            Reason(
                w["no_test_change"],
                "code changed without a test change",
                "no_test_change",
            )
        )
    return _scored(commit, reasons)


def rank(scored: list[ScoredCommit]) -> list[ScoredCommit]:
    """Highest score first; ties go to the newer commit, then by sha."""
    return sorted(scored, key=lambda s: (-s.score, -s.commit.timestamp, s.commit.sha))
