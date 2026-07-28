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
call it against a real PR. The only automated checks are `tests/` (static invariants, see below).

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
scripts/          check.sh · token_report.py · dup_scan.py
tests/            test_prompt_graph.py + budgets.json + duplication_allowlist.json
backlogs/         historical, not an ops doc
```

## Rules

**Token budget is a hard rule.** After ANY edit under `src/`, run `scripts/check.sh <base-ref>` — the
tests, the duplication scan and the context-cost report in one pass.

- went DOWN → good, `token_report.py --base <ref> --update-budgets` locks in the new ceilings
- went UP → **WARN the user explicitly**, state which scenario grew, by how much, and WHY. Never
  present an increase as neutral. Only acceptable when the increase buys something named and the
  user agrees; otherwise revert.
- NEVER trade away core behaviour for tokens. Losing a rule, a guard, a vendor entry or a severity
  level is a failure even if the number improves.

**Nothing is done until `scripts/check.sh` passes.** The suite enforces ref integrity, vendor-entry
parity, single-source config defaults, duplication both across and inside files, template axis names,
reachability from a command, and the token ceilings.

| want | run |
|---|---|
| where the tokens sit inside a file | `token_report.py --sections 'commands/*.md'` |
| hunt duplication harder than the gate | `dup_scan.py --window 10 --all --min-waste 20` |
| accept a duplicate | its `sha` + a reason in `tests/duplication_allowlist.json` |

## Compressing without losing quality

Structural cuts are the cheap ones; prose compression is the weakest lever, worth roughly a third of
what deleting a restatement yields in the same file. So work in this order.

1. **Measure first.** `scripts/check.sh <base-ref>`. Never compress against a red suite — a lost rule
   and a pre-existing failure look identical.
2. **Aim at what always loads.** `token_report.py --sections '<glob>'`. A token saved in a file every
   run reads is worth many saved in a `cases/` file that fires occasionally. Rank by size × load
   frequency.
3. **Cut in this order.** Everything above step 5 is free of rule loss:
   1. a restatement — another file or section already owns that rule ⇒ delete this copy
   2. a conditional block inside an always-loaded file ⇒ move it to `cases/` or its own atom
   3. the same sentence shape repeated per case ⇒ one table
   4. prose: articles, hedging, rationale that changes no behaviour ⇒ compress
   5. a rule, a guard, a vendor entry, a severity level ⇒ FORBIDDEN. Only the user decides that, only
      when asked outright, and the trade must be stated.
4. **Hunt the restatements the scanner cannot see.** `dup_scan.py --window 10 --all --min-waste 20`
   reports near-verbatim repeats. The valuable kind is reworded: read a section and ask which file OWNS
   this rule. Intra-file is the easiest to miss — both copies read as native.
5. **Prove nothing was lost.** The suite covers refs, parity, defaults and ceilings; it does NOT prove
   a rule survived an edit. Grep the invariants you touched — a `MUST`, a `FORBIDDEN:`, a marker, a
   threshold, a vendor entry name — and confirm each still has exactly one home.
6. **Lock in, then report.** `token_report.py --base <ref> --update-budgets`, then state the
   per-scenario numbers. An increase gets the warning above, never a shrug.

**Suspect the measurement before the content** when a number moves the wrong way. A role whose
pre-refactor path went missing makes the base look cheaper than it was; counting a `cp`-ed seed as a
load overstates a run. Fix the model first, then judge the content.

**Dedupe between `review.md` and `fix.md` wins nothing per run** — only one of them ever loads. Do it
for single ownership, but never book it as a saving.

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

Exceptions, written as plain human prose: `README*.md`, `src/reference/`, `src/seeds/`.

**No patchwork, no past tense.** The commonest failure when an agent edits these files: bolting a new
clause on beside the old one instead of rewriting the rule, and narrating history — "used to do X",
"this broke when…", a bug report followed by its fix, a note about a past decision. State only what is
true now, once, in the place that owns it. The reader needs the rule, not how it came to exist. This
governs `memory.md` and every lesson the plugin writes into a reviewed repo too, not just `src/`.

**Never duplicate content, across files OR inside one.** A rule has exactly 1 owner. `dup_scan.py`
catches near-verbatim repeats only — a restatement in fresh words is the common case and still needs
you to spot it.

**Split a file only when the split-off part is conditional.** An extra `Read` costs ~40-60 tokens;
splitting an always-loaded file into 2 always-loaded files is a pure loss.

**Callers never name a vendor.** They use `V§"<entry>"` (`src/core/pr-target.md` §3). A new vendor =
4 new files under `src/vendors/<name>/`, nothing else.

**Files must be self-contained.** No refs to task ids, plan phases, design-doc sections, or anything
that gets deleted. Inline the rule or point at a durable file.

**A seed belongs to the user once copied.** `src/seeds/*` is `cp`-ed into the reviewed repo and then
theirs — human prose only, no criteria, no config placeholders, and never `Read` back into context.
Baseline criteria live in `src/core/review-criteria.md`.
