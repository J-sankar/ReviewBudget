"""Command-line interface: `rb queue`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reviewbudget.git_changes import GitError, load_commits
from reviewbudget.h0 import ScoredCommit, rank, score_commit

SUBJECT_WIDTH = 40
SHOWN_REASONS = 3


def _shorten(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def format_queue(ranked: list[ScoredCommit], title: str) -> str:
    lines = [
        title,
        "Scores are review priorities estimated from the diff alone, not bug predictions.",
        "",
        f"{'#':>3}  {'commit':8}  {'score':>5}  {'size':>11}  {'subject':{SUBJECT_WIDTH}}  why",
    ]
    for i, scored in enumerate(ranked, 1):
        c = scored.commit
        size = f"+{c.added}/-{c.deleted}"
        subject = _shorten(c.subject, SUBJECT_WIDTH)
        why = "; ".join(r.text for r in scored.reasons[:SHOWN_REASONS])
        lines.append(
            f"{i:>3}  {c.sha[:8]:8}  {scored.score:>5.1f}  {size:>11}  "
            f"{subject:{SUBJECT_WIDTH}}  {why}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rb", description="ReviewBudget: rank commits for review."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    queue = commands.add_parser(
        "queue", help="print a ranked review queue (H0 heuristic)"
    )
    queue.add_argument(
        "--repo", type=Path, default=Path("."), help="local git repository"
    )
    selection = queue.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--range", dest="rev_range", metavar="A..B", help="commit range"
    )
    selection.add_argument(
        "--last", type=int, metavar="N", help="the last N commits on HEAD"
    )
    args = parser.parse_args(argv)

    if args.last is not None and args.last < 1:
        queue.error("--last must be at least 1")
    if args.rev_range is not None and ".." not in args.rev_range:
        queue.error("--range must look like A..B")
    if args.rev_range:
        revisions, label = [args.rev_range], args.rev_range
    else:
        revisions, label = ["-n", str(args.last), "HEAD"], f"last {args.last} on HEAD"

    try:
        commits = load_commits(args.repo, revisions)
    except GitError as error:
        print(f"rb: error: {error}", file=sys.stderr)
        return 2
    if not commits:
        print(f"No non-merge commits in {label}.")
        return 0

    ranked = rank([score_commit(c) for c in commits])
    title = f"Strategy H0 (change-only heuristic) · {len(ranked)} commits · {label}"
    print(format_queue(ranked, title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
