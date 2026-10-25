"""Shared local pull-request analysis for the CLI-facing data model and dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from reviewbudget import h1, model, smallest
from reviewbudget.budget import DEFAULT_SPEED, Plan, make_plan
from reviewbudget.dataset import Dataset, dataset_from_commits
from reviewbudget.git_changes import HistoryCommit, load_commits, load_history
from reviewbudget.h0 import rank as rank_h0
from reviewbudget.h0 import score_commit
from reviewbudget.history import compute_history
from reviewbudget.labels import LabelSet, load_labels
from reviewbudget.pr import LocalPR, has_tracked_changes
from reviewbudget.selector import Choice, select


@dataclass
class AnalysisResult:
    local_pr: LocalPR
    dataset: Dataset
    choice: Choice
    strategy: str
    ranked: list
    plan: Plan
    labels: LabelSet
    history_commits: list[HistoryCommit]


def analyze_local_pr(
    local_pr: LocalPR,
    budget: int,
    speed: int = DEFAULT_SPEED,
    strategy: str = "auto",
) -> AnalysisResult:
    """Analyze a local PR with repository evidence and a review budget."""
    if strategy not in {"auto", "h0", "s", "h1", "l"}:
        raise ValueError(f"unknown strategy: {strategy}")
    history_commits = load_history(local_pr.repo, "HEAD")
    all_commits = load_commits(local_pr.repo, ["HEAD"])
    labels, _ = load_labels(local_pr.repo)
    dataset = dataset_from_commits(all_commits, labels)
    choice = select(dataset)
    selected = choice.strategy if strategy == "auto" else strategy.upper()
    history = compute_history(all_commits, labels.labels)
    ranked_committed = _rank_commits(local_pr.commits, selected, history, dataset)
    worktree = score_commit(local_pr.working_tree)
    ranked = list(ranked_committed)
    if has_tracked_changes(local_pr.working_tree):
        ranked.append(worktree)
    plan = make_plan(ranked, budget, speed)
    return AnalysisResult(
        local_pr,
        dataset,
        choice,
        selected,
        ranked,
        plan,
        labels,
        history_commits,
    )


def _rank_commits(commits, strategy: str, history, dataset: Dataset) -> list:
    if strategy == "H0":
        return rank_h0([score_commit(commit) for commit in commits])
    if strategy == "S":
        return smallest.rank([smallest.score_commit(commit) for commit in commits])
    if strategy == "H1":
        return h1.rank(
            [h1.score_commit(commit, history[commit.sha]) for commit in commits]
        )
    learned = model.train(dataset.rows)
    if learned is None:
        return rank_h0([score_commit(commit) for commit in commits])
    return model.rank(model.score_commits(learned, commits, history))
