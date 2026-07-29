# CLAUDE.md

## Mission

Claude Code plugin `open-pr`. 3 slash commands, GitHub + GitLab (no Bitbucket yet):

- `/open-pr:review <PR_URL>` — review a PR/MR, learn that repo's conventions, post 1 review via the
  vendor's own CLI (`gh`/`glab`).
- `/open-pr:fix <PR_URL>` — read the findings review left, fix the code, 1 commit, reply on the PR.
  Edits real code at pwd.
- `/open-pr:update-plugin` — no PR. Migrate the CURRENT repo's local config to the latest
  `schema_version`, fetching `llm-upgrades/` live from this plugin's GitHub repo.

Everything is markdown + 1 JSON config. No build, no runtime. "Trying it" = install the plugin and
call it against a real PR.

## Structure

`src/` is the plugin root — `/plugin install` copies only `src/`. Repo-root files never ship.

```
src/commands/     entry points; ONLY these have frontmatter
src/core/         shared procedure any run may Read
src/setup/        per-repo provisioning: bootstrap, doctor, template, lesson
src/cases/        gated branches, read only when the caller's condition matched
src/vendors/<v>/  fetch | worktree | post | thread — same entry names on every vendor
src/templates/    per-stack criteria, cp'd into the reviewed repo
src/reference/    FORBIDDEN to Read at run time (schema + vendor contract, for humans)
src/seeds/        cp'd verbatim into the reviewed repo, never Read
llm-upgrades/     config migrations, fetched live, never packaged
scripts/          check.sh · token_report.py · dup_scan.py · vendor_lint.py · install_hooks.sh
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
- Imperative keywords carry the force (`MUST`, `NEVER`, `FORBIDDEN:` …). Drop softeners entirely.
- Drop articles, hedging, and any rationale that doesn't change what the agent does. State a reason
  only when the reason IS the rule, e.g. a value being attacker-controlled.
- Structure beats repetition: a branch set, field list or mapping becomes a table, never the same
  sentence shape restated per case.
- Symbols and emoji only when they carry meaning (severity 🔴🟠🔵📝), never as decoration.
- Verbatim and untouched: command lines, code fences, payload shapes, markers, error text the agent
  must print.
- Compression stops where ambiguity starts. Two readings possible ⇒ spend the tokens.
- Notation the HARNESS claims is off limits, whatever it would save: `` !`x` `` in a command body
  is auto-exec, so a `!` never touches a backtick — write the negation in words.

Exceptions, written as plain human prose: `README*.md`, `src/reference/`, `src/seeds/`.

**Split a file only when the split-off part is conditional.** An extra `Read` costs ~40-60 tokens;
splitting an always-loaded file into 2 always-loaded files is a pure loss.

**Callers never name a vendor.** They use `V§"<entry>"` (`src/core/pr-target.md` §3). A new vendor =
4 new files under `src/vendors/<name>/`, nothing else.

**Files must be self-contained.** No refs to task ids, plan phases, design-doc sections, or anything
that gets deleted. Inline the rule or point at a durable file.

**A seed belongs to the user once copied.** `src/seeds/*` is `cp`-ed into the reviewed repo and then
theirs — human prose only, no criteria, no config placeholders, and never `Read` back into context.
Baseline criteria live in `src/core/review-criteria.md`.

## Working loop

After ANY edit under `src/`. `scripts/check.sh <base-ref>` runs all three checks — suite, duplication
scan, context-cost report — and nothing is done until it passes.

Everything shipped under `src/` has a CI check: the markdown by the suite, the vendor commands by the
flag lint, the manifests by their own two tests. GitHub Actions is currently DISABLED on this repository
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
   threshold, a vendor entry name — and confirm each still has exactly one home.
6. **Lock in, then report.** Cheaper ⇒ `--update-budgets`. More expensive ⇒ **WARN the user
   explicitly**: which scenario, by how much, and why. Never present an increase as neutral.

| want | run |
|---|---|
| all three checks | `scripts/check.sh <base-ref>` |
| where the tokens sit inside a file | `token_report.py --sections 'commands/*.md'` |
| new ceilings after a win | `token_report.py --base <ref> --update-budgets` |
| duplication, harder than the gate | `dup_scan.py --window 10 --all --min-waste 20` |
| do the vendor flags exist | `vendor_lint.py` — offline, also in CI |
| do the vendor commands actually run | `vendor_lint.py --pr <n>` — needs an open e2e fixture |

**Suspect the measurement before the content** when a number moves the wrong way. A role whose
pre-refactor path went missing makes the base look cheaper than it was; counting a `cp`-ed seed as a
load overstates a run. Fix the model first, then judge the content.

**Dedupe between `review.md` and `fix.md` wins nothing per run** — only one of them ever loads. Do it
for single ownership, but never book it as a saving.
