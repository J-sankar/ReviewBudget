# ReviewBudget demo (about 3 minutes)

The demo runs `rb` on three public Python repositories of similar size, pinned to the
commits the snapshot datasets in `data/` were made from, so the numbers on screen match
the documentation. Saved outputs of every command are in [demo/](demo/) as a fallback.

## Before the demo (needs network, about 3 minutes)

Prerequisites: Git, Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/J-sankar/ReviewBudget && cd ReviewBudget
uv sync

mkdir -p ~/rb-demo
git clone https://github.com/fastapi/typer ~/rb-demo/fastapi_typer
git clone https://github.com/encode/httpx ~/rb-demo/encode_httpx
git clone https://github.com/httpie/cli ~/rb-demo/httpie_cli
git -C ~/rb-demo/fastapi_typer checkout a5882ded
git -C ~/rb-demo/encode_httpx checkout b5addb64
git -C ~/rb-demo/httpie_cli checkout 5b604c37

# Warm the bug-label cache (~/.cache/reviewbudget/) so the live commands are quicker.
for r in fastapi_typer encode_httpx httpie_cli; do
  uv run rb labels --repo ~/rb-demo/$r --sample 0
done
```

Each live command below takes about 8-12 seconds; start the talking point while it runs.

### Analyze a local pull request

The optional dashboard uses the reviewer's existing checkout. It does not clone or fetch.
Start it with:

```bash
uv run streamlit run reviewbudget/ui.py
```

Paste the GitHub PR URL, the local repository path and the local base ref (usually `main`).
The dashboard validates that a configured local remote matches the PR URL, analyzes each
committed change in `base..HEAD`, and adds tracked working-tree edits as a separate
`WORKTREE` item. Untracked files are not included.

## Script

### 1. The problem (20 s)

> "A reviewer has 30 new commits and 15 minutes. Diffs show what changed, but not which
> changes have historically been the ones that break. ReviewBudget learns that from the
> repository's own history and fits the riskiest work into the time you have."

### 2. Same size, different evidence, different strategy (60 s)

```bash
uv run rb evaluate --repo ~/rb-demo/fastapi_typer
uv run rb evaluate --repo ~/rb-demo/encode_httpx
uv run rb evaluate --repo ~/rb-demo/httpie_cli
```

Point at the `Strategy selection` block at the end of each output
([typer](demo/evaluate_fastapi_typer.txt), [httpx](demo/evaluate_encode_httpx.txt),
[httpie](demo/evaluate_httpie_cli.txt)):

- **typer → H0.** Only 2 newer bug labels: too little evidence to test anything, so it
  uses the change-only heuristic.
- **httpx → S (smallest first).** It tried H0, S and H1 on older commits; S found the
  most bugs per line read (38%), and the newer commits confirm it (44%).
- **httpie → H1.** Enough evidence for the learned model L, so L competes: it learns
  from older commits and is tested on commits it never saw. It ties H1 (43%), and a tie
  goes to the simpler strategy. On newer commits L finds 42% against 50% for H1.

> "Repository size is never an input. The tool picks the strategy the evidence supports,
> and rejects a fancier one, with numbers, when it does not earn its place."

### 3. The 15-minute plan (60 s)

```bash
uv run rb queue --repo ~/rb-demo/httpie_cli --last 30 --budget 15m --export plan.md
```

Walk through the output ([saved](demo/queue_httpie_budget.txt)):

- **Within your 15 minutes:** 5 of 30 commits, 12 minutes, each with its reasons (files
  with many earlier bugs, SSL code changed without a test change).
- **Skipped:** every other commit has a reason: "needs 6 min, only 3 min left", or docs,
  tests or config only.
- **Riskiest changes:** H0's top 5 by risk signals, with whether each made the plan.
- **`plan.md`:** the same plan as Markdown for a PR comment ([saved](demo/httpie_plan.md)).

### 4. Proof and honesty (20 s)

- `data/*.csv`: one row per commit with the features, labels and train/test window the
  numbers come from.
- `uv run pytest -q`: 109 tests, including checks that nothing is learned from bugs
  discovered later.
- Known limitations are in the README: labels are noisy, the history-aware strategies
  barely beat smallest-first, and review minutes use one guideline speed.

## If something fails on stage

Open the saved outputs in [demo/](demo/). They were produced with the commands above on
fresh clones at the pinned commits, with an empty cache.
