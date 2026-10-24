# ReviewBudget: Project Brief (15-hour version)

**Track:** 2, Make the Invisible Visible
**Build window:** 15 hours, solo
**Core idea (unchanged):** a developer tool that learns from a Git repository's history to prioritise code changes that deserve human review when review time is limited.
**Key differentiator (unchanged):** it profiles the available history and **chooses its feature set, ranking strategy and, if justified, a model based on the quantity and quality of usable evidence, not on repository size.**

**Pitch:** *Two repos of the same size get two different strategies, because one has trustworthy evidence and the other doesn't. ReviewBudget tells you which changes to review in the time you have, and why it trusts its own ranking.*

---

## 1. Why Track 2

- **Invisible to visible, twice:**
  1. *Which changes are risky*, which a plain log or diff hides.
  2. *How much the repo's history can be trusted* to judge that, which no other tool tells you.
- **After detection:** a review plan that fits a time budget (`--budget 30m`), with reasons for each item and an explicit "not reviewed" list, exported as a Markdown checklist.

## 2. Starting point

We build from scratch in a new repo. The "current state" in the spec describes the **baseline to rebuild first** (commit inspection, basic features, heuristic scores, ranked queue). Every later step keeps that baseline working.

## 3. Pipeline

```
commits ──► features (as-of, no future data)
        └─► labels (reverts + SZZ, with confidence)
                    │
              evidence profile ──► strategy selector ──► ranker ──► budget plan + reasons
                                     │                     │
                                     └─ evaluation (chronological, effort-aware)
```

### 3.1 Features (computed only from history before each commit)
| Feature | Needs history? | Notes |
|---|---|---|
| files changed, insertions, deletions | No | Change size |
| test files changed (yes/no) | No | |
| directories touched | No | How spread out the change is |
| risky constructs in added lines (`except`, `raise`, `lock`, `auth`, `transaction`…) | No | A visible keyword list |
| prior churn of touched files (last 90 days) | Yes | |
| author familiarity (author's share of earlier commits to those files) | Yes | |
| prior bug-introducing count of touched files | Yes (labels) | Only used if labels are trustworthy |

Commit message text is **not** a ranking feature (a known limitation in your spec).

### 3.2 Labels: replacing "inferred from commit messages"
| Source | How | Confidence |
|---|---|---|
| **Reverts** | `This reverts commit <sha>` → `<sha>` is labelled buggy | High |
| **SZZ** | Fix commits (keyword match) → PyDriller `Git.get_commits_last_modified_lines` blames the lines the fix touched → earlier commits become candidates | Medium |
| Noise filters | Ignore fix commits touching more than 10 files, non-code files, whitespace or comment-only lines, and candidates more than 2 years older than the fix | — |

Labels are reported as **counts with confidence**, never presented as ground truth.

### 3.3 Evidence profile (what the selector looks at)
- Number of usable labels (high- and medium-confidence counted separately).
- Positive rate (the share of commits labelled buggy; too high suggests a noisy keyword match).
- History time span and commits per month.
- **Coverage:** the share of recent changed files with any prior history, and the share of authors with at least 3 earlier commits.
- Labels in the *training* window and the *test* window separately, so a chronological check is possible.

### 3.4 Strategy selector (transparent rules, printed to the user)
| Tier | When | Feature set | Ranker |
|---|---|---|---|
| **H0: Minimal heuristic** | Short or thin history (low coverage) | Change-only features | Weighted heuristic |
| **H1: History-aware heuristic** | Good coverage, but too few trustworthy labels | + churn, familiarity | Weighted heuristic |
| **L: Learned candidate** | Enough labels in *both* the train and test windows (minimum to be fixed in Step 0, e.g. ≥30 positives each), positive rate in a sane range | + prior-bug counts | Logistic regression **evaluated against H1**; adopted only if it wins on the newer commits by a set margin, otherwise it stays H1 **and says why** |

- **Feature-level selection:** a history feature is dropped if its coverage is too low. For example, author familiarity is dropped when most authors are new.
- **Size never decides:** commit count is not an input to the rules. The demo proves this with two similar-size repos.

### 3.5 Evaluation (chronological, effort-aware)
- **Split:** train or tune on the older 70% of commits, test on the newer 30%.
- **Metric:** recall at 20% effort, the share of labelled-buggy test commits caught when reviewing the top-ranked changes up to 20% of total changed lines. This is the standard effort-aware measure ([Kamei et al., TSE 2013](https://posl.ait.kyushu-u.ac.jp/~kamei/publications/Kamei_TSE2013.pdf)).
- **Comparators:** random order (averaged over several shuffles) and largest change first.
- **Results reported as they come out,** including when the heuristic loses to "largest change first".

### 3.6 Review budget (the action)
- **Effort per commit:** `minutes = 1 + changed_lines / 5` (about 300 lines an hour, from the [SmartBear/Cisco](https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/) 200–400 LOC guidance; configurable).
- **Allocation:**
  1. Always include the top-ranked change.
  2. Then add changes by highest risk per minute until the budget is spent.
  3. Everything else goes into "Not reviewed", with its main reason.
- **Explanations:**
  - Heuristic: the points from each feature.
  - Logistic regression: each feature's weight times its value.
  - Both show the top 3 reasons in plain words.

## 4. CLI (the product surface)

```
rb profile --repo .                 # evidence profile + chosen strategy and why
rb eval    --repo .                 # chronological evaluation vs comparators
rb queue   --repo . --range main..feature --budget 30m [--export plan.md]
```
A small Streamlit view is a **stretch goal** only. The terminal output (using the `rich` library) is the demo.

## 5. Demo (about 3 minutes)

1. **`rb profile` on repo A** (sparse or unreliable labels). It picks **H1** and explains why: "only 6 trustworthy labels".
2. **`rb profile` on repo B** (similar commit count, rich reverts and fix history). It picks **L**, then shows whether the learned ranker beat the heuristic on newer commits.
3. **`rb eval` on B:** recall at 20% effort for the chosen strategy, random, and largest-first.
4. **`rb queue --budget 30m`** on a recent range of B: a ranked plan with reasons, a "Not reviewed" list, and the exported checklist.
5. **Verify one item:** open a queued commit that was later reverted or fixed (shown as a retrospective check, clearly separate from the prediction).

Repos A and B are chosen in Step 0 from real open-source Python projects. Nothing is hard-coded.

## 6. Out of scope
GitHub App or PR comments, web dashboard, function-level ranking, languages other than Python for the risky-construct list (the core works on any language), deep models, a database or any services.

## 7. 15-hour plan (each step follows your working method)

| Hours | Step | Tested by |
|---|---|---|
| 0–1.5 | **Step 0: feasibility.** Time PyDriller SZZ on candidate repos, pick repos A and B, fix the thresholds | Timings and label counts recorded |
| 1.5–3.5 | **Step 1: baseline.** Commit extraction, change-only features, heuristic score with reasons, `rb queue` | pytest on tiny temp git repos |
| 3.5–5.5 | **Step 2: labels.** Reverts + SZZ with noise filters and confidence | Fixture repo with a known bug-introducing commit and a revert |
| 5.5–7.5 | **Step 3: evaluation.** Chronological split, recall at 20% effort, comparators | Hand-computed metric on a toy ranking; as-of check (no future data in features) |
| 7.5–9.5 | **Step 4: evidence profile + selector**, history features, feature-level selection | Two fixture repos with the same commit count but different label quality pick different tiers |
| 9.5–11 | **Step 5: learned ranker.** Logistic regression (scikit-learn), adopt-only-if-better gate, contribution-based reasons | Gate rejects when it loses; deterministic seed |
| 11–12 | **Step 6: budget plan.** Allocation, "Not reviewed" list, Markdown export | 5 / 30 / 60-minute budgets on a fixture |
| 12–13.5 | Run on repos A and B, README with limitations | Clean-clone run |
| 13.5–15 | Rehearse twice, buffer | — |

**Cut order if behind:**
1. The learned ranker. The selector still shows tier L was *eligible* but stays on the heuristic, and says so.
2. The Markdown export.
3. The history-aware features.

**Never cut:** the evidence profile and selector (the differentiator), the as-of rule, the reasons.

## 8. Risks

| Risk | Mitigation |
|---|---|
| SZZ is slow on large histories | Cap the window (e.g. the last 2,000 commits), cache blame results, pick medium repos |
| SZZ labels are noisy | Confidence tiers, noise filters, reverts weighted higher, labelled "noisy" in the output |
| No repo pair of similar size with different evidence quality | Use history windows of one repo, or say plainly the pair differs in size and show size isn't a rule input |
| The learned ranker never wins | Fine: the gate working honestly *is* the point |

## 9. Definition of success
A judge sees two similar-size repos get different strategies for stated evidence reasons, sees a chronological evaluation against simple baselines, and gets a budgeted, explained review queue.
