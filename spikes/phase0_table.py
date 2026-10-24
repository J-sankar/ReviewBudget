"""Summarise phase 0 spike results (a directory of JSON files) as a Markdown table.

Also applies the draft selector thresholds from docs/phase0.md, so the table shows
which strategy tier each repository would get. Commit count is not an input.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

L_MIN_TRAIN = 50
L_MIN_TEST = 20
L_POSITIVE_RATE = (0.03, 0.30)
H1_MIN_TEST = 10
H1_MIN_COVERAGE = 0.6


def draft_tier(s: dict) -> str:
    low, high = L_POSITIVE_RATE
    if s["train_labels"] >= L_MIN_TRAIN and s["test_labels"] >= L_MIN_TEST and low <= s["positive_rate"] <= high:
        return "L eligible"
    coverage = min(s["file_history_coverage"], s["author_history_coverage"])
    if s["test_labels"] >= H1_MIN_TEST and coverage >= H1_MIN_COVERAGE:
        return "H1"
    return "H0"


def table(results_dir: Path) -> str:
    rows = [
        "| Repo | Commits | Code commits | Authors | File cov. | Author cov. | Revert | SZZ "
        "| Positive rate | Train labels | Test labels | SZZ time (s) | Draft tier |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for path in sorted(results_dir.glob("*.json")):
        s = json.loads(path.read_text())["summary"]
        rows.append(
            f"| {s['repo']} | {s['window_commits']} | {s['code_commits']} | {s['authors']} "
            f"| {s['file_history_coverage']:.2f} | {s['author_history_coverage']:.2f} "
            f"| {s['revert_labels']} | {s['szz_labels']} | {s['positive_rate']:.2f} "
            f"| {s['train_labels']} | {s['test_labels']} | {s['seconds']['szz']:.0f} | {draft_tier(s)} |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args(argv)
    if not args.results_dir.is_dir():
        parser.error(f"not a directory: {args.results_dir}")
    print(table(args.results_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
