from dataclasses import fields

import pytest
from gitfixture import commit, init

from reviewbudget import h1
from reviewbudget.cli import main
from reviewbudget.git_changes import CommitChange, FileChange
from reviewbudget.history import History, compute_history
from reviewbudget.labels import Label
from reviewbudget.selector import Evidence, choose


def change(sha: str, ts: int, author: str, path: str, old_path=None) -> CommitChange:
    files = [FileChange(path, old_path, added_lines=["x = 1"])]
    return CommitChange(sha, author, ts, sha, files)


def label(sha: str, found_at: int) -> Label:
    return Label(sha, "medium", "szz", ["fix"], found_at, "")


def test_history_counts_only_earlier_commits():
    commits = [
        change("c1", 10, "ann", "pkg/m.py"),
        change("c2", 20, "bob", "pkg/m.py"),
        change("c3", 30, "ann", "pkg/m.py"),
    ]
    history = compute_history(commits, {})
    assert history["c1"] == History(0, 0, 0, False)
    assert history["c2"] == History(1, 0, 0, False)
    assert history["c3"] == History(2, 0, 1, True)


def test_bug_only_counts_once_its_evidence_has_appeared():
    commits = [
        change("c1", 10, "ann", "pkg/m.py"),
        change("c2", 20, "ann", "pkg/m.py"),
        change("c3", 30, "ann", "pkg/m.py"),
    ]
    history = compute_history(commits, {"c1": label("c1", 25)})
    assert history["c2"].file_bugs == 0  # the bug in c1 was found after c2
    assert history["c3"].file_bugs == 1
    at_c3 = compute_history(commits, {"c1": label("c1", 30)})
    assert at_c3["c3"].file_bugs == 0  # evidence at the same moment is not yet known


def test_renamed_file_keeps_its_history():
    commits = [
        change("c1", 10, "ann", "pkg/old.py"),
        change("c2", 20, "bob", "pkg/new.py", old_path="pkg/old.py"),
        change("c3", 30, "bob", "pkg/new.py"),
    ]
    assert compute_history(commits, {})["c3"].file_changes == 2


def code_change(lines: int, risky: bool) -> CommitChange:
    added = [f"value_{i} = {i}" for i in range(lines)]
    if risky:
        added[0] = "except ValueError:"
    return CommitChange("s", "ann", 0, "s", [FileChange("pkg/m.py", added_lines=added)])


FAMILIAR = History(
    file_changes=0, file_bugs=0, author_commits=10, author_knows_files=True
)


def test_small_risky_change_ranks_above_large_one_with_the_same_risk():
    small = h1.score_commit(code_change(2, risky=True), FAMILIAR)
    large = h1.score_commit(code_change(200, risky=True), FAMILIAR)
    assert small.risk == large.risk  # H1 risk has no size points
    assert small.score > large.score
    assert h1.rank([large, small])[0] is small


def test_history_points_come_with_reasons():
    past = History(
        file_changes=7, file_bugs=2, author_commits=1, author_knows_files=False
    )
    scored = h1.score_commit(code_change(5, risky=False), past)
    texts = [r.text for r in scored.reasons]
    assert "files had 2 earlier bug-linked commits" in texts
    assert "files changed 7 times before" in texts
    assert "author's first change to these files" in texts
    assert "author has 1 earlier commit" in texts
    assert scored.risk == pytest.approx(sum(r.points for r in scored.reasons))


def test_config_only_commit_does_not_jump_the_queue():
    config = CommitChange(
        "c", "ann", 0, "c", [FileChange("setup.cfg", added_lines=["a"] * 20)]
    )
    code = h1.score_commit(code_change(20, risky=True), FAMILIAR)
    assert h1.score_commit(config, FAMILIAR).score < code.score


def test_docs_only_commit_gets_no_history_points():
    docs = CommitChange(
        "d", "ann", 0, "d", [FileChange("README.md", added_lines=["x"])]
    )
    scored = h1.score_commit(docs, History(9, 3, 0, False))
    assert scored.risk == 0.0


def test_selector_does_not_take_repository_size():
    names = {f.name for f in fields(Evidence)}
    assert names == {
        "train_labels",
        "test_labels",
        "positive_rate",
        "file_coverage",
        "author_coverage",
    }


@pytest.mark.parametrize(
    ("evidence", "strategy", "eligible"),
    [
        (Evidence(74, 26, 0.13, 0.8, 0.8), "H1", True),  # rich evidence
        (Evidence(50, 20, 0.03, 0.1, 0.1), "H1", True),  # model thresholds, exactly
        (Evidence(49, 20, 0.10, 0.8, 0.8), "H1", False),
        (Evidence(60, 25, 0.31, 0.8, 0.8), "H1", False),  # too many labels: noisy
        (Evidence(40, 10, 0.07, 0.6, 0.6), "H1", False),  # H1 thresholds, exactly
        (Evidence(40, 9, 0.07, 0.8, 0.8), "H0", False),
        (Evidence(40, 18, 0.07, 0.59, 0.8), "H0", False),
        (Evidence(40, 18, 0.07, 0.8, 0.59), "H0", False),
        (Evidence(15, 2, 0.06, 0.9, 0.9), "H0", False),  # thin evidence
    ],
)
def test_selector_tiers(evidence, strategy, eligible):
    choice = choose(evidence, h0_recall=0.1, h1_recall=0.3)
    assert (choice.strategy, choice.model_eligible) == (strategy, eligible)
    assert choice.reasons[-1].startswith(strategy)


def test_selector_falls_back_to_h0_when_h1_does_not_win():
    choice = choose(Evidence(74, 26, 0.13, 0.8, 0.8), h0_recall=0.2, h1_recall=0.2)
    assert choice.strategy == "H0"
    assert "did not beat H0" in choice.reasons[-1]


def test_thin_evidence_explains_what_is_missing():
    choice = choose(Evidence(15, 2, 0.06, 0.5, 0.9), h0_recall=None, h1_recall=None)
    assert "only 2 newer labels" in choice.reasons[-1]
    assert "file history coverage 0.50" in choice.reasons[-1]


@pytest.fixture
def small_repo(tmp_path):
    repo = init(tmp_path / "repo")
    commit(repo, "add app", 1, {"pkg/app.py": "def run():\n    return 1\n"})
    commit(repo, "docs", 2, {"README.md": "hello\n"})
    commit(repo, "error path", 3, {"pkg/app.py": "def run():\n    raise ValueError\n"})
    return repo


def test_queue_auto_explains_its_choice(small_repo, capsys):
    assert main(["queue", "--repo", str(small_repo), "--last", "3"]) == 0
    out = capsys.readouterr().out
    assert "Strategy H0 (change-only heuristic) · 3 commits" in out
    assert "Strategy selection:" in out and "H0: only 0 newer labels" in out


def test_queue_can_force_h1(small_repo, capsys):
    assert (
        main(
            [
                "queue",
                "--repo",
                str(small_repo),
                "--range",
                "HEAD~2..HEAD",
                "--strategy",
                "h1",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Strategy H1 (history-aware, per line) · 2 commits" in out
    assert "risk points per 100 changed code lines" in out
    assert "author has 2 earlier commits" in out


def test_evaluate_prints_the_selection(small_repo, capsys):
    assert main(["evaluate", "--repo", str(small_repo)]) == 0
    out = capsys.readouterr().out
    assert "Too few test labels" in out and "Strategy selection:" in out
