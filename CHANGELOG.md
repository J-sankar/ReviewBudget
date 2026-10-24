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
