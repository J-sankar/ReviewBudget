"""Local Streamlit dashboard for reviewing a pasted GitHub PR URL."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from reviewbudget import h0
from reviewbudget.budget import DEFAULT_SPEED, format_plan, make_plan, parse_budget
from reviewbudget.pr import has_tracked_changes, load_local_pr


def main() -> None:
    st.set_page_config(page_title="ReviewBudget", layout="wide")
    st.title("ReviewBudget")
    st.caption(
        "Analyze a local checkout of a GitHub pull request without cloning or fetching."
    )

    with st.sidebar:
        st.header("Pull request")
        pr_url = st.text_input(
            "GitHub PR URL", placeholder="https://github.com/org/repo/pull/42"
        )
        repo_text = st.text_input("Local repository", value=str(Path.home()))
        base_ref = st.text_input("Local base ref", value="main")
        budget_text = st.text_input("Review budget", value="15m")
        speed = st.number_input(
            "Review speed (code lines/hour)", min_value=1, value=DEFAULT_SPEED, step=50
        )
        analyze = st.button("Analyze local changes", type="primary")

    if not analyze:
        st.info("Paste a PR URL and select the local checkout to begin.")
        return
    if not pr_url:
        st.error("Enter a GitHub PR URL.")
        return

    try:
        local_pr = load_local_pr(
            Path(repo_text).expanduser().resolve(), pr_url, base_ref
        )
        budget = parse_budget(budget_text)
    except (ValueError, OSError, RuntimeError) as exc:
        st.error(str(exc))
        return

    changes = list(local_pr.commits)
    if has_tracked_changes(local_pr.working_tree):
        changes.append(local_pr.working_tree)
    ranked = h0.rank([h0.score_commit(change) for change in changes])
    plan = make_plan(ranked, budget, int(speed))
    st.success(f"Analyzed PR #{local_pr.pull_request.number} from the local checkout.")

    columns = st.columns(4)
    columns[0].metric("Branch", local_pr.branch)
    columns[1].metric("PR commits", len(local_pr.commits))
    columns[2].metric("Review items", len(ranked))
    columns[3].metric(
        "Code lines", sum(item.commit.added + item.commit.deleted for item in ranked)
    )
    st.write(f"Base: `{local_pr.base_ref}` at `{local_pr.base_sha[:8]}`")
    st.write(f"Remote: `{local_pr.remote}`")

    if not ranked:
        st.warning(
            "No committed PR changes or tracked working-tree changes were found."
        )
        return

    st.subheader("Review budget")
    st.code(
        format_plan(
            plan, "Local PR review", "H0 scores review priority from the diff only.", []
        )
    )

    st.subheader("Review items")
    st.dataframe(
        [
            {
                "commit": item.commit.sha[:8],
                "subject": item.commit.subject,
                "score": item.score,
                "added": item.commit.added,
                "deleted": item.commit.deleted,
                "reasons": "; ".join(reason.text for reason in item.reasons[:3]),
            }
            for item in ranked
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Changed files by review item")
    st.dataframe(
        [
            {
                "commit": change.sha[:8],
                "file": file.path,
                "old file": file.old_path or "",
                "added": file.added,
                "deleted": file.deleted,
                "binary": file.binary,
            }
            for change in changes
            for file in change.files
        ],
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
