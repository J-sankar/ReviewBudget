"""L: a small learned model, ranked by bug likelihood per line to review.

A logistic regression on H0's signals and the history counts, so each signal gets one
readable weight. It learns from one repository's own bug labels and ranks by
likelihood per 100 changed code lines, the same budget logic as H1. Settings are fixed
in advance; nothing is tuned on evaluation results.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from reviewbudget import h0
from reviewbudget.git_changes import CommitChange
from reviewbudget.h0 import Reason, ScoredCommit, code_lines, file_kind
from reviewbudget.history import History

if TYPE_CHECKING:
    from reviewbudget.dataset import Row

NAME = "L (learned, per line)"
LINES_PER_UNIT = 100
MIN_EFFECT = 0.05
FEATURES = {
    "code_lines": "lines of code changed",
    "code_files": "code files changed",
    "folders": "folders touched",
    "error_handling": "error handling changed",
    "security": "security-sensitive code changed",
    "concurrency": "concurrency code changed",
    "no_test_change": "no test changed",
    "file_changes": "earlier changes to the files",
    "file_bugs": "earlier bug-linked commits in the files",
    "author_commits": "author's earlier commits",
    "author_new_to_files": "author new to these files",
}
FLAGS = {
    "error_handling",
    "security",
    "concurrency",
    "no_test_change",
    "author_new_to_files",
}
LOGGED = {"code_lines", "file_changes", "author_commits"}  # long-tailed counts


def commit_features(
    commit: CommitChange, history: History, h0_scored: ScoredCommit
) -> dict[str, float]:
    """The model's inputs for one commit, as raw values (logs are taken when fitting)."""
    signals = {r.key for r in h0_scored.reasons}
    changed = [
        f
        for f in commit.files
        if file_kind(f.path) == "code" and not f.binary and not f.is_pure_rename
    ]
    return {
        "code_lines": float(code_lines(commit)),
        "code_files": float(len(changed)),
        "folders": float(len({str(PurePosixPath(f.path).parent) for f in changed})),
        "error_handling": float("error_handling" in signals),
        "security": float("security" in signals),
        "concurrency": float("concurrency" in signals),
        "no_test_change": float("no_test_change" in signals),
        "file_changes": float(history.file_changes),
        "file_bugs": float(history.file_bugs),
        "author_commits": float(history.author_commits),
        "author_new_to_files": float(not history.author_knows_files),
    }


def _vector(features: dict[str, float]) -> list[float]:
    return [
        math.log2(1 + features[n]) if n in LOGGED else features[n] for n in FEATURES
    ]


def _describe(name: str, value: float, above_average: bool) -> str:
    if name in FLAGS:
        return FEATURES[name]
    side = "above" if above_average else "below"
    return f"{FEATURES[name]}: {value:g}, {side} average"


@dataclass
class Model:
    pipeline: Pipeline
    labels: int  # buggy rows it learned from
    rows: int

    def probabilities(self, features: list[dict[str, float]]) -> list[float]:
        matrix = [_vector(f) for f in features]
        return [float(p) for p in self.pipeline.predict_proba(matrix)[:, 1]]

    def weights(self) -> list[tuple[str, float]]:
        """Weight per signal on the scaled inputs, largest effect first."""
        coefs = self.pipeline[-1].coef_[0]
        pairs = [(name, round(float(c), 2)) for name, c in zip(FEATURES, coefs)]
        return sorted(pairs, key=lambda p: (-abs(p[1]), p[0]))

    def explain(self, features: dict[str, float]) -> list[Reason]:
        """The signals that raised this commit's likelihood most, with their effect.

        An absent flag (say, no security code) is never given as a reason.
        """
        scaler, coefs = self.pipeline[0], self.pipeline[-1].coef_[0]
        effects = []
        for name, x, mean, scale, c in zip(
            FEATURES, _vector(features), scaler.mean_, scaler.scale_, coefs
        ):
            effect = float(c * (x - mean) / scale)
            if effect > MIN_EFFECT and (name not in FLAGS or features[name]):
                text = _describe(name, features[name], x > mean)
                effects.append(Reason(round(effect, 2), f"{text} (+{effect:.1f})"))
        effects.sort(key=lambda r: -r.points)
        return effects or [Reason(0.0, "no signal raised the likelihood")]


def train(rows: list[Row]) -> Model | None:
    """Fit on the rows' features and `buggy` flags; None without both classes."""
    targets = [r.buggy for r in rows]
    if len(set(targets)) < 2:
        return None
    pipeline = make_pipeline(
        StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)
    )
    pipeline.fit([_vector(r.features) for r in rows], targets)
    return Model(pipeline, sum(targets), len(rows))


def per_line(probability: float, lines: int) -> float:
    return probability * LINES_PER_UNIT / max(1, lines)


def order(model: Model, rows: list[Row]) -> list[Row]:
    """Rows ranked by likelihood per line; ties go to higher likelihood, then newer."""
    probs = model.probabilities([r.features for r in rows])
    ranked = sorted(
        zip(rows, probs),
        key=lambda rp: (
            -per_line(rp[1], rp[0].code_lines),
            -rp[1],
            -rp[0].timestamp,
            rp[0].sha,
        ),
    )
    return [r for r, _ in ranked]


@dataclass
class LScore:
    commit: CommitChange
    probability: float
    lines: int
    has_code: bool
    reasons: list[Reason]

    @property
    def score(self) -> float:
        """Bug likelihood (%) per 100 changed code lines; 0 without program code."""
        if not self.has_code:
            return 0.0
        return round(100 * per_line(self.probability, self.lines), 1)


def score_commits(
    model: Model, commits: list[CommitChange], history: dict[str, History]
) -> list[LScore]:
    scored = [h0.score_commit(c) for c in commits]
    features = [commit_features(c, history[c.sha], s) for c, s in zip(commits, scored)]
    result = []
    for c, s, f, p in zip(commits, scored, features, model.probabilities(features)):
        has_code = any(file_kind(x.path) == "code" for x in c.files)
        reasons = model.explain(f) if has_code else s.reasons
        result.append(LScore(c, p, code_lines(c), has_code, reasons))
    return result


def rank(scored: list[LScore]) -> list[LScore]:
    """Code commits by likelihood per line, then commits without program code."""
    return sorted(
        scored,
        key=lambda s: (
            not s.has_code,
            -s.score,
            -s.probability,
            -s.commit.timestamp,
            s.commit.sha,
        ),
    )
