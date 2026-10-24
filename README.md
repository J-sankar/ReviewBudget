# ReviewBudget

A developer tool that learns from a Git repository's history to prioritise the code changes that deserve human review when review time is limited.

It profiles the repository's history and chooses its features, ranking strategy and (only when justified) a lightweight learned model based on the quantity and quality of usable evidence, not on repository size.

Built for **Devin Hacks Kochi**, Track 2: *Make the Invisible Visible*.

## Status

Planning. See [docs/BRIEF.md](docs/BRIEF.md) for the scope, phases and demo plan.

## Planned CLI

```
rb profile --repo .                                   # evidence profile + chosen strategy
rb eval    --repo .                                   # chronological evaluation vs baselines
rb queue   --repo . --range main..feature --budget 30m [--export plan.md]
```
