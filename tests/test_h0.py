import os
import subprocess
from pathlib import Path

import pytest

from reviewbudget.cli import main
from reviewbudget.git_changes import CommitChange, FileChange, load_commits
from reviewbudget.h0 import file_kind, rank, score_commit

BASE_TS = 1_700_000_000
BILLING_V1 = (
    "def charge(amount):\n"
    "    try:\n"
    "        return int(amount)\n"
    "    except ValueError:\n"
    "        return None\n"
)
BILLING_V2 = (
    "def charge(amount):\n"
    "    try:\n"
    "        return int(amount)\n"
    "    except (ValueError, TypeError):\n"
    "        return 0\n"
)
BIG = "".join(f"value_{i} = {i}\n" for i in range(300))


def _git(repo: Path, *args: str, day: int = 0) -> str:
    date = f"{BASE_TS + day * 86400} +0000"
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def _commit(
    repo: Path, message: str, day: int, files: dict[str, str] | None = None
) -> str:
    for name, content in (files or {}).items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message, day=day)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    """Initial commit, then: risky 3-line except change, 300-line pure rename
    (with a misleading "Fix" message), docs-only edit, whitespace-only reformat."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    shas = {
        "initial": _commit(
            r,
            "initial",
            0,
            {
                "pkg/billing.py": BILLING_V1,
                "pkg/big.py": BIG,
                "tests/test_billing.py": "def test_charge():\n    assert True\n",
                "README.md": "# Demo\n",
            },
        )
    }
    shas["risky"] = _commit(r, "tidy billing", 1, {"pkg/billing.py": BILLING_V2})
    _git(r, "mv", "pkg/big.py", "pkg/large.py")
    shas["rename"] = _commit(r, "Fix: rename big module", 2)
    shas["docs"] = _commit(r, "docs", 3, {"README.md": "# Demo\n\nUsage notes.\n"})
    shas["whitespace"] = _commit(
        r, "format", 4, {"pkg/large.py": BIG.replace(" = ", "  =  ")}
    )
    return r, shas


def _ranked(r: Path, shas: dict[str, str]):
    return rank(
        [score_commit(c) for c in load_commits(r, [f"{shas['initial']}..HEAD"])]
    )


def test_reads_range_oldest_first(repo):
    r, shas = repo
    commits = load_commits(r, [f"{shas['initial']}..HEAD"])
    assert [c.sha for c in commits] == [
        shas[k] for k in ("risky", "rename", "docs", "whitespace")
    ]
    rename = commits[1].files[0]
    assert (rename.old_path, rename.path, rename.is_pure_rename) == (
        "pkg/big.py",
        "pkg/large.py",
        True,
    )


def test_risky_small_change_outranks_big_rename(repo):
    r, shas = repo
    ranked = _ranked(r, shas)
    by_sha = {s.commit.sha: s for s in ranked}
    assert ranked[0].commit.sha == shas["risky"]
    assert by_sha[shas["rename"]].score <= 0.1
    assert any("error handling" in reason.text for reason in ranked[0].reasons)


def test_docs_only_ranks_last(repo):
    r, shas = repo
    ranked = _ranked(r, shas)
    assert ranked[-1].commit.sha == shas["docs"]
    assert ranked[-1].score == 0.0


def test_whitespace_only_change_scores_near_zero(repo):
    r, shas = repo
    scored = {s.commit.sha: s for s in _ranked(r, shas)}[shas["whitespace"]]
    assert scored.commit.added == 300
    assert scored.score <= 0.1
    assert scored.reasons[0].text == "whitespace-only code change"


def test_mode_only_paths_do_not_hide_config_changes():
    mode_only = FileChange(path="pkg/module.py")
    config = FileChange(
        path="nginx/nginx.conf",
        added_lines=["add_header Access-Control-Allow-Origin * always;"],
    )
    scored = score_commit(
        CommitChange("c" * 40, "t@example.com", 0, "cors", [mode_only, config])
    )
    assert scored.reasons[0].text == "non-code files only (config, build, data)"
    assert all(reason.text != "whitespace-only code change" for reason in scored.reasons)


def test_same_change_scores_lower_with_a_test_change():
    code = FileChange(path="pkg/mod.py", added_lines=["x = compute()", "y = x + 1"])
    test = FileChange(path="tests/test_mod.py", added_lines=["assert y == 2"])
    without = score_commit(CommitChange("a" * 40, "t@example.com", 0, "x", [code]))
    with_test = score_commit(
        CommitChange("b" * 40, "t@example.com", 0, "x", [code, test])
    )
    assert with_test.score < without.score
    assert "tests updated" in [r.text for r in with_test.reasons]


def test_every_commit_has_reasons_and_ranking_is_stable(repo):
    r, shas = repo
    first, second = _ranked(r, shas), _ranked(r, shas)
    assert all(s.reasons for s in first)
    assert [(s.commit.sha, s.score) for s in first] == [
        (s.commit.sha, s.score) for s in second
    ]


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("pkg/billing.py", "code"),
        ("tests/test_billing.py", "test"),
        ("pkg/test_util.py", "test"),
        ("web/app.spec.ts", "test"),
        ("docs_src/tutorial001.py", "docs"),
        ("README.md", "docs"),
        ("pyproject.toml", "other"),
        ("setup.py", "other"),
    ],
)
def test_file_kind(path, kind):
    assert file_kind(path) == kind


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ("token = load_token()", True),
        ("user = authenticate(request)", True),
        ("author_email = 'a@example.com'", False),
        ("authors = []", False),
    ],
)
def test_security_signal_ignores_author_words(line, flagged):
    change = FileChange(path="pkg/mod.py", added_lines=[line])
    scored = score_commit(CommitChange("c" * 40, "t@example.com", 0, "x", [change]))
    assert any("security" in r.text for r in scored.reasons) == flagged


def test_cli_range_puts_risky_commit_first(repo, capsys):
    r, shas = repo
    assert main(["queue", "--repo", str(r), "--range", f"{shas['initial']}..HEAD"]) == 0
    out = capsys.readouterr().out
    assert "Strategy H0" in out and "4 commits" in out
    first_row = next(
        line for line in out.splitlines() if line.lstrip().startswith("1 ")
    )
    assert shas["risky"][:8] in first_row


def test_cli_last_n_selects_newest_commits(repo, capsys):
    r, shas = repo
    assert main(["queue", "--repo", str(r), "--last", "3"]) == 0
    out = capsys.readouterr().out
    assert "3 commits" in out
    for key in ("rename", "docs", "whitespace"):
        assert shas[key][:8] in out
    assert shas["risky"][:8] not in out


def test_cli_reports_a_non_repository(tmp_path, capsys):
    assert main(["queue", "--repo", str(tmp_path), "--last", "1"]) == 2
    assert "not a git repository" in capsys.readouterr().err


def test_cli_rejects_a_range_without_dots(repo):
    r, _ = repo
    with pytest.raises(SystemExit):
        main(["queue", "--repo", str(r), "--range", "HEAD~2"])
