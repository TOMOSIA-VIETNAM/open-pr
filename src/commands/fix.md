---
argument-hint: <PR URL> [content]
description: Fix code per findings left by /open-pr:review on a PR (GitHub or GitLab) — decides to fix/decline by severity, edits code to match the project's convention, commits/pushes in a controlled way, and replies on the PR (dev-facing, edits real code, no worktree involved).
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` FIRST — shared rules, not repeated
> here. On top of those:
> - This command EDITS REAL CODE at pwd (no worktree), then commits/pushes — higher risk than the
>   read-only `/open-pr:review`. Step 1 MUST run BEFORE ANY other action and STOP IMMEDIATELY on
>   failure. FORBIDDEN: "helpfully" fixing the remote/branch just to pass it.
> - FORBIDDEN: `git commit --amend`, `git push --force`/`--force-with-lease`, `git add -A`/`git add .`,
>   `git branch -D`, `git reset --hard`, resolving a PR thread, editing/committing on a protected branch
>   or when the remote/branch doesn't match the PR, deciding alone on a 🔵/📝 finding, checking out the
>   PR/MR, `git worktree` (anything — this command never uses one), close/merge/reopen, creating a
>   review/draft-note batch (this command only replies; posting is `review.md`'s job). `cd`/`find` are
>   allowed ONLY to self-locate the project directory (Step 1a), and only once `git remote` proves the
>   match — never by directory name. This bullet + the one above are the SOLE enforcement layer — no
>   `allowed-tools` backs them (deliberate).

## Step 0 — Target

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/pr-target.md`, taking its no-store branch (§2): this command never
persists `git_remote_type`, it uses `<vendor_guess>` as-is. `Usage:` block:

```
❌ Error: No PR URL provided.
Usage: /open-pr:fix <PR URL> [content]
Example (GitHub): /open-pr:fix https://github.com/org/repo/pull/123
Example (GitLab): /open-pr:fix https://gitlab.com/org/repo/-/merge_requests/123
Example with instructions: /open-pr:fix https://github.com/org/repo/pull/123 only fix the security part
```

Free-form text outside the URL narrows this run's scope (Step 3 item 3).

## Context

Fetch:

| `V§` entry | label |
|---|---|
| "Fetch PR basic info", fields `number,headRefName,baseRefName` | PR info |
| "Fetch PR review comments (LINE-level findings)" | Comments |
| "Fetch PR reviews (FILE-level findings + review_id)" | Reviews |
| "Fetch account running the command" | Account running this command |
| "Fetch review threads (id + isResolved + comment ids)" | Review threads |

Plus 2 plain `git` commands, identical on any vendor so not in a vendor file — label "Git remote +
current branch": `git remote -v` && `git branch --show-current`.

A vendor whose "Fetch PR reviews" entry has no equivalent returns nothing here; Step 3 item 2 then
does not apply, while LINE-level handling continues normally.

`core/pr-target.md` §4-5 give `<repo>` and the empty-"PR info" stop.

## Step 1 — Verify a safe context (STOP IMMEDIATELY on failure)

**1a.** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/locate-repo.md`, follow it. Everything below runs at the
directory it establishes.

**1b. Check BOTH at the 1a directory.** Either failing → print that error, STOP COMPLETELY. FORBIDDEN:
fixing the branch yourself, touching any file, proceeding to Step 2.

1. the current branch matches `headRefName` EXACTLY. Mismatch:
   ```
   ❌ Current branch (`<current branch>`) doesn't match the PR's branch (`<headRefName>`). Check
      out the correct branch `<headRefName>` and call this again.
   ```
2. the current branch is NOT one of `main`, `master`, `production`, `prod`, `staging`, `stg`,
   `release`, `rls`, `dev`, `development`, `develop` (case-insensitive, EXACT match, not substring).
   It is one — regardless of item 1, since a PR may itself target a protected branch:
   ```
   ❌ Currently on a protected branch (`<branch>`) — this command does NOT run on a protected
      branch even if it matches the PR. Create/check out a dedicated feature branch for this PR
      and call this again.
   ```

## Step 2 — Settings

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/repo-settings.md`, then `notebooks/review/<repo>/settings.json`.
Resolve `chat_language` per that file.

- `.fix` present → use its values, do NOT ask again
- absent, or no file at all → `Read` `"${CLAUDE_PLUGIN_ROOT}"/setup/fix-bootstrap.md`, follow it

## Step 3 — Identify findings to handle

2 KINDS, differing in data source and in how "still open" is decided:

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/finding-markers.md` — it defines how both kinds are recognized.

1. **LINE-level** (from "Comments") → drop a finding when EITHER holds: its `id` (databaseId) belongs to
   a thread in "Review threads" with `isResolved: true`, || that same thread is already handled
   (`core/finding-markers.md`). That is what stops a duplicate commit/reply while the thread is still
   unresolved — this command never resolves threads (Step 10).
2. **FILE-level / OVERVIEW-level** (from "Reviews") → an individual bullet has no resolve concept and no
   readable reply history, so EVERY FILE-level finding in the most recent review is ALWAYS treated as
   still open and re-handled every run. Accepted limitation: a repeat run after that part is already
   fixed may add 1 duplicate reply.
3. Free-form instructions present (Step 0) → filter both lists BY MEANING (e.g. "only fix the security
   part"), no rigid syntax.
4. Both lists empty after filtering → say so in 1 short sentence, STOP CLEANLY.

## Step 4 — Read the project's convention

`notebooks/review/<repo>/` absent (repo never reviewed) → skip this Step, fix on ordinary judgment at
Step 7. FORBIDDEN: blocking or erroring on this.

Present → map each finding's file to its stack via
`"${CLAUDE_PLUGIN_ROOT}"/core/stack-detection.md`, then `Read`
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
→ ordinary judgment, favouring the surrounding style. Directly at pwd — no worktree.

## Step 8 — Commit

`git add` ONLY the exact files `Edit`-ed at Step 7, each path listed explicitly. FORBIDDEN: `git add
-A`/`git add .`. EXACTLY 1 commit covering every finding fixed this run; message follows the
convention from Step 4 when there's a clear signal (e.g. the repo's recent `git log`), else
`fix: address review comments (PR #<pull_number>)` + a bullet per finding fixed.

## Step 9 — Push

- **`auto_push: false`** (default) → STOP at local, tell the dev in 1 short sentence ("Fixed +
  committed locally. Say 'push' when you want me to push it up + reply."). The dev expresses the INTENT
  to push (matched by intent, not a fixed string) → `git push`, NORMAL, then Step 10.
- **`auto_push: true`** → `git push`, NORMAL, right after Step 8, then Step 10 in the same run.

## Step 10 — Reply on the PR

ONLY after the code has actually reached the remote. FORBIDDEN: replying while the commit is local.

For EACH finding decided (fixed or declined), `V§"Reply on a PR"`:

- **LINE-level** — `comment_id` = the ORIGINAL finding comment's id. Content SHORT: fixed → a short
  confirmation ("Fixed, thanks!"); declined → a short reason. FORBIDDEN: recounting the process ("read
  file X then checked Y").
- **FILE-level / OVERVIEW-level** — link to that finding's location via `V§"Finding permalink"` when
  the vendor has an addressable one; otherwise reference it by file path + short description.
  FORBIDDEN: blockquoting the whole review verbatim.

Content MUST end with `<!-- bot-reply -->` — the stable marker Step 3 reads back, independent of prose
shape.

FORBIDDEN: resolving a thread — this command has no auto-resolve setting, unlike `re-review.md`.

## Step 11 — Lesson-saving

At any point, a finding reflecting a GENERAL project convention (not PR-specific) → propose it in chat
(content + stack tag + recommendation + reasoning), WAIT for the dev to confirm, only then log it per
`"${CLAUDE_PLUGIN_ROOT}"/setup/lesson.md`, into the repo's SAME `memory.md`/`ALWAYS_RULE.md`. FORBIDDEN:
a separate lesson file for `/open-pr:fix`.

## Reconfiguring fix

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/reconfigure.md`, `<node>` = `.fix`.

---

ARGUMENTS: $ARGUMENTS
