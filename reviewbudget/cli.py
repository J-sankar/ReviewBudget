"""Command-line interface: `rb queue` and `rb labels`."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from reviewbudget.git_changes import GitError, load_commits
from reviewbudget.h0 import ScoredCommit, rank, score_commit
from reviewbudget.labels import LabelSet, load_labels

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


def format_labels(label_set: LabelSet, title: str, sample: int) -> str:
    labels = list(label_set.labels.values())
    high = sum(1 for label in labels if label.confidence == "high")
    s = label_set.stats
    lines = [
        title,
        (
            f"Code commits: {label_set.code_commits} · labelled buggy: {len(labels)} "
            f"({label_set.positive_rate:.0%}) · high (revert): {high} · "
            f"medium (SZZ): {len(labels) - high}"
        ),
        (
            f"Fix commits: {s['fix_commits']} · skipped, more than 10 files: "
            f"{s['skipped_too_many_files']} · skipped, no code: {s['skipped_no_code']} · "
            f"suspects dropped, over 2 years older than the fix: {s['dropped_too_old']}"
        ),
        (
            "Labels are evidence, not ground truth: about 50-65% of SZZ labels looked "
            "plausible in the phase 0 hand check."
        ),
    ]
    shown = sorted(labels, key=lambda label: (-label.found_at, label.sha))[:sample]
    if shown:
        lines += ["", f"Sample, newest evidence first ({len(shown)} of {len(labels)}):"]
        lines += [
            f"  {label.sha[:8]}  {label.confidence:6}  {label.note}" for label in shown
        ]
    return "\n".join(lines)


def _queue(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.last is not None and args.last < 1:
        parser.error("--last must be at least 1")
    if args.rev_range is not None and ".." not in args.rev_range:
        parser.error("--range must look like A..B")
    if args.rev_range:
        revisions, label = [args.rev_range], args.rev_range
    else:
        revisions, label = ["-n", str(args.last), "HEAD"], f"last {args.last} on HEAD"

    commits = load_commits(args.repo, revisions)
    if not commits:
        print(f"No non-merge commits in {label}.")
        return 0
    ranked = rank([score_commit(c) for c in commits])
    title = f"Strategy H0 (change-only heuristic) · {len(ranked)} commits · {label}"
    print(format_queue(ranked, title))
    return 0


def _labels(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.sample < 0:
        parser.error("--sample must be 0 or more")
    start = time.perf_counter()
    label_set, cached = load_labels(args.repo, use_cache=not args.no_cache)
    source = (
        "from cache" if cached else f"computed in {time.perf_counter() - start:.1f} s"
    )
    title = f"Bug labels for {args.repo} at {label_set.head[:8]} ({source})"
    print(format_labels(label_set, title, args.sample))
    return 0


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
    queue.set_defaults(handler=_queue, parser=queue)

    labels = commands.add_parser(
        "labels", help="find bug labels (reverts and SZZ) in history"
    )
    labels.add_argument(
        "--repo", type=Path, default=Path("."), help="local git repository"
    )
    labels.add_argument(
        "--sample", type=int, default=10, metavar="N", help="labels to show"
    )
    labels.add_argument(
        "--no-cache", action="store_true", help="recompute and refresh the cache"
    )
    labels.set_defaults(handler=_labels, parser=labels)

    args = parser.parse_args(argv)
    try:
        return args.handler(args, args.parser)
    except GitError as error:
        print(f"rb: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
