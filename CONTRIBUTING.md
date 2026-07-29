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

## Verify before opening a PR

```
pip install -r requirements-dev.txt   # once
scripts/check.sh main
```

That runs the test suite, the duplication scan and the context-cost report. The tests check reference
integrity, vendor parity, single-source config defaults, duplication across and inside files, and the
token ceilings.

If a scenario got cheaper, lock it in with `python3 scripts/token_report.py --base main
--update-budgets`. If one got more expensive, say so in the PR and explain why — and never trade away
a rule, a guard or a vendor entry to win tokens back.

Two tools for when you are looking for something specific:

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

Unit tests check the prompt graph as text; they cannot tell you whether a real review still comes out
right. `e2e/` holds a fixture with planted defects plus a checklist mapping each one to the code path it
exercises. `e2e/bootstrap.sh --pr <n>` puts that fixture on the shared `open-pr-test` repos, records the fixture
URL in your PR's description, and `--teardown` closes it afterwards. No write access to those repos?
Fork one and pass `--repo <your-fork>` — see `e2e/README.md`.

CI never runs it: it costs a real model call and posts to a real vendor.

## Commits

Conventional commits (`refactor(scope): …`). Once a PR has been reviewed, push follow-up work as new
commits — no amend, no squash, no force-push over what a reviewer already read.
