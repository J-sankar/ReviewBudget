import csv

import pytest
from gitfixture import commit, init, timestamp

from reviewbudget import evaluate as ev
from reviewbudget.cli import format_evaluation, main
from reviewbudget.dataset import Dataset, Row, make_rows
from reviewbudget.git_changes import CommitChange, FileChange
from reviewbudget.h0 import score_commit
from reviewbudget.labels import Label


def row(name: str, lines: int, buggy: int = 0, score: float = 0.0) -> Row:
    return Row(
        sha=name,
        timestamp=0,
        subject=name,
        code_lines=lines,
        h0_score=score,
        buggy=buggy,
    )


# Total effort is 200 lines, so the 20% budget is 40 lines.
ROWS = [
    row("a", 10, 1, 1.0),
    row("b", 50, 0, 3.0),
    row("c", 20, 1, 2.0),
    row("d", 120, 0, 4.0),
]
BY_NAME = {r.sha: r for r in ROWS}


def ordered(names: str) -> list[Row]:
    return [BY_NAME[n] for n in names]


def test_recall_at_effort_stops_at_the_budget():
    assert ev.recall_at_effort(ordered("acbd")) == 1.0  # 10 + 20 lines fit in 40
    assert ev.recall_at_effort(ordered("abcd")) == 0.5  # a fits, then b would make 60
    assert ev.recall_at_effort(ordered("dabc")) == 0.0  # d alone is over the budget


def test_recall_without_bugs_is_none():
    assert ev.recall_at_effort([row("x", 5)]) is None


def test_zero_line_commits_still_cost_effort():
    rows = [row("x0", 0), row("x1", 0), row("bug", 0, 1)] + [
        row(f"y{i}", 0) for i in range(7)
    ]
    assert ev.recall_at_effort(rows) == 0.0  # budget is 2 of 10 lines; the bug is third


def test_precision_at_k():
    assert ev.precision_at_k(ordered("abcd"), k=2) == 0.5
    assert ev.precision_at_k(ordered("abcd")) == 0.5
    assert ev.precision_at_k([]) is None


def test_strategy_orders():
    assert [r.sha for r in ev.by_h0(ROWS)] == ["d", "b", "c", "a"]
    assert [r.sha for r in ev.largest_first(ROWS)] == ["d", "b", "c", "a"]
    assert [r.sha for r in ev.smallest_first(ROWS)] == ["a", "c", "b", "d"]


def test_random_baseline_is_repeatable():
    first, second = ev.random_baseline(ROWS), ev.random_baseline(ROWS)
    assert first == second
    assert 0.0 <= first.recall_at_effort <= 1.0


def test_evaluate_needs_enough_test_labels(monkeypatch):
    dataset = Dataset("head", 0, ROWS)
    assert ev.evaluate(dataset) is None
    monkeypatch.setattr(ev, "MIN_TEST_LABELS", 2)
    results = {r.name: r for r in ev.evaluate(dataset)}
    assert results["H0 (change-only heuristic)"].recall_at_effort == 0.0
    assert results["smallest first"].recall_at_effort == 1.0
    text = format_evaluation(dataset, list(results.values()), "title")
    assert "bugs found in 20% effort" in text and "smallest first" in text


def _commit(sha: str, day: int, path: str = "pkg/a.py") -> CommitChange:
    files = [FileChange(path, added_lines=["x = 1"])]
    return CommitChange(sha, "dev@example.com", timestamp(day), f"commit {sha}", files)


def _label(sha: str, found_day: int) -> Label:
    return Label(
        sha, "medium", "szz", ["f" * 40], timestamp(found_day), "fixed by ffffffff"
    )


def test_split_hides_training_bugs_found_after_the_split():
    scored = [
        score_commit(_commit(sha, day))
        for sha, day in [("c0", 0), ("c1", 1), ("c2", 2), ("c3", 3)]
    ]
    labels = {"c0": _label("c0", 1), "c1": _label("c1", 3), "c3": _label("c3", 4)}
    rows, split_time = make_rows(scored, labels, train_share=0.5)
    assert split_time == timestamp(2)
    assert [r.window for r in rows] == ["train", "train", "test", "test"]
    assert [r.buggy for r in rows] == [1, 0, 0, 1]
    assert [r.hidden_from_training for r in rows] == [0, 1, 0, 0]


def test_only_code_commits_become_rows():
    scored = [
        score_commit(_commit("c0", 0)),
        score_commit(_commit("d0", 1, "docs/index.md")),
    ]
    rows, _ = make_rows(scored, {})
    assert [r.sha for r in rows] == ["c0"]


@pytest.fixture
def small_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    r = init(tmp_path / "repo")
    good = "def parse(v):\n    return int(v)\n"
    commit(r, "initial", 0, {"pkg/core.py": good})
    shas = {
        "bug": commit(
            r, "Add scaling", 10, {"pkg/core.py": good.replace("(v)\n", "(v) * 10\n")}
        )
    }
    shas["fix"] = commit(r, "Fix crash when parsing", 20, {"pkg/core.py": good})
    commit(r, "Update readme", 30, {"README.md": "# Demo\n"})
    commit(
        r,
        "Add render",
        40,
        {"pkg/core.py": good + "\n\ndef render(v):\n    return str(v)\n"},
    )
    return r, shas


def test_cli_dataset_writes_csv(small_repo, tmp_path, capsys):
    r, shas = small_repo
    out = tmp_path / "data.csv"
    assert main(["dataset", "--repo", str(r), "--out", str(out)]) == 0
    assert "Wrote 4 rows" in capsys.readouterr().out
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [x["window"] for x in rows] == ["train", "train", "test", "test"]
    bug = next(x for x in rows if x["sha"] == shas["bug"])
    # Its fix landed exactly at the split, so training must not see it.
    assert (bug["buggy"], bug["hidden_from_training"], bug["label_source"]) == (
        "0",
        "1",
        "szz",
    )
    assert bug["evidence"] == shas["fix"]


def test_cli_evaluate_reports_too_few_labels(small_repo, capsys):
    r, _ = small_repo
    assert main(["evaluate", "--repo", str(r)]) == 0
    out = capsys.readouterr().out
    assert "train 2" in out and "test 2" in out
    assert "Too few test labels to measure rankings (0; need at least 10)" in out


def test_cli_dataset_reports_an_unwritable_path(small_repo, tmp_path, capsys):
    r, _ = small_repo
    assert (
        main(
            ["dataset", "--repo", str(r), "--out", str(tmp_path / "missing" / "x.csv")]
        )
        == 2
    )
    assert "rb: error" in capsys.readouterr().err
