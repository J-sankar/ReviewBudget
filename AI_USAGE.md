# AI usage record

If maintaining this record, briefly document the actual contributions of whichever AI tools you use at Devin Hack Kochi. Add a row after each meaningful task or milestone. Keep summaries concise and omit secrets, private data, and full chat transcripts.

## Event build log

Mark human review as pending until someone has reviewed the contribution.

| Date and time with timezone | Tool / model, if known | Task | Assistance and affected files | Human review / corrections | Validation and result |
| --- | --- | --- | --- | --- | --- |
| 2026-10-25T03:05:00+05:30 | GitHub Copilot | Commit-by-commit local PR analysis | Updated `reviewbudget/pr.py`, `reviewbudget/ui.py`, `tests/test_pr.py` and documentation so committed PR changes and pending tracked edits are separate review items | Pending | `uv run pytest -q tests/test_pr.py` (7 passed) |
| 2026-10-25T02:45:00+05:30 | GitHub Copilot | Local PR dashboard | Added `reviewbudget/pr.py`, `reviewbudget/ui.py`, Streamlit setup, focused tests and documentation for analyzing a pasted PR URL from an existing local checkout | Pending | `uv run pytest -q tests/test_pr.py` (6 passed); dependency lock updated |
| 2026-10-25T01:09:48+05:30 | Codex (GPT-5) | README status correction | Replaced remaining template language and stale demo status in `README.md`; recorded this documentation correction in `CHANGELOG.md` | Pending | Read all repository Markdown files; checked README links and statements against demo and submission documentation |
| 2026-10-25T00:12:52+05:30 | Devin (Cognition) | Demo script and submission details | Wrote `docs/DEMO.md`, generated `docs/demo/` outputs, filled in `SUBMISSION.md` and updated `README.md` from verified results | Pending | Demo commands rerun on fresh pinned clones; numbers match the docs; `uv run pytest -q` (109 passed) |
| 2026-10-24T23:51:43+05:30 | Devin (Cognition) | Phase 6 time budget and export | Wrote `reviewbudget/budget.py`, `rb queue --budget/--speed/--export`, the `low_value` keys in `h0.py` and `tests/test_budget.py` to the agreed plan | Pending | `uv run pytest -q` (109 passed); ruff check/format; 15-minute plans on httpie, httpx and typer; Markdown export checked by eye |
| 2026-10-24T23:39:29+05:30 | Devin (Cognition) | Phase 5 learned strategy L | Wrote `reviewbudget/model.py`, the selector's inner time split and L competition, `rb evaluate`/`rb queue --strategy l` changes, dataset feature columns and `tests/test_model.py` to the agreed plan; changed L's explanations after a real run showed below-average counts given as reasons without saying so | Pending | `uv run pytest -q` (88 passed); ruff check/format; `rb evaluate`/`rb queue` on typer, httpx and httpie |
| 2026-10-24T23:19:39+05:30 | Devin (Cognition) | Phase 4.1 smallest-first strategy and selector change | Wrote `reviewbudget/smallest.py`, the selector's choice among H0/S/H1 on the older commits, `rb queue --strategy s` and tests in `tests/test_h1.py` to the agreed plan | Pending | `uv run pytest -q` (78 passed); ruff check/format; `rb evaluate`/`rb queue` on typer, httpx and httpie |
| 2026-10-24T23:01:56+05:30 | Devin (Cognition) | Phase 4 H1 and strategy selector | Wrote `reviewbudget/history.py`, `h1.py`, `selector.py`, the `rb queue --strategy` and `rb evaluate` changes, dataset/CSV columns, `tests/test_h1.py` and `tests/conftest.py` to the agreed plan; fixed config-only commits ranking high in H1, found in a real-repo run | Pending | `uv run pytest -q` (74 passed); ruff check/format; `rb evaluate`/`rb queue` on typer, httpx and httpie |
| 2026-10-24T22:39:24+05:30 | Devin (Cognition) | Phase 3 dataset and evaluation | Wrote `reviewbudget/dataset.py`, `reviewbudget/evaluate.py`, `rb dataset` and `rb evaluate`, and `tests/test_evaluate.py` to the agreed plan; added a smallest-first baseline beyond the plan | Pending | `uv run pytest -q` (52 passed); ruff check/format; `rb evaluate` and `rb dataset` on typer, httpx and httpie |
| 2026-10-24T22:23:53+05:30 | Devin (Cognition) | Phase 2 bug labels | Wrote `reviewbudget/labels.py`, `rb labels`, `load_history`/`head_sha` in `git_changes.py`, `tests/test_labels.py` and `tests/gitfixture.py` to the agreed plan, porting the phase 0 spike's label logic | Pending | `uv run pytest -q` (40 passed); ruff check/format; `rb labels` on full httpie/cli history |
| 2026-10-24T22:09:08+05:30 | Devin (Cognition) | Phase 1 H0 ranker | Wrote `reviewbudget/` (`git_changes.py`, `h0.py`, `cli.py`) and `tests/test_h0.py` to the agreed plan; fixed two false signals found in the httpie sanity run (author words, `setup.py`) | Pending | `uv run pytest -q` (27 passed); ruff check/format; `rb queue --last 30` on httpie/cli |
| 2026-10-24T21:49:35+05:30 | Devin (Cognition) | uv environment and checks | Created the uv project (`pyproject.toml`, `uv.lock`, `.python-version`), fixed ruff findings, formatted `spikes/` and `tests/`, documented setup in `README.md` | Pending | `uv run pytest -q`; `uv run ruff check .`; spike run on httpie/cli |
| 2026-10-24T21:30:33+05:30 | Devin (Cognition) | Phase 0 feasibility check | Wrote the spike script and its tests, ran it on 12 repositories, hand-checked SZZ labels, added noise filters found by the hand check, wrote `docs/phase0.md` | Pending | `python -m pytest -q tests`; script runs on 12 repositories |
| 2026-10-24T21:25:04+05:30 | Devin (Cognition) | Plan the project and set up the repository | Wrote `docs/BRIEF.md` and the initial `README.md` and `.gitignore`; merged the DevDay Kochi hackathon template files (`RULES.md`, `AGENTS.md`, `SUBMISSION.md`, `AI_USAGE.md`, `CHANGELOG.md`, `.github/pull_request_template.md`) and filled in the project overview | Pending | Documentation only; checked local Markdown links resolve |

## Template preparation

This historical preparation note refers to the older template. It does not define Devin Hack Kochi's event rules or AI tool requirements.

On 10 October 2026, Codex prepared this documentation template from the organizer's supplied rules and checked the linked Luma page for the event name and dates. This covered `README.md`, `RULES.md`, `AGENTS.md`, `CHANGELOG.md`, `AI_USAGE.md`, `SUBMISSION.md`, `.gitignore`, and the pull request checklist. Agent validation covered local links, event consistency, required documents, and diff whitespace; organizer review is pending.

This preparation is separate from participant project implementation and participant AI usage during the event.

## Event documentation correction — 2026-10-24T21:53:05+05:30

- Tool: Codex.
- Task: correct the organizer-shared template to Devin Hack Kochi and clarify
  that the event has no major AI usage constraints.
- Affected files: `.github/pull_request_template.md`, `AGENTS.md`, `AI_USAGE.md`, `CHANGELOG.md`, `README.md`, `RULES.md`, `SUBMISSION.md`.
- Human review: pending maintainer review of this pull request.
- Validation: documentation diff, whitespace, and local Markdown link checks;
  no application code changed and no runtime checks were needed.
