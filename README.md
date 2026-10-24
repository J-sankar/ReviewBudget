# DevDay Exchange Community Hackathon: Kochi

A repository template for participants at the 10–11 October 2026 hackathon. It contains event rules and documentation scaffolding; build your project from scratch at the event.

**[Event and registration on Luma](https://luma.com/z10nz8gp)** · **[Event rules](RULES.md)** · **[Agent instructions](AGENTS.md)**

## Event details

| Detail | Information |
| --- | --- |
| Venue | JAIN University, Kochi |
| Location | [Open the venue map](https://maps.app.goo.gl/Eme7gR7NDXSNRANu5) |
| Rooms | 2008 and 2009 |
| Check-in | 10 October 2026, 6:00 PM IST |
| Kick-off | 10 October 2026, 6:30 PM IST |
| Wrap-up | 11 October 2026, by 10:00 AM IST |
| Participation | Solo or a team of up to 4 participants |
| Theme | Open — build anything you like |

Keep your approved Luma QR code ready for entry, and bring your laptop and charger. Eligible checked-in participants will receive Codex credits and OpenAI API credits.

## Use this template

1. Select **Use this template → Create a new repository** on GitHub. Create your own project repository and clone it.
2. Read [RULES.md](RULES.md) and [AGENTS.md](AGENTS.md) before building. Begin project implementation at the event.
3. Fill in the project overview below as you build. Use any suitable language or framework, keeping the implementation simple.
4. Record meaningful changes in [CHANGELOG.md](CHANGELOG.md) and your Codex usage in [AI_USAGE.md](AI_USAGE.md). Commit after completed milestones; aim for a meaningful checkpoint about every 30 minutes.
5. Complete [SUBMISSION.md](SUBMISSION.md) with your code repository, short project description, and working demo. Follow submission instructions announced by the organizers.

This template has no application code or required technology stack. The documentation and commit cadence are repository workflow guidance; the event participation rules are in [RULES.md](RULES.md).

## Project overview — complete during the event

- **Project name:** ReviewBudget
- **Short description:** A developer tool that learns from a Git repository's history to show which changes most deserve human review in the time a reviewer has. It chooses its features, ranking strategy and (only when justified) a lightweight learned model from the quality of the available evidence, not from repository size. Full plan: [docs/BRIEF.md](docs/BRIEF.md).
- **Team:** Jayasankar ([@J-sankar](https://github.com/J-sankar)), solo.
- **Working demo:** TODO — not built yet.
- **Technology stack:** Python, Git CLI, PyDriller; scikit-learn only if the learned ranker is adopted (planned).

Planned CLI (not implemented yet):

```text
rb profile --repo .                                   # evidence profile + chosen strategy
rb eval    --repo .                                   # chronological evaluation vs baselines
rb queue   --repo . --range main..feature --budget 30m [--export plan.md]
```

### Run the project

Replace these placeholders with commands that actually work for your project:

1. Prerequisites and versions: TODO
2. Dependency installation: TODO
3. Environment setup: TODO — list required variable names and provide a sanitized `.env.example` if needed.
4. Start the project: TODO
5. Run checks or tests: TODO

### Current status

- Working features: none yet; planning stage (see [docs/BRIEF.md](docs/BRIEF.md)).
- Known limitations: TODO
- Libraries, APIs, and public datasets used: TODO — include source links and applicable attribution.

See [AI_USAGE.md](AI_USAGE.md) for AI assistance and [CHANGELOG.md](CHANGELOG.md) for the development record.
