# Contributing

This plugin is markdown, not code. There is no build and no runtime — the "program" is a set of files
an agent reads in order. So the conventions below are about **what a file is allowed to contain** and
**how much context a run costs**.

`CLAUDE.md` is the agent guide for this repo. This page is the short version for a human.
Every interaction here follows the [Code of Conduct](./CODE_OF_CONDUCT.md).

## Where things go

Only `src/` ships to users. Everything else is repo-side.

| Directory | Holds | Loaded |
|---|---|---|
| `src/commands/` | the 4 slash commands | always (one per run) |
| `src/core/` | procedure shared by any run | always |
| `src/setup/` | per-repo provisioning (bootstrap, doctor, template, lesson) | first run / on schedule |
| `src/cases/` | branches behind a condition | only when that condition matched |
| `src/bin/open-pr.sh` | the deterministic runtime — every vendor/git mechanic | one script, vendor branches inside |
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
- **Context cost is tracked.** Every scenario has a ceiling in `tests/budgets.json`. Cheaper →
  lower ceilings; costlier for a correct fix → explain on the PR. Do not strip behaviour for budget.
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

- cheaper → lower ceilings (`token_report.py --base main --update-budgets`, or by hand if
  you had tightened them)
- more expensive → state which scenario and why in the PR; do not strip behaviour for budget

## Touched `src/bin/open-pr.sh`

```bash
python3 -m pytest tests/test_cli.py -q          # shims + real git fixtures
python3 scripts/vendor_lint.py                  # offline: flags vs the real CLIs
python3 scripts/vendor_lint.py --url <fixture>  # live, needs an open fixture PR
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
2. its mapping row in `src/bin/open-pr.sh`'s `stacks` subcommand (+ a case in `tests/test_cli.py`)
3. axis names 1/2/3/4/6 must match `src/core/review-criteria.md`

## Adding a vendor

1. branches in each subcommand of `src/bin/open-pr.sh` + its URL shape in `target`
2. fixtures in `tests/test_cli.py`; `src/reference/vendor-interface.md` maps the capabilities
3. no prompt changes

## Adding a config field

1. classify it in `src/reference/settings-schema.md`
2. read-time default in `src/core/repo-settings.md`
3. ask it in `src/setup/bootstrap.md`
4. `llm-upgrades/vN.md` + a line in `llm-upgrades/index.md`

## Commits

Conventional commits (`refactor(scope): …`). PR already reviewed → new commits only, no amend, no
squash, no force-push.

## Branches

`<type>/<short-description>` — `feat/submodule-review`, `fix/detach-head-after-checkout`,
`docs/readme-en-ja`. Never commit straight to `main`: it is what installs from the marketplace.

## Pull requests

1. Branch (or fork) → commit → push → PR against `main`, [template](./.github/PULL_REQUEST_TEMPLATE.md)
   filled in completely.
2. "How you tested" may not be empty. `scripts/check.sh` passing is the floor, not the proof — link the
   fixture PR you dogfooded against, or say how else you verified it.
3. Behaviour or architecture changed → update `CLAUDE.md`. Bootstrap UX or config changed → all three
   READMEs. New config field → the 4 steps above.
4. One purpose per PR. Changing behaviour *and* renaming files → two PRs; the review is far easier.

## Reporting bugs, requesting features

An [issue template](https://github.com/TOMOSIA-VIETNAM/open-pr/issues/new/choose) — blank issues are
off. For a bug: the exact command, the reviewed repo's stack, what the plugin did, what you expected.

## License

Contributing here releases your contribution under the [MIT License](./LICENSE).
