"""Review time budget: what fits in the reviewer's time, and why the rest is skipped.

Commits are taken in ranked order until the next one no longer fits: the same rule
`rb evaluate` uses for "bugs found in 20% effort", so those numbers describe this list.
Minutes come from changed code lines at a review speed; the default of 300 lines an
hour sits in the commonly cited 200-400 lines/hour guideline for careful code review.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from reviewbudget import h0
from reviewbudget.git_changes import CommitChange
from reviewbudget.h0 import code_lines

DEFAULT_SPEED = 300  # lines of code reviewed per hour
RISKIEST = 5
SHOWN_REASONS = 3
SUBJECT_WIDTH = 40
_BUDGET = re.compile(r"(?:(\d+)h)?(?:(\d+)m)?")


def parse_budget(text: str) -> int:
    """Minutes from a budget such as 15m, 90m, 1h or 1h30m."""
    match = _BUDGET.fullmatch(text.strip().lower())
    if not match or not any(match.groups()):
        raise ValueError(f"budget must look like 15m, 1h or 1h30m, not {text!r}")
    minutes = int(match[1] or 0) * 60 + int(match[2] or 0)
    if minutes <= 0:
        raise ValueError("budget must be more than 0 minutes")
    return minutes


def minutes_for(commit: CommitChange, speed: int) -> int:
    """Minutes to review a commit's code lines; every commit takes at least one."""
    return max(1, math.ceil(code_lines(commit) * 60 / speed))


def _low_value(scored: h0.ScoredCommit) -> str | None:
    return next((r.text for r in scored.reasons if r.key == "low_value"), None)


@dataclass
class Entry:
    item: object  # a ranked score with .commit, .score and .reasons
    rank: int
    minutes: int
    reason: str = ""  # why it was skipped


@dataclass
class Risky:
    scored: h0.ScoredCommit
    minutes: int
    status: str


@dataclass
class Plan:
    budget: int
    speed: int
    included: list[Entry]
    skipped: list[Entry]
    riskiest: list[Risky]

    @property
    def used(self) -> int:
        return sum(e.minutes for e in self.included)


def make_plan(ranked: list, budget: int, speed: int = DEFAULT_SPEED) -> Plan:
    """Fill the budget in ranked order, stopping at the first commit that does not fit."""
    included, skipped = [], []
    used, stop = 0, None
    for rank, item in enumerate(ranked, 1):
        minutes = minutes_for(item.commit, speed)
        if stop is None and used + minutes <= budget:
            included.append(Entry(item, rank, minutes))
            used += minutes
            continue
        if stop is None:
            stop = rank
            reason = f"needs {minutes} min, only {budget - used} min left: the plan stops here"
        else:
            reason = (
                _low_value(h0.score_commit(item.commit))
                or f"ranked #{rank}; the plan stopped at #{stop}"
            )
        skipped.append(Entry(item, rank, minutes, reason))
    riskiest = _riskiest(ranked, included, budget, speed)
    return Plan(budget, speed, included, skipped, riskiest)


def _riskiest(
    ranked: list, included: list[Entry], budget: int, speed: int
) -> list[Risky]:
    """H0's riskiest code changes, and whether each made it into the plan."""
    planned = {e.item.commit.sha: e.rank for e in included}
    ranks = {item.commit.sha: rank for rank, item in enumerate(ranked, 1)}
    scored = [h0.score_commit(item.commit) for item in ranked]
    risky = [s for s in h0.rank(scored) if not _low_value(s)][:RISKIEST]
    result = []
    for s in risky:
        minutes = minutes_for(s.commit, speed)
        sha = s.commit.sha
        if sha in planned:
            status = f"in your plan (#{planned[sha]})"
        elif minutes > budget:
            status = (
                f"needs {minutes} min, more than the whole budget: "
                "schedule a separate review"
            )
        else:
            status = f"not in your plan: ranked #{ranks[sha]}, needs {minutes} min"
        result.append(Risky(s, minutes, status))
    return result


def _shorten(text: str, width: int = SUBJECT_WIDTH) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _why(item) -> str:
    return "; ".join(r.text for r in item.reasons[:SHOWN_REASONS])


def _summary(plan: Plan) -> str:
    total = len(plan.included) + len(plan.skipped)
    return (
        f"Budget {plan.budget} min at {plan.speed} lines of code an hour: "
        f"{len(plan.included)} of {total} commits fit, {plan.used} min used."
    )


def format_plan(plan: Plan, title: str, note: str, details: list[str]) -> str:
    w = SUBJECT_WIDTH
    lines = [title, *details, note, _summary(plan), ""]
    lines.append(f"Within your {plan.budget} minutes:")
    if not plan.included:
        lines.append("  nothing fits: the first commit alone needs more time")
    else:
        lines.append(
            f"  {'#':>3}  {'commit':8}  {'min':>4}  {'size':>11}  {'subject':{w}}  why"
        )
        for e in plan.included:
            c = e.item.commit
            size = f"+{c.added}/-{c.deleted}"
            lines.append(
                f"  {e.rank:>3}  {c.sha[:8]}  {e.minutes:>4}  {size:>11}  "
                f"{_shorten(c.subject):{w}}  {_why(e.item)}"
            )
    if plan.skipped:
        lines += ["", f"Skipped ({len(plan.skipped)}):"]
        for e in plan.skipped:
            c = e.item.commit
            lines.append(
                f"  {e.rank:>3}  {c.sha[:8]}  {_shorten(c.subject):{w}}  {e.reason}"
            )
    if plan.riskiest:
        lines += [
            "",
            (
                f"Riskiest changes by H0's risk signals (top {RISKIEST}), "
                "whether or not they fit:"
            ),
        ]
        for r in plan.riskiest:
            c = r.scored.commit
            lines.append(
                f"  {c.sha[:8]}  {r.scored.score:>5.1f}  {_shorten(c.subject):{w}}  "
                f"{_why(r.scored)}  -> {r.status}"
            )
    return "\n".join(lines)


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def plan_markdown(plan: Plan, title: str, note: str, details: list[str]) -> str:
    md = ["# Review plan", "", f"**{title}**", ""]
    for line in details:
        stripped = line.strip()
        md.append(stripped if stripped.startswith("- ") else f"{stripped}")
    md += [
        "",
        note,
        "",
        _summary(plan),
        "",
        f"## Within your {plan.budget} minutes",
        "",
    ]
    if not plan.included:
        md.append("Nothing fits: the first commit alone needs more time.")
    else:
        md += [
            "| # | commit | min | subject | why |",
            "| --- | --- | --- | --- | --- |",
        ]
        for e in plan.included:
            c = e.item.commit
            md.append(
                f"| {e.rank} | `{c.sha[:8]}` | {e.minutes} | {_cell(c.subject)} "
                f"| {_cell(_why(e.item))} |"
            )
    if plan.skipped:
        md += [
            "",
            f"## Skipped ({len(plan.skipped)})",
            "",
            "| # | commit | subject | why skipped |",
            "| --- | --- | --- | --- |",
        ]
        for e in plan.skipped:
            c = e.item.commit
            md.append(
                f"| {e.rank} | `{c.sha[:8]}` | {_cell(c.subject)} | {_cell(e.reason)} |"
            )
    if plan.riskiest:
        md += [
            "",
            f"## Riskiest changes (H0 risk signals, top {RISKIEST})",
            "",
            "| commit | risk | subject | why risky | status |",
            "| --- | --- | --- | --- | --- |",
        ]
        for r in plan.riskiest:
            c = r.scored.commit
            md.append(
                f"| `{c.sha[:8]}` | {r.scored.score:.1f} | {_cell(c.subject)} "
                f"| {_cell(_why(r.scored))} | {_cell(r.status)} |"
            )
    return "\n".join(md) + "\n"
