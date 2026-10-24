import pytest
from gitfixture import commit, init

from reviewbudget import h0
from reviewbudget.budget import make_plan, minutes_for, parse_budget, plan_markdown
from reviewbudget.cli import main
from reviewbudget.git_changes import CommitChange, FileChange


@pytest.mark.parametrize(
    ("text", "minutes"),
    [("15m", 15), ("90m", 90), ("1h", 60), ("1h30m", 90), (" 2H ", 120)],
)
def test_parse_budget(text, minutes):
    assert parse_budget(text) == minutes


@pytest.mark.parametrize("text", ["", "15", "0m", "-5m", "abc", "1h-3m", "0h0m"])
def test_parse_budget_rejects_bad_input(text):
    with pytest.raises(ValueError, match="budget"):
        parse_budget(text)


def change(sha: str, lines: int, risky: bool = False, path: str = "pkg/m.py"):
    added = [f"value_{i} = {i}" for i in range(lines)]
    if risky and added:
        added[0] = "except ValueError:"
    return CommitChange(
        sha, "ann", 0, f"commit {sha}", [FileChange(path, added_lines=added)]
    )


def ranked(*commits: CommitChange) -> list[h0.ScoredCommit]:
    return [h0.score_commit(c) for c in commits]


def test_minutes_follow_code_lines_and_review_speed():
    assert minutes_for(change("a", 300), 300) == 60
    assert minutes_for(change("a", 7), 300) == 2  # 1.4 minutes, rounded up
    assert minutes_for(change("d", 0, path="README.md"), 300) == 1


def test_plan_stops_at_the_first_commit_that_does_not_fit():
    plan = make_plan(
        ranked(change("a", 5), change("b", 30), change("c", 600), change("d", 5)),
        budget=10,
    )
    assert [e.item.commit.sha for e in plan.included] == ["a", "b"]
    assert plan.used == 7
    reasons = {e.item.commit.sha: e.reason for e in plan.skipped}
    assert reasons["c"] == "needs 120 min, only 3 min left: the plan stops here"
    assert reasons["d"] == "ranked #4; the plan stopped at #3"


def test_every_skipped_commit_has_a_reason():
    docs = change("docs", 3, path="README.md")
    plan = make_plan(ranked(change("big", 900), change("a", 5), docs), budget=5)
    assert plan.included == []
    assert all(e.reason for e in plan.skipped)
    assert plan.skipped[-1].reason == "docs or tests only"


def test_riskiest_list_flags_risky_commits_that_do_not_fit():
    small, big = change("small", 3, risky=True), change("big", 600, risky=True)
    plan = make_plan(ranked(small, change("plain", 4), big), budget=10)
    status = {r.scored.commit.sha: r.status for r in plan.riskiest}
    assert status["small"] == "in your plan (#1)"
    assert status["big"].startswith("needs 120 min, more than the whole budget")


def test_markdown_export_has_all_three_sections():
    plan = make_plan(ranked(change("a", 5), change("b", 900, risky=True)), budget=5)
    text = plan_markdown(
        plan, "Strategy S", "a note", ["Strategy selection:", "  - S: best"]
    )
    assert text.startswith("# Review plan")
    assert "## Within your 5 minutes" in text and "| 1 | `a` |" in text
    assert "## Skipped (1)" in text and "the plan stops here" in text
    assert "## Riskiest changes" in text and "\n- S: best\n" in text


@pytest.fixture
def small_repo(tmp_path):
    repo = init(tmp_path / "repo")
    commit(repo, "add app", 1, {"pkg/app.py": "def run():\n    return 1\n"})
    commit(repo, "docs", 2, {"README.md": "hello\n"})
    commit(repo, "error path", 3, {"pkg/app.py": "def run():\n    raise ValueError\n"})
    return repo


def test_queue_with_budget_and_export(small_repo, tmp_path, capsys):
    out_file = tmp_path / "plan.md"
    args = ["queue", "--repo", str(small_repo), "--last", "3", "--strategy", "s"]
    assert main([*args, "--budget", "2m", "--export", str(out_file)]) == 0
    out = capsys.readouterr().out
    assert "Within your 2 minutes:" in out and "Budget 2 min at 300 lines" in out
    assert "Skipped (1):" in out and "Riskiest changes" in out
    assert f"Wrote the plan to {out_file}" in out
    assert out_file.read_text(encoding="utf-8").startswith("# Review plan")


@pytest.mark.parametrize(
    "extra",
    [["--budget", "0m"], ["--export", "plan.md"], ["--budget", "5m", "--speed", "0"]],
)
def test_queue_rejects_bad_budget_options(small_repo, extra):
    with pytest.raises(SystemExit):
        main(["queue", "--repo", str(small_repo), "--last", "3", *extra])
