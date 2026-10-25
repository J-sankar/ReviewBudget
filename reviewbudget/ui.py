"""Local Streamlit dashboard for reviewing a pasted GitHub PR URL."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from reviewbudget.analysis import analyze_local_pr
from reviewbudget.budget import DEFAULT_SPEED, format_plan, parse_budget
from reviewbudget.pr import load_local_pr
from reviewbudget.selector import gather_evidence


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

    result = analyze_local_pr(local_pr, budget, int(speed))
    changes = [item.commit for item in result.ranked]
    ranked = result.ranked
    plan = result.plan
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
    worktree_present = any(item.commit.sha == "WORKTREE" for item in ranked)
    strategy_note = f"{result.strategy} for committed PR items"
    if worktree_present:
        strategy_note += "; H0 for the uncommitted WORKTREE item"
    st.write(
        f"Strategy: **{strategy_note}** · {len(result.dataset.train)} "
        f"training commits · {len(result.dataset.test)} test commits · "
        f"{result.labels.positive_rate:.0%} labelled"
    )

    evidence = gather_evidence(result.dataset)
    st.subheader("Evidence profile")
    evidence_columns = st.columns(5)
    evidence_columns[0].metric("Older labels", evidence.train_labels)
    evidence_columns[1].metric("Newer labels", evidence.test_labels)
    evidence_columns[2].metric("File coverage", f"{evidence.file_coverage:.0%}")
    evidence_columns[3].metric("Author coverage", f"{evidence.author_coverage:.0%}")
    evidence_columns[4].metric(
        "Model eligible", "Yes" if evidence.model_eligible else "No"
    )

    with st.expander("Why this strategy?"):
        for reason in result.choice.reasons:
            st.write(f"- {reason}")

    if not ranked:
        st.warning(
            "No committed PR changes or tracked working-tree changes were found."
        )
        return

    st.subheader("Review budget")
    budget_columns = st.columns(4)
    budget_columns[0].metric("Within budget", len(plan.included))
    budget_columns[1].metric("Skipped", len(plan.skipped))
    budget_columns[2].metric("Minutes used", f"{plan.used}/{plan.budget}")
    budget_columns[3].metric("Minutes remaining", max(0, plan.budget - plan.used))
    st.code(
        format_plan(
            plan,
            "Local PR review",
            f"{strategy_note} scores review priority from local repository evidence.",
            [
                "Strategy selection:",
                *(f"  - {reason}" for reason in result.choice.reasons),
            ],
        )
    )

    if plan.included:
        st.caption("Items included in the review plan")
        st.dataframe(
            [
                {
                    "rank": entry.rank,
                    "commit": entry.item.commit.sha[:8],
                    "minutes": entry.minutes,
                    "subject": entry.item.commit.subject,
                }
                for entry in plan.included
            ],
            use_container_width=True,
            hide_index=True,
        )
    if plan.skipped:
        st.caption("Items skipped from the review plan")
        st.dataframe(
            [
                {
                    "rank": entry.rank,
                    "commit": entry.item.commit.sha[:8],
                    "minutes": entry.minutes,
                    "subject": entry.item.commit.subject,
                    "reason": entry.reason,
                }
                for entry in plan.skipped
            ],
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Top H0 risk signals"):
        st.dataframe(
            [
                {
                    "commit": risky.scored.commit.sha[:8],
                    "risk": risky.scored.score,
                    "subject": risky.scored.commit.subject,
                    "status": risky.status,
                    "reasons": "; ".join(
                        reason.text for reason in risky.scored.reasons[:3]
                    ),
                }
                for risky in plan.riskiest
            ],
            use_container_width=True,
            hide_index=True,
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

    with st.expander("Detailed reasons"):
        for item in ranked:
            label = f"{item.commit.sha[:8]} · {item.commit.subject}"
            st.markdown(f"**{label}**")
            for reason in item.reasons:
                st.write(f"- {reason.text} ({reason.points:g} points)")

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
