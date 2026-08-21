---
argument-hint: "<PR URL> [other PR URL...] [content]"
description: Review PRs against the conventions learned from each repo — 1 post per PR, findings tagged by severity, code left untouched.
disable-model-invocation: true
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
FORBIDDEN: parallel, subagent. `[content]` applies to every PR. All done → 1 chat summary, 1 line per
PR, shaped by Step 9's reporting rule; nothing further posted.

## Context

`<git_remote_type>` MUST be resolved (`core/pr-target.md` §2) BEFORE the first fetch, which needs
`.shared.git_remote_type` → try `Read`ing `notebooks/review/<repo>/settings.json` now (Step 3
re-`Read`s it for the rest of its content).

Then fetch:

| `V§` entry | label |
|---|---|
| "Fetch PR basic info", fields `number,title,body,author,baseRefName,headRefName` | PR info |
| "Fetch PR head commit SHA" | Head SHA |
| "Fetch PR diff — file list" | Files |
| "Fetch PR diff size per file" | Diff size per file |
| "Fetch PR diff — patch, omitting oversized files", `<max_patch_bytes>` = `big_file_threshold_kb` × 1024 | Diff |
| "Fetch PR commits headlines" | Commits |
| "Fetch PR review comments (LINE-level findings)" | Old comments |
| "Fetch CI checks" | CI checks |

Fetch "Head SHA" BEFORE "Diff", and the size list BEFORE the patch, in that order — the rest of the table
is 1 tool block. Taken AFTER "Diff", a "Head SHA" matches a push landing between the two and Step 1's
gate passes on a stale diff; taken before, that push costs 1 extra STOP. Any path the size list names
that "Diff" then lacks is an omitted file → carry that list to Step 7 as **"Oversized paths"**. Omission
MUST happen inside the vendor's own call — a printed patch is permanent context; Step 7's guard is
post-hoc.

`big_file_threshold_kb` (`core/repo-settings.md`) — from this Context's own `settings.json` read,
never a 2nd.

"CI checks" MUST stay unfiltered — Step 7 and `setup/bootstrap.md` q6 each read the raw array.

**Filesystem:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/locate-repo.md` BEFORE Step 1 for `<repo_dir>`.
FORBIDDEN: `cd`. Everything this command writes — `notebooks/review/<repo>/`, the worktree, `.gitignore`
— is relative to pwd: 1 workspace ⇒ 1 `notebooks/review/` for every repo reviewed from it.
`<repo_dir>` ONLY aims git: `git -C "<repo_dir>" …`. Before writing under `notebooks/review/` → state
pwd + `<repo>` in chat.

`core/pr-target.md` §5 gates entry into Step 1.

## Step 1 — Ephemeral worktree

PR code on disk, main tree untouched — no branch change, nothing to restore.

1. `git -C "<repo_dir>" worktree add "$PWD/notebooks/review/<repo>/worktrees/pr<pull_number>-$RANDOM"
   --detach` — random name, never reused; the ABSOLUTE path is what lets pwd be no repo at all. Then
   `V§"Check out the PR head into a worktree"`, DETACHED, in a subshell pinned to the worktree so the
   working directory never moves. `Read`/`Grep` at `<worktree>/<path>`.
2. `git -C "<worktree>" rev-parse HEAD` MUST prefix-match "Head SHA" — the commit the Context "Diff"
   was read at, NEVER a SHA fetched here. Born on the main clone's HEAD, the worktree reviews a tree
   that is NOT the PR whenever the checkout errored; a push between that fetch and this checkout leaves
   the "Diff" stale instead, and re-fetching the SHA now would MATCH the new tree and hide it.
   Mismatch ⇒ STOP, print both SHAs + `<worktree>` and that `/open-pr:clean` removes it. FORBIDDEN:
   retrying the checkout.
3. `git -C "<repo_dir>" fetch origin "+<baseRefName>:refs/remotes/origin/<baseRefName>"` — the refspec
   is what creates `origin/<baseRefName>`; a single-branch clone (`--depth` implies one) otherwise lands
   `FETCH_HEAD` alone and that ref dies on `invalid object name`.
4. Try `Read`ing `<worktree>/.gitmodules` — every run, never cached. Exists && "Diff" contains `Subproject
   commit` → `Read` `"${CLAUDE_PLUGIN_ROOT}"/cases/submodule-review.md`. Else skip.
   FORBIDDEN: `submodule update` here — that file inits bumped paths only.

## Step 2 — Detect stack

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/stack-detection.md`; keep the `(file, [stacks])` mapping for Steps 4-7.

## Step 3 — Setup / doctor

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/repo-settings.md`, then `Read` `notebooks/review/<repo>/settings.json`
in full (Context read it only to resolve `<git_remote_type>`). Resolve `chat_language` and
`doctor_due` per that file.

`<git_remote_type>` is already resolved, never re-asked. Persisting it:

- about to bootstrap → q1's pre-marked default, `setup/bootstrap.md` writes it
- bootstrapped, field predates this schema → read-time fallback only. FORBIDDEN: writing it back
  (`/open-pr:upgrade` owns that backfill)
- `core/pr-target.md` §2's mismatch confirmed a DIFFERENT value → `Edit` `.shared.git_remote_type` here

Branch:

- no file || no `.review` || `.review.bootstrapped` != `true` → `Read`
  `"${CLAUDE_PLUGIN_ROOT}"/setup/bootstrap.md`, then `setup/doctor.md`
- `bootstrapped: true` && `doctor_due` → `setup/doctor.md` only, FORBIDDEN: re-asking bootstrap
- `bootstrapped: true`, `doctor_due` false → skip both

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

FORBIDDEN in EVERY finding: naming a role to reconfirm with ("the BA/client/PM/QA…") — may not exist.
Write "reconfirm this requirement/spec".

Criteria + precedence: Step 5.

**FILE vs LINE** = contextual judgment, no enum, BOUNDED by the diff: LINE only where the target line
sits INSIDE a hunk — an unchanged region of a touched file is FILE by force. LINE:
`-` line ⇒ `side: "LEFT"` (base), `+`/context line ⇒ `side: "RIGHT"` (head). FILE → Step 8 body; LINE →
Step 9 `comments[]`. FORBIDDEN: a FILE finding inside `comments[]`.

**Scope:**

- in-scope first; a 📝 puts no pressure to fix and counts toward nothing
- reading further at `<worktree>/<path>` is optional, but MUST use `Read`'s `offset`/`limit` around the
  changed region (hunk header `@@ -a,b +c,d @@` ± ~20-30 lines). FORBIDDEN: a bare `Read` of a file
  whose change is localized, i.e. not a new file or wholesale rewrite
- the Context "Diff" is the sole source for the files it contains — never refetch it. An "Oversized
  paths" file is absent BY DESIGN; the guard above owns how it gets read
- never read library source unless genuinely unsure
- never pad the count with trivia; there is no minimum N

**Finding format** — every `<…>` is a placeholder to REPLACE, never to print, `<Fix>` being that word in
the output language:

```
<emoji> <short description>.
**<Fix>** — <the fix in words>
<why, 1 sentence, only when it adds to the description>
<marker>
```

A code fix is a fence on its own line, the label line then ending at `**<Fix>**` — no dangling `—`.

`<marker>` = `V§"Finding marker"`, verbatim including any blank line it requires; MUST end EVERY finding,
FILE and LINE alike.

FORBIDDEN: a text label before the description ("Vấn đề"/"Issue") — in a finding the emoji IS the label,
unlike a Step 8 grouping heading, which names the severity too. Severity: 🔴 MUST FIX / 🟠 SHOULD FIX /
🔵 SUGGESTION, and 📝 NOTE for out-of-scope or genuinely not worth fixing in this PR — minor but easy to
fix now is 🔵, not 📝. Each finding carries its own emoji, whatever heading it ends up under.

The fix shows the corrected CODE in a fence by default: a LINE comment replacing that exact line ⇒
` ```suggestion `, anything else ⇒ a normal language fence. Inline code inside prose is NOT a substitute.
Prose-only ⇔ the fix has no code form (a missing test, a spec to reconfirm) — FORBIDDEN: prose when the
code is writable.

≥2 independent points (common on LINE) → one `-` bullet each, never one multi-clause sentence.

## Step 8 — Formatting

Output language = `.shared.output_language` (`core/repo-settings.md`), or Step 0's override.

`<commit_id>` = `V§"Fetch PR head commit SHA"` RIGHT NOW, never Context's "Head SHA". ≠ that value ⇒ the
head moved mid-review and every Step read the older tree: STOP, print both SHAs, say the run must be
called again. Reuse it in the overview and in Step 9's payload; never fetch it twice.

Step 6 ran → apply `re-review.md`'s early-stop gate BEFORE continuing; Step 8/9 may be dropped entirely.

FORBIDDEN in the overview: the agent's own WORK PROCESS (what was fetched or checked out, which commit
was compared, API retries, an interruption midway) — conclusions only. Also FORBIDDEN:
repeating a `comments[]` finding or its Fix, already inline at its diff line; say ONLY what is NOT in
LINE. A closing summary ("No new issues found in this round of changes.") → **bold**, same tier as
**LGTM 🌟**.

Every body anchors itself to `<commit_id>`, linked per `V§"Commit URL"`, and MUST convey that the
ENTIRE diff was reviewed at that point — never that one commit was. 2 forms, both language-neutral in
the parenthetical:

- **prose** (the full structure below) → a real sentence, not a translated fragment
- **bare anchor** → `(commit <link>)`, language-neutral already. FORBIDDEN: an English connective like
  "as of" inside it.

**Body shape** — the 2 reduced shapes:

| FILE | LINE | overview-exclusive¹ | body |
|---|---|---|---|
| – | – | – | EXACTLY 1 line: **LGTM 🌟** (commit `<link>`). No `### 🤖【AI REVIEW】Overview` heading, no thanks, no assessment — only a non-empty skipped-files list may follow it |
| – | ≥1 | – | the opening line ONLY. DROP every severity heading. A normal outcome ⇒ FORBIDDEN: filler like "good PR"/"reviewed thoroughly"; the LINE comments suffice |

¹ an Overview item from Step 7, or a non-empty skipped-files list.

Anything else — ≥1 FILE finding || ≥1 overview-exclusive item — → the full structure:

```
### 🤖【AI REVIEW】Overview
Open with a bare thanks + 🙏, ITSELF IN THE OUTPUT LANGUAGE like all prose here (no embellishment like
"for submitting this PR"/"for the effort"), then state that the ENTIRE SET OF CHANGES WAS REVIEWED AT
that commit (link per above), then 1 sentence of reply instructions, addressing the reader as "you",
then the title/prefix note if any. Assessment prose is OPTIONAL: include it ONLY to carry a conclusion
no finding below does. Nothing such ⇒ stop after the reply instructions.

#### 🔴 MUST FIX
#### 🟠 SHOULD FIX
#### 🔵 SUGGESTION
#### 📝 NOTE

#### <files skipped, IN THE OUTPUT LANGUAGE>
- `<path>` — <short reason, e.g. "diff ~35KB, looks like seed/dump data">
```

Only FILE findings get the full Fix + path structure; LINE stays inline-only. Before printing any
`#### <emoji>` heading: ≥1 FILE finding at EXACTLY that severity? No — even if a LINE finding has it,
even for 📝 → drop the heading. FORBIDDEN: an empty heading, writing "no issues", or a count of N.

The files-skipped section = the content of `<worktree>/.review-skipped.md` (`Read` it again
while writing this Step, don't rely on context) → ALWAYS last in the overview WHEN that file exists
non-empty, even under LGTM. Missing/empty → drop the
heading, never write "none".

## Step 9 — Post (1 composite op, main PR)

Payload: `<commit_id>` from Step 8, `comments[]`
(LINE entries: `path` + `line` + `side` + `body`), and the Step 8 overview (FILE findings + assessment).

Every `line` CONFIRMED against the file, never counted off the hunk header: `RIGHT` ⇒ `Read`
`<worktree>/<path>` at that `offset`, `limit: 2`; `LEFT` ⇒ `git -C "<worktree>" show "$(git -C
"<worktree>" merge-base origin/<baseRefName> HEAD):<path>" | sed -n "<line>p"` — the LEFT side is the
MERGE BASE, never the base tip, which is a DIFFERENT blob once that branch moved. Mismatch ⇒ fix it
BEFORE posting; an off-by-N is a VALID payload on unrelated code.

`V§"Post a review"` — COMPOSITE, step count and mechanism are the vendor's own; follow EXACTLY.
FORBIDDEN: forcing one vendor through another's shape, e.g. inventing a review id for a vendor with
none. Invariants on every vendor:

- exactly 1 review / 1 batch of notes for the main PR, never split. A submodule post is a separate
  result for a DIFFERENT PR and doesn't count here.
- every LINE finding attached to its correct diff line + side

`auto_submit_review`: `true` → carry that entry through to its own submit/publish step; `false` → stop at
whatever holds the review unpublished there — a server-side draft, or the composed review in chat on a
vendor with none — and say it isn't published, FORBIDDEN: publishing on the user's behalf. That entry may
also describe how to verify the post landed — follow it if present.

Post/publish error || that verify reports a mismatch → `Read`
`"${CLAUDE_PLUGIN_ROOT}"/cases/post-review.md`. Happy path → skip that file.

**Then report in chat in ≤3 sentences:** the link, per-severity counts, published or still draft, plus
the worktree path and that `/open-pr:clean` removes it. FORBIDDEN: repeating a finding's description or
its Fix — the PR carries that text. FORBIDDEN: removing the worktree or asking to — the user's later call.

## Step 10 — Asked for something outside the review flow

User asks about memory, a re-scan, or the config — this run or a later PR-less chat → `Read`
`"${CLAUDE_PLUGIN_ROOT}"/cases/chat-requests.md`. Nothing asked → skip; the scheduled doctor is Step
3's job.

---

ARGUMENTS: $ARGUMENTS
