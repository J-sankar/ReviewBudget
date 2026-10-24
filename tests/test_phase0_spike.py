import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spikes"))
import phase0_feasibility as spike

BASE_TS = 1_700_000_000


def _commit(repo: Path, msg: str, day: int, files: dict[str, str]) -> str:
    for name, content in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        subprocess.run(["git", "-C", str(repo), "add", name], check=True)
    date = f"@{BASE_TS + day * 86400} +0000"
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", msg], check=True, env=env)
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _fixture(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    shas = {}
    shas["base"] = _commit(
        repo,
        "Add calculator",
        0,
        {
            "calc.py": "def add(a, b):\n    return a + b\n\n\ndef div(a, b):\n    return a / b\n"
        },
    )
    shas["bug"] = _commit(
        repo,
        "Speed up div",
        1,
        {
            "calc.py": "def add(a, b):\n    return a + b\n\n\ndef div(a, b):\n    return a // b\n"
        },
    )
    shas["docs"] = _commit(repo, "Add readme", 2, {"README.md": "calc\n"})
    shas["fix"] = _commit(
        repo,
        "Fix integer division bug in div",
        3,
        {
            "calc.py": "def add(a, b):\n    return a + b\n\n\ndef div(a, b):\n    return a / b\n"
        },
    )
    shas["feature"] = _commit(
        repo, "Add mul", 4, {"mul.py": "def mul(a, b):\n    return a * b\n"}
    )
    (repo / "mul.py").unlink()
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "mul.py"], check=True)
    shas["revert"] = _commit(
        repo, f'Revert "Add mul"\n\nThis reverts commit {shas["feature"]}.', 5, {}
    )
    shas["typo"] = _commit(repo, "Fix typo in readme", 6, {"README.md": "calculator\n"})
    return repo, shas


def test_labels_known_revert_and_bug(tmp_path):
    repo, shas = _fixture(tmp_path)
    labels = spike.analyse(repo, years=3)["labels"]
    assert set(labels) == {shas["bug"], shas["feature"]}
    assert labels[shas["feature"]]["confidence"] == "high"
    assert labels[shas["feature"]]["reverted_by"] == [shas["revert"]]
    assert labels[shas["bug"]]["confidence"] == "medium"
    assert labels[shas["bug"]]["fixed_by"] == [shas["fix"]]


def test_doc_fix_is_not_a_bug_fix(tmp_path):
    repo, _ = _fixture(tmp_path)
    summary = spike.analyse(repo, years=3)["summary"]
    assert summary["fix_commits"] == 1


def test_deterministic(tmp_path):
    repo, _ = _fixture(tmp_path)
    a, b = spike.analyse(repo, years=3), spike.analyse(repo, years=3)
    for r in (a, b):
        r["summary"].pop("seconds")
    assert a == b


def test_is_code_file():
    assert spike.is_code_file("src/flask/app.py")
    assert not spike.is_code_file("tests/test_app.py")
    assert not spike.is_code_file("src/pkg/test_x.py")
    assert not spike.is_code_file("docs/conf.py")
    assert not spike.is_code_file("README.md")
    assert not spike.is_code_file("setup.py")
    assert not spike.is_code_file("tests.py")
    assert not spike.is_code_file("docs_src/app/tutorial001.py")


def test_fix_keyword_in_squash_body_is_ignored():
    c = spike.Commit(
        "a" * 40,
        "t@example.com",
        0,
        "Add forward references (#93)",
        "* Add forward references\n\n* Fix coverage in completion\n",
        [],
    )
    assert not spike.is_bug_fix(c)
    assert spike.is_bug_fix(
        spike.Commit("b" * 40, "t@example.com", 0, "Fix zsh completion install", "", [])
    )
