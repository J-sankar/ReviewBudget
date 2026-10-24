# Project submission

Complete this file during the hackathon and use it to prepare your submission through the method announced by the organizers. Do not submit your project to the template repository.

## Project

- **Project name:** ReviewBudget
- **Short description:** A command-line tool that learns from a Git repository's history which changes deserve human review first, and fits them into the time a reviewer has. It chooses its ranking strategy (a change-only heuristic, smallest-first, a history-aware heuristic, or a small learned model) from the quality of the repository's bug evidence, never its size, and explains what it included, what it skipped and why.
- **Code repository URL:** https://github.com/J-sankar/ReviewBudget
- **Final submitted implementation commit SHA:** `1b374a2` (https://github.com/J-sankar/ReviewBudget/commit/1b374a2). Later commits only add documentation.
- **Working demo URL or local demo steps:** local CLI demo; step-by-step script with exact commands in [docs/DEMO.md](docs/DEMO.md), saved outputs in [docs/demo/](docs/demo/).
- **Demo access requirements:** Git, Python 3.12, [uv](https://docs.astral.sh/uv/) and network access to clone the public demo repositories. No accounts or credentials.

## Participants

List participants according to the organizers' current participation format. Remove unused rows.

| Participant name | GitHub handle | Contribution |
| --- | --- | --- |
| Jayasankar | [@J-sankar](https://github.com/J-sankar) | Everything (solo), built with Devin (see [AI_USAGE.md](AI_USAGE.md)) |

## Run and demonstrate

- **Prerequisites and versions:** Git, Python 3.12, uv.
- **Install command:** `uv sync`
- **Required environment variable names:** none. Optional: `XDG_CACHE_HOME` moves the label cache (default `~/.cache/reviewbudget/`).
- **Start command:** `uv run rb queue --repo <path-to-git-repo> --last 30 --budget 15m`
- **Demo walkthrough:** (full script in [docs/DEMO.md](docs/DEMO.md))
  1. `rb evaluate` on fastapi/typer, encode/httpx and httpie/cli (similar sizes): it selects H0, S and H1 respectively, each with its evidence, and tries and rejects the learned model on httpie.
  2. `rb queue --last 30 --budget 15m --export plan.md` on httpie: the commits that fit in 15 minutes, a reason for every skipped commit, the riskiest changes, and a Markdown export.
  3. `data/*.csv` as the inspectable data behind the numbers.
- **Checks performed and results:** `uv run pytest -q` (109 passed); `uv run ruff check .` and `uv run ruff format --check .` clean; every demo command run on fresh clones at the pinned commits with an empty cache (8-12 s each), outputs saved in [docs/demo/](docs/demo/).
- **Known limitations or incomplete features:** bug labels come from reverts and SZZ tracing of commit subjects, so they are noisy (roughly 50-65% looked plausible in a phase 0 hand check). The history-aware H1 and the learned model L do not beat plain smallest-first ordering on the newer commits of the demo repositories. Strategies ranked per line rarely have buggy commits in their top 10, which the separate riskiest list covers. Review minutes use one guideline speed (300 lines an hour, configurable with `--speed`). It is a CLI only, with no web UI or GitHub integration. More in [README.md](README.md).
- **Libraries, APIs, and public datasets used:**
  - [PyDriller](https://github.com/ishepard/pydriller) (Apache-2.0): SZZ tracing of bug-introducing commits.
  - [scikit-learn](https://scikit-learn.org/) (BSD-3-Clause): logistic regression for the learned strategy L.
  - Development: [pytest](https://pytest.org/), [Ruff](https://docs.astral.sh/ruff/), [uv](https://docs.astral.sh/uv/).
  - Public repositories analysed for the demo and the `data/` snapshots (commit metadata and subjects only): [fastapi/typer](https://github.com/fastapi/typer) (MIT), [encode/httpx](https://github.com/encode/httpx) (BSD-3-Clause), [httpie/cli](https://github.com/httpie/cli) (BSD-3-Clause). The phase 0 feasibility check also analysed nine other public repositories, listed in [docs/phase0.md](docs/phase0.md).
- **AI usage record:** [AI_USAGE.md](AI_USAGE.md)
- **Development change log:** [CHANGELOG.md](CHANGELOG.md)

## Submission checklist

- [ ] The project follows the organizers' current project-start and eligibility instructions.
- [ ] The participation format follows the organizers' current instructions.
- [x] Any AI usage record included accurately identifies the tools used; this template requires no particular AI tool or provider.
- [x] The code repository URL, short description, and working demo are provided.
- [x] README setup and demo instructions match the submitted code.
- [x] Actual checks and known limitations are documented.
- [x] Meaningful changes are documented and committed throughout development.
- [x] The final implementation is committed and pushed, and its SHA is recorded above.
- [x] No credentials or private data are included in the repository or demo instructions.
- [ ] The organizers' announced submission method and timing have been followed.

Event: **Devin Hack Kochi**. Follow the organizers' current submission method and deadline. The event has no major AI usage constraints.
