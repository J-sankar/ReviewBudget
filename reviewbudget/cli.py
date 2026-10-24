"""Command-line interface: `rb queue`, `rb labels`, `rb dataset` and `rb evaluate`."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

from reviewbudget import evaluate as ev
from reviewbudget import h1, model, smallest
from reviewbudget.budget import (
    DEFAULT_SPEED,
    format_plan,
    make_plan,
    parse_budget,
    plan_markdown,
)
from reviewbudget.dataset import (
    Dataset,
    build_dataset,
    count_buggy,
    dataset_from_commits,
    iso_date,
    write_csv,
)
from reviewbudget.git_changes import GitError, git, load_commits
from reviewbudget.h0 import rank, score_commit
from reviewbudget.history import compute_history
from reviewbudget.labels import LabelSet, load_labels
from reviewbudget.selector import Choice, select

SUBJECT_WIDTH = 40
SHOWN_REASONS = 3
H0_NAME = "H0 (change-only heuristic)"
H1_NAME = "H1 (history-aware, per line)"
S_NAME = "S (smallest first)"
L_NAME = model.NAME
H0_NOTE = (
    "Scores are review priorities estimated from the diff alone, not bug predictions."
)
H1_NOTE = (
    "Scores are risk points per 100 changed code lines, from the diff and the "
    "repository's history: review priorities, not bug predictions."
)
L_NOTE = (
    "Scores are the learned bug likelihood (%) per 100 changed code lines, from this "
    "repository's noisy labels; reasons are the signals that raised it most."
)
S_NOTE = (
    "Scores are lines of program code to review, fewest first, so the budget covers "
    "the most commits; the reasons are context and do not change the order."
)


def _shorten(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def format_queue(
    ranked: list, title: str, note: str = H0_NOTE, details: list[str] | None = None
) -> str:
    """Ranked commits as a table; works for H0 and H1 scores."""
    lines = [
        title,
        *(details or []),
        note,
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


def _split_summary(dataset: Dataset) -> list[str]:
    train, test = dataset.train, dataset.test
    split = iso_date(dataset.split_time)
    rate = count_buggy(test) / len(test) if test else 0.0
    return [
        (
            f"Code commits: {len(dataset.rows)} · train {len(train)} (before {split}) · "
            f"test {len(test)} (from {split})"
        ),
        (
            f"Bug labels: train {count_buggy(train)} (evidence found before the split) · "
            f"test {count_buggy(test)} ({rate:.0%} of test commits)"
        ),
    ]


def _results_table(results: list[ev.Result]) -> list[str]:
    effort_header = f"bugs found in {ev.EFFORT_SHARE:.0%} effort"
    top_header = f"precision, top {ev.TOP_K}"
    lines = [f"{'strategy':28}  {effort_header:>24}  {top_header:>17}"]
    for r in results:
        lines.append(
            f"{r.name:28}  {r.recall_at_effort:>24.0%}  {r.precision_at_k:>17.0%}"
        )
    return lines


def format_choice(choice: Choice) -> list[str]:
    return ["Strategy selection:", *(f"  - {reason}" for reason in choice.reasons)]


def format_evaluation(
    dataset: Dataset,
    results: list[ev.Result] | None,
    title: str,
    train_results: list[ev.Result] | None = None,
    choice: Choice | None = None,
    learned: model.Model | None = None,
) -> str:
    lines = [title, *_split_summary(dataset)]
    lines.append(
        "Labels are noisy evidence, and the newest commits have had less time "
        "for their bugs to be found."
    )
    if results is None:
        lines += [
            "",
            (
                f"Too few test labels to measure rankings ({count_buggy(dataset.test)}; "
                f"need at least {ev.MIN_TEST_LABELS})."
            ),
        ]
    else:
        lines += ["", *_results_table(results)]
        lines.append(
            f"Bugs found in {ev.EFFORT_SHARE:.0%} effort: review in ranked order and "
            f"stop at {ev.EFFORT_SHARE:.0%} of the window's changed code lines."
        )
    if learned is not None:
        lines += [
            "",
            (
                f"What L learned from {learned.labels} bug labels in {learned.rows} "
                "older commits (weight per signal, inputs scaled):"
            ),
            *(f"  {w:+.2f}  {model.FEATURES[name]}" for name, w in learned.weights()),
        ]
    if train_results is not None:
        lines += [
            "",
            "Same strategies on the older (training) commits, for comparison"
            + (" (L left out: it learned from them):" if learned else ":"),
            *_results_table(train_results),
        ]
    if choice is not None:
        lines += ["", *format_choice(choice)]
    return "\n".join(lines)


def _queue(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.last is not None and args.last < 1:
        parser.error("--last must be at least 1")
    if args.rev_range is not None and ".." not in args.rev_range:
        parser.error("--range must look like A..B")
    minutes = None
    if args.budget is not None:
        try:
            minutes = parse_budget(args.budget)
        except ValueError as exc:
            parser.error(str(exc))
    if args.export is not None and minutes is None:
        parser.error("--export needs --budget")
    if args.speed < 1:
        parser.error("--speed must be at least 1 line an hour")
    if args.rev_range:
        revisions, label = [args.rev_range], args.rev_range
        tip = args.rev_range.rsplit("..", 1)[-1] or "HEAD"
    else:
        revisions, label = ["-n", str(args.last), "HEAD"], f"last {args.last} on HEAD"
        tip = "HEAD"

    if args.strategy in ("h0", "s"):
        commits = load_commits(args.repo, revisions)
        if not commits:
            print(f"No non-merge commits in {label}.")
            return 0
        name, note, ranked = _diff_only_ranking(args.strategy.upper(), commits)
        title = f"Strategy {name} · {len(ranked)} commits · {label}"
        return _show(args, ranked, title, note, [], minutes)

    # H1 and the selector need the whole history up to the range, and the bug labels.
    history_commits = load_commits(args.repo, [tip])
    wanted = set(
        git(args.repo, "log", "--no-merges", "--format=%H", *revisions, "--").split()
    )
    commits = [c for c in history_commits if c.sha in wanted]
    if not commits:
        print(f"No non-merge commits in {label}.")
        return 0
    label_set, _ = load_labels(args.repo, use_cache=not args.no_cache)
    dataset = dataset_from_commits(history_commits, label_set)
    details = []
    strategy = args.strategy.upper()
    if args.strategy == "auto":
        choice = select(dataset)
        strategy = choice.strategy
        details = format_choice(choice)
    history = compute_history(history_commits, label_set.labels)
    if strategy == "L":
        # Ranking new work, so L learns from every label known now.
        everything = [replace(r, buggy=int(bool(r.label_source))) for r in dataset.rows]
        learned = model.train(everything)
        if learned is None:
            print("No bug labels to learn from in this history; try --strategy auto.")
            return 1
        details.append(
            f"L learned from {learned.labels} bug labels in {learned.rows} code commits."
        )
        ranked = model.rank(model.score_commits(learned, commits, history))
        name, note = L_NAME, L_NOTE
    elif strategy == "H1":
        ranked = h1.rank([h1.score_commit(c, history[c.sha]) for c in commits])
        name, note = H1_NAME, H1_NOTE
    else:
        name, note, ranked = _diff_only_ranking(strategy, commits)
    title = f"Strategy {name} · {len(ranked)} commits · {label}"
    return _show(args, ranked, title, note, details, minutes)


def _show(
    args: argparse.Namespace,
    ranked: list,
    title: str,
    note: str,
    details: list[str],
    minutes: int | None,
) -> int:
    """Print the queue, or the budgeted plan (and its Markdown export) when asked."""
    if minutes is None:
        print(format_queue(ranked, title, note, details))
        return 0
    plan = make_plan(ranked, minutes, args.speed)
    print(format_plan(plan, title, note, details))
    if args.export is not None:
        try:
            args.export.write_text(
                plan_markdown(plan, title, note, details), encoding="utf-8"
            )
        except OSError as exc:
            print(f"rb: cannot write {args.export}: {exc.strerror}", file=sys.stderr)
            return 1
        print(f"\nWrote the plan to {args.export}")
    return 0


def _diff_only_ranking(strategy: str, commits: list) -> tuple[str, str, list]:
    """Rank with H0 or S, which need only the diffs."""
    if strategy == "S":
        ranked = smallest.rank([smallest.score_commit(c) for c in commits])
        return S_NAME, S_NOTE, ranked
    return H0_NAME, H0_NOTE, rank([score_commit(c) for c in commits])


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


def _dataset(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    dataset = build_dataset(args.repo, use_cache=not args.no_cache)
    write_csv(dataset, args.out)
    train, test = dataset.train, dataset.test
    print(
        f"Wrote {len(dataset.rows)} rows to {args.out} (train {len(train)}, test {len(test)}; "
        f"bug labels: train {count_buggy(train)}, test {count_buggy(test)})."
    )
    return 0


def _evaluate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    dataset = build_dataset(args.repo, use_cache=not args.no_cache)
    if not dataset.rows:
        print("No commits that change program code; nothing to evaluate.")
        return 0
    title = f"Evaluation for {args.repo} at {dataset.head[:8]}"
    choice = select(dataset)
    learned = model.train(dataset.train) if choice.model_eligible else None
    print(
        format_evaluation(
            dataset,
            ev.evaluate(dataset, learned=learned),
            title,
            train_results=ev.evaluate(dataset, "train"),
            choice=choice,
            learned=learned,
        )
    )
    return 0


def _add_repo_options(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--repo", type=Path, default=Path("."), help="local git repository"
    )
    command.add_argument(
        "--no-cache", action="store_true", help="recompute the bug labels"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rb", description="ReviewBudget: rank commits for review."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    queue = commands.add_parser("queue", help="print a ranked review queue")
    _add_repo_options(queue)
    queue.add_argument(
        "--strategy",
        choices=["auto", "h0", "s", "h1", "l"],
        default="auto",
        help="auto picks H0, S, H1 or L from the repository's bug evidence (default)",
    )
    queue.add_argument(
        "--budget", metavar="TIME", help="review time, such as 15m, 1h or 1h30m"
    )
    queue.add_argument(
        "--speed",
        type=int,
        default=DEFAULT_SPEED,
        help=f"lines of code reviewed per hour (default {DEFAULT_SPEED})",
    )
    queue.add_argument(
        "--export",
        type=Path,
        metavar="FILE",
        help="also write the plan as Markdown (needs --budget)",
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
    _add_repo_options(labels)
    labels.add_argument(
        "--sample", type=int, default=10, metavar="N", help="labels to show"
    )
    labels.set_defaults(handler=_labels, parser=labels)

    dataset = commands.add_parser(
        "dataset", help="write one row per code commit to a CSV file"
    )
    _add_repo_options(dataset)
    dataset.add_argument("--out", type=Path, required=True, help="CSV file to write")
    dataset.set_defaults(handler=_dataset, parser=dataset)

    evaluate = commands.add_parser(
        "evaluate", help="score H0, H1 and baselines on newer commits"
    )
    _add_repo_options(evaluate)
    evaluate.set_defaults(handler=_evaluate, parser=evaluate)

    args = parser.parse_args(argv)
    try:
        return args.handler(args, args.parser)
    except (GitError, OSError) as error:
        print(f"rb: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
