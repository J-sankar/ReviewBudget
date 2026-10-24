# AI usage record

If maintaining this record, briefly document the actual contributions of whichever AI tools you use at Devin Hack Kochi. Add a row after each meaningful task or milestone. Keep summaries concise and omit secrets, private data, and full chat transcripts.

## Event build log

Mark human review as pending until someone has reviewed the contribution.

| Date and time with timezone | Tool / model, if known | Task | Assistance and affected files | Human review / corrections | Validation and result |
| --- | --- | --- | --- | --- | --- |
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
