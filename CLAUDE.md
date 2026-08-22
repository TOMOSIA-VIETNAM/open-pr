# CLAUDE.md

How an agent works in this repo. Orientation + durable invariants — not a ritual to game.

## Plugin

Claude Code plugin `open-pr`. Markdown + one JSON config. No build, no runtime. Only `src/` ships (`/plugin install` copies `src/`).

| command | does |
|---|---|
| `/open-pr:review <PR_URL>` | review PR/MR, learn repo conventions, post one review via vendor CLI (`gh`/`glab`) or REST/`curl` |
| `/open-pr:fix <PR_URL>` | read findings, edit real code at pwd, one commit, reply on the PR |
| `/open-pr:upgrade` | migrate this repo's config to latest `schema_version`; fetches `llm-upgrades/` live |
| `/open-pr:clean` | remove review worktrees after confirm. Never touches memory or config |
| `/open-pr:feedback` | turn this chat into one issue on this plugin's tracker (user-approved, de-identified) |

Vendors: GitHub, GitLab, Bitbucket.

## Layout

```
src/commands/     entry points; only these have frontmatter; each `disable-model-invocation: true`
src/core/         shared procedure
src/setup/        bootstrap, doctor, template, lesson
src/cases/        gated branches — Read only when the condition matches
src/vendors/<v>/  fetch | worktree | post | thread (same names on every vendor)
src/templates/    per-stack criteria, copied into the reviewed repo
src/reference/    schema + vendor contract — do not Read at run time
src/seeds/        copied verbatim into the reviewed repo — never Read back
llm-upgrades/     config migrations, fetched live, not packaged
adapters/         ROOT + tool-name map; sole file that names a non-Claude platform
skills/           one shim per command (Cursor · Codex · Gemini · Antigravity)
commands/*.toml   Gemini CLI entry format
install.sh        non-Claude install: clone → install-local.sh
scripts/          check.sh · token_report.py · dup_scan.py · vendor_lint.py · hooks · install-local.sh
tests/            test_prompt_graph.py · budgets.json · duplication_allowlist.json
e2e/              real-run fixture; never in CI
.claude/skills/   dev skills (`e2e-loop`)
.github/workflows ci.yml + hol-plugin-scanner.yml on PRs · e2e.yml manual
backlogs/         historical, not ops
```

## How to work

**Fix the real problem.** Keep a rule, guard, vendor entry, or severity when the product still needs it. Do not strip or reword solely to shrink a number or go green while behaviour drifts. Moving a conditional block into `cases/` (or its own atom) is fine — that is the intended load split, not a bypass.

**One owner per rule.** Prefer a single home; point elsewhere rather than restating. Allowed duplicates need `sha` + reason in `tests/duplication_allowlist.json`. `dup_scan.py` catches near-verbatim only.

**State what is true now**, once, where it belongs. No bolting a new clause beside the old one. No history ("used to…", "this broke when…").

**Short and clear.** In agent-read files (`src/commands/`, `core/`, `setup/`, `cases/`, `vendors/`, `templates/`, and this file): cut filler; prefer tables/maps over repeated sentence shapes. Cryptic text that the agent misreads costs more than the tokens you saved — two readings possible ⇒ write enough. Verbatim material is never compressed: command lines, fences, payload shapes, markers, printed error text. Human prose stays in `README*.md`, `src/reference/`, `src/seeds/`.

**Tokens are a priority, not a wall.** When cutting, prefer: drop a restatement (keep the owner) → move conditionals out of always-loaded files → table over repeated sentences → tighten prose. An extra `Read` is ~40–60 tokens; splitting an always-loaded file into two always-loaded files loses. Savings where every run loads beat occasional `cases/`. Deduping `review.md`↔`fix.md` is ownership hygiene, not a per-run win — only one loads each run.

**Harness trap:** in a command body, `!` never touches a backtick and never opens a fence (auto-exec) — write the negation in words. Emoji the plugin prints = one codepoint (no ZWJ / skin-tone).

## Hard edges (product breaks if ignored)

- **Stage by path touched.** Forbidden: `git add -A`, `git add .`, `git commit -a`.
- **Push only the branch you were given.** Never push or force-push `main` (UAT installs from it). Path into `main` is a PR. `token_chart.py --commit` squash-merges `chore/chart-<tag>` only when the diff is chart files, pwd is `main`, and `HEAD` = `origin/main`. Never `--force`.
- **One release, one `schema_version`.** Bump only when an existing repo's config needs transforming. On an unreleased branch, edit the pending `llm-upgrades/vN.md` — do not add a second. Config must not outrun the prompts that read it — `/open-pr:upgrade` refuses when the installed build is older than the index.
- **Callers never name a vendor.** Use `V§"<entry>"` (`src/core/pr-target.md` §3). New vendor = four files under `src/vendors/<name>/` + URL row in pr-target §1 + atoms/scenarios in `token_report.py`. No-CLI vendor also touches `scripts/vendor_lint.py` and `e2e/bootstrap.sh`. API gaps live in those four vendor files, never worked around in a caller.
- **Adapters carry no behaviour.** `adapters/`, `skills/`, `commands/*.toml` only resolve ROOT, map tools, delegate. Edit only for a new command or a platform manifest-schema change.
- **Files are self-contained.** No refs to task ids, plan phases, or docs that get deleted.
- **Seeds belong to the user after `cp`.** `src/seeds/*` is human prose; baseline criteria live in `src/core/review-criteria.md`.

## After edits under `src/`

```bash
scripts/check.sh <base-ref>
```

Run until green. The suite proves the graph still holds — not that a rule you touched survived; grep invariants when behaviour changed.

| want | run |
|---|---|
| all three checks | `scripts/check.sh <base-ref>` |
| tokens by section | `token_report.py --sections 'commands/*.md'` |
| per-scenario delta | `token_report.py --base <ref>` |
| refresh ceilings (none hand-tightened) | `token_report.py --base <ref> --update-budgets` |
| harder dup hunt | `dup_scan.py --window 10 --all --min-waste 20` |
| vendor flags offline | `vendor_lint.py` |
| vendor commands live | `vendor_lint.py --pr <n>` |

Cheaper → lower affected ceilings (by hand by the measured delta if you had tightened them; otherwise `--update-budgets` is fine). Costlier because the fix is correct → say which scenario / by how much / why on the PR. Never strip behaviour for budget.

Numbers move the wrong way: suspect the measurement first (missing path in base, a `cp`'d seed counted as a load). Fix the model, then judge the content.

Only actions owned by TOMOSIA-VIETNAM may be used, and only by tag — a `uses:` naming any
other owner, or pinning a SHA, fails the whole workflow at startup. Third-party tooling has to
run from a `run:` step instead. `scripts/install_hooks.sh` wires the same checks to pre-push.
