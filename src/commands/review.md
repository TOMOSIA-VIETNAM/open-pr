---
argument-hint: <PR URL> [other PR URL...] [content]
description: Review one or more PRs (GitHub or GitLab) across multiple stacks (sequentially), learn each repo's own conventions via memory, post results via the vendor's own CLI/API.
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` FIRST — shared rules, not repeated
> here. On top of those:
> - Read-only on the reviewed repo; the only write is Step 9's 1 review (+ 1 more on a submodule PR
>   when Step 1 detects a bump). FORBIDDEN: close/merge/reopen, create/delete/switch a branch, push,
>   edit code → mention it in the review instead.
> - `git worktree add` confined to `notebooks/review/*/worktrees/*`.
> - `Read`/`Grep` in the worktree may surface the REVIEWED repo's own `.claude/skills/` — its dev
>   workflow, not a review tool. FORBIDDEN: invoking it, even when listed as available.

## Step 0 — Target

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/pr-target.md`; it names what every later Step reuses. `Usage:`
block for this command:

```
❌ Error: No PR URL provided.
Usage: /open-pr:review <PR URL>
Example (GitHub): /open-pr:review https://github.com/org/repo/pull/123
Example (GitLab): /open-pr:review https://gitlab.com/org/repo/-/merge_requests/123
```

A language instruction in `ARGUMENTS`/chat overrides `.shared.output_language`, this run only.

**≥2 valid PR URLs** && the intent isn't already clear from `ARGUMENTS`/chat → ask "Found N PRs —
review all N or just the first?", WAIT (extras may be reference-only). Confirmed multi-PR → run Step 0
→ Step 9 to COMPLETION per URL, in order, SEQUENTIALLY, each with its own worktree/memory/post.
FORBIDDEN: parallel, subagent. `[content]` applies to every PR. Then 1 summary IN CHAT listing each PR
+ status, nothing further posted.

## Context

`<git_remote_type>` MUST be resolved (`core/pr-target.md` §2) BEFORE the first fetch, which needs
`.shared.git_remote_type` → try `Read`ing `notebooks/review/<repo>/settings.json` now (Step 3
re-`Read`s it for the rest of its content).

Then fetch:

| `V§` entry | label |
|---|---|
| "Fetch PR basic info", fields `number,title,body,author,baseRefName,headRefName` | PR info |
| "Fetch PR diff — file list" | Files |
| "Fetch PR diff size per file" | Diff size per file |
| "Fetch PR diff — patch, omitting oversized files", `<max_patch_bytes>` = `big_file_threshold_kb` × 1024 | Diff |
| "Fetch PR commits headlines" | Commits |
| "Fetch PR review comments (LINE-level findings)" | Old comments |
| "Fetch CI checks" | CI checks |

Fetch the size list BEFORE the patch, in that order. Any path it names that "Diff" then lacks is an
omitted file → carry that list to Step 7 as **"Oversized paths"**. A whole patch that reaches the
terminal stays in context for the rest of the run, so the omission MUST happen inside the vendor's own
call; Step 7's guard fires far too late to help.

`big_file_threshold_kb` (`core/repo-settings.md`) — this Context already reads
`settings.json` for `<git_remote_type>`, so take it from that same read.

"CI checks" MUST stay unfiltered — Step 7 and `setup/bootstrap.md` q6 each read the raw array.

**Filesystem:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/locate-repo.md` and follow it BEFORE Step 1 — the
worktree and the memory folder both live under the directory it establishes, and Step 1's `git fetch
origin` only resolves there. Before writing under `notebooks/review/` → state that directory + `<repo>`
in chat.

`core/pr-target.md` §5 gates entry into Step 1.

## Step 1 — Ephemeral worktree

The PR's code on disk, main tree untouched — it never changes branch, so nothing needs restoring.

1. `git worktree add "notebooks/review/<repo>/worktrees/review-pr<pull_number>-$RANDOM" --detach` —
   random name, never reused. Then `V§"Check out the PR head into a worktree"` to put the PR's code
   there, DETACHED — a subshell pinned to the worktree, so the working directory itself never moves.
   Then `Read`/`Grep` at `<worktree>/<path>`.
2. `git fetch origin "<baseRefName>"` — refs are shared across worktrees.
3. `git -C "notebooks/review/<repo>/worktrees/<name>" submodule update --init --recursive` — ALWAYS,
   submodule-touching PR or not.
4. Try `Read`ing `<worktree>/.gitmodules` — checked directly every run, never cached, so a
   not-yet-doctored repo still detects a bump on its first PR. Exists && "Diff" contains `Subproject
   commit` → `Read` `"${CLAUDE_PLUGIN_ROOT}"/cases/submodule-review.md`. Else skip.

## Step 2 — Detect stack

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/stack-detection.md`; keep the `(file, [stacks])` mapping for Steps 4-7.

## Step 3 — Setup / doctor

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/repo-settings.md`, then `Read` `notebooks/review/<repo>/settings.json`
in full (Context read it only to resolve `<git_remote_type>`). Resolve `chat_language` and
`doctor_due` per that file.

`<git_remote_type>` is already resolved, never re-asked. Persisting it:

- about to bootstrap → q1's pre-marked default, `setup/bootstrap.md` writes it
- bootstrapped, field predates this schema → read-time fallback only. FORBIDDEN: writing it back
  (`/open-pr:update-plugin` owns that backfill)
- `core/pr-target.md` §2's mismatch confirmed a DIFFERENT value → `Edit` `.shared.git_remote_type` here

Branch:

- no file || no `.review` || `.review.bootstrapped` != `true` → `Read`
  `"${CLAUDE_PLUGIN_ROOT}"/setup/bootstrap.md`, then `setup/doctor.md`
- `bootstrapped: true` && `doctor_due` → `setup/doctor.md` only, FORBIDDEN: re-asking bootstrap
- `bootstrapped: true` && !`doctor_due` → skip both

Setup stable ⇒ don't touch `notebooks/review/` outside Step 4 (new template), Step 6 (lesson), or a due
doctor.

## Step 4 — Local template per stack

Each Step 2 stack absent from `.review.templates_copied` → `Read`
`"${CLAUDE_PLUGIN_ROOT}"/setup/template.md`, follow it. Present → use
`notebooks/review/<repo>/templates/<stack>.md`. Runs every time: a new stack can appear post-bootstrap.

## Step 5 — Load the criteria

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/review-criteria.md` and load every layer it names, for the stacks
from Step 2.

## Step 6 — Re-review

"Old comments" non-empty → `Read` `"${CLAUDE_PLUGIN_ROOT}"/cases/re-review.md`; it also gates whether
Step 8/9 post at all. Empty (brand-new PR) → skip to Step 7.

## Step 7 — Review

**Large-diff guard, before anything else here:** count("Files") > `many_files_threshold` || "Oversized
paths" (Context) non-empty || any "Diff size per file" entry > `big_file_threshold_kb` KB or `UNKNOWN` →
`Read`
`"${CLAUDE_PLUGIN_ROOT}"/cases/large-diff-guards.md`, follow it (it may STOP the command). Neither →
proceed.

**Overview items** — never counted toward N, never entered into `comments[]`:

- title/body vague on business context → note it atop the Step 8 overview, suggest the dev add detail.
  FORBIDDEN: writing it for them.
- `headRefName` carries a ticket code but the title lacks a matching prefix → note it. No ticket in the
  branch → skip.
- "CI checks" has ≥1 `bucket==fail` && `review_ci_status` != `false` → 1 warning sentence (check name +
  link). WARNING ONLY: no severity, forces no fix (it may be flaky). No `fail` line, no CI, or
  `review_ci_status: false` → completely silent.

**PR template:** `.review.pr_template_paths` non-empty → `Read`
`"${CLAUDE_PLUGIN_ROOT}"/cases/pr-template-checklist.md`. Empty → skip.

FORBIDDEN in EVERY finding: naming a role to reconfirm with ("the BA/client/PM/QA…") — the project may
not have it. Write "reconfirm this requirement/spec".

Criteria + precedence: Step 5.

**FILE vs LINE** = contextual judgment, no enum. LINE: `-` line ⇒ `side: "LEFT"` (base), `+`/context
line ⇒ `side: "RIGHT"` (head). FILE → Step 8 body; LINE → Step 9 `comments[]`. FORBIDDEN: a FILE
finding inside `comments[]`.

**Scope:**

- in-scope first; a 📝 puts no pressure to fix and counts toward nothing
- reading further at `<worktree>/<path>` is optional, but MUST use `Read`'s `offset`/`limit` around the
  changed region (hunk header `@@ -a,b +c,d @@` ± ~20-30 lines). FORBIDDEN: a bare `Read` of a file
  whose change is localized, i.e. not a new file or wholesale rewrite
- the Context "Diff" is the sole source for the files it contains — never refetch it. An "Oversized
  paths" file is absent BY DESIGN; the guard above owns how it gets read
- never read library source unless genuinely unsure
- never pad the count with trivia; there is no minimum N

**Finding format** (`**Fix**` → `**Gợi ý**` when the output language is Vietnamese):

```
<emoji> <short description>.
**Fix** — <code or words>
*(optional)* because <one sentence>.
<!-- bot-finding -->
```

`<!-- bot-finding -->` MUST end EVERY finding, FILE and LINE alike — the marker `core/finding-markers.md`
matches on later.

FORBIDDEN: a text label before the description ("Vấn đề"/"Issue") — in a finding the emoji IS the label,
unlike a Step 8 grouping heading, which names the severity too. Severity: 🔴 MUST FIX / 🟠 SHOULD FIX /
🔵 SUGGESTION, and 📝 NOTE for out-of-scope or genuinely not worth fixing in this PR — minor but easy to
fix now is 🔵, not 📝. Each finding carries its own emoji, whatever heading it ends up under.

Fix-as-code → a code block: a LINE comment replacing that exact line ⇒ ` ```suggestion `, else a normal
language fence. Fix-as-prose → 1 sentence, no forced fence. ≥2 independent points (common on LINE) → one
`-` bullet each, never one multi-clause sentence.

## Step 8 — Formatting

Output language = `.shared.output_language` (`core/repo-settings.md`), or Step 0's override.

`<commit_id>` = `V§"Fetch PR head commit SHA"` RIGHT NOW, never Context's older `headRefOid`. Reuse
that exact value in the overview and in Step 9's payload; never fetch it twice.

Step 6 ran → apply `re-review.md`'s early-stop gate BEFORE continuing; Step 8/9 may be dropped entirely.

FORBIDDEN in the overview: the agent's own WORK PROCESS (what was fetched or checked out, which commit
was compared, API retries, an interruption midway) — the reader wants conclusions only. Also FORBIDDEN:
repeating a `comments[]` finding or its Fix, already inline at its diff line; say ONLY what is NOT in
LINE. A closing summary ("No new issues found in this round of changes.") → **bold**, same tier as
**LGTM 🌟**.

Every body MUST read "as of commit […]", linked per `V§"Commit URL"` — bare "reviewed commit […]"
misreads as that 1 commit alone, where the ENTIRE diff was reviewed at that point.

**Body shape** — the 2 reduced shapes:

| FILE | LINE | overview-exclusive¹ | body |
|---|---|---|---|
| – | – | – | EXACTLY 1 line: **LGTM 🌟** (as of commit […]). No `### 🤖【AI REVIEW】Overview` heading, no thanks, no assessment — only a non-empty skipped-files list may follow it |
| – | ≥1 | – | the opening line ONLY. DROP every severity heading. A normal outcome ⇒ FORBIDDEN: filler like "good PR"/"reviewed thoroughly"; the LINE comments suffice |

¹ an Overview item from Step 7, or a non-empty skipped-files list.

Anything else — ≥1 FILE finding || ≥1 overview-exclusive item — → the full structure:

```
### 🤖【AI REVIEW】Overview
Open with EXACTLY "Thank you! 🙇🏻‍♂️" (no embellishment like "for submitting this PR"/"for the
effort"), then state that the ENTIRE SET OF CHANGES WAS REVIEWED AS OF commit (link + phrasing
above), then 1 sentence of reply instructions, addressing the reader as "you". Then the title/prefix
note if any. Assessment prose is OPTIONAL: include it ONLY to carry a conclusion no finding below
does. Nothing such ⇒ stop after the reply instructions.

#### 🔴 MUST FIX
#### 🟠 SHOULD FIX
#### 🔵 SUGGESTION
#### 📝 NOTE

#### Files skipped for detailed review
- `<path>` — <short reason, e.g. "diff ~35KB, looks like seed/dump data">
```

Only FILE findings get the full Fix + path structure; LINE stays inline-only. Before printing any
`#### <emoji>` heading: ≥1 FILE finding at EXACTLY that severity? No — even if a LINE finding has it,
even for 📝 → drop the heading. FORBIDDEN: an empty heading, writing "no issues", or a count of N.

A heading carries emoji + label, verbatim as above — it groups findings for someone skimming the PR
body, who needs the severity named. An individual finding carries the emoji ALONE (Step 7), heading or
not: there the emoji sits against a description that already says what the problem is.

**Files skipped for detailed review** = the content of `<worktree>/.review-skipped.md` (`Read` it again
while writing this Step, don't rely on context) → ALWAYS last in the overview WHEN that file exists
non-empty, even under LGTM, so the user knows what to check personally. Missing/empty → drop the
heading, never write "none".

## Step 9 — Post (1 composite operation for the main PR)

Payload: `<commit_id>` from Step 8 (never re-fetched here, never Context's `headRefOid`), `comments[]`
(LINE entries: `path` + `line` + `side` + `body`), and the Step 8 overview (FILE findings + assessment).

`V§"Post a review"` — COMPOSITE, its step count and mechanism are the vendor's own; follow it EXACTLY.
FORBIDDEN: forcing one vendor through another's shape, e.g. inventing a review id for a vendor that has
none. Invariants on every vendor:

- exactly 1 review / 1 batch of notes for the main PR, never split. A submodule post is a separate
  result for a DIFFERENT PR and doesn't count here.
- every LINE finding attached to its correct diff line + side
- every FILE finding inside the overview body — FORBIDDEN: mixing one into a LINE-level entry

`auto_submit_review`: `true` → carry that entry through to its own submit/publish step; `false` → stop at
whatever the vendor calls pending/draft and say it isn't published, FORBIDDEN: publishing on the user's
behalf. That entry may also describe how to verify the post landed — follow it if present.

Post/publish error || that verify reports a mismatch → `Read`
`"${CLAUDE_PLUGIN_ROOT}"/cases/post-review.md`. Happy path → skip that file.

## Step 10 — Asked for something outside the review flow

User asks about memory, a re-scan, or the config — during this run or in a later chat with no PR →
`Read` `"${CLAUDE_PLUGIN_ROOT}"/cases/chat-requests.md`. Nothing asked → skip; the scheduled doctor is
Step 3's job.

---

ARGUMENTS: $ARGUMENTS
