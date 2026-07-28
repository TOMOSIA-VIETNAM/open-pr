# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mission

A Claude Code **plugin** named `open-pr`, providing three slash commands. Supports **GitHub and
GitLab** PRs/MRs (Bitbucket not yet supported — see `src/vendors/`).

- `/open-pr:review <PR_URL>` — reviews a GitHub or GitLab PR across multiple stacks, learns each
  reviewed repo's own conventions over time, and posts results directly on the PR via that vendor's
  own CLI/API (`gh api` for GitHub, `glab api` for GitLab).
- `/open-pr:fix <PR_URL>` — dev-facing. Reads the findings `/open-pr:review` left on a PR, fixes
  the code to match the project's convention, commits/pushes in a controlled way, and replies on
  the PR.
- `/open-pr:update-plugin` — dev-facing, no PR involved. Upgrades the CURRENT repo's local
  review/fix config to the plugin's latest schema by fetching migrations live from
  `llm-upgrades/index.md` in this plugin's own GitHub repo.

Both commands auto-detect which language to chat in (falls back to asking once, then remembers it
per repo) — independent from the language review comments themselves get posted in.

The whole plugin is markdown (command files + content templates) plus one JSON config file. There
is no build/lint/test and no standalone runtime code to run in isolation — "trying it" means
installing the plugin and calling `/open-pr:review <PR_URL>` for real against another repo.

## Features

### `/open-pr:review <PR_URL>`

- Reviews one or more GitHub or GitLab PRs (Bitbucket not yet supported). Multiple PR URLs in one
  invocation run sequentially in the same chat session, never as parallel subagents, so the agent
  can notice cross-PR relationships.
- Detects the stack of every changed file (Rails, Vue, React, Python, Node.js, Lambda, PHP,
  Laravel, WordPress, Shell, Makefile, or `agent-instructions`) and mixes stacks within one PR.
- Learns and reuses each repo's own coding convention: a per-repo local rule file, a per-repo
  memory of past lessons, and per-repo local copies of stack templates.
- Bootstraps a per-repo config on first use (output language, auto-submit, auto-resolve, doctor
  schedule, CI-failure handling, large-diff thresholds) and reuses it on every later review.
- Scans the target repo's own documented conventions (README/CLAUDE.md/AGENTS.md/docs/wiki/cursor
  or copilot rules) via a "doctor" pass — on first run, on a schedule, or on request — and records
  references to them instead of copying their content.
- Re-reviews a PR that already has past review comments: checks whether old findings got fixed,
  proposes new convention lessons from thread consensus (only after the user confirms in chat), and
  skips posting a redundant overview when a round produced nothing new.
- Cross-checks the PR description against the repo's own PR template checklist, when the repo has
  one.
- Detects a submodule pointer bump; if the main PR links a submodule PR, reviews that PR too and
  posts a second, separate review on it.
- Guards against oversized PRs: asks for a review strategy above a file-count threshold, and gives
  a limited classification peek (data/dump vs. real logic) to any file above a size threshold.
- Posts exactly one review (a summary body + inline line comments) via that vendor's own CLI/API
  (`gh api` for GitHub, `glab api` for GitLab), with findings labeled by severity (MUST FIX / SHOULD
  FIX / SUGGESTION / NOTE).
- Supports "reconfigure review" and "doctor again" at any time in chat, without waiting for the
  next review.

### `/open-pr:fix <PR_URL>`

- Reads the findings a previous `/open-pr:review` left on a PR — both inline LINE comments and
  FILE-level bullets inside a review body.
- Decides fix vs. decline per finding by severity; only asks the dev for low-severity items or for
  a high-severity finding the agent itself judges to be wrong.
- Edits the real code at the current working directory (no worktree) to match the project's
  learned convention, producing exactly one commit per run.
- Leaves the commit local by default; pushes only when the dev asks (or immediately if `auto_push`
  is enabled), and replies on the PR only after the code has actually reached the remote.
- Supports "reconfigure fix" at any time in chat, without waiting for the next run.

### `/open-pr:update-plugin`

- Takes no PR URL — operates on whichever repo the session's pwd is currently in.
- Reads that repo's local config `schema_version` checkpoint, fetches `llm-upgrades/index.md` live
  from `TOMOSIA-VIETNAM/open-pr`, and fetches every `vN.md` newer than the checkpoint in one batch.
- Applies the fetched migrations cumulatively and writes the new checkpoint — the only command with
  any notion of config schema versioning; `review.md`/`fix.md` never check or upgrade it themselves.

## Project structure

`src/` is the real plugin root (has its own `.claude-plugin/plugin.json`). `/plugin install` copies
only `src/` — READMEs, this file, `backlogs/`, and `scripts/` at the repo root never reach a user's
machine.

- `src/commands/review.md` — the `/open-pr:review` command.
- `src/commands/fix.md` — the `/open-pr:fix` command.
- `src/commands/update-plugin.md` — the `/open-pr:update-plugin` command: applies config migrations
  to the repo the user is currently in.
- `src/stack-detection.md` — file/path → stack mapping table.
- `src/setup-flow.md` — per-repo bootstrap/doctor flow, loaded only when needed.
- `src/cases/*.md` — conditional review-time logic, one file per case, hard-gated.
- `src/vendors/github.md` — every `gh`/`git` command `review.md`/`fix.md`/`cases/*.md` run against
  GitHub, gathered into 1 reference file (fetch PR context, checkout worktree, post/verify/submit a
  review, reply, resolve a thread, react...); no frontmatter, not a slash command. `review.md`/
  `fix.md`'s "Context" sections fetch via the real `Bash` tool too (not a `!`...`` auto-exec block
  anymore — see Rules below) so they `Read` this file like every other Step.
- `src/vendors/gitlab.md` — the SAME 19 entries as `github.md` (copied heading names verbatim, an
  interface both files share), but against `glab`/GitLab's REST API — Draft Notes + `bulk_publish`
  instead of a single review object, since that concept doesn't exist on GitLab (see the file's own
  "Post a review" entry). `review.md`/`fix.md`/`cases/*.md` never hardcode which of the 2 files to
  `Read` — they substitute `${CLAUDE_PLUGIN_ROOT}/vendors/<git_remote_type>.md` at the exact call
  site, `<git_remote_type>` resolved per-PR from the PR/MR URL's own shape (`setup-flow.md` Part D).
  Adding a 3rd vendor later = 1 new `src/vendors/<name>.md` with these same 19 headings, no change
  needed to `review.md`/`fix.md`/`cases/*.md`.
- `src/templates/*.md` — per-stack review criteria (source of truth; each repo keeps a local copy).
- `src/ALWAYS_RULE.md` — baseline review criteria seed, common to every stack.
- `.claude-plugin/marketplace.json`, `src/.claude-plugin/plugin.json` — plugin/marketplace manifests.
- `scripts/reinstall.sh` — dev script to reinstall the plugin locally.
- `backlogs/*.md` — historical task breakdowns from the initial build; temporary, not an ops doc.
- `llm-upgrades/index.md` (+ `llm-upgrades/vN.md`) — at the repo ROOT, NOT under `src/`: never
  packaged into `/plugin install`. `/open-pr:update-plugin` fetches it LIVE via `gh api` from
  `TOMOSIA-VIETNAM/open-pr` every time it runs; it is not a local file the plugin ships with. A
  machine-readable index of config `schema_version` migrations, not a human-facing changelog
  (GitHub Releases, drafted by the dev-only `.claude/commands/release-now.md`, cover that).
