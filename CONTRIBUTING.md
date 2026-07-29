# Contributing

This plugin is markdown, not code. There is no build and no runtime — the "program" is a set of files
an agent reads in order. So the conventions below are about **what a file is allowed to contain** and
**how much context a run costs**.

`CLAUDE.md` holds the full rule set (it is what the agent itself follows). This page is the short
version for a human.

## Where things go

Only `src/` ships to users. Everything else is repo-side.

| Directory | Holds | Loaded |
|---|---|---|
| `src/commands/` | the 3 slash commands | always (one per run) |
| `src/core/` | procedure shared by any run | always |
| `src/setup/` | per-repo provisioning (bootstrap, doctor, template, lesson) | first run / on schedule |
| `src/cases/` | branches behind a condition | only when that condition matched |
| `src/vendors/<name>/` | `fetch` · `worktree` · `post` · `thread` | per phase, per vendor |
| `src/templates/` | per-stack review criteria | per detected stack |
| `src/seeds/` | files copied into the reviewed repo | never — copied with `cp` |
| `src/reference/` | schema + vendor contract, for humans | never |
| `llm-upgrades/` | config migrations, fetched live | not packaged |

## Conventions that get enforced

- **One owner per rule.** If two files say the same thing, one of them is wrong. Accepted exceptions
  live in `tests/duplication_allowlist.json` with a reason.
- **Split a file only when the split-off part is conditional.** An extra read costs tokens; splitting
  something that always loads is a loss.
- **Callers never name a vendor.** They write `V§"<entry>"` and the entry resolves per vendor.
- **Context cost may not grow.** Every scenario has a ceiling in `tests/budgets.json`.
- **Files must be self-contained.** No pointers to task ids, plan phases or docs that get deleted.

## Setup, once

```bash
pip install -r requirements-dev.txt
scripts/install_hooks.sh
```

Actions is disabled on this repo by the org — `.github/workflows/` does not run. The hook does.

## Every change under `src/`

```bash
scripts/check.sh main
```

- cheaper → `python3 scripts/token_report.py --base main --update-budgets`
- more expensive → state which scenario and why, in the PR

## Touched `src/vendors/`

```bash
python3 scripts/vendor_lint.py                  # offline
python3 scripts/vendor_lint.py --pr <n>         # needs an open fixture
```

## Before merging something substantial

```bash
e2e/bootstrap.sh --pr <n>                       # fixture PR/MR, link recorded on PR <n>
```

New session:

```
/e2e-loop --pr <n>
```

By hand instead: `/open-pr:review <fixture url>`, then work through `e2e/checklist.md`.

The `/open-pr:fix` half:

```bash
e2e/bootstrap.sh --pr <n> --checkout --clone-dir /tmp/fixture
cd /tmp/fixture
```

then `/open-pr:fix <fixture url>`.

Never re-run the seeding mode on a `--pr` whose review is posted — it force-pushes the branch.

Round over:

```bash
e2e/bootstrap.sh --pr <n> --teardown
```

## Which path a round takes

`notebooks/review/open-pr-test/` at this repo's root:

- present → warm path (no bootstrap, no doctor). Default.
- delete it first → first-run path. Do this when `src/setup/`, `src/core/repo-settings.md` or the schema changed.

## Digging, not gating

```bash
python3 scripts/token_report.py --sections 'commands/*.md'
python3 scripts/dup_scan.py --window 10 --all --min-waste 20
```

## Adding a stack

1. `src/templates/<stack>.md` — every bullet names a concrete API, idiom or tool of that stack
2. a row in `src/core/stack-detection.md`
3. axis names 1/2/3/4/6 must match `src/core/review-criteria.md`

## Adding a vendor

1. `src/vendors/<name>/{fetch,worktree,post,thread}.md`
2. same entry headings as the existing vendors — `src/reference/vendor-interface.md` lists them
3. no caller changes

## Adding a config field

1. classify it in `src/reference/settings-schema.md`
2. read-time default in `src/core/repo-settings.md`
3. ask it in `src/setup/bootstrap.md`
4. `llm-upgrades/vN.md` + a line in `llm-upgrades/index.md`

## Commits

Conventional commits (`refactor(scope): …`). PR already reviewed → new commits only, no amend, no
squash, no force-push.
