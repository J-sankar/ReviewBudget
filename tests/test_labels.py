import pytest
from gitfixture import commit, init, timestamp

from reviewbudget.cli import main
from reviewbudget.git_changes import HistoryCommit
from reviewbudget.labels import cache_path, combine, is_bug_fix, load_labels

CORE_V1 = "def parse(value):\n    return int(value)\n\n\ndef render(value):\n    return str(value)\n"


@pytest.fixture
def history(tmp_path):
    """A history with exactly two true labels: one SZZ pair and one revert.

    Everything else is a case the filters must reject.
    """
    r = init(tmp_path / "repo")
    shas = {}
    shas["initial"] = commit(
        r,
        "initial",
        0,
        {
            "pkg/core.py": CORE_V1,
            "tests/test_core.py": "def test_parse():\n    assert True\n",
            "README.md": "# Demo\n",
        },
    )
    core_bug = CORE_V1.replace("return int(value)", "return int(value) * 10")
    shas["bug"] = commit(r, "Add scaling to parse", 10, {"pkg/core.py": core_bug})
    shas["fix"] = commit(
        r, "Fix crash when parsing values", 20, {"pkg/core.py": CORE_V1}
    )
    shas["flag"] = commit(
        r, "Add feature flag", 30, {"pkg/core.py": CORE_V1 + "FLAG = True\n"}
    )
    shas["revert"] = commit(
        r,
        'Revert "Add feature flag"',
        31,
        {"pkg/core.py": CORE_V1},
        body=f"This reverts commit {shas['flag']}.",
    )
    shas["docs_fix"] = commit(r, "Fix typo in docs", 40, {"README.md": "# Demo app\n"})
    core_render = CORE_V1.replace("return str(value)", "return repr(value)")
    shas["squash"] = commit(
        r,
        "Add render option",
        41,
        {"pkg/core.py": core_render},
        body="* Fix lint\n* Fix tests",
    )
    shas["test_fix"] = commit(
        r,
        "Fix flaky test",
        42,
        {"tests/test_core.py": "def test_parse():\n    assert 1\n"},
    )
    modules = {f"pkg/m{i}.py": f"VALUE = {i}\n" for i in range(12)}
    shas["modules"] = commit(r, "Add twelve modules", 50, modules)
    shas["wide_fix"] = commit(
        r, "Fix bug across modules", 51, {name: "VALUE = 0\n" for name in modules}
    )
    shas["helper"] = commit(
        r, "Add helper", 60, {"pkg/old.py": "def helper():\n    return 1\n"}
    )
    shas["late_fix"] = commit(
        r, "Fix helper crash", 900, {"pkg/old.py": "def helper():\n    return 2\n"}
    )
    return r, shas


def test_finds_exactly_the_known_labels(history, tmp_path):
    r, shas = history
    label_set, cached = load_labels(r, cache_dir=tmp_path / "cache")
    assert not cached
    assert set(label_set.labels) == {shas["bug"], shas["flag"]}

    szz = label_set.labels[shas["bug"]]
    assert (szz.confidence, szz.source, szz.evidence) == (
        "medium",
        "szz",
        [shas["fix"]],
    )
    assert szz.found_at == timestamp(20)
    assert "Fix crash when parsing values" in szz.note

    revert = label_set.labels[shas["flag"]]
    assert (revert.confidence, revert.source, revert.evidence) == (
        "high",
        "revert",
        [shas["revert"]],
    )
    assert revert.found_at == timestamp(31)


def test_filters_are_counted(history, tmp_path):
    r, _ = history
    label_set, _ = load_labels(r, cache_dir=tmp_path / "cache")
    stats = label_set.stats
    assert stats["fix_commits"] == 4
    assert stats["skipped_too_many_files"] == 1
    assert stats["skipped_no_code"] == 1
    assert stats["dropped_too_old"] >= 1
    assert label_set.code_commits == 10
    assert label_set.positive_rate == pytest.approx(0.2)


def test_revert_evidence_wins_over_szz():
    def c(sha, day):
        return HistoryCommit(sha, timestamp(day), f"commit {sha}", "", [])

    by_sha = {
        sha: c(sha, day) for sha, day in (("a" * 40, 0), ("f" * 40, 5), ("r" * 40, 9))
    }
    labels = combine({"a" * 40: ["r" * 40]}, {"a" * 40: ["f" * 40]}, by_sha)
    label = labels["a" * 40]
    assert (label.confidence, label.source) == ("high", "revert")
    assert label.found_at == timestamp(5)


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("Fix crash on empty body", "", True),
        ("Handle regression in redirects", "", True),
        ("Fix typo in README", "", False),
        ("Add option", "* Fix lint\n* Fix tests", False),
        ('Revert "Fix x"', "This reverts commit abc1234.", False),
    ],
)
def test_is_bug_fix(subject, body, expected):
    assert is_bug_fix(HistoryCommit("a" * 40, 0, subject, body, [])) is expected


def test_cache_returns_the_same_labels(history, tmp_path):
    r, _ = history
    fresh, cached_first = load_labels(r, cache_dir=tmp_path / "cache")
    again, cached_second = load_labels(r, cache_dir=tmp_path / "cache")
    assert (cached_first, cached_second) == (False, True)
    assert again == fresh


def test_unreadable_cache_is_recomputed(history, tmp_path):
    r, _ = history
    fresh, _ = load_labels(r, cache_dir=tmp_path / "cache")
    cache_path(r, fresh.head, tmp_path / "cache").write_text("not json")
    again, cached = load_labels(r, cache_dir=tmp_path / "cache")
    assert not cached
    assert again == fresh


def test_cli_labels_prints_counts_then_uses_cache(
    history, tmp_path, monkeypatch, capsys
):
    r, shas = history
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert main(["labels", "--repo", str(r), "--sample", "5"]) == 0
    out = capsys.readouterr().out
    assert "computed in" in out
    assert "labelled buggy: 2 (20%)" in out
    assert "high (revert): 1" in out and "medium (SZZ): 1" in out
    assert shas["bug"][:8] in out and shas["flag"][:8] in out
    assert main(["labels", "--repo", str(r)]) == 0
    assert "from cache" in capsys.readouterr().out


def test_cli_labels_reports_a_non_repository(tmp_path, capsys):
    assert main(["labels", "--repo", str(tmp_path)]) == 2
    assert "not a git repository" in capsys.readouterr().err


def test_cli_labels_reports_an_empty_repository(tmp_path, capsys):
    r = init(tmp_path / "empty")
    assert main(["labels", "--repo", str(r)]) == 2
    assert "no commits" in capsys.readouterr().err
