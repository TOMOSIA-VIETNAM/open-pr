---
argument-hint: "[PR URL] [content]"
description: Act on the findings a review left on a PR — takes or declines each by severity, edits code at pwd to match the project, 1 commit, replies once pushed.
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` FIRST, and `core/cli.md` with it —
> they carry the shared rules and the `<op>` runtime. `<op>` ≡ `sh "${CLAUDE_PLUGIN_ROOT}"/bin/open-pr.sh`,
> exactly as THIS line spells it — no env var exists in the shell. On top of those:
> - This command EDITS REAL CODE at pwd, then commits/pushes — higher risk than the
>   read-only `/open-pr:review`. Step 1 MUST run BEFORE ANY other action. FORBIDDEN: "helpfully"
>   fixing the remote/branch just to pass it.
> - FORBIDDEN: `git commit --amend`, `git push --force`/`--force-with-lease`, `git add -A`/`git add .`,
>   `git branch -D`, `git reset --hard`, resolving a PR thread, editing/committing when the PR's branch
>   is protected or the remote/branch doesn't match the PR, deciding alone on a 🔵/📝 finding, RAW-git
>   branch checkouts or worktree add/remove (Step 1b's `<op> checkout` is the ONLY sanctioned one),
>   close/merge/reopen, `<op> post`/`publish` (this command only replies; posting is `review.md`'s job). `cd` is allowed ONLY between the invocation
>   directory, the 1a directory (once its git remote proves the match — never by name), and the
>   Step 1b worktree. This bullet + the one above are the SOLE
>   enforcement layer — no `allowed-tools` backs them (deliberate).

## Step 0 — Target

`<op> target <url>`; exit 4 or no URL → the block below. `Read`
`"${CLAUDE_PLUGIN_ROOT}"/core/pr-target.md`, taking its no-store branch (§2): this command never
persists `git_remote_type`, it uses the parsed vendor as-is.

```
❌ Error: No PR URL provided.
Usage: /open-pr:fix <PR URL> [content]
Example (GitHub): /open-pr:fix https://github.com/org/repo/pull/123
Example (GitLab): /open-pr:fix https://gitlab.com/org/repo/-/merge_requests/123
Example with instructions: /open-pr:fix https://github.com/org/repo/pull/123 only fix the security part
```

Free-form text outside the URL narrows this run's scope (Step 3 item 3).

No URL → take the PR THIS session already establishes (its review ran here, the user named it, pwd is
its worktree), say which in 1 short sentence, continue. NOT exactly 1 ⇒ the `Usage:` block. FORBIDDEN:
guessing past it.

## Context

`<op> context --sections info,head,comments,reviews,account,threads` — labels "PR info", "Head SHA",
"Old comments", "Reviews", "Account", "Review threads". Plus 2 plain `git` commands, label "Git
remote + current branch": `git remote -v` && `git branch --show-current` — pwd may be no repo (exit
128) or the wrong one; not fatal, Step 1 re-checks everything at the 1a directory.

"Reviews" empty ⇒ Step 3 item 2 does not apply; LINE-level handling continues normally.

`core/pr-target.md` §4-5 give `<repo>` and the empty-"PR info" stop.

## Step 1 — Verify a safe context (STOP IMMEDIATELY on failure)

**1a.** `<op> locate-repo` → `<repo_dir>` (exit 5 → ask with a CHOICE in plain language, STOP if
unresolved). `<memory-dir>` = `notebooks/review/<repo>` at THIS invocation directory, ABSOLUTE — the
place review.md writes from its own pwd; `<repo_dir>` = a `review` worktree
(`notebooks/review/*/worktrees/pr<pull_number>-*`) ⇒ its `../../`. FORBIDDEN: resolving memory inside
`<repo_dir>` — a repo that is a subdirectory of the workspace grows a second, drifting copy. Then
`cd` into `<repo_dir>` — this command EDITS that repo's files ⇒ works from inside.

**1b. Check BOTH at the 1a directory.** Either failing → print that error, STOP COMPLETELY. FORBIDDEN:
touching any file, proceeding to Step 2.

1. the current branch matches `headRefName` EXACTLY **and its tip prefix-matches "Head SHA"** ⇒ fix
   in place — a matching name on a stale tip edits a tree the findings do not describe and the push
   cannot fast-forward. Else `<repo_dir>` = a review worktree whose `git rev-parse HEAD`
   prefix-matches "Head SHA" ⇒ fix there (DETACHED is normal). Anything else — wrong branch, stale
   tip, stale worktree — ⇒ ONE CHOICE per `core/guardrails.md`:
   `Fix in a fresh worktree (Recommended)` — `<op> checkout`, run FROM the invocation directory so
   the worktree lands under `<memory-dir>`, gates it to "Head SHA"; the user's own branch/tree stays
   untouched; `cd` into the printed worktree, continue there — vs stop-and-checkout yourself, printing:
   ```
   ❌ Current branch (`<current branch>`) doesn't match the PR's branch (`<headRefName>`). Check
      out the correct branch `<headRefName>` and call this again.
   ```
2. `headRefName` is NOT one of `main`, `master`, `production`, `prod`, `staging`, `stg`,
   `release`, `rls`, `dev`, `development`, `develop` (case-insensitive, EXACT match, not substring).
   Read off the PR ⇒ holds detached too, and a PR may itself target a protected branch:
   ```
   ❌ The PR's branch (`<headRefName>`) is a protected branch — this command does NOT commit to
      one. Move the change onto a dedicated feature branch and open the PR from that.
   ```

## Step 2 — Settings

`<op> settings --dir <memory-dir>` (`core/repo-settings.md` names what each field means). Resolve
`chat_language` per that file.

- the FILE carries a `.fix` node → use its values, do NOT ask again
- absent, or no file at all → `Read` `"${CLAUDE_PLUGIN_ROOT}"/setup/fix-bootstrap.md`, follow it

## Step 3 — Identify findings to handle

2 KINDS, differing in data source and in how "still open" is decided; `Read`
`"${CLAUDE_PLUGIN_ROOT}"/core/finding-markers.md` — it defines how both are recognized.

1. **LINE-level** (from "Old comments") → drop a finding when EITHER holds: its `id` belongs to a
   thread in "Review threads" with `resolved: true`, || that same thread is already handled
   (`core/finding-markers.md`).
2. **FILE-level / OVERVIEW-level** (from "Reviews") → an individual bullet has no resolve concept and no
   readable reply history, so EVERY FILE-level finding in the most recent review is ALWAYS treated as
   still open and re-handled every run. Accepted limitation: a repeat run after that part is already
   fixed may add 1 duplicate reply.
3. Free-form instructions present (Step 0) → filter both lists BY MEANING (e.g. "only fix the security
   part"), no rigid syntax.
4. Both lists empty after filtering → say so in 1 short sentence, STOP CLEANLY.

## Step 4 — Read the project's convention

`<memory-dir>` absent (repo never reviewed) → skip this Step, fix on ordinary judgment at Step 7.
FORBIDDEN: blocking or erroring on this.

Present → `<op> stacks --repo-dir . <each finding's file>`, then `Read`
`"${CLAUDE_PLUGIN_ROOT}"/core/review-criteria.md` and load the layers it names for those stacks. A layer
whose file doesn't exist yet → skip it; FORBIDDEN: creating one here (`setup/template.md`'s job).

## Step 5 — Decide on each finding

- **LINE-level**: read the original finding + EVERY reply on THAT EXACT thread. A CLEAR human reply
  already settling it (leave as-is / no fix needed / intended behaviour) → skip that finding ENTIRELY.
  FORBIDDEN: asking again, or fixing over an existing decision.
- **FILE-level**: no thread to read (Step 3 item 2) → skip the branch above, rest applies normally.
- **🔴 MUST FIX / 🟠 SHOULD FIX** → default FIX. The agent itself judges it wrong/unreasonable (code
  doesn't match the description, or a clear technical reason) → `decline_needs_confirmation`: `true` ⇒
  fold into Step 6, wait for the dev; `false` ⇒ decline right away.
- **🔵 SUGGESTION / 📝 NOTE** → NEVER decide alone, whatever the setting. ALWAYS fold into Step 6 with a
  recommendation + reasoning + impact scope, and let the dev choose.

## Step 6 — Combine questions

≥1 finding needs asking → combine ALL into EXACTLY 1 question (never ask separately), WAIT for the
dev's COMPLETE answer before Step 7. FORBIDDEN: fixing the certain parts first and asking about the
rest later — every decision this run is finalized before any `Edit`.

Nothing to ask → straight to Step 7.

## Step 7 — Fix

`Edit` the code for EVERY finding decided as FIX, matching the layers loaded at Step 4; nothing readable
→ ordinary judgment, favouring the surrounding style. Directly at `<repo_dir>`. Decisions may OVERLAP
(one edit settles several findings, or one accepted finding erases another's target) — plan the edits
jointly; Step 10 still replies to EACH finding with its own outcome.

## Step 8 — Commit

`git add` ONLY the exact files `Edit`-ed at Step 7, each path listed explicitly. EXACTLY 1 commit
covering every finding fixed this run; message follows the convention from Step 4 when there's a clear
signal (e.g. the repo's recent `git log`), else
`fix: address review comments (PR #<pull_number>)` + a bullet per finding fixed.

## Step 9 — Push

`<push>` = `<op> push --branch <headRefName> --dir <repo_dir>`, on a branch and detached alike — the
remote is matched to the PR's host, never a blind `origin`. It failing ⇒ report its stderr as printed,
STOP. FORBIDDEN: retrying with other credentials or remotes.

- **`auto_push: false`** (default) → STOP at local, tell the dev in 1 short sentence ("Fixed +
  committed locally. Say 'push' when you want me to push it up + reply."). The dev expresses the INTENT
  to push (matched by intent, not a fixed string) → `<push>`, then Step 10.
- **`auto_push: true`** → `<push>` right after Step 8, then Step 10 in the same run.

## Step 10 — Reply on the PR

ONLY after the code has actually reached the remote.

For EACH finding decided (fixed or declined), body written to a file, then `<op> reply`:

- **LINE-level** — `--comment-id` = the ORIGINAL finding comment's id, `--kind line`. Content SHORT:
  fixed → a short confirmation ("Fixed, thanks!"); declined → a short reason; settled by ANOTHER
  finding's decision (its target removed/rewritten) → name what happened and why the code is gone.
  FORBIDDEN: recounting the process ("read file X then checked Y").
- **FILE-level / OVERVIEW-level** — `--kind top`, referencing the finding by file path + short
  description. FORBIDDEN: blockquoting the whole review verbatim.

Content MUST end with `<op> marker --kind reply`, exactly as printed — Step 3 reads it back.

FORBIDDEN: `<op> resolve` — this command has no auto-resolve setting, unlike `re-review.md`.

## Step 11 — Lesson-saving

At any point, a finding reflecting a GENERAL project convention (not PR-specific) → propose it in chat
(content + stack tag + recommendation + reasoning), WAIT for the dev to confirm, only then log it per
`"${CLAUDE_PLUGIN_ROOT}"/setup/lesson.md`, into the repo's SAME `memory.md`/`ALWAYS_RULE.md`. FORBIDDEN:
a separate lesson file for `/open-pr:fix`.

## Reconfiguring fix

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/reconfigure.md`, `<node>` = `.fix`.

---

ARGUMENTS: $ARGUMENTS
