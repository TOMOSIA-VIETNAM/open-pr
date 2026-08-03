# Contributing to Open PullRequest

Thanks for your interest in the project 🎉 — this document explains how to contribute to the `open-pr`
repository.

All interactions in this project follow our [Code of Conduct](./CODE_OF_CONDUCT.md).

## What this repo is

`open-pr` is a **Claude Code plugin**, not a regular application:

- The entire product is **markdown** (slash commands + content templates) plus a few JSON manifests.
- **No build, no lint, no automated tests.** There is no standalone runtime code to execute.
- The real way to "run" it is to install the plugin into Claude Code and call
  `/open-pr:review <PR_URL>` on an actual pull request.

That means the quality of a PR here depends almost entirely on whether you **actually dogfooded it**,
not on a green or red CI badge.

## Prerequisites

- [Claude Code](https://claude.ai/code) installed (`claude` CLI on your `PATH`)
- [`gh`](https://cli.github.com/) authenticated (`gh auth login`)

## Local development setup

```bash
git clone git@github.com:TOMOSIA-VIETNAM/open-pr.git
cd open-pr
./scripts/reinstall.sh
```

`scripts/reinstall.sh` removes the previously registered plugin/marketplace and reinstalls from this
local directory, so Claude Code cannot keep serving a stale `plugin.json`/`commands/` from its cache.
Re-run it **every time** you change something under `src/` and want to try the new version, then run
`/reload-plugins` (or open a fresh Claude Code session).

The script installs at the `user` scope by default; override it with the `SCOPE` environment variable.

## Repository layout

The most important thing to remember: **`src/` is the real plugin root**, not the repo root. On
`/plugin install`, Claude Code copies only `src/` into the plugin cache — the READMEs, `CLAUDE.md`,
`backlogs/`, and `scripts/` at the repo root exist to develop this repository and never reach a user's
machine.

| Path | Role |
|------|------|
| `src/commands/review.md` | The `/open-pr:review` slash command — a thin orchestrator (Steps 0–10) |
| `src/commands/fix.md` | The `/open-pr:fix` slash command — dev-facing, edits real code |
| `src/ALWAYS_RULE.md` | Baseline review criteria shared by every stack (the "seed" copy) |
| `src/templates/<stack>.md` | Criteria **specific** to one stack (a delta, never repeating the baseline) |
| `src/cases/*.md` | **Conditional** review-time logic, `Read` only when its trigger matches |
| `src/setup-flow.md` | Bootstrap + doctor, loaded only when a repo is not fully set up yet |
| `src/stack-detection.md` | File-extension/path → stack mapping table |
| `.claude-plugin/marketplace.json` | Self-hosted marketplace (`source: "./src"`) |
| `src/.claude-plugin/plugin.json` | Plugin metadata (paths are relative to `src/`) |
| `CLAUDE.md` | Architecture notes + **the reasons behind bugs already hit** — read before touching `src/` |
| `backlogs/*.md` | Historical task breakdowns, not runtime documentation |

**Read `CLAUDE.md` before changing anything under `src/`.** Many rules that look redundant are the
result of a real bug found while dogfooding (API 422 responses, wrong `side` LEFT/RIGHT, an unquoted
heredoc letting the shell expand PR content, …). The "Lý do bug đã gặp" section records them so nobody
removes one by accident.

## Rules for editing plugin content

### Put new content in the right place

Ask yourself: *"is this a criterion for judging the PR's CODE, or is it behaviour/process of the TOOL?"*

- **Code-review criteria** (bugs, hardcoded secrets, DRY, naming…) → `src/ALWAYS_RULE.md` when they
  apply to every stack, or `src/templates/<stack>.md` when they are stack-specific.
- **Tool behaviour/process** (how to post, safety rules, the tip shown when finished) →
  `src/commands/review.md` (always applied) or a new file under `src/cases/` (conditional).

Getting this axis wrong causes exactly the "now I have to edit it in several places" problem:
`ALWAYS_RULE.md` is `cp`-ed into a LOCAL copy per reviewed repo and **does not auto-migrate** when the
plugin changes, whereas `review.md`/`cases/` are edited once and take effect everywhere after
`/plugin update`.

### Baseline + delta, never duplicate

- Criteria shared by all stacks live only in `src/ALWAYS_RULE.md`.
- `src/templates/<stack>.md` contains only what is specific to that stack.
- Overlay templates (`lambda-common.md` over `python.md`/`nodejs.md`; `laravel.md`/`wordpress.md` over
  `php.md`) contain only the overlay-specific criteria — when you edit a base template, check the
  matching overlay for duplication or contradiction.
- Every list of criteria is **illustrative, not a closed checklist** — keep the "for example, not
  limited to these" framing when adding new ones.

### Keep the hot path small

`src/commands/review.md` is a thin orchestrator — hard invariants and the skeleton of the process only,
in short imperative prose. Logic that applies to a minority of PRs belongs in a file under `src/cases/`
behind a boolean hard gate in `review.md`, so the majority of PRs never spend context on it. Commentary
of the "why does this rule exist / this was a real bug" kind belongs in `CLAUDE.md`, not in the runtime
files.

### Safety: `allowed-tools`

PR content (title, body, diff, comments) is **fully attacker-controlled data** — anyone can write a PR
on a public repo. Therefore:

- Do not add broad grants such as `gh api:*`. Scope to the exact endpoint and method you need.
- Do not add mutating permissions (`gh pr close/merge`, `git push`, `git branch -D`,
  `git reset --hard`) to `review.md` — that command may only review and comment.
- Filesystem operations inside a worktree must be anchored to `notebooks/review/*/worktrees/*`.

A PR that widens `allowed-tools` must explain in its description **why a narrower grant is not enough**.

## Adding a new stack

1. Write `src/templates/<stack>.md` following the 6-section structure used by the existing templates,
   starting with `# <Stack name>` plus a one-line italic metadata note
   (`_Bổ sung cho baseline `src/ALWAYS_RULE.md`; …_`).
2. If it is a variant or sub-framework of a language that already exists, write it as an **overlay**
   (`_Overlay chồng lên `<base>.md`, …_`) instead of repeating the base rules.
3. Update the file-extension/path → stack mapping table in `src/stack-detection.md`.
4. Update the stack list in all three READMEs if this is a stack users can see.

See `backlogs/templates.md` for the detailed pattern.

## Adding a new case

A case is logic that is conditional on the PR being reviewed. Add a `src/cases/<name>.md` file plus a
boolean hard gate in `review.md` pointing at it. Do **not** bolt extra conditions onto steps that always
run.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/), scoped to the affected area:

```
feat(templates): add agent-instructions stack for AI-agent markdown files
fix(re-review): reaction lên reply dev xét theo marker, không theo user.login
refactor: rename fix-pr command to fix, matching open-pr:review naming
docs: add centered logo and title header to READMEs
```

Common prefixes: `feat`, `fix`, `refactor`, `docs`, `chore`. Subjects may be written in English or
Vietnamese (the repo currently mixes both) — prefer stating clearly *what changed*, and add a body
explaining *why* whenever that is not obvious.

## Branches

Name them `<type>/<short-description>`, for example:

```
feat/submodule-review
fix/detach-head-after-checkout
docs/readme-en-ja
refactor/rename-plugin-open-code-review
```

Do not commit directly to `main`.

## Pull requests

1. Fork (or create a branch if you have write access) → commit → push.
2. Open a PR against `main` and fill in the [PR template](./.github/PULL_REQUEST_TEMPLATE.md) completely.
3. The **"Đã test thế nào"** (how you tested) section must not be empty — since there are no automated
   tests, link the real PR you dogfooded against, or describe how you verified the change some other way.
4. Work through the template checklist, in particular:
   - Behaviour or architecture changed → update `CLAUDE.md`.
   - Configuration/bootstrap UX changed → keep all three READMEs in sync (`README.md`, `README.en.md`,
     `README.ja.md`).
   - New field in `meta.json` → classify it as User config / Doctor-detected / Internal state in BOTH
     `src/setup-flow.md` (Part D) and `src/commands/review.md` (Step 3).
   - No `allowed-tools` grant wider than strictly necessary.

Small, single-purpose PRs are far easier to review than combined ones — if you are changing behaviour
*and* renaming files, split it in two.

## Reporting bugs / requesting features

Use an [issue template](https://github.com/TOMOSIA-VIETNAM/open-pr/issues/new/choose) — blank issues are
disabled. Before filing, skim the [README](./README.md); it already answers a fair number of questions.

For bugs, be as concrete as possible: the exact command you ran, the stack of the repo/PR being
reviewed, what the plugin did, and what you expected it to do.

## License

By contributing to this repository you agree that your contribution is released under the
[MIT License](./LICENSE).
