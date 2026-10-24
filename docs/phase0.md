# Phase 0: feasibility check

**Verdict: go.** Real Python repositories give enough bug labels, quickly enough, and repositories of similar size land in different strategy tiers for reasons the selector can explain.

This is research output from a throwaway script, not product code. Reproduce with:

```bash
pip install pydriller==2.12
python spikes/phase0_feasibility.py <path-to-clone> --years 100 --out result.json   # full history
python spikes/phase0_feasibility.py <path-to-clone> --years 3                      # last 3 years
python spikes/phase0_feasibility.py <path-to-clone> --years 100 --sample 10       # labels to hand-check
python -m pytest -q tests
```

## What the script measures

For the non-merge commits inside the window, oldest first:

- **Profile:** commits, commits touching production Python code, authors, share of recent code changes whose files (≥ 3 earlier changes) and authors (≥ 5 earlier commits) have history.
- **Revert labels (high confidence):** a commit whose message says `This reverts commit <sha>` labels `<sha>`.
- **SZZ labels (medium confidence):** a commit whose *subject* matches fix/bug/regression/crash keywords is a fix; PyDriller's `Git.get_commits_last_modified_lines` traces its deleted/changed lines back to the commits that last touched them.
- **Noise filters:** skip fixes touching more than 10 files; ignore tests, docs, examples, `docs_src/`, `setup.py`, `tests.py`, `conftest.py`, `noxfile.py`; drop candidates more than 2 years older than their fix; skip fixes whose subject looks like docs, typing, lint or style.
- **Time split:** label counts in the older 70% (train) and newer 30% (test) of the window.

## Results (12 repositories, cloned 2026-10-24)

### Full history

| Repo | Commits | Code commits | Authors | File cov. | Author cov. | Revert | SZZ | Positive rate | Train labels | Test labels | SZZ time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Textualize/rich | 3387 | 1879 | 303 | 0.87 | 0.85 | 0 | 392 | 0.21 | 341 | 51 | 19 |
| encode/httpx | 1482 | 846 | 259 | 0.78 | 0.73 | 3 | 60 | 0.07 | 45 | 18 | 4 |
| fastapi/typer | 1753 | 270 | 110 | 0.80 | 0.78 | 0 | 19 | 0.07 | 17 | 2 | 2 |
| httpie/cli | 1690 | 710 | 174 | 0.81 | 0.84 | 4 | 97 | 0.14 | 74 | 26 | 4 |
| marshmallow-code/marshmallow | 3033 | 1670 | 241 | 0.96 | 0.80 | 5 | 217 | 0.13 | 183 | 38 | 21 |
| pallets/click | 2172 | 1117 | 468 | 0.95 | 0.61 | 6 | 135 | 0.13 | 99 | 41 | 13 |
| pallets/flask | 3829 | 1638 | 871 | 0.92 | 0.70 | 8 | 162 | 0.10 | 133 | 31 | 13 |
| psf/requests | 4883 | 2227 | 794 | 0.91 | 0.64 | 38 | 329 | 0.16 | 290 | 62 | 22 |
| python-poetry/poetry | 3758 | 2213 | 709 | 0.83 | 0.75 | 13 | 486 | 0.22 | 389 | 106 | 27 |
| scrapy/scrapy | 9594 | 5392 | 766 | 0.79 | 0.85 | 18 | 618 | 0.12 | 495 | 130 | 40 |

pytest and aiohttp (about 13,000 commits each) were run on the 3-year window only.

### Last 3 years

| Repo | Commits | Code commits | Revert | SZZ | Train labels | Test labels | SZZ time (s) |
|---|---|---|---|---|---|---|---|
| Textualize/rich | 465 | 240 | 0 | 14 | 9 | 5 | 5 |
| aio-libs/aiohttp | 5058 | 1817 | 2 | 223 | 178 | 45 | 91 |
| encode/httpx | 251 | 101 | 0 | 5 | 4 | 1 | 1 |
| fastapi/typer | 1312 | 185 | 0 | 6 | 5 | 1 | 1 |
| httpie/cli | 238 | 81 | 0 | 8 | 6 | 2 | 1 |
| marshmallow-code/marshmallow | 431 | 165 | 1 | 18 | 14 | 5 | 6 |
| pallets/click | 584 | 238 | 4 | 32 | 30 | 6 | 8 |
| pallets/flask | 229 | 80 | 0 | 6 | 6 | 0 | 2 |
| psf/requests | 233 | 75 | 0 | 2 | 0 | 2 | 2 |
| pytest-dev/pytest | 1930 | 884 | 8 | 88 | 71 | 22 | 37 |
| python-poetry/poetry | 906 | 457 | 0 | 62 | 55 | 7 | 12 |
| scrapy/scrapy | 1413 | 823 | 1 | 54 | 52 | 2 | 10 |

### Findings

1. **Use full history by default.** Most 3-year windows hold fewer than 10 test labels, too few to evaluate anything.
2. **Commit count is a poor proxy for evidence.** typer has 1,753 commits but only 270 touch production code (most are docs, translations and dependency bumps), so it yields 19 labels. httpie/cli has fewer commits and five times the labels.
3. **The time split matters on its own.** scrapy's last 3 years have 52 train labels but only 2 test labels, so a model could be trained but not checked.
4. **Reverts are rare.** Only requests (38) and scrapy (18) have more than 13; the labels are mostly SZZ.
5. **Runtime is fine.** At most 40 s per repository for full history (scrapy, 9,594 commits), 91 s for aiohttp's busy 3-year window. Results are cached as JSON.

## Hand check of SZZ labels

Ten random SZZ labels per demo repository were read (bug commit subject, fix commit subject and the fix's changed files), and each was judged plausible, uncertain or implausible.

| Repo | Plausible | Uncertain | Implausible | Main causes of bad labels |
|---|---|---|---|---|
| httpie/cli | 5 | 2 | 3 | fixes to the root `tests.py`; a version-bump commit titled "Version fix" |
| fastapi/typer | 6 | 3 | 1 | a fix that only changed `docs_src/` tutorial code |

That puts precision at roughly 50–65%: noisy, as expected, so SZZ labels stay **medium confidence** and reverts **high**.

The first pass found three avoidable noise sources, which are now filtered and covered by tests: fix keywords inside squash-merge bodies (`* Fix lint` in a feature PR), `setup.py`/`tests.py` counted as production code, and `docs_src/` counted as production code. The tables above are from the filtered run. The two hand-check samples were drawn before the last two filters, so they slightly understate the current precision.

## Demo repositories

Three repositories of similar size (1,482–1,753 commits) land in three different tiers:

| Repo | Commits | Train / test labels | Draft tier | Why |
|---|---|---|---|---|
| fastapi/typer | 1753 | 17 / 2 | **H0** | Too few newer labels to show history features help |
| encode/httpx | 1482 | 45 / 18 | **H1** | Enough to validate history features, not enough to train a model |
| httpie/cli | 1690 | 74 / 26 | **L eligible** | Enough labels in both windows to try logistic regression |

The core demo pair is **typer vs httpie/cli**; httpx is the optional middle example.

## Draft selector thresholds

Starting values, to be revisited when the evaluation in phase 3 exists. Counts are high- or medium-confidence labels inside the analysed window.

- **L eligible** if train labels ≥ 50, test labels ≥ 20, and positive rate between 3% and 30% (outside that range the labels are probably noise or too rare). The model is adopted only if it beats H1 on the test window.
- **H1** if test labels ≥ 10 and both file- and author-history coverage ≥ 0.6. A history feature whose own coverage is below 0.6 is dropped.
- **H0** otherwise.

Applied to the tables above: full history gives typer H0, httpx H1 and the other eight L eligible; the 3-year windows give H0 everywhere except pytest and aiohttp (L eligible). Commit count is not an input.

## Limitations

- Bug-fix detection is keyword-based, so fixes with vague subjects are missed and some non-bug "fix" commits get through.
- The hand check is 20 labels judged from subjects and file lists, not a full review of each diff.
- Thresholds are set by eye from these 12 repositories, not tuned.
- Python production code only.
