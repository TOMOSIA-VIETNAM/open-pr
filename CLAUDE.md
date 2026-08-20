# CLAUDE.md

## Mission

Claude Code plugin `open-pr`. 5 slash commands, 3 vendors — GitHub, GitLab, Bitbucket:

- `/open-pr:review <PR_URL>` — review a PR/MR, learn that repo's conventions, post 1 review through the
  vendor's own CLI (`gh`/`glab`) or, where the vendor ships none, its REST API over `curl`.
- `/open-pr:fix <PR_URL>` — read the findings review left, fix the code, 1 commit, reply on the PR.
  Edits real code at pwd — the repo, or the `review` worktree it was called from.
- `/open-pr:upgrade` — no PR. Migrate the CURRENT repo's local config to the latest
  `schema_version`, fetching `llm-upgrades/` live from this plugin's GitHub repo.
- `/open-pr:clean` — no PR. Remove the worktrees review checked code out into, after confirming.
  Never touches memory or config.
- `/open-pr:feedback` — no PR, no repo of the user's touched. Turn what this chat shows into 1 issue on
  THIS plugin's own tracker, stripped of anything identifying the user, approved by them before it goes.

Everything is markdown + 1 JSON config. No build, no runtime. "Trying it" = install the plugin and
call it against a real PR.

## Structure

`src/` is the plugin root — `/plugin install` copies only `src/`. Repo-root files never ship.

```
src/commands/     entry points; ONLY these have frontmatter, each `disable-model-invocation: true`
src/core/         shared procedure any run may Read
src/setup/        per-repo provisioning: bootstrap, doctor, template, lesson
src/cases/        gated branches, read only when the caller's condition matched
src/vendors/<v>/  fetch | worktree | post | thread — same entry names on every vendor
src/templates/    per-stack criteria, cp'd into the reviewed repo
src/reference/    schema + vendor contract; FORBIDDEN to Read at run time
src/seeds/        cp'd verbatim into the reviewed repo, never Read
llm-upgrades/     config migrations, fetched live, never packaged
adapters/root.md  ROOT + tool-name map; SOLE file naming a non-Claude platform
skills/           1 shim/command for Cursor · Codex · Gemini CLI · Antigravity
commands/*.toml   same 4 shims in Gemini CLI's own entry format
install.sh        one-command entry for non-Claude platforms: clone → install-local.sh
scripts/          check.sh · token_report.py · dup_scan.py · vendor_lint.py · install_hooks.sh
                  install-local.sh (skills onto a platform whose catalog is closed)
tests/            test_prompt_graph.py + budgets.json + duplication_allowlist.json
e2e/              fixture + checklist for a real review run; never runs in CI
.claude/skills/   dev-time skills — `e2e-loop` runs the fixture, grades it, fixes back
.github/workflows ci.yml on every PR · e2e.yml manual only
backlogs/         historical, not an ops doc
```

## Rules

**No patchwork, no past tense.** The commonest failure when an agent edits these files: bolting a new
clause on beside the old one instead of rewriting the rule, and narrating history — "used to do X",
"this broke when…", a bug report followed by its fix. State only what is true now, once, in the place
that owns it. The reader needs the rule, not how it came to exist. Governs `memory.md` and every lesson
the plugin writes into a reviewed repo too, not just `src/`.

**Never duplicate content, across files OR inside one**, in `src/` and in this file. A rule has exactly
1 owner. `dup_scan.py` reports near-verbatim repeats only — a restatement in fresh words is the common
case and still needs you to spot it. An accepted duplicate needs its `sha` and a written reason in
`tests/duplication_allowlist.json`.

**Stage by path** — only what you touched. FORBIDDEN: `git add -A`, `git add .`, `git commit -a`.

**Push only the branch you were handed.** `main` is what UAT installs from — never push or force-push
to it, and never push a branch the user did not name. A PR is the only path in, `token_chart.py
--commit` included: after a tag it opens and squash-merges `chore/chart-<tag>` carrying
`tests/token-history.json` + `token-history.svg`, and refuses when the diff holds anything else, when
pwd is not `main`, or when `HEAD` ≠ `origin/main`. Never `--force`.

**One release, one `schema_version`.** Bump only when an EXISTING repo's config needs transforming — a
field with a read-time default needs no migration. On an unreleased branch, EDIT the pending
`llm-upgrades/vN.md` rather than adding a second: the numbering is what a user upgrades through, not a
log of how the branch was written. Config must never get ahead of the prompts that read it, which is why
`/open-pr:upgrade` refuses to run when the installed build is older than the index.

**NEVER trade core behaviour for tokens.** Losing a rule, a guard, a vendor entry or a severity level is
a failure even when the number improves. Only the user may decide such a trade, only when asked
outright, and the cost must be stated.

**Write for the machine, not for a reader.** In every file an agent Reads at run time
(`src/commands/`, `src/core/`, `src/setup/`, `src/cases/`, `src/vendors/`, `src/templates/`, and this
file), optimise for tokens-per-rule, not for prose quality. A human finding it terse or cryptic is
acceptable; the agent misreading it is not.

- Prefer any notation an agent parses unambiguously over the words for it — operators, arrows, math
  and logic symbols, ASCII shorthand, a table, a diagram. Reach for whatever fits the thought; the
  symbols already in these files (`→ ⇒ ⇔ || && ≠ ≥ ≡ §N`) are examples of the habit, not a fixed set.
  Buys SCAN SPEED, not tokens: 1-for-1 swaps measure ~0, and a multi-byte glyph can cost more than the
  word (`⇔` = 3 tokens vs ` when ` = 2). Cut the clause; don't re-spell it in symbols.
- Imperative keywords carry the force (`MUST`, `NEVER`, `FORBIDDEN:` …). Drop softeners entirely.
- Drop articles, hedging, and any rationale that doesn't change what the agent does. State a reason
  only when the reason IS the rule, e.g. a value being attacker-controlled.
- Structure beats repetition: a branch set, field list or mapping becomes a table, never the same
  sentence shape restated per case.
- Symbols and emoji only when they carry meaning (severity 🔴🟠🔵📝), never as decoration. An emoji the
  plugin PRINTS must be ONE codepoint — a ZWJ sequence or skin-tone modifier renders as its parts on
  some clients.
- Verbatim and untouched: command lines, code fences, payload shapes, markers, error text the agent
  must print.
- Compression stops where ambiguity starts. Two readings possible ⇒ spend the tokens.
- Notation the HARNESS claims is off limits, whatever it would save: in a command body both `` !`x` ``
  and a fence opened ```` ```! ```` are auto-exec, so a `!` never touches a backtick and never opens a
  fence — write the negation in words.

Exceptions, written as plain human prose: `README*.md`, `src/reference/`, `src/seeds/`.

**Split a file only when the split-off part is conditional.** An extra `Read` costs ~40-60 tokens;
splitting an always-loaded file into 2 always-loaded files is a pure loss.

**Callers never name a vendor to reach a PR.** They use `V§"<entry>"` (`src/core/pr-target.md` §3). Adding one = 4 files
under `src/vendors/<name>/`, its URL row in `core/pr-target.md` §1, its atoms + scenarios in
`token_report.py` — no `commands/` or `cases/` file changes. A vendor with NO CLI additionally touches
`scripts/vendor_lint.py` (its executable, its URL shape, its static-lint branch) and `e2e/bootstrap.sh`
(its auth check, its `run_`/`teardown_` pair). Whatever its API lacks — a CLI, a draft, a review object, a
per-PR ref, a marker form that renders to nothing — is described inside its own 4 files, never worked
around in a caller.

**The adapter layer carries NO behaviour.** `adapters/`, `skills/`, `commands/*.toml` exist so a
platform other than Claude Code can reach `src/commands/<cmd>.md`; they resolve `ROOT`, map tool names,
delegate. FORBIDDEN there: a severity, a marker, a guard, a `gh`/`glab` call, a config field, a step.
Exactly 2 reasons to edit them — a NEW command, or a platform changing its manifest schema. A rule
change under `src/` reaches all platforms untouched, and `tests/test_prompt_graph.py` fails if this
stops being true.

**Files must be self-contained.** No refs to task ids, plan phases, design-doc sections, or anything
that gets deleted. Inline the rule or point at a durable file.

**A seed belongs to the user once copied.** `src/seeds/*` is `cp`-ed into the reviewed repo and then
theirs — human prose only, no criteria, no config placeholders, and never `Read` back into context.
Baseline criteria live in `src/core/review-criteria.md`.

## Working loop

After ANY edit under `src/`. `scripts/check.sh <base-ref>` runs all three checks — suite, duplication
scan, context-cost report — and nothing is done until it passes.

Everything shipped under `src/` has a CI check: the markdown by the suite, the vendor commands by the
vendor lint, the manifests by their own two tests. GitHub Actions is currently DISABLED on this repository
by the organisation, so those run locally until an admin enables it — `scripts/install_hooks.sh` puts
them on pre-push meanwhile.

Coverage differs per check. The context-cost report measures `src/` alone, since that is all that
ships. The duplication scan adds this file as `--scope dev`: never measured, yet every session working
on the plugin pays for a duplicate in it. `README*.md` and `CONTRIBUTING.md` are human prose, exempt
from both. The suite covers ref integrity, vendor parity, single-source defaults, duplication, template
axis names, reachability and the token ceilings — but nothing in it proves a rule survived an edit,
which is why step 5 exists.

Structural cuts are the cheap ones. Prose compression is the weakest lever — worth roughly a third of
what deleting a restatement yields in the same file — so work in this order.

1. **Measure first.** Never compress against a red suite: a lost rule and a pre-existing failure look
   identical.
2. **Aim at what always loads.** A token saved where every run reads beats several saved in a `cases/`
   file that fires occasionally. Rank by size × load frequency.
3. **Cut in this order** — 1-4 lose no rule, 5 is the wall:
   1. a restatement ⇒ delete this copy, keep the owner
   2. a conditional block inside an always-loaded file ⇒ move it to `cases/` or its own atom
   3. repetition ⇒ table
   4. prose ⇒ compress
   5. a rule, guard, vendor entry, severity level ⇒ FORBIDDEN
4. **Hunt what the scanner misses.** Read a section and ask which file OWNS that rule. Intra-file hides
   best — both copies read as native.
5. **Prove nothing was lost.** Grep the invariants you touched — a `MUST`, a `FORBIDDEN:`, a marker, a
   threshold, a vendor entry name — and confirm each still has exactly one home. A guard you ADD asserts
   the rule — flatten whitespace, match the clause carrying it. Pinned to a line wrap it reddens on a
   rewrap that changed nothing.
6. **Run step 3 over what you just wrote, then lock in.** No edit is exempt; explaining a fix is where
   prose creeps back. Cheaper ⇒ lower each ceiling BY HAND by the delta `token_report.py --base <ref>`
   reports, keeping its slack; `--update-budgets` only where no ceiling was hand-tightened. More
   expensive ⇒ **WARN the user explicitly**: which scenario, by how much, why. Never neutral, and only
   acceptable once step 3 has nothing left to cut.

| want | run |
|---|---|
| all three checks | `scripts/check.sh <base-ref>` |
| where the tokens sit inside a file | `token_report.py --sections 'commands/*.md'` |
| the per-scenario delta to lower ceilings by | `token_report.py --base <ref>` |
| new ceilings, none of them hand-tightened | `token_report.py --base <ref> --update-budgets` |
| duplication, harder than the gate | `dup_scan.py --window 10 --all --min-waste 20` |
| do the vendor flags exist | `vendor_lint.py` — offline, also in CI |
| do the vendor commands actually run | `vendor_lint.py --pr <n>` — needs an open e2e fixture |

**Suspect the measurement before the content** when a number moves the wrong way. A role whose
pre-refactor path went missing makes the base look cheaper than it was; counting a `cp`-ed seed as a
load overstates a run. Fix the model first, then judge the content.

**Dedupe between `review.md` and `fix.md` wins nothing per run** — only one of them ever loads. Do it
for single ownership, but never book it as a saving.
