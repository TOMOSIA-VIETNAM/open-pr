# e2e runbook

Unit tests read the prompts as text. Only a real run on a real PR tells you the review still comes out
right. `bootstrap.sh` builds that PR, `checklist.md` grades it. `<n>` below = the number of the PR of
THIS project you are testing.

## Run

```bash
e2e/bootstrap.sh --pr <n>                 # asks which vendor, prints the fixture URL
python3 scripts/vendor_lint.py --pr <n>   # free, read-only — before the review, never after
/open-pr:review <fixture url>             # in a Claude Code session, plugin installed
```

Grade against `checklist.md` — each row names the rule its defect exercises, so a miss says WHICH rule
regressed. Lint first because a broken vendor command fails every row for an unrelated reason.

Fix half, then cleanup:

```bash
e2e/bootstrap.sh --pr <n> --checkout --clone-dir /tmp/fixture   # no writes to the remote
cd /tmp/fixture && echo "then: /open-pr:fix <same url>"
e2e/bootstrap.sh --pr <n> --teardown      # closes the PR, deletes the branch, nothing else
```

## Setup, once

| vendor | credential | fixture repo |
|---|---|---|
| GitHub | `gh auth login` | `targets.env` → `GITHUB_REPO` |
| GitLab | `glab auth login --hostname gitlab.com` (PAT, `api` scope) | `GITLAB_REPO` |
| Bitbucket | `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` in the environment — no CLI exists | `BITBUCKET_REPO` |

Also needs an SSH key on that vendor: pushing never uses the token. A vendor you skip is simply skipped,
with a message. No write access to a fixture repo → fork it and pass `--repo <your-fork>`.
`pip install -r requirements-dev.txt` once, for the unit suite.

## Flags

| flag | does |
|---|---|
| `--vendor github\|gitlab\|bitbucket\|all` | skip the question |
| `--repo ns/name` | build on a fork instead of `targets.env` |
| `--checkout --clone-dir DIR` | working copy on the fixture branch, no writes |
| `--teardown` | close the fixture PR, delete its branch |

## Watch out

- **Never re-seed a `--pr` whose review is already posted** — it force-pushes the branch and strands the
  commits that review points at. Use `--checkout`.
- **Seeding writes to `main`** of the fixture repo; other open PRs there will see their base move.
- **Bitbucket has no draft** — `auto_submit_review: false` leaves the review in the CHAT with the PR
  empty, so read the draft rows as "not published yet".
- **A visible `[bot-finding]: #` is a defect** — it must render to nothing. Confirm it is there by
  reading a comment's raw body, not by looking at the page.
- **CI never runs this**: real model call, real vendor. `.github/workflows/e2e.yml` drives it by hand.

`fixtures/base/` is `main`, `fixtures/pr/` overwrites it on the branch, and that difference is the diff
under review — 9 planted defects, listed in `checklist.md`. The 40KB dump is generated, never committed.
