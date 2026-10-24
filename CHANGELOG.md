# Change log

Record each meaningful project change during the event, newest first. Update this file in the same commit as the change. Use a real timestamp with timezone, for example `YYYY-MM-DDTHH:MM:SS+05:30`.

## Event build log

Entry format:

```text
## <actual timestamp> — <short change title>

- Changed: <feature or files changed>
- Why: <reason for the change>
- Validation: <commands or manual checks actually run, with results>
- Limitations: <known issues or "None identified in these checks">
```

## 2026-10-24T23:39:29+05:30 — Phase 5: learned strategy L

- Changed: Added `reviewbudget/model.py`: L is a logistic regression (scikit-learn, balanced class weights, fixed settings) on H0's signals and the history counts, ranked by bug likelihood per 100 changed code lines; explanations list the signals that raised a commit's likelihood (absent flags are never reasons), and the learned weights can be printed. `reviewbudget/selector.py`: L competes only when the phase 0 model rule holds; then the older commits are split again by time, L learns from the first 70% with bugs found after that cut hidden, and H0, S, H1 and L are compared on the rest (ties go to the simpler strategy). `rb evaluate` adds an L row and L's weights (L is left out of the older-commit table it learned from); `rb queue --strategy` gains `l`, which learns from every label known now. H0 reasons now carry signal keys (scores unchanged). Dataset rows and the CSV gain `feature_*` columns, and `data/*.csv` are regenerated from the same source commits. Added `scikit-learn` to `pyproject.toml`/`uv.lock`, `tests/test_model.py`; updated `README.md`.
- Why: Phase 5 of the plan: try a learned model only where the evidence supports it, and keep it only if it beats the rule-based strategies on commits it did not learn from.
- Validation: `uv run pytest -q` (88 passed; new tests: learns the predictive signal, needs both classes, repeatable training, explanations, features from a diff, inner split hides late evidence, L must beat every rule-based strategy, L ignored without model eligibility, `--strategy l` without labels); `uv run ruff check .` and `uv run ruff format --check .` clean. Real runs (8-11 s): typer H0 and httpx S, as before (not model-eligible); httpie selects H1: on the newest 30% of the older commits H0 0% / S 36% / H1 43% / L 43%, on the newer commits 4% / 50% / 50% / 42%.
- Limitations: L does not beat S or H1 on httpie and its top-10 precision is 0%. It learns a negative weight for earlier bugs in the files and a positive one for size, which is hard to interpret; it is trained on one repository's few, noisy labels. The selection slice is small, so one bug can change the choice. `rb queue --strategy l` learns from all labels known now, including those of older commits in the requested range.

## 2026-10-24T23:19:39+05:30 — Phase 4.1: smallest-first strategy; selector chooses on older commits

- Changed: Added `reviewbudget/smallest.py`: strategy S ranks commits that change program code by changed code lines, fewest first, with commits without code last; H0's risk reasons are shown for context only. `reviewbudget/selector.py` now picks among H0, S and H1 (when the phase 0 evidence rules allow more than H0) by bugs found within 20% effort on the older (training) commits, with ties going to the simpler strategy (H0, then S, then H1); the newer commits are only reported as a check. `rb queue --strategy` gains `s`. Updated `tests/test_h1.py` and `README.md`.
- Why: Phase 4 showed H1 only matching plain smallest-first ordering, and the selector chose using the same newer commits it reported. H1 now has to beat both simpler strategies, on data that is not used to report results.
- Validation: `uv run pytest -q` (78 passed; new tests: H1 must beat both simpler strategies, ties go to the simpler one, only the older commits decide, no older labels falls back to H0, S ordering and reasons, `rb queue --strategy s`); `uv run ruff check .` and `uv run ruff format --check .` clean. Real runs: typer selects H0 (2 newer labels); httpx selects S (older commits H0 10% / S 38% / H1 32%, newer 6% / 44% / 44%); httpie selects S (older 6% / 46% / 42%, newer 4% / 50% / 50%; learning model eligible).
- Limitations: No demo repository selects H1. S and H1 rarely put buggy commits in their top 10 (0-10%); the effort measure favours small commits by design. A strategy picked on the older commits may not stay best on newer ones.

## 2026-10-24T23:01:56+05:30 — Phase 4: H1 history-aware ranker and strategy selector

- Changed: Added `reviewbudget/history.py` (per-commit history from earlier commits only: changes to the commit's code files, earlier bug-labelled commits on those files counted only once their evidence had appeared, author's earlier commits, whether the author touched the files before; renames keep history), `reviewbudget/h1.py` (H0's signals without size points plus history points, ranked by risk per 100 changed code lines, reasons for every point) and `reviewbudget/selector.py` (phase 0 evidence rules on train/test labels, positive rate and file/author history coverage, no commit count; H1 kept only if it beats H0 on the newer commits; learning model eligibility reported). `rb queue` gains `--strategy auto|h0|h1` (default `auto`) and `--no-cache`; `rb evaluate` adds H1, a table for the older commits and the selector's reasons. The dataset and CSV gain `h1_risk`, `h1_score`, `h1_reasons`, `file_changes_before`, `file_bugs_before` and `author_commits_before`; `data/*.csv` regenerated from the same source commits. `h0.Reason` gains a `key` marking size points (H0 scores unchanged) and `code_lines` moved to `h0.py`. Added `tests/test_h1.py` and `tests/conftest.py` (keeps test label caches out of the user's cache). Updated `README.md`.
- Why: The selector is the project's core idea: choose a strategy from evidence quality and explain it. H1 addresses H0's effort-aware weakness found in phase 3.
- Validation: `uv run pytest -q` (74 passed; 22 new tests: no-peek history, renames, ranking by risk per line, reasons, selector tiers and exact thresholds, fallback to H0, CLI); `uv run ruff check .` and `uv run ruff format --check .` clean. Real runs (6-8 s each): typer selects H0 (2 newer labels); httpx selects H1 (bugs found in 20% effort H1 44% vs H0 6%; coverage files 0.97, authors 0.60); httpie is learning-model eligible and selects H1 (50% vs 4%). A real-repo `rb queue` run showed config-only commits jumping the H1 queue (0 code lines counted as 1); fixed by using all changed lines as the effort for commits without program code, with a test.
- Limitations: H1 matches plain smallest-first ordering on the newer commits (httpx 44% vs 44%, httpie 50% vs 50%) and is slightly worse on the older commits, and its top-10 precision is low (0-10%), so the history signals add little so far. Dividing by size was decided after seeing phase 3's H0 results; H1's weights were set once and not tuned. The selector's H1-vs-H0 check uses the same newer commits that are reported. Version bumps and formatting changes in bug-prone files can rank high. With a range on another branch, labels still come from HEAD.

## 2026-10-24T22:39:24+05:30 — Phase 3: dataset, time split and evaluation

- Changed: Added `reviewbudget/dataset.py` (one row per code commit with its H0 score and label; older 70% train, newer 30% test; a training row only counts as buggy if its evidence appeared before the split; CSV export) and `reviewbudget/evaluate.py` (share of buggy test commits found within 20% of the changed code lines, precision in the top 10, and largest-first, smallest-first and random baselines; needs at least 10 test labels). Added `rb dataset --out` and `rb evaluate` to `cli.py`. Added `tests/test_evaluate.py`. Added snapshot datasets `data/fastapi_typer.csv`, `data/encode_httpx.csv` and `data/httpie_cli.csv` (source commits listed in `README.md`). Updated `README.md`.
- Why: Measures whether a ranking finds buggy commits better than simple baselines, and gives the phase 4 selector its train/test label counts. The CSV is inspectable proof of the data behind each number.
- Validation: `uv run pytest -q` (52 passed; 12 new tests, including metrics checked against hand-worked examples and the no-peek split); `uv run ruff check .` and `uv run ruff format --check .` clean. Real runs (about 7-9 s each, labels cached): typer 270 code commits, 15/2 train/test labels, too few to evaluate; httpx 846, 40/18; httpie 720, 71/26. Bugs found in 20% effort, H0 / largest / smallest / random: httpx 6% / 6% / 44% / 20%, httpie 4% / 0% / 50% / 21%. Top-10 precision: httpx 40% / 50% / 0% / 7%, httpie 30% / 50% / 10% / 14%.
- Limitations: H0 is worse than random order on the effort-aware measure because its size points favour large commits; its weights were deliberately not tuned on these results. The newest test commits have had less time for their bugs to be found, so test recall is a slight underestimate. Labels remain noisy.

## 2026-10-24T22:23:53+05:30 — Phase 2: bug labels and `rb labels`

- Changed: Added `reviewbudget/labels.py`: revert labels (high confidence) and SZZ labels via PyDriller (medium confidence), with the phase 0 filters (bug-fix keywords in the subject only, non-bug fixes such as docs, typos and lint excluded, fixes touching more than 10 files skipped, only program code traced, suspects more than 2 years older than the fix dropped). Each label stores its evidence commits and the date that evidence appeared, for leak-free evaluation in phase 3. Results are cached in `~/.cache/reviewbudget/` keyed by repository path and HEAD. Added `load_history` and `head_sha` to `git_changes.py` and the `rb labels` command to `cli.py`. Added `tests/test_labels.py` and the shared `tests/gitfixture.py` helper. Updated `README.md`.
- Why: Phase 3 needs labels to evaluate the ranking against, and the phase 4 selector needs to know how much trustworthy evidence a repository has.
- Validation: `uv run pytest -q` (40 passed; 13 new tests on a throwaway repository with exactly one revert and one SZZ pair, plus decoys for each filter); `uv run ruff check .` and `uv run ruff format --check .` clean. Full httpie/cli history: 4 revert and 98 SZZ labels (phase 0: 4 and 97), 720 code commits (phase 0: 710), computed in 2.0 s; the second run came from the cache. The small differences come from using the ranker's multi-language code-file rules instead of the spike's Python-only rules.
- Limitations: Labels are noisy evidence, not ground truth; the httpie sample still includes test-related fixes. Fix detection relies on English keywords in commit subjects.

## 2026-10-24T22:15:32+05:30 — Move the event-guidance entry into the build log

- Changed: Moved the 21:53 "Correct Devin Hack Kochi event guidance" entry (merged from PR #1) from above the file introduction into the build log, in newest-first order. Its text is unchanged.
- Why: The merged entry sat outside the build log and out of time order.
- Validation: Checked the entry order by eye; `git diff --check` clean.
- Limitations: None identified in these checks.

## 2026-10-24T22:09:08+05:30 — Phase 1: H0 ranker and `rb queue`

- Changed: Added the `reviewbudget` package. `git_changes.py` reads the non-merge commits in a range with the git CLI (files, renames, added and removed lines). `h0.py` scores each commit from its diff alone, with a reason for every point and all weights in one `WEIGHTS` table. `cli.py` adds `rb queue --repo <path> (--range A..B | --last N)`. Registered the `rb` entry point and a hatchling build in `pyproject.toml`. Added `tests/test_h0.py`. Updated `README.md`.
- Why: A working, explainable baseline that later phases (labels, evaluation, strategy selector) build on and are measured against.
- Validation: `uv run pytest -q` (27 passed: 22 new tests on throwaway git repos, plus the 5 phase 0 tests); `uv run ruff check .` and `uv run ruff format --check .` clean. Ran `rb queue --last 30` on httpie/cli (about 1 s). That sanity run found two false signals, now fixed and covered by tests: `author`/`author_email` matched the security keywords, and `setup.py` counted as program code.
- Limitations: Weights are hand-set and not yet validated against bug labels. Keyword risk signals are approximate. Mechanical multi-file changes (for example a project rename) can still rank high.

## 2026-10-24T21:53:05+05:30 — Correct Devin Hack Kochi event guidance

- Changed: corrected the current event name and AI tool guidance in `.github/pull_request_template.md`, `AGENTS.md`, `AI_USAGE.md`, `CHANGELOG.md`, `README.md`, `RULES.md`, `SUBMISSION.md`.
- Why: the organizer shared an older event template; Devin Hack Kochi has no
  major AI usage constraints and the template must not require a particular AI provider.
- Scope: preserved project implementation and historical assistance records.
- Removed obsolete template logistics, participation limits, and credit promises; current organizer instructions remain authoritative.
- Validation: reviewed documentation diffs, checked whitespace with `git diff --check`, and checked local Markdown links for new breakage.
- Limitations: maintainer review is pending; application tests were not run for this documentation-only correction.

## 2026-10-24T21:49:35+05:30 — uv environment and lint clean-up

- Changed: Added `pyproject.toml`, `uv.lock` and `.python-version` (Python 3.12; `pydriller>=2.12,<3`; dev group `pytest`, `ruff`). Fixed the ruff findings in `spikes/phase0_table.py` and `tests/test_phase0_spike.py` and applied `ruff format` to `spikes/` and `tests/`. Added setup, run and check commands to `README.md`.
- Why: One reproducible environment for the repository instead of system-wide installs.
- Validation: `uv sync --locked` succeeded; `uv run pytest -q` (5 passed); `uv run ruff check .` (all checks passed); `uv run ruff format --check .` (clean). Ran the spike and table scripts on a fresh httpie/cli clone: same row as `docs/phase0.md`, and the spike's JSON output was identical before and after formatting (timings excluded).
- Limitations: No behavior change; the product CLI does not exist yet.

## 2026-10-24T21:40:18+05:30 — Phase 0 results table script

- Changed: Added `spikes/phase0_table.py`, which turns a directory of spike JSON results into the Markdown table in `docs/phase0.md` and applies the draft selector thresholds to show each repository's tier. Added it to the reproduce steps in `docs/phase0.md`.
- Why: Make the phase 0 tables and tier assignments reproducible from the cached results.
- Validation: Ran it on the full-history and 3-year results for the 12 repositories; rows and tiers match `docs/phase0.md`. `pyflakes` reported no issues.
- Limitations: Research helper, not product code. Cloning and running the spike per repository is still manual.

## 2026-10-24T21:30:33+05:30 — Phase 0 feasibility check

- Changed: Added `spikes/phase0_feasibility.py` (throwaway research script: history profile, revert and SZZ labels via PyDriller, train/test label counts, timing), `tests/test_phase0_spike.py`, and `docs/phase0.md` with results for 12 Python repositories, a hand check of 20 SZZ labels, the demo repositories and draft selector thresholds.
- Why: Check that real repositories give enough trustworthy bug labels, fast enough, before writing product code.
- Validation: `python -m pytest -q tests` (5 passed); ran the script on 12 cloned repositories (3-year and full-history windows); hand-checked 10 SZZ labels each for httpie/cli and fastapi/typer.
- Limitations: Keyword-based fix detection; SZZ precision roughly 50–65% in the hand check; thresholds are drafts. The script is not product code.

## 2026-10-24T21:25:04+05:30 — Adopt the DevDay Kochi hackathon template

- Changed: Added `RULES.md`, `AGENTS.md`, `SUBMISSION.md`, `AI_USAGE.md`, `CHANGELOG.md` and `.github/pull_request_template.md` from [anima-regem/devday-kochi-hackathon-template](https://github.com/anima-regem/devday-kochi-hackathon-template). Rewrote `README.md` on the template's structure with the ReviewBudget overview, merged `.gitignore`, and kept `docs/BRIEF.md`.
- Why: Follow the event's repository workflow (rules, change log, AI usage record, submission checklist).
- Validation: Checked that local Markdown links resolve; no code to run yet.
- Limitations: Documentation only; no implementation or demo yet.

## Template setup — 10 October 2026

- Changed: Added the event README, rules, agent guide, change log, AI usage record, submission checklist, Git ignore rules, and pull request checklist.
- Why: Give participants a consistent starting point for event rules, basic coding patterns, documented changes, and regular commits.
- Validation: Checked local Markdown links, event detail consistency, required documents, and diff whitespace before publishing.
- Limitations: Documentation scaffolding only; no participant project, application, or working demo is included. GitHub publication and template status are verified separately after creation.
