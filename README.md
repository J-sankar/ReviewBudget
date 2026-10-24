# Devin Hack Kochi

A repository template for participants at Devin Hack Kochi. It contains event guidance and documentation scaffolding; follow the organizers' current project-start instructions.

**[Event rules](RULES.md)** · **[Agent instructions](AGENTS.md)**

## Event details

Devin Hack Kochi has no major AI usage constraints. Participants may use Devin and other AI tools, models, and providers; this template does not require Codex or restrict AI usage to OpenAI. AI usage notes are project documentation, not an additional event eligibility requirement.

The organizer shared an older event template. Follow the current organizer announcements for logistics, participation format, eligibility, submission timing, and credits; the older template's details do not apply. See [RULES.md](RULES.md).

## Use this template

1. Select **Use this template → Create a new repository** on GitHub. Create your own project repository and clone it.
2. Read [RULES.md](RULES.md) and [AGENTS.md](AGENTS.md) before building. Follow the organizers' current project-start instructions.
3. Fill in the project overview below as you build. Use any suitable language or framework, keeping the implementation simple.
4. Record meaningful changes in [CHANGELOG.md](CHANGELOG.md) and, if maintained, your actual AI assistance in [AI_USAGE.md](AI_USAGE.md). Commit after completed milestones; aim for a meaningful checkpoint about every 30 minutes.
5. Complete [SUBMISSION.md](SUBMISSION.md) with your code repository, short project description, and working demo. Follow submission instructions announced by the organizers.

This template has no application code or required technology stack. The documentation and commit cadence are repository workflow guidance; the event participation rules are in [RULES.md](RULES.md).

## Project overview — complete during the event

- **Project name:** ReviewBudget
- **Short description:** A developer tool that learns from a Git repository's history to show which changes most deserve human review in the time a reviewer has. It chooses its features, ranking strategy and (only when justified) a lightweight learned model from the quality of the available evidence, not from repository size. Full plan: [docs/BRIEF.md](docs/BRIEF.md).
- **Team:** Jayasankar ([@J-sankar](https://github.com/J-sankar)), solo.
- **Working demo:** in progress. `rb queue` (ranking with an automatic H0/S/H1/L strategy choice), `rb labels`, `rb dataset` and `rb evaluate` work; the time budget is not built yet.
- **Technology stack:** Python, Git CLI, PyDriller, scikit-learn (logistic regression for the learned strategy L).

Implemented CLI (phases 1-5):

```text
rb queue --repo <path> --range A..B [--strategy auto|h0|s|h1|l]   # rank the non-merge commits in a range
rb queue --repo <path> --last N     [--strategy auto|h0|s|h1|l]   # rank the last N commits on HEAD
rb labels --repo <path> [--sample N] [--no-cache]   # bug labels found in the history
rb dataset --repo <path> --out data.csv             # one row per code commit: H0 score, label, train/test window
rb evaluate --repo <path>                           # score H0, H1, L and baselines; show the strategy selection
```

Planned CLI (not implemented yet):

```text
rb queue   --repo . --range main..feature --budget 30m [--export plan.md]
```

### Run the project

1. Prerequisites: Git, Python 3.12 and [uv](https://docs.astral.sh/uv/).
2. Install dependencies (creates `.venv` from `uv.lock`): `uv sync`
3. Environment setup: none; no environment variables or credentials are needed.
4. Rank commits for review:
   ```bash
   uv run rb queue --repo <path-to-repo> --last 30
   uv run rb queue --repo <path-to-repo> --range main..feature
   uv run rb queue --repo <path-to-repo> --last 30 --strategy h0   # diff only, fastest
   uv run rb queue --repo <path-to-repo> --last 30 --strategy s    # smallest code changes first
   ```
   Each row shows the score and its top three reasons. By default (`--strategy auto`) the selector reads the full history and bug labels first and explains which strategy it chose (about 7-9 s on a 1,700-commit repository).
   Show the bug labels found in the full history (cached in `~/.cache/reviewbudget/`, or `$XDG_CACHE_HOME/reviewbudget/`):
   ```bash
   uv run rb labels --repo <path-to-repo> --sample 10
   ```
   Export the dataset for inspection, and score H0 against the labels on the newer commits:
   ```bash
   uv run rb dataset --repo <path-to-repo> --out data.csv
   uv run rb evaluate --repo <path-to-repo>
   ```
   Snapshot datasets are committed in `data/`, made with `rb dataset` from fastapi/typer `a5882ded`, encode/httpx `b5addb64` and httpie/cli `5b604c37`. Clone a repository, check out that commit and rerun `rb dataset` to regenerate one.
5. Run the phase 0 spike on a local clone:
   ```bash
   uv run python spikes/phase0_feasibility.py <path-to-clone> --years 100 --out result.json
   uv run python spikes/phase0_table.py <dir-of-result-json>
   ```
6. Run checks and tests:
   ```bash
   uv run pytest -q
   uv run ruff check .
   uv run ruff format --check .
   ```

### Current status

- Working features: phase 0 (feasibility check, see [docs/phase0.md](docs/phase0.md)); phase 1 `rb queue` with the H0 change-only heuristic. H0 scores each commit from its diff alone: code size (log scale, capped), files and folders touched, error-handling / security / concurrency keywords in changed lines, and whether tests changed. Docs-only, test-only, pure-rename and whitespace-only changes score near zero. Commit messages are never used for scoring. Phase 2 `rb labels` finds bug labels in the full history: reverted commits (high confidence) and SZZ suspects traced back from bug-fix commits (medium confidence), with the phase 0 noise filters. Each label records its evidence and the date that evidence appeared. Phase 3 `rb dataset` and `rb evaluate` split the code commits by time (older 70% train, newer 30% test; a training bug only counts if its evidence appeared before the split) and measure the share of buggy test commits found within 20% of the review effort (changed code lines), plus precision in the top 10, for H0 against largest-first, smallest-first and random baselines. First results: H0 currently finds fewer bugs per line reviewed than random order (httpx 6% vs 20%, httpie 4% vs 21%), because its size points push large commits to the top; it does beat random on top-10 precision. Phase 4 adds H1 and the strategy selector. H1 drops H0's size points, adds history points computed only from earlier commits (files with earlier bugs whose evidence had already appeared, frequently changed files, an author new to the files or with fewer than 5 earlier commits) and ranks by risk per 100 changed code lines. S ranks code commits by changed code lines, fewest first. The selector applies the phase 0 evidence rules (never commit count); thin evidence means H0, otherwise it picks whichever of H0, S and H1 found the most bugs within 20% effort on the older (training) commits, with ties going to the simpler strategy, and only reports the newer commits as a check. `rb evaluate` and `rb queue` print its reasons. Results (bugs found in 20% effort, older commits, then newer): httpx H0 10% / S 38% / H1 32%, then 6% / 44% / 44%; httpie H0 6% / S 46% / H1 42%, then 4% / 50% / 50%; httpx selects S. typer has 2 newer labels and stays on H0. Phase 5 adds L, a logistic regression (scikit-learn) on H0's signals and the history counts, ranked by bug likelihood per 100 changed code lines; its reasons are the signals that raised a commit's likelihood most, and `rb evaluate` prints its learned weights. L competes only where the phase 0 model rule holds. Then the older commits are split again by time: L learns from the first 70% (bugs found after that cut are hidden) and all strategies are compared on the rest. On httpie, the only model-eligible demo repository, H1 and L tie at 43% on that slice, so the simpler H1 is selected; on the newer commits L finds 42% against 50% for S and H1.
- Known limitations: H0 does worse than random order on the effort-aware measure (see above). H1 does not beat plain smallest-first ordering on the newer commits, so its history signals add little so far. L does worse than S and H1 on httpie's newer commits, and learns a negative weight for earlier bugs in the files; it is trained on one repository's few, noisy labels. S, H1 and L rarely put buggy commits in their top 10 (0-10%), where H0 reaches 30-40%. The selection slice is small, so a single bug can change the choice. `rb queue --strategy l` learns from all labels known now, including those of older commits in the requested range. The effort measure favours small commits by design. Version bumps and formatting changes in bug-prone files can rank high. The newest test commits have had less time for their bugs to be found. Bug-fix commits are found by keywords in the commit subject, and SZZ labels are noisy (about 50-65% looked plausible in the phase 0 hand check), so labels are evidence, not ground truth. H0 weights are hand-set and not yet validated against bug labels (phase 3). The risk signals are keyword matches, so they can fire on unrelated words or miss real risk. Mechanical changes spread across many files (for example a project rename) can still rank high. History signals, the strategy selector and the time budget are not built yet.
- Libraries, APIs, and public datasets used: [PyDriller](https://github.com/ishepard/pydriller) (Apache-2.0) for Git history and SZZ; [pytest](https://pytest.org) and [ruff](https://docs.astral.sh/ruff/) for checks. Phase 0 analysed public GitHub repositories listed in [docs/phase0.md](docs/phase0.md).

See [AI_USAGE.md](AI_USAGE.md) for AI assistance and [CHANGELOG.md](CHANGELOG.md) for the development record.
