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
- **Working demo:** in progress. `rb queue` (H0 heuristic ranking) and `rb labels` (bug labels from history) work; the strategy selector, evaluation and time budget are not built yet.
- **Technology stack:** Python, Git CLI, PyDriller; scikit-learn only if the learned ranker is adopted (planned).

Implemented CLI (phases 1 and 2):

```text
rb queue --repo <path> --range A..B     # rank the non-merge commits in a range
rb queue --repo <path> --last N         # rank the last N commits on HEAD
rb labels --repo <path> [--sample N] [--no-cache]   # bug labels found in the history
rb dataset --repo <path> --out data.csv             # one row per code commit: H0 score, label, train/test window
rb evaluate --repo <path>                           # score H0 and baselines on the newer 30% of commits
```

Planned CLI (not implemented yet):

```text
rb profile --repo .                                   # evidence profile + chosen strategy
rb eval    --repo .                                   # chronological evaluation vs baselines
rb queue   --repo . --range main..feature --budget 30m [--export plan.md]
```

### Run the project

1. Prerequisites: Git, Python 3.12 and [uv](https://docs.astral.sh/uv/).
2. Install dependencies (creates `.venv` from `uv.lock`): `uv sync`
3. Environment setup: none; no environment variables or credentials are needed.
4. Rank commits for review (H0 heuristic):
   ```bash
   uv run rb queue --repo <path-to-repo> --last 30
   uv run rb queue --repo <path-to-repo> --range main..feature
   ```
   Each row shows the score and its top three reasons.
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

- Working features: phase 0 (feasibility check, see [docs/phase0.md](docs/phase0.md)); phase 1 `rb queue` with the H0 change-only heuristic. H0 scores each commit from its diff alone: code size (log scale, capped), files and folders touched, error-handling / security / concurrency keywords in changed lines, and whether tests changed. Docs-only, test-only, pure-rename and whitespace-only changes score near zero. Commit messages are never used for scoring. Phase 2 `rb labels` finds bug labels in the full history: reverted commits (high confidence) and SZZ suspects traced back from bug-fix commits (medium confidence), with the phase 0 noise filters. Each label records its evidence and the date that evidence appeared. Phase 3 `rb dataset` and `rb evaluate` split the code commits by time (older 70% train, newer 30% test; a training bug only counts if its evidence appeared before the split) and measure the share of buggy test commits found within 20% of the review effort (changed code lines), plus precision in the top 10, for H0 against largest-first, smallest-first and random baselines. First results: H0 currently finds fewer bugs per line reviewed than random order (httpx 6% vs 20%, httpie 4% vs 21%), because its size points push large commits to the top; it does beat random on top-10 precision.
- Known limitations: H0 does worse than random order on the effort-aware measure (see above). The newest test commits have had less time for their bugs to be found. Bug-fix commits are found by keywords in the commit subject, and SZZ labels are noisy (about 50-65% looked plausible in the phase 0 hand check), so labels are evidence, not ground truth. H0 weights are hand-set and not yet validated against bug labels (phase 3). The risk signals are keyword matches, so they can fire on unrelated words or miss real risk. Mechanical changes spread across many files (for example a project rename) can still rank high. History signals, the strategy selector and the time budget are not built yet.
- Libraries, APIs, and public datasets used: [PyDriller](https://github.com/ishepard/pydriller) (Apache-2.0) for Git history and SZZ; [pytest](https://pytest.org) and [ruff](https://docs.astral.sh/ruff/) for checks. Phase 0 analysed public GitHub repositories listed in [docs/phase0.md](docs/phase0.md).

See [AI_USAGE.md](AI_USAGE.md) for AI assistance and [CHANGELOG.md](CHANGELOG.md) for the development record.
