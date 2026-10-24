# Review plan

**Strategy H1 (history-aware, per line) · 30 commits · last 30 on HEAD**

Strategy selection:
- bug labels: 71 older, 26 newer; 14% of code commits labelled
- history coverage of newer commits: files 0.95, authors 0.83
- learning model eligible (at least 50 older and 20 newer labels, 3%-30% labelled), so L competes
- H1: best on the newest 30% of the older commits, after L learned from the rest (bugs found in 20% effort: H0 0%, S 36%, H1 43%, L 43%); check on the newer commits: H0 4%, S 50%, H1 50%, L 42%

Scores are risk points per 100 changed code lines, from the diff and the repository's history: review priorities, not bug predictions.

Budget 15 min at 300 lines of code an hour: 5 of 30 commits fit, 12 min used.

## Within your 15 minutes

| # | commit | min | subject | why |
| --- | --- | --- | --- | --- |
| 1 | `2105caa4` | 1 | 3.2.4 | files had 17 earlier bug-linked commits; files changed 105 times before; code changed without a test change |
| 2 | `7f03c52d` | 1 | Fix SSL connections by pinning the `requests` version to `2.31.0` | files had 16 earlier bug-linked commits; files changed 104 times before; code changed without a test change |
| 3 | `fd30c4ef` | 2 | Explicitly load default certificates when creating SSL context (#1583) (#1596) | files had 2 earlier bug-linked commits; code changed without a test change; author's first change to these files |
| 4 | `01140215` | 4 | Rename repo from `httpie/httpie` to `httpie/cli` | files had 56 earlier bug-linked commits; 6 code files changed; files changed 171 times before |
| 5 | `ff742581` | 4 | Cleanup default cert loading | security-sensitive code changed (cert_file); files had 2 earlier bug-linked commits; code changed without a test change |

## Skipped (25)

| # | commit | subject | why skipped |
| --- | --- | --- | --- |
| 6 | `2ef4a57d` | Fix/refactor default cert loading | needs 6 min, only 3 min left: the plan stops here |
| 7 | `8560d119` | Update test.yml | non-code files only (config, build, data) |
| 8 | `5c068f81` | Re-add conditional colorama dependency | non-code files only (config, build, data) |
| 9 | `5b604c37` | Fix `https` behaviour in fish (#1611) | non-code files only (config, build, data) |
| 10 | `e52a60e6` | [automated] Update generated content (#1524) | non-code files only (config, build, data) |
| 11 | `2843b874` | [automated] Update generated content (#1607) | non-code files only (config, build, data) |
| 12 | `9eb86998` | Added an alias for HTTPS in fish completions (#1598) | non-code files only (config, build, data) |
| 13 | `c8c135ff` | [automated] Update generated content (#1509) | non-code files only (config, build, data) |
| 14 | `8ac44b57` | Ensure support for Python 3.11/3.12 (#1540) | non-code files only (config, build, data) |
| 15 | `3524ccf0` | Drop dependency on the abandoned python-lazy-fixture | non-code files only (config, build, data) |
| 16 | `10b7d317` | Migrate setup.py to setup.cfg (#1553) | non-code files only (config, build, data) |
| 17 | `cee82c82` | Fix link to CurliPie tool (#1582) | docs or tests only |
| 18 | `30373274` | Update the raw json fields example (#1606) | docs or tests only |
| 19 | `50e15646` | Update the Forms section of README.md (#1593) | docs or tests only |
| 20 | `f4cf43ec` | Cleanup | docs or tests only |
| 21 | `3de7c820` | Cleanup | docs or tests only |
| 22 | `db16bbee` | Drop dependency on the abandoned python-lazy-fixture II. | docs or tests only |
| 23 | `2db28ef6` | docs: fix typo (#1548) | docs or tests only |
| 24 | `7a234d60` | [automated] Update generated content (#1566) | docs or tests only |
| 25 | `a842a932` | docs: Update the url for offline mode (#1556) | docs or tests only |
| 26 | `b934eec7` | Replace redirection with tee command with sudo for file creation (#1557) | docs or tests only |
| 27 | `9e8e3691` | Update README.md | docs or tests only |
| 28 | `8aa654d1` | Update README.md | docs or tests only |
| 29 | `30a6f73e` | README.md: fix the file based separators internal link (#1510) | docs or tests only |
| 30 | `ec4fb842` | Document restriction on top-level JSON types explicitly (#1496) | docs or tests only |

## Riskiest changes (H0 risk signals, top 5)

| commit | risk | subject | why risky | status |
| --- | --- | --- | --- | --- |
| `2ef4a57d` | 6.0 | Fix/refactor default cert loading | 30 lines of code changed; security-sensitive code changed (ssl); code changed without a test change | not in your plan: ranked #6, needs 6 min |
| `ff742581` | 5.0 | Cleanup default cert loading | 16 lines of code changed; security-sensitive code changed (cert_file); code changed without a test change | in your plan (#5) |
| `01140215` | 4.5 | Rename repo from `httpie/httpie` to `httpie/cli` | 16 lines of code changed; 6 code files changed; spread over 4 folders | in your plan (#4) |
| `fd30c4ef` | 2.5 | Explicitly load default certificates when creating SSL context (#1583) (#1596) | 7 lines of code changed; code changed without a test change | in your plan (#3) |
| `2105caa4` | 2.2 | 3.2.4 | 4 lines of code changed; code changed without a test change | in your plan (#1) |
