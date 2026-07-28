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
scripts/          token_report.py
tests/            test_prompt_graph.py + budgets.json + duplication_allowlist.json
backlogs/         historical, not an ops doc
```

## Rules

**Token budget is a hard rule.** After ANY edit under `src/`, run:

```
python3 scripts/token_report.py --base <branch-before-the-change>
```

- went DOWN → good, lower the ceilings in `tests/budgets.json` to the new numbers
- went UP → **WARN the user explicitly**, state which scenario grew, by how much, and WHY. Never
  present an increase as neutral. Only acceptable when the increase buys something named and the
  user agrees; otherwise revert.
- NEVER trade away core behaviour for tokens. Losing a rule, a guard, a vendor entry or a severity
  level is a failure even if the number improves.

**Run the tests before saying done:** `python3 -m pytest tests/ -q`. They enforce ref integrity,
vendor-entry parity across vendors, single-source-of-truth for config defaults, cross-file
duplication, axis names, reachability, and the token ceilings.

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

**Never duplicate content across files.** A rule has exactly 1 owner. Accepted exceptions live in
`tests/duplication_allowlist.json` with a written reason.

**Split a file only when the split-off part is conditional.** An extra `Read` costs ~40-60 tokens;
splitting an always-loaded file into 2 always-loaded files is a pure loss.

**Callers never name a vendor.** They use `V§"<entry>"` (`src/core/pr-target.md` §3). A new vendor =
4 new files under `src/vendors/<name>/`, nothing else.

**Files must be self-contained.** No refs to task ids, plan phases, design-doc sections, or anything
that gets deleted. Inline the rule or point at a durable file.

**A seed belongs to the user once copied.** `src/seeds/*` is `cp`-ed into the reviewed repo and then
theirs — human prose only, no criteria, no config placeholders, and never `Read` back into context.
Baseline criteria live in `src/core/review-criteria.md`.
