# Setup flow — first-time setup for a repo

Not a slash command (lives outside `commands/`); `commands/review.md` loads it via `Read` when the
repo's setup isn't complete yet.

Every operation below runs at the **EXACT current pwd of the session** — the directory where
`/open-pr:review` was invoked. ABSOLUTELY do NOT `cd` elsewhere, do NOT self-discover the "git
root"/"the real repo directory", do NOT use any directory's basename to infer a path or repo name.
The memory folder name `<repo>` is ALWAYS the `<repo>` segment parsed from the PR URL (see the
"Context" block of `review.md`), never inferred from pwd/subdirectory/git remote. Wherever you're
standing, create it there — no exceptions.

Allowed tools: `Read`/`Write`/`Edit`, `git`/`cp`/`mkdir` (via Bash), and `Agent` (Part C only —
spawning subagents to scan conventions in parallel). Use `cp` to copy a file verbatim (not
Read+Write through context — wastes tokens); `mkdir -p` to create directories.

## Part A — Bootstrap `notebooks/review/<repo>/`

1. `Write` to create `notebooks/review/<repo>/memory.md` — an EMPTY index skeleton:
   ```
   <!-- Index. One entry per line, concise, no repeated words:
        - [tag] [short label](path) — a 1-line hook
        `path` points to memories/<slug>.md (a self-learned lesson, see Part E) OR directly to a
        path within the repo (a reference to the project's existing convention, see Part C —
        doctor; do NOT copy the content, just point to the path). Multiple tags if it applies to
        multiple stacks, e.g. [rails][ruby]. Keep each line under 1 sentence, merge duplicate
        points, don't restate "see the convention at..." — the link itself already says that. -->
   ```
2. `Write` to create `notebooks/review/<repo>/memories/.gitkeep` (empty) — just to materialize the
   `memories/` directory (git doesn't track empty directories).
3. `Write` to create `notebooks/review/<repo>/templates/.gitkeep` (empty) — this directory will
   hold LOCAL copies of the stack template(s) used in the repo (see Part B), create the directory
   ahead of time.
4. Check whether `notebooks/review/.gitignore` already exists (try `Read`) — a SEPARATE file
   belonging to the nested git repo `notebooks/review/.git` (different from the main repo's
   `.gitignore` in step 8 below), needed so the ephemeral worktree holding the checked-out PR code
   (`review.md` Step 1, under `notebooks/review/<repo>/worktrees/...`) NEVER leaks into this
   nested git repo — the nested repo should only ever contain memory/template/rule content, not
   the PR code under review:
   - Doesn't exist yet → `Write` a new `notebooks/review/.gitignore` containing exactly 1 line:
     `worktrees/`.
   - Exists but does NOT yet have a `worktrees/` line (the nested repo may have been created before
     this rule existed) → `Edit` to append that line.
   - Already has it → skip.
5. Copy `ALWAYS_RULE.md` from the plugin into the repo's LOCAL copy using `cp` (NOT Read+Write
   through context): `cp "${CLAUDE_PLUGIN_ROOT}/ALWAYS_RULE.md" "notebooks/review/<repo>/ALWAYS_RULE.md"`.
   From now on `review.md` (Step 5) reads THIS LOCAL COPY — the team can open/edit it directly
   within their own repo for their project, no need to touch the plugin itself. The plugin's copy
   is just the default "seed" used at bootstrap time.
6. Ask the user **6 or 7 questions in 1 bootstrap batch** (depending on whether CI exists — see
   question 5) — use the agent's built-in choice-based Q&A feature if available (see CRITICAL in
   `review.md`), each question pre-marked with the recommended choice matching the default value
   listed below; that feature caps the number of questions per call (e.g. max 4) → split into 2
   sequential calls (questions 1-4, then 5-7, finishing the first call before making the next). No
   such feature available → ask naturally via chat: (1) output language — vi/en/ja; (2)
   `auto_submit_review` true/false (default **false**); (3) `auto_resolve_fixed_findings`
   true/false (default **false**); (4) `doctor_schedule` — how often to re-scan conventions
   (`{N} days` | `{N} weeks` | `{N} months` | `never`; default **`1 months`** if the user doesn't
   choose); (5) `review_ci_status` true/false — **ONLY ask this if the "CI checks" array in the
   Context of the PR being reviewed is NOT empty** (this repo/PR has at least 1 real check,
   whether passing or failing — meaning CI is configured); that array is EMPTY (no CI ran on this
   PR at all) → **skip this question entirely** (asking would be meaningless with nothing to
   compare against), auto-write `false`, no need to explain why in chat (it's obvious from
   context); (6) `many_files_threshold` — file-change count above which review strategy gets asked
   before proceeding (default **`30`** if the user doesn't choose); (7) `big_file_threshold_kb` —
   diff size per file (KB) above which it's treated as a large/dump file, a limited peek instead
   of a detailed review (default **`20`** ~ 5,000 tokens, estimated at ~4 characters/token, if the
   user doesn't choose). Handling the answers:
   - **Language** → `Edit` the LOCAL copy just made in step 5: replace the exact token
     `{{OUTPUT_LANGUAGE}}` in the code fence block with a concrete value (`English` /
     `Vietnamese` / `Japanese`, ...). Do NOT add a language field to `meta.json`. "Already asked" =
     whether the placeholder is still there or has been replaced.
   - **`auto_submit_review` / `auto_resolve_fixed_findings` / `doctor_schedule` /
     `review_ci_status` / `many_files_threshold` / `big_file_threshold_kb`** → remember them, write
     into `meta.json` together with `bootstrapped: true` in step 9 (Part D schema).
     `doctor_schedule` missing or unparsable → write `"1 months"`; `review_ci_status` NOT asked
     (question 5 skipped because there's no CI) → write `false`; `many_files_threshold`
     missing/unparsable as a number → write `30`; `big_file_threshold_kb` missing/unparsable as a
     number → write `20`.
7. Check whether `notebooks/review/.git` already exists (try `Read`-ing the file
   `notebooks/review/.git/HEAD`):
   - **Doesn't exist yet** → `git init notebooks/review` — a SINGLE nested git repo, fully
     independent from the main repo being reviewed, encompassing EVERY `<repo>/` that will exist
     under it later. ABSOLUTELY do NOT set a remote, do NOT push — local auto-commits only. Then
     `git -C notebooks/review add <repo>` (including the `notebooks/review/.gitignore` just
     created in step 4 if applicable) then
     `git -C notebooks/review commit -m "chore: init review memory for <repo>"`
     — see how to determine `user.name`/`user.email` for this commit right below.
   - **Already exists** (some other repo was already reviewed on this machine) → do NOT re-init.
     Just `git -C notebooks/review add <repo>` (including `notebooks/review/.gitignore` if step 4
     just created/edited it) then
     `git -C notebooks/review commit -m "chore: add review memory for <repo>"`.

   **Commit identity** (applies to every commit into `notebooks/review/.git`, here and in Part
   B/C/E): try `git config user.name` / `git config user.email` at pwd (the root of the MAIN repo
   being reviewed — `git config` without `--local`/`--global` resolves local (project) first then
   global, the exact priority order needed here). If it returns a result → use that value for the
   commit into `notebooks/review/.git` via the flags `-c user.name="<value>" -c user.email="<value>"`
   placed IMMEDIATELY AFTER `-C notebooks/review` (i.e.
   `git -C notebooks/review -c user.name="..." -c user.email="..." commit -m "..."` — keep this
   exact order to match `allowed-tools`, do NOT put `-c` before `-C`). If NEITHER the project NOR
   global config has any `user.name`/`user.email` at all (commit errors about a missing identity)
   → only then fall back to
   `-c user.name="review-plugin" -c user.email="review-plugin@local"`. Never set the machine's
   global config under any circumstance.
8. Check `.gitignore` at the current pwd (`Read` at `./.gitignore`):
   - Exists and does NOT yet have a `notebooks/review/` line → `Edit` to append that line.
   - No `.gitignore` yet → `Write` a new one containing exactly 1 line: `notebooks/review/`.
9. Record into `notebooks/review/<repo>/meta.json` (create the file if it doesn't exist, keep
   every other field untouched if the file already existed — see Part D): `"bootstrapped": true`,
   `"auto_submit_review": <step 6>`, `"auto_resolve_fixed_findings": <step 6>`,
   `"doctor_schedule": "<step 6, default 1 months>"`,
   `"review_ci_status": <step 6 — PR has CI → asked, default true if the user didn't choose; PR has
   no CI → not asked, write false directly>`,
   `"many_files_threshold": <step 6, default 30>`, `"big_file_threshold_kb": <step 6, default 20>`,
   and the `_comments` object (at minimum the key
   `doctor_schedule` — hint text listing valid values, for a user editing the file by hand; see
   Part D). The runtime/`review.md` **ignores** every key inside `_comments` (it's purely a
   comment for human readers).

## Part B — Copy/create a local template for the stack(s) present in the PR being reviewed

For EACH stack detected at Step 2 of `review.md` that is NOT YET in `templates_copied` (an array in
`meta.json`, see Part D):

1. Check whether `${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md` exists (does the plugin already have
   a template for this stack).
   - **Already exists** → copy it verbatim with `cp` (NOT Read+Write through context — wastes
     tokens on a long file):
     `cp "${CLAUDE_PLUGIN_ROOT}/templates/<stack>.md" "notebooks/review/<repo>/templates/<stack>.md"`
     (the LOCAL copy; the repo can edit its own version later without affecting the plugin's
     shared copy used by other repos).
   - **Not available yet** (the plugin doesn't cover this stack) → author a NEW template yourself
     following the exact 6-item framework (1. Bugs & logic 2. Security 3. Performance 4. Code
     quality 5. Framework/language specifics 6. Maintainability & readability — refer to the files
     in `${CLAUDE_PLUGIN_ROOT}/templates/` to keep tone/level of detail consistent, do NOT repeat
     criteria already covered in the `ALWAYS_RULE.md` baseline, write only the stack-specific
     part), save it to `notebooks/review/<repo>/templates/<stack>.md`. Tell the user in chat that
     a new template was authored for this stack, along with a suggestion: the user can manually
     copy this file into `${CLAUDE_PLUGIN_ROOT}/templates/` to share it with other repos — the
     plugin does NOT do this automatically (to avoid mutating a shared file from a single repo's
     review session).
2. Add `<stack>` to the `templates_copied` array in `meta.json`.
3. `git -C notebooks/review add <repo>` + commit (local only) this change.

## Part C — Doctor: discovering the project's existing conventions

Goal: if the project being reviewed has already defined its own convention/coding rules somewhere
(README, CLAUDE.md, AGENTS.md, docs/, wiki, cursor/copilot rules...), the review must REFERENCE
that exact source instead of guessing or imposing an unrelated external rule.

Doctor runs when `doctored` isn't `true` yet, **or** the `doctor_schedule` has expired relative to
`doctored_at` (see `review.md` Step 3), **or** the user proactively asks to "doctor again". Every
run must be THOROUGH: scan the ENTIRE repo, not scoped to the current PR's stack/feature.

1. **RECURSIVELY scan the entire repo directory tree at pwd** (NOT just the root) to find EVERY
   convention source — real projects often scatter multiple files across subfolders, e.g.
   `app/operation/AGENTS.md`, `app/serializers/AGENTS.md`, not just one root file. Look for:
   `README.md`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` (and similar agent-instruction-style `.md`
   variants), a `docs/` folder, `wiki/`, `.cursorrules` / `.cursor/rules/`,
   `.github/copilot-instructions.md` — regardless of which subfolder they're in. Skip sources that
   don't exist, don't treat that as an error.
   **Use `Agent` to run this IN PARALLEL for speed on large repos** (already present in
   `review.md`'s `allowed-tools`): 1 subagent scans the whole directory tree (glob/grep) and
   returns a LIST of convention-file paths; then spawn MULTIPLE subagents in parallel (each
   handling 1 file or 1 group of files) to read + summarize + surface conventions/conflicts —
   instead of the main agent reading each file sequentially (slow). No specific subagent type
   required (stays portable across environments where teams configure different subagent names).

   **In this SAME scan pass (do NOT add a separate step), also check for the existence of the
   project's PR template** — different from `project_docs_found` above (a general convention
   source), this is its own separate field used at `review.md` Step 7 to cross-check the PR
   template checklist against the PR's real description. Check the common paths:
   `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`,
   `.github/PULL_REQUEST_TEMPLATE/*.md` (GitHub supports multiple templates in one directory,
   selected via a query param), `PULL_REQUEST_TEMPLATE.md` (root), `docs/PULL_REQUEST_TEMPLATE.md`.
   Keep the list of paths that ACTUALLY exist (an empty array if none exist) to record into
   `meta.json` at step 6 below.
2. For each source found, read the parts relevant to coding convention/review criteria (skip
   irrelevant parts like a product intro or install/deploy instructions).
3. **Do NOT copy the content you read into memory.** For each source with a clear convention that
   doesn't conflict with anything else, only add 1 REFERENCE line to `memory.md`, in the exact
   format given in the comment skeleton in Part A:
   `- [tag if a related stack can be identified] [short label](path) — a 1-line hook summarizing the convention`
   — e.g. `- [rails] [Controllers](app/controllers/AGENTS.md) — thin, no params.permit`. The hook
   must be SHORT, condensing the main point, not repeating the phrase "see the project's
   convention at" (the link itself already points there). While reviewing, the agent reads that
   exact file at that path again when needed — it does not rely on a copy that may have gone
   stale.
4. **If a conflict is found** — 2 sources disagree about the same issue, OR 1 source
   contradicts/is ambiguous with itself, OR that source conflicts with the plugin's
   baseline/template (`ALWAYS_RULE.md`/template): use your own best judgment on how to reconcile
   it (prefer a source written specifically for convention/AI-agents, like
   `CLAUDE.md`/`AGENTS.md`, over a general-purpose `README.md`; prefer a specific/detailed source
   over a generic one). Record the reconciled version as 1 lesson per Part E (content you author
   yourself to resolve the conflict, not copied verbatim from either source), stating clearly which
   sources conflicted and why this direction was chosen. This is the ONE case where a lesson gets
   logged without needing the user's confirmation (the agent authors it itself during doctor).
5. Record into `meta.json`: `"doctored": true`, `"doctored_at": "<current date/time>"`,
   `"project_docs_found": [<list of paths found in step 1, empty array if none>]`,
   `"pr_template_paths": [<list of PR template paths found in step 1, empty array if none>]`.
   (Submodules are NOT detected here — `review.md` Step 1 item 5 checks `.gitmodules` directly
   every time, with no caching via `meta.json`.)
6. `git -C notebooks/review add <repo>` + commit (local only) this change.

## Part D — `meta.json` schema

```json
{
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
}
```

`_comments` (an object of strings): a note for whoever edits `meta.json` by hand — **not** runtime
config. `review.md` / doctor / bootstrap ignore every key inside it. Bootstrap (Part A step 9)
ALWAYS writes (or backfills if missing) `_comments.doctor_schedule` with the exact sample text
above. Whenever Part C/`Edit` touches `meta.json`, keep `_comments` unchanged if already present.

**4 field groups — clearly categorized so new fields aren't miscategorized:**
- **User config** (Part A asks the user at bootstrap, changeable later via "reconfigure review"):
  `auto_submit_review`, `auto_resolve_fixed_findings`, `doctor_schedule`, `review_ci_status`,
  `many_files_threshold`, `big_file_threshold_kb`. Missing on a repo bootstrapped before it existed
  → `review.md` Step 3 backfills the default itself + notifies once (full detail lives in that
  Step 3, not repeated here).
- **Doctor-detected** (Part C re-detects it on its own schedule, not a setting the user chooses):
  `project_docs_found`, `templates_copied`, `pr_template_paths`. Missing because doctor has never
  run/is due → just wait for Part C to run again normally, do NOT apply the User config group's
  backfill behavior.
- **Internal/system state** (the plugin's own internal state flags — not a setting, no concept of
  "missing because outdated"): `bootstrapped`, `doctored`, `doctored_at`, `_comments`. NO
  backfill/notification applies at all — always written by Part A/C exactly when needed.
- **Detected-once** (not asked at Part A, not a fixed default to backfill): `chat_language`.
  Detected on demand at `review.md` Step 3 (chain: `ARGUMENTS` free text → this chat session's own
  language → this project's Claude Code memory, if any → OS locale → ask as a last resort), then
  remembered. Missing → run that detection, do not silently backfill a fixed default (there isn't
  one to fall back to).

**When adding a new field to this schema**: classify it IMMEDIATELY into exactly 1 of the 4 groups
above, right in this section. If it's a **User config** field → it MUST ALSO be added to the
"Retained from meta" sentence at Step 3 of `review.md` (that's the SOLE place that decides
backfill/notification for existing repos) — the two places must stay in sync; adding it here but
forgetting there means the new field will never get backfilled for already-live repos.

`review.md` treats bootstrap as done once `bootstrapped: true`. Doctor: `doctored: true` **and**
the schedule hasn't expired (`doctor_schedule` + `doctored_at`). `templates_copied` is checked
separately each time (Part B) — a new stack can still get its template copied after bootstrap/
doctor are already done.

`doctor_schedule` (string): `{N} days` | `{N} weeks` | `{N} months` | `never`. Asked at bootstrap
(Part A step 6), default `"1 months"`. Field missing (old repo) → treat as `"1 months"`. `never` →
never re-runs doctor on a schedule (still runs when the user asks to "doctor again" or when
`doctored: false`). Expired when `now > doctored_at + schedule` (parse N + unit; missing/`invalid`
`doctored_at` while `doctored: true` → treat as expired, rerun Part C). After every successful
Part C run: update `doctored_at` (and `doctored: true`).

Submodules have NO dedicated field in `meta.json` — `review.md` Step 1 item 5 itself tries
`Read`-ing `<worktree>/.gitmodules` directly every time (no caching), avoiding the gap where "the
first PR of a new repo always skips submodule handling because doctor has never run".

`auto_submit_review`/`auto_resolve_fixed_findings`/`doctor_schedule` are asked + written at
bootstrap (Part A step 6/9). `review.md` Step 3 reads them back; used at Step 6/9 and the doctor
schedule gate.

`pr_template_paths` is written at doctor time (Part C step 1/5). `review.md` Step 3 reads it,
Step 7 uses it.

`review_ci_status` (boolean): ONLY ASKED at bootstrap (Part A step 6/9) when the PR being reviewed
has at least 1 CI check (the "CI checks" array in Context is non-empty) — default `true` if the
user doesn't choose; PR has no CI at all → NOT asked, write `false` directly (asking would be
pointless). Field missing (old repo, backfilled at `review.md` Step 3) → treat it according to the
CURRENT review run's CI-checks signal (not a hardcoded `true`). `review.md` Step 3 reads it back;
Step 7 uses it to decide whether to raise a warning about a failing CI check (already fetched in
Context) in the overview, or skip it entirely.

`many_files_threshold` (number): asked + written at bootstrap (Part A step 6/9), default `30`.
Field missing or not a valid number (old repo) → treat as `30`. `review.md` Step 3 reads it back;
Step 7 uses it in the file-count guard (a PR changing more files than this threshold → ask about
review strategy, unless ARGUMENTS/chat already specified one).

`big_file_threshold_kb` (number): asked + written at bootstrap (Part A step 6/9), default `20`
(~5,000 tokens, estimated at ~4 characters/token — just a rough reference conversion, not exact
since it depends on the real tokenizer/language). Field missing or not a valid number (old repo) →
treat as `20`. `review.md` Step 3 reads it back; Step 7 uses it in the size/dump guard (a file
whose diff exceeds this threshold, in KB, or `UNKNOWN` → a limited peek to classify data/dump
instead of a detailed line-by-line review).

## Part E — Logging 1 lesson into memory

The mechanical procedure shared by: thread consensus (Step 6 / `re-review.md` — **after** the user
confirms in chat), a convention suggestion the user types in chat (`review.md` Step 10 — log it
immediately, no re-confirmation), and a conflict reconciled in Part C (no confirmation needed).
Part E only describes the write operation itself.

1. Create `notebooks/review/<repo>/memories/<lesson-slug>.md` (a short kebab-case slug, no
   meaningless sequence numbers). Minimum content: a description of the convention; before/after
   code example (if any); stack tag; date logged; source (a link to the related PR if any).
2. Add 1 line to the index at `notebooks/review/<repo>/memory.md`, in the exact format given in
   the comment skeleton in Part A: `- [stack-tag] [short label](memories/<lesson-slug>.md) — a
   1-line hook` (multiple tags if it applies to multiple stacks). Keep the hook concise, no
   repeated words, no lengthy explanation — the detail already lives in the
   `memories/<lesson-slug>.md` file, the index only needs enough to recognize what the lesson is.
3. `git -C notebooks/review add <repo>` + commit (local only, no push; if the commit errors about
   a missing `user.name`/`user.email`, use the `-c` flags as in Part A).

## When the user asks to "doctor again" / "rescan the project's conventions"

Change `doctored` in `meta.json` to `false` (or delete that field entirely) then redo Part C. Can
be done right in chat, no need to wait for the next `/open-pr:review` run.
