import pytest
from gitfixture import commit, git, init

from reviewbudget.pr import load_local_pr, parse_pull_request_url


def test_parse_pull_request_url():
    pull_request = parse_pull_request_url("https://github.com/acme/widget/pull/42")
    assert pull_request.owner == "acme"
    assert pull_request.repository == "widget"
    assert pull_request.number == 42


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/acme/widget/pull/42",
        "https://gitlab.com/acme/widget/pull/42",
        "https://github.com/acme/widget/issues/42",
    ],
)
def test_parse_pull_request_url_rejects_other_urls(url):
    with pytest.raises(ValueError, match="PR URL"):
        parse_pull_request_url(url)


def test_load_local_pr_uses_tracked_worktree_diff(tmp_path):
    repo = init(tmp_path / "repo")
    commit(repo, "base", 1, {"pkg/app.py": "return 1\n"})
    git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
    (repo / "pkg/app.py").write_text("raise ValueError\n")
    (repo / "untracked.py").write_text("raise RuntimeError\n")

    local_pr = load_local_pr(repo, "https://github.com/acme/widget/pull/42")

    assert local_pr.base_ref == "main"
    assert local_pr.branch == "main"
    assert [file.path for file in local_pr.change.files] == ["pkg/app.py"]
    assert local_pr.change.files[0].added_lines == ["raise ValueError"]


def test_load_local_pr_separates_commits_from_pending_worktree(tmp_path):
    repo = init(tmp_path / "repo")
    commit(repo, "base", 1, {"pkg/app.py": "return 1\n"})
    git(repo, "switch", "-c", "feature")
    git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
    first = commit(repo, "add validation", 2, {"pkg/app.py": "raise ValueError\n"})
    second = commit(repo, "add logging", 3, {"pkg/log.py": "print('log')\n"})
    (repo / "pkg/app.py").write_text("raise RuntimeError\n")

    local_pr = load_local_pr(repo, "https://github.com/acme/widget/pull/42")

    assert [change.sha for change in local_pr.commits] == [first, second]
    assert local_pr.working_tree.sha == "WORKTREE"
    assert [file.path for file in local_pr.working_tree.files] == ["pkg/app.py"]
    assert [file.path for file in local_pr.commits[0].files] == ["pkg/app.py"]
    assert [file.path for file in local_pr.commits[1].files] == ["pkg/log.py"]


def test_load_local_pr_rejects_a_different_remote(tmp_path):
    repo = init(tmp_path / "repo")
    commit(repo, "base", 1, {"pkg/app.py": "return 1\n"})
    git(repo, "remote", "add", "origin", "https://github.com/acme/other.git")

    with pytest.raises(RuntimeError, match="remotes do not match"):
        load_local_pr(repo, "https://github.com/acme/widget/pull/42")
