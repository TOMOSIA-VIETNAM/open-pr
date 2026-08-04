# Review criteria — the layers, their precedence, and the baseline

4 layers. All load together; on conflict the higher one wins:

1. `notebooks/review/<repo>/ALWAYS_RULE.md` — the team's own rules, edited by hand. Read it exactly as
   authored, whatever shape it has taken; empty is normal and means the team has added nothing yet.
2. `notebooks/review/<repo>/memory.md` + each `memories/<lesson>.md` tagged with a stack in play. A
   REFERENCE line points at a path inside the reviewed repo — read that path, it is the live source.
3. `notebooks/review/<repo>/templates/<stack>.md` for every detected stack, plus overlays. FORBIDDEN:
   `${CLAUDE_PLUGIN_ROOT}/templates/` — the LOCAL copy is the one that counts.
4. The baseline below, owned by the plugin and therefore always current.

## Baseline — every PR, every stack

6 shared axes. A stack template contributes to the SAME axes, adding that stack's concrete instances
(APIs, idioms, tooling) — it never takes an axis over, except axis 5 which is entirely its own.
Illustrative, not a closed checklist: a real problem outside the list is still worth raising.

#### 1. Bugs & logic

- Obvious bug or logic error?
- Edge cases handled — empty/null/undefined, limits, empty collections?
- Every conditional branch and error path accounted for?
- New logic over stored rows — read/write path pre-exists (not added by this PR) && `baseRefName` = a
  PERMANENT branch of the repo, whatever this one names them (its trunk, a release or environment line),
  never one cut for a single change ⇒ first write PRESERVES what a row holds? old rows still read back?
  Schema untouched is the dangerous case: a field dropped from a write allowlist arrives absent ⇒ NULL
  over stored value. 🟠 max, evidence = 1 branch name; FORBIDDEN: claiming it is deployed.

#### 2. Security

- Hardcoded secrets: API key, token, password, connection string?
- Untrusted input reaching a query/command/eval/render without being checked?
- Authentication or authorization check missing on a sensitive action?

#### 3. Performance

- Repeated API/DB/subprocess/computation calls that could be cached or batched?
- Large datasets loaded whole where streaming or batching would do?

#### 4. Code quality

- Names clear and consistent with this project's convention?
- Duplicated code?
- Responsibilities separated, rather than one unit doing everything?
- Dead leftovers — commented-out block, unused branch/flag/import, or a comment or list item pointing
  at a TODO, task or plan that no longer exists?

#### 5. Framework/language specifics

- Owned entirely by the stack template — nothing generic belongs here.

#### 6. Maintainability & readability

- Comments where the logic is non-obvious?
- Comments state what the code does NOW — FORBIDDEN: narrating history ("was broken before", "changed
  because…"), a bug report and its fix, or a ticket id a future reader can't resolve?
- Tests added or updated, covering the happy path and the error path?
- Design leaves room for the next change?
