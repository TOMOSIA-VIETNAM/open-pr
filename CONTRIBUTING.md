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

## Workflow

Setup, once:

```
pip install -r requirements-dev.txt
scripts/install_hooks.sh              # the checks below, on pre-push
```

Then, per change:

| when | run | catches |
|---|---|---|
| every edit under `src/` | `scripts/check.sh <base-ref>` | broken refs, duplication, a rule with two owners, a token-budget regression |
| touched `src/vendors/` | `scripts/vendor_lint.py --pr <n>` | a flag the CLI does not have, a moved endpoint, a jq path matching nothing |
| before merging a substantial change | `/e2e-loop --pr <n>` in a FRESH session | the review itself behaving differently — nothing above can see that |
| after the e2e round | `e2e/bootstrap.sh --pr <n> --teardown` | — |

Only the first row is mandatory. `check.sh <base-ref> <pr>` folds the second in when a fixture is open.

Actions is disabled on this repository by the organisation, so `.github/workflows/` does not run yet;
the pre-push hook is what enforces this meanwhile.

**Reading the token report.** Cheaper ⇒ lock it in with `token_report.py --base <ref> --update-budgets`.
More expensive ⇒ say so in the PR and why. Never trade away a rule, a guard or a vendor entry to win
tokens back.

When you need to aim rather than gate:

```
python3 scripts/token_report.py --sections 'commands/*.md'    # where the tokens sit in a file
python3 scripts/dup_scan.py --window 10 --all --min-waste 20  # duplication, harder than the gate
```

## Common changes

- **New stack** — add `src/templates/<stack>.md` and a row in `src/core/stack-detection.md`. Every
  bullet must name a concrete API, idiom or tool of that stack; generic criteria already live in
  `src/core/review-criteria.md`.
- **New vendor** — add `src/vendors/<name>/{fetch,worktree,post,thread}.md` with the same entry
  headings the existing vendors use (`src/reference/vendor-interface.md` lists them). No caller
  changes.
- **New config field** — classify it in `src/reference/settings-schema.md`, add its read-time default
  to `src/core/repo-settings.md`, and add an `llm-upgrades/vN.md` migration plus an index line so
  existing repos catch up.

## End-to-end

`e2e/` holds a fixture with planted defects and a checklist mapping each one to the code path it
exercises, so a miss names the rule that regressed. `bootstrap.sh` puts it on the shared `open-pr-test`
repos and records the fixture URL in your PR's description as the record of the run. No write access
there? Fork one and pass `--repo <your-fork>` — see `e2e/README.md`.

CI never runs it: it costs a real model call and posts to a real vendor.

Touched a `src/vendors/` entry? `python3 scripts/vendor_lint.py` checks every flag in every entry
against that subcommand's own `--help`. Offline and free, it runs in CI, and it covers the post/thread
entries too. Add `--pr <n>` and it also executes the read-only Fetch entries against the open fixture —
that half needs a token, so CI leaves it out.

Working with an agent? The `e2e-loop` skill drives that whole cycle — fixture, review, grading by a
second independent agent, diagnosis back to the prompt file that owns the rule — instead of you running
each step by hand.

## Commits

Conventional commits (`refactor(scope): …`). Once a PR has been reviewed, push follow-up work as new
commits — no amend, no squash, no force-push over what a reviewer already read.
