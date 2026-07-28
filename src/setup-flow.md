# Setup flow — first-time setup for a repo

Not a slash command (lives outside `commands/`); `commands/review.md` `Read`s it when the repo's
setup isn't complete yet.

Every operation below runs at the EXACT current pwd of the session — where `/open-pr:review` was
invoked. FORBIDDEN: `cd` elsewhere, self-discovering "git root"/"the real repo directory", using
any directory's basename to infer path or repo name. Memory folder name `<repo>` ALWAYS = the
`<repo>` segment parsed from the PR URL (see `review.md` "Context"), never inferred from
pwd/subdirectory/git remote. Wherever you're standing, create it there — no exceptions.

Allowed tools: `Read`/`Write`/`Edit`, `git`/`cp`/`mkdir` (via Bash), `Agent` (Part C only —
parallel subagents scanning conventions). Use `cp` for a verbatim file copy (not Read+Write
through context — wastes tokens); `mkdir -p` to create directories.

## Part A — Bootstrap `notebooks/review/<repo>/`

1. `Write` `notebooks/review/<repo>/memory.md` — EMPTY index skeleton:
   ```
   <!-- Index. One entry per line, concise, no repeated words:
        - [tag] [short label](path) — a 1-line hook
        `path` points to memories/<slug>.md (a self-learned lesson, see Part E) OR directly to a
        path within the repo (a reference to the project's existing convention, see Part C —
        doctor; do NOT copy the content, just point to the path). Multiple tags if it applies to
        multiple stacks, e.g. [rails][ruby]. Keep each line under 1 sentence, merge duplicate
        points, don't restate "see the convention at..." — the link itself already says that. -->
   ```
2. `Write` `notebooks/review/<repo>/memories/.gitkeep` (empty) — materializes `memories/` (git
   doesn't track empty dirs).
3. `Write` `notebooks/review/<repo>/templates/.gitkeep` (empty) — will hold LOCAL stack template
   copies (Part B), create ahead of time.
4. `notebooks/review/.gitignore` (try `Read`) — a SEPARATE file for the nested git repo
   `notebooks/review/.git` (different from the main repo's `.gitignore`, step 8 below), needed so
   the ephemeral worktree (`review.md` Step 1, `notebooks/review/<repo>/worktrees/...`) NEVER
   leaks into this nested repo — it should only ever hold memory/template/rule content, never PR
   code under review:
   - Doesn't exist → `Write` a new file, exactly 1 line: `worktrees/`.
   - Exists but no `worktrees/` line yet (repo created before this rule existed) → `Edit` to
     append that line.
   - Already has it → skip.
5. `cp "${CLAUDE_PLUGIN_ROOT}/ALWAYS_RULE.md" "notebooks/review/<repo>/ALWAYS_RULE.md"` (NOT
   Read+Write through context). From now on `review.md` Step 5 reads THIS LOCAL COPY — the team
   can edit it directly for their project, no need to touch the plugin. The plugin's copy is just
   the default "seed" at bootstrap time.
6. Ask the user **6 or 7 questions in 1 bootstrap batch** (7th depends on CI, see q5) — use the
   built-in choice-Q&A feature if available (CRITICAL, `review.md`), each pre-marked with the
   recommended default below; feature caps questions per call (e.g. 4) ⇒ split into 2 SEQUENTIAL
   calls (q1-4, then q5-7, finish the first before the next). No such feature → ask naturally:
   1. output language — vi/en/ja.
   2. `auto_submit_review` true/false (default **false**).
   3. `auto_resolve_fixed_findings` true/false (default **false**).
   4. `doctor_schedule` — re-scan frequency (`{N} days`|`{N} weeks`|`{N} months`|`never`; default
      **`"1 months"`** if unchosen).
   5. `review_ci_status` true/false — ONLY ask WHEN the PR's "CI checks" array in Context is NOT
      empty (≥1 real check, passing or failing ⇒ CI is configured). Empty (no CI ran) → SKIP this
      question entirely (meaningless with nothing to compare against), auto-write `false`, no need
      to explain why in chat (obvious from context).
   6. `many_files_threshold` — file-change count above which review strategy gets asked before
      proceeding (default **`30`** if unchosen).
   7. `big_file_threshold_kb` — diff size per file (KB) above which it's a large/dump file
      (limited peek instead of detailed review; default **`20`** ≈ 5,000 tokens ≈ 4 chars/token,
      if unchosen).

   Handling answers:
   - **Language** → `Edit` the LOCAL copy from step 5: replace the exact token
     `{{OUTPUT_LANGUAGE}}` in the code fence with a concrete value (`English`/`Vietnamese`/
     `Japanese`...). FORBIDDEN: adding a language field to `settings.json` — `chat_language` is a
     DIFFERENT, independent field (Part D "Detected-once"), never touched here. "Already asked" =
     whether the placeholder is still there or replaced.
   - **`auto_submit_review`/`auto_resolve_fixed_findings`/`doctor_schedule`/`review_ci_status`/
     `many_files_threshold`/`big_file_threshold_kb`** → remember, write into `settings.json`'s
     `.review` node together with `bootstrapped: true` at step 9 (Part D schema). Missing/
     unparsable → `doctor_schedule` → `"1 months"`; `review_ci_status` not asked (no CI) →
     `false`; `many_files_threshold` → `30`; `big_file_threshold_kb` → `20`.
7. `notebooks/review/.git` already exists? (try `Read` `notebooks/review/.git/HEAD`):
   - **Doesn't exist** → `git init notebooks/review` — 1 nested git repo, fully independent from
     the main repo, encompassing EVERY `<repo>/` under it later. FORBIDDEN: setting a remote,
     pushing — local auto-commits only. Then `git -C notebooks/review add <repo>` (+ the
     `notebooks/review/.gitignore` from step 4 if applicable) then
     `git -C notebooks/review commit -m "chore: init review memory for <repo>"` — commit identity
     below.
   - **Already exists** (another repo already reviewed on this machine) → do NOT re-init. Just
     `git -C notebooks/review add <repo>` (+ `.gitignore` if step 4 just touched it) then
     `git -C notebooks/review commit -m "chore: add review memory for <repo>"`.

   **Commit identity** (applies to every commit into `notebooks/review/.git` — here + Part
   B/C/E): try `git config user.name`/`user.email` at pwd (the MAIN repo's root — `git config`
   without `--local`/`--global` resolves local-then-global, the exact priority needed). Result
   found → use it via
   `git -C notebooks/review -c user.name="<value>" -c user.email="<value>" commit -m "..."` (keep
   `-c` right AFTER `-C notebooks/review`, git's own required option order — FORBIDDEN:
   `-c` before `-C`). NEITHER project nor global config has any identity (commit errors) → ONLY
   THEN fall back to `-c user.name="review-plugin" -c user.email="review-plugin@local"`.
   FORBIDDEN: setting the machine's global config, ever.
8. `.gitignore` at pwd (`Read` `./.gitignore`):
   - Exists, no `notebooks/review/` line → `Edit` to append.
   - Doesn't exist → `Write` a new file, exactly 1 line: `notebooks/review/`.
9. Record into `notebooks/review/<repo>/settings.json`'s `.review` node (Part D full schema):
   `"bootstrapped": true`, `"auto_submit_review": <step 6>`,
   `"auto_resolve_fixed_findings": <step 6>`, `"doctor_schedule": "<step 6, default 1 months>"`,
   `"review_ci_status": <step 6 — PR has CI → asked, default true if unchosen; PR has no CI → not
   asked, write false directly>`, `"many_files_threshold": <step 6, default 30>`,
   `"big_file_threshold_kb": <step 6, default 20>`, + the `_comments` object (at minimum key
   `doctor_schedule` — hint text of valid values, for a human editing the file by hand; Part D).
   `review.md`/doctor/bootstrap IGNORE every key inside `_comments` (comment only, not runtime).

   **File doesn't exist yet** → `Write` fresh: top-level `"schema_version": 2` (plugin's current
   latest — bump this AND Part D's schema block on any future migration, since a brand-new repo
   bootstraps directly into the target shape, never needs its own migration) + the `.review` node
   above. FORBIDDEN: adding `.fix`/`.shared` yet — created later independently, by whichever of
   `/open-pr:fix`'s bootstrap (`fix.md` Step 2) or this `review.md`'s chat-language detection
   (Step 3) runs first.

   **File already exists** (an earlier `/open-pr:fix` run created it with just `.fix`, possibly
   `.shared.chat_language`) → `Edit` in place: keep `schema_version`/`.fix`/`.shared` untouched,
   only add/overwrite the `.review` node above.

## Part B — Copy/create a local template for the stack(s) present in the PR being reviewed

For EACH stack detected at `review.md` Step 2 NOT YET in `templates_copied` (array in
`settings.json`'s `.review` node, Part D):

1. `${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md` exists?
   - **Yes** → `cp` verbatim (NOT Read+Write through context — wastes tokens on a long file):
     `cp "${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md" "notebooks/review/<repo>/templates/<stack>.md"`
     (LOCAL copy; repo can edit its own version later without affecting the plugin's shared copy).
   - **No** (plugin doesn't cover this stack) → author a NEW template yourself following the exact
     6-item framework (1. Bugs & logic 2. Security 3. Performance 4. Code quality 5.
     Framework/language specifics 6. Maintainability & readability — refer to
     `${CLAUDE_PLUGIN_ROOT}/templates/` files for tone/detail consistency, don't repeat
     `ALWAYS_RULE.md` baseline criteria, write only the stack-specific part), save to
     `notebooks/review/<repo>/templates/<stack>.md`. Tell the user in chat a new template was
     authored, with a suggestion: manually copy it into `${CLAUDE_PLUGIN_ROOT}/templates/` to
     share with other repos — the plugin does NOT do this automatically (avoids mutating a shared
     file from 1 repo's review session).
2. Add `<stack>` to `templates_copied` in `settings.json`'s `.review` node.
3. `git -C notebooks/review add <repo>` + commit (local only).

## Part C — Doctor: discovering the project's existing conventions

Goal: project being reviewed already has its own convention/coding rules somewhere (README,
CLAUDE.md, AGENTS.md, docs/, wiki, cursor/copilot rules...) → the review must REFERENCE that exact
source, never guess or impose an unrelated external rule.

Doctor runs WHEN `doctored` isn't `true` yet, || `doctor_schedule` expired relative to
`doctored_at` (`review.md` Step 3), || the user asks to "doctor again". Every run MUST be
THOROUGH: scan the ENTIRE repo, not scoped to the current PR's stack/feature.

1. RECURSIVELY scan the entire repo tree at pwd (NOT just root) for EVERY convention source —
   real projects scatter multiple files across subfolders (e.g. `app/operation/AGENTS.md`,
   `app/serializers/AGENTS.md`, not just 1 root file). Look for: `README.md`, `CLAUDE.md`,
   `AGENTS.md`, `GEMINI.md` (+ similar agent-instruction-style `.md` variants), `docs/`, `wiki/`,
   `.cursorrules`/`.cursor/rules/`, `.github/copilot-instructions.md` — any subfolder. Missing
   source → skip, not an error.

   **Use `Agent` to run this IN PARALLEL for speed on large repos**: 1 subagent scans the whole
   tree (glob/grep) → LIST of convention-file paths;
   then MULTIPLE subagents in parallel (1 file or group each) read+summarize+surface
   conventions/conflicts — instead of the main agent reading sequentially (slow). No specific
   subagent type required — stays portable across environments with different subagent names.

   **Same scan pass (no separate step)** → also check the project's PR template — a DIFFERENT
   field from `project_docs_found` above, used at `review.md` Step 7 to cross-check the PR
   template checklist against the PR's real description. Check:
   `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`,
   `.github/PULL_REQUEST_TEMPLATE/*.md` (GitHub supports multiple, selected via query param),
   `PULL_REQUEST_TEMPLATE.md` (root), `docs/PULL_REQUEST_TEMPLATE.md`. Keep the paths that
   ACTUALLY exist (empty array if none) for step 5 below.
2. Each source found → read the parts relevant to coding convention/review criteria (skip product
   intro, install/deploy instructions).
3. FORBIDDEN: copying the content read into memory. Each source with a clear, non-conflicting
   convention → 1 REFERENCE line in `memory.md`, exact format from Part A's comment skeleton:
   `- [tag if identifiable] [short label](path) — a 1-line hook` — e.g.
   `- [rails] [Controllers](app/controllers/AGENTS.md) — thin, no params.permit`. Hook SHORT,
   condensing the main point, never repeating "see the project's convention at" (the link already
   says that). While reviewing, the agent re-reads that exact path when needed — never relies on
   a copy that may have gone stale.
4. **Conflict found** (2 sources disagree on the same issue, || 1 source contradicts/is ambiguous
   with itself, || a source conflicts with `ALWAYS_RULE.md`/template baseline) → reconcile with
   your own best judgment (prefer a source written specifically for convention/AI-agents —
   `CLAUDE.md`/`AGENTS.md` — over a general `README.md`; prefer specific/detailed over generic).
   Record the reconciled version as 1 lesson per Part E (authored yourself, not copied verbatim
   from either source), stating clearly which sources conflicted + why this direction was chosen.
   WHY exception: the ONE case a lesson logs WITHOUT the user's confirmation — agent authors it
   itself during doctor.
5. Record into `settings.json`'s `.review` node: `"doctored": true`,
   `"doctored_at": "<current date/time>"`,
   `"project_docs_found": [<paths from step 1, empty array if none>]`,
   `"pr_template_paths": [<PR template paths from step 1, empty array if none>]`. (Submodules have
   NO field here — `review.md` Step 1 item 5 checks `.gitmodules` directly every time, no caching
   via `settings.json`.)
6. `git -C notebooks/review add <repo>` + commit (local only) this change.

## Part D — `settings.json` schema

One shared file per repo, `notebooks/review/<repo>/settings.json` — split into 1 node per
feature. `review.md` ONLY reads/writes `.review` (+ `.shared` for `chat_language`); `fix.md` ONLY
reads/writes `.fix` (+ `.shared` for `chat_language`). Neither ever writes the other's node — this
invariant makes the `chat_language` dual-write bug-class (PR #19) structurally impossible, not
just patched.

```json
{
  "schema_version": 2,
  "shared": {
    "chat_language": "vi"
  },
  "review": {
    "bootstrapped": true,
    "doctored": true,
    "doctored_at": "2026-07-13T10:00:00Z",
    "doctor_schedule": "1 months",
    "project_docs_found": ["README.md", "CLAUDE.md"],
    "templates_copied": ["rails", "vue"],
    "auto_submit_review": false,
    "auto_resolve_fixed_findings": false,
    "pr_template_paths": [".github/PULL_REQUEST_TEMPLATE.md"],
    "review_ci_status": true,
    "many_files_threshold": 30,
    "big_file_threshold_kb": 20,
    "_comments": {
      "doctor_schedule": "Allowed: \"{N} days\" | \"{N} weeks\" | \"{N} months\" | \"never\". Examples: \"7 days\", \"2 weeks\", \"1 months\". Default: \"1 months\"."
    }
  },
  "fix": {
    "decline_needs_confirmation": true,
    "auto_push": false
  }
}
```

`schema_version` (top-level number): ONE checkpoint governing the WHOLE file, not per-node —
read/written ONLY by `/open-pr:update-plugin` (CLAUDE.md Rules). Fresh bootstrap (Part A, or
`fix.md` Step 2) writes it directly at the plugin's current latest value (`2` as of this schema) —
a brand-new repo starts already at the target shape, never needs its own migration. Neither
`review.md` nor `fix.md` ever reads/changes this field themselves.

`_comments` (object of strings, nested under `.review`): a note for whoever edits `settings.json`
by hand — NOT runtime config. `review.md`/doctor/bootstrap ignore every key inside it. Bootstrap
(Part A step 9) ALWAYS writes `.review._comments.doctor_schedule` with the exact sample text
above. Part C/`Edit` touching `.review` → keep `_comments` unchanged if already present.

**Field groups — classified by node + purpose, so new fields aren't miscategorized:**
- **User config, `.review` node** (Part A asks at bootstrap, changeable via "reconfigure review"):
  `auto_submit_review`, `auto_resolve_fixed_findings`, `doctor_schedule`, `review_ci_status`,
  `many_files_threshold`, `big_file_threshold_kb`. Missing on a repo bootstrapped before it
  existed → `review.md` Step 3 falls back to the listed default AT READ TIME ONLY, never writing
  it into the file (full detail lives in that Step 3, not repeated here) — upgrading the file
  itself is the sole job of `/open-pr:update-plugin` (CLAUDE.md Rules), never inline during a
  review/fix run.
- **User config, `.fix` node** (asked at `fix.md` Step 2's OWN bootstrap, NOT Part A — changeable
  via "reconfigure fix"): `decline_needs_confirmation`, `auto_push`. Same
  read-time-fallback/update-plugin-only-upgrade rule as above, owned by `fix.md` instead of
  `review.md`.
- **Doctor-detected, `.review` node** (Part C re-detects on its own schedule, not user-chosen):
  `project_docs_found`, `templates_copied`, `pr_template_paths`. Missing because doctor never
  ran/is due → just wait for Part C to run again — a DIFFERENT rule from User config above: a
  Doctor-detected field heals itself next doctor run, `/open-pr:update-plugin` never touches it.
- **Internal/system state, `.review` node** (the plugin's own state flags — not a setting, no
  "missing because outdated" concept): `bootstrapped`, `doctored`, `doctored_at`, `_comments`.
  Always written by Part A/C exactly when needed; no other rule applies.
- **Detected-once, `.shared` node** (not asked at Part A or `fix.md` Step 2, not a fixed default):
  `chat_language`. Detected on demand at `review.md` Step 3 OR `fix.md` Step 2 — whichever runs
  first for a given repo (chain: `ARGUMENTS` free text → this chat session's own language → this
  project's Claude Code memory, if any → OS locale → ask as last resort) → remembered into
  `.shared.chat_language`. Missing → run that detection, no fixed default to fall back to instead.
  Whichever command writes it first, the other reads that SAME value later, never
  re-detects/overwrites it.

**Adding a new field to this schema:** classify it IMMEDIATELY into exactly 1 of the 5 groups
above, right in this section. A **User config, `.review`** field → MUST ALSO be added to the
`.review` fields sentence at `review.md` Step 3 (SOLE place listing the in-memory default
`review.md` falls back to when a field is missing from an older repo's file) — keep the two places
in sync; adding here but forgetting there ⇒ an older repo has no fallback for that field until
`/open-pr:update-plugin` upgrades it. A **User config, `.fix`** field → the equivalent sentence
lives at `fix.md` Step 2 instead.

`review.md` treats bootstrap as done once `.review.bootstrapped: true`. Doctor: `.review.doctored:
true` && the schedule hasn't expired (`.review.doctor_schedule` + `.review.doctored_at`).
`.review.templates_copied` is checked separately each time (Part B) — a new stack can still get
its template copied after bootstrap/doctor are already done.

`doctor_schedule` (string): `{N} days` | `{N} weeks` | `{N} months` | `never`. Asked at bootstrap
(Part A step 6), default `"1 months"`. Field missing (old repo) → treat as `"1 months"`. `never` →
never re-runs doctor on a schedule (still runs on "doctor again" or when `doctored: false`).
Expired WHEN `now > doctored_at + schedule` (parse N+unit; missing/invalid `doctored_at` while
`doctored: true` → treat as expired, rerun Part C). Every successful Part C run → update
`doctored_at` (and `doctored: true`).

Submodules have NO dedicated field in `settings.json` — `review.md` Step 1 item 5 tries `Read`-ing
`<worktree>/.gitmodules` directly every time (no caching via `.review`), avoiding the gap where
the first PR of a new repo would skip submodule handling because doctor has never run.

`auto_submit_review`/`auto_resolve_fixed_findings`/`doctor_schedule` are asked + written at
bootstrap (Part A step 6/9). `review.md` Step 3 reads them back; used at Step 6/9 and the doctor
schedule gate.

`pr_template_paths` is written at doctor time (Part C step 1/5). `review.md` Step 3 reads it,
Step 7 uses it.

`review_ci_status` (boolean): ONLY ASKED at bootstrap (Part A step 6/9) WHEN the PR being
reviewed has ≥1 CI check ("CI checks" array in Context non-empty) — default `true` if unchosen; no
CI at all → NOT asked, write `false` directly (asking pointless). Field missing (old repo, not yet
upgraded) → `review.md` Step 3 falls back to the CURRENT run's CI-checks signal at read time (not
a hardcoded `true`), without writing anything back. `review.md` Step 3 reads it back; Step 7 uses
it to decide whether to raise a failing-CI warning (already fetched in Context) in the overview,
or skip entirely.

`many_files_threshold` (number): asked + written at bootstrap (Part A step 6/9), default `30`.
Missing or invalid (old repo) → treat as `30`. `review.md` Step 3 reads it back; Step 7 uses it in
the file-count guard (PR changing more files than threshold → ask about review strategy, unless
ARGUMENTS/chat already specified one).

`big_file_threshold_kb` (number): asked + written at bootstrap (Part A step 6/9), default `20`
(~5,000 tokens ≈ 4 chars/token — a rough reference conversion, not exact, depends on the real
tokenizer/language). Missing or invalid (old repo) → treat as `20`. `review.md` Step 3 reads it
back; Step 7 uses it in the size/dump guard (a file whose diff exceeds this threshold in KB, or
`UNKNOWN` → a limited peek to classify data/dump instead of a detailed line-by-line review).

## Part E — Logging 1 lesson into memory

Mechanical procedure shared by: thread consensus (Step 6 / `re-review.md` — AFTER the user
confirms in chat), a convention suggestion the user types in chat (`review.md` Step 10 — log
immediately, no re-confirmation), and a conflict reconciled in Part C (no confirmation needed).
Part E only describes the write operation itself.

1. Create `notebooks/review/<repo>/memories/<lesson-slug>.md` (short kebab-case slug, no
   meaningless sequence numbers). Minimum content: description of the convention; before/after
   code example (if any); stack tag; date logged; source (link to the related PR if any).
2. Add 1 line to `notebooks/review/<repo>/memory.md`'s index, exact format from Part A's comment
   skeleton: `- [stack-tag] [short label](memories/<lesson-slug>.md) — a 1-line hook` (multiple
   tags if it applies to multiple stacks). Hook concise, no repeated words, no lengthy explanation
   — detail lives in the `memories/<lesson-slug>.md` file, the index only needs enough to
   recognize what the lesson is.
3. `git -C notebooks/review add <repo>` + commit (local only, no push; commit errors about a
   missing `user.name`/`user.email` → use the `-c` flags as in Part A).

## When the user asks to "doctor again" / "rescan the project's conventions"

Change `doctored` in `settings.json`'s `.review` node to `false` (or delete the field entirely)
then redo Part C. Can be done right in chat, no need to wait for the next `/open-pr:review` run.
