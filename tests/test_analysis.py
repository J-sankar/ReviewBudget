from gitfixture import commit, git, init

from reviewbudget import analysis
from reviewbudget.labels import LabelSet
from reviewbudget.pr import load_local_pr


def test_analyze_local_pr_ranks_commits_and_worktree_separately(tmp_path, monkeypatch):
    repo = init(tmp_path / "repo")
    base = commit(repo, "base", 1, {"pkg/app.py": "return 1\n"})
    git(repo, "switch", "-c", "feature")
    git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
    first = commit(repo, "add validation", 2, {"pkg/app.py": "raise ValueError\n"})
    second = commit(repo, "add logging", 3, {"pkg/log.py": "print('log')\n"})
    (repo / "pkg/app.py").write_text("raise RuntimeError\n")
    local_pr = load_local_pr(repo, "https://github.com/acme/widget/pull/42")
    head = git(repo, "rev-parse", "HEAD")
    monkeypatch.setattr(
        analysis,
        "load_labels",
        lambda repo: (LabelSet(head, 2, {}), False),
    )

    result = analysis.analyze_local_pr(local_pr, budget=15, strategy="h0")

    assert result.strategy == "H0"
    assert [item.commit.sha for item in result.ranked] == [first, second, "WORKTREE"]
    assert result.local_pr.base_sha == base
    assert result.plan.used > 0
