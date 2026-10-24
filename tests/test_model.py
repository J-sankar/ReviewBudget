from gitfixture import commit, init

from reviewbudget import model
from reviewbudget.cli import main
from reviewbudget.dataset import Row
from reviewbudget.git_changes import CommitChange, FileChange
from reviewbudget.h0 import score_commit
from reviewbudget.history import History
from reviewbudget.selector import Evidence, choose, inner_split

BASE = dict.fromkeys(model.FEATURES, 0.0) | {
    "code_lines": 10.0,
    "code_files": 1.0,
    "folders": 1.0,
}


def row(i: int, buggy: bool, file_bugs: float = 0.0, found_at: int | None = None):
    return Row(
        sha=f"c{i}",
        timestamp=i,
        subject="s",
        code_lines=10,
        h0_score=0.0,
        window="train",
        buggy=int(buggy),
        evidence_found_at=found_at,
        features=BASE | {"file_bugs": file_bugs},
    )


def signal_rows() -> list[Row]:
    """Every 4th commit is buggy and touches files with earlier bugs; a few clean ones do too."""
    return [
        row(i, i % 4 == 0, 5.0 if i % 4 == 0 else float(i % 10 == 1)) for i in range(40)
    ]


def test_learns_the_signal_that_predicts_bugs():
    learned = model.train(signal_rows())
    weights = dict(learned.weights())
    assert max(weights, key=lambda n: abs(weights[n])) == "file_bugs"
    assert weights["file_bugs"] > 0
    ranked = model.order(learned, signal_rows())
    assert all(r.buggy for r in ranked[:10])


def test_needs_both_buggy_and_clean_rows():
    assert model.train([row(i, False) for i in range(5)]) is None


def test_training_is_repeatable():
    features = [r.features for r in signal_rows()]
    first = model.train(signal_rows()).probabilities(features)
    assert model.train(signal_rows()).probabilities(features) == first


def test_explanations_name_the_signals_that_raised_the_score():
    learned = model.train(signal_rows())
    reasons = learned.explain(BASE | {"file_bugs": 5.0})
    assert reasons[0].text.startswith(
        "earlier bug-linked commits in the files: 5, above average (+"
    )
    assert reasons[0].points > 0


def test_absent_flags_are_never_reasons():
    rows = signal_rows()
    for r in rows:
        r.features = r.features | {"security": float(not r.buggy)}
    learned = model.train(rows)  # security code is *less* common in buggy rows here
    reasons = learned.explain(BASE | {"security": 0.0})
    assert not any("security" in r.text for r in reasons)


def test_commit_features_come_from_the_diff_and_history():
    c = CommitChange(
        "c", "ann", 0, "c", [FileChange("pkg/m.py", added_lines=["try:", "x = 1"])]
    )
    f = model.commit_features(c, History(4, 2, 7, False), score_commit(c))
    assert (f["error_handling"], f["security"], f["no_test_change"]) == (1, 0, 1)
    assert (f["code_lines"], f["code_files"], f["folders"]) == (2, 1, 1)
    assert (f["file_changes"], f["file_bugs"], f["author_commits"]) == (4, 2, 7)
    assert f["author_new_to_files"] == 1


def test_inner_split_hides_bugs_found_after_the_cut():
    found = [5, 9, 20, 3, 30, 4, 6, 7, 8, 9]
    rows = [row(i, True, found_at=f) for i, f in enumerate(found)]
    fit, check = inner_split(rows)  # cut at the 8th row, timestamp 7
    assert [r.buggy for r in fit] == [1, 0, 0, 1, 0, 1, 1]
    assert check == rows[7:]


RICH = Evidence(74, 26, 0.13, 0.8, 0.8)


def test_l_must_beat_every_rule_based_strategy():
    tie = choose(RICH, {"H0": 0.1, "S": 0.4, "H1": 0.3, "L": 0.4}, {})
    assert tie.strategy == "S"
    choice = choose(RICH, {"H0": 0.1, "S": 0.4, "H1": 0.3, "L": 0.5}, {}, "slice")
    assert choice.strategy == "L"
    assert choice.reasons[-1].startswith("L: best on slice")
    assert "S 40%, H1 30%, L 50%" in choice.reasons[-1]


def test_l_does_not_compete_without_enough_evidence():
    medium = Evidence(40, 18, 0.07, 0.8, 0.8)
    choice = choose(medium, {"H0": 0.1, "S": 0.2, "H1": 0.3, "L": 0.9}, {})
    assert choice.strategy == "H1"
    assert "L" not in choice.reasons[-1].split(";")[0]


def test_queue_with_l_needs_labels(tmp_path, capsys):
    repo = init(tmp_path / "repo")
    commit(repo, "add app", 1, {"pkg/app.py": "x = 1\n"})
    args = ["queue", "--repo", str(repo), "--last", "1", "--strategy", "l"]
    assert main(args) == 1
    assert "No bug labels to learn from" in capsys.readouterr().out
