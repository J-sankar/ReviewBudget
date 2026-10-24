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
- **Working demo:** in progress. `rb queue` (H0 heuristic ranking) works; the strategy selector, evaluation and time budget are not built yet.
- **Technology stack:** Python, Git CLI, PyDriller; scikit-learn only if the learned ranker is adopted (planned).

Implemented CLI (phase 1):

```text
rb queue --repo <path> --range A..B     # rank the non-merge commits in a range
rb queue --repo <path> --last N         # rank the last N commits on HEAD
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

- Working features: phase 0 (feasibility check, see [docs/phase0.md](docs/phase0.md)); phase 1 `rb queue` with the H0 change-only heuristic. H0 scores each commit from its diff alone: code size (log scale, capped), files and folders touched, error-handling / security / concurrency keywords in changed lines, and whether tests changed. Docs-only, test-only, pure-rename and whitespace-only changes score near zero. Commit messages are never used for scoring.
- Known limitations: H0 weights are hand-set and not yet validated against bug labels (phase 3). The risk signals are keyword matches, so they can fire on unrelated words or miss real risk. Mechanical changes spread across many files (for example a project rename) can still rank high. History signals, the strategy selector and the time budget are not built yet.
- Libraries, APIs, and public datasets used: [PyDriller](https://github.com/ishepard/pydriller) (Apache-2.0) for Git history and SZZ; [pytest](https://pytest.org) and [ruff](https://docs.astral.sh/ruff/) for checks. Phase 0 analysed public GitHub repositories listed in [docs/phase0.md](docs/phase0.md).

See [AI_USAGE.md](AI_USAGE.md) for AI assistance and [CHANGELOG.md](CHANGELOG.md) for the development record.
