---
argument-hint: "<PR URL> [other PR URL...] [content]"
description: Review PRs against the conventions learned from each repo — 1 post per PR, findings tagged by severity, code left untouched.
disable-model-invocation: true
---

> **CRITICAL:** `Read` `"${CLAUDE_PLUGIN_ROOT}"/core/guardrails.md` and `core/cli.md` FIRST — shared
> rules + the `<op>` runtime, not repeated here. `<op>` ≡ `sh "${CLAUDE_PLUGIN_ROOT}"/bin/open-pr.sh`
> — THIS line carries the absolute path; the env var does not exist inside the shell. On top of those:
> - Read-only on the reviewed repo; the only write is Step 9's 1 review (+ 1 more on a submodule PR
>   when Step 1 detects a bump). FORBIDDEN: close/merge/reopen, create/delete/switch a branch, push,
>   edit code → mention it in the review instead.
> - The worktree may surface the REVIEWED repo's own `.claude/skills/` — its dev workflow, not a
>   review tool. FORBIDDEN: invoking it, even when listed as available.

## Step 0 — Target

`<op> target <url>` → `vendor/owner/repo/pull_number/host`; exit 4 or no URL → print:

```
❌ Error: No PR URL provided.
Usage: /open-pr:review <PR URL>
Example (GitHub): /open-pr:review https://github.com/org/repo/pull/123
Example (GitLab): /open-pr:review https://gitlab.com/org/repo/-/merge_requests/123
```

`Read` `"${CLAUDE_PLUGIN_ROOT}"/core/pr-target.md` — vendor reconciliation, `<repo>`, free-form-text
rule, empty-"PR info" stop. A language instruction in `ARGUMENTS`/chat overrides
`.shared.output_language`, this run only.

**≥2 valid PR URLs** && the intent isn't already clear from `ARGUMENTS`/chat → ask "Found N PRs —
review all N or just the first?", WAIT (extras may be reference-only). Confirmed multi-PR → run Step 0
→ Step 9 to COMPLETION per URL, SEQUENTIALLY, each with its own worktree/memory/post. FORBIDDEN:
parallel, subagent. `[content]` applies to every PR. All done → 1 chat summary, 1 line per PR, shaped
by Step 9's reporting rule; nothing further posted.

## Context

`<op> settings --repo <repo>` → this run's resolved config (`core/repo-settings.md` names what each
field means). `<vendor>` MUST be reconciled (`core/pr-target.md` §2) BEFORE the next call. Then ONE
call fetches everything — `<op> context` with `--max-patch-bytes` = `big_file_threshold_kb` × 1024;
its `## <label>` sections are what later Steps name. Any path "Diff size per file" lists that "Diff"
lacks is an omitted file → carry to Step 7 as **"Oversized paths"**. "CI checks" stays unfiltered —
Step 7 and `setup/bootstrap.md` q6 each read the raw list.

**Filesystem:** `<op> locate-repo` → `<repo_dir>`; exit 5 → ask with a CHOICE in plain language —
name the N directories found and why each might be it — STOP if unresolved. FORBIDDEN: `cd`.
Everything this command writes — `notebooks/review/<repo>/`, the worktree, `.gitignore` — is
relative to pwd: 1 workspace ⇒ 1 `notebooks/review/` for every repo reviewed from it. Before
writing under `notebooks/review/` → state pwd + `<repo>` in chat. No `notebooks/review/` line in
`.gitignore` at pwd → add exactly that line.

## Step 1 — Ephemeral worktree

`<op> checkout` with `--head-sha` = "Head SHA", `--base` = `baseRefName`, `--repo-dir <repo_dir>` →
`worktree=<path>`; PR code on disk, main tree untouched, gated to the commit the "Diff" was read at.
`Read`/`Grep` at `<worktree>/<path>`. Exit 2 ⇒ STOP, print both SHAs + `<worktree>` and that
`/open-pr:clean` removes it. Exit 3 ⇒ STOP with its stderr. FORBIDDEN: retrying past the script's own
retry, or comparing against a freshly fetched SHA — that hides the stale diff.

Then try `Read`ing `<worktree>/.gitmodules` — every run, never cached. Exists && "Diff" contains
`Subproject commit` → `Read` `"${CLAUDE_PLUGIN_ROOT}"/cases/submodule-review.md`. Else skip.

## Step 2 — Detect stack

`<op> stacks --repo-dir <repo_dir> <every "Files" path>` → keep the `(file, stacks)` mapping for
Steps 4-7; judge each `.md` line per `core/cli.md`'s note.

## Step 3 — Setup / doctor

From the Context `settings` call: resolve `chat_language` per `core/repo-settings.md`; `doctor_due` is
already computed. `<vendor>` is already reconciled, never re-asked. Persisting it:

- about to bootstrap → q1's pre-marked default, `setup/bootstrap.md` writes it
- bootstrapped, field predates this schema → read-time value only. FORBIDDEN: writing it back
  (`/open-pr:upgrade` owns that backfill); a confirmed mismatch was already persisted at §2

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
`Read` `"${CLAUDE_PLUGIN_ROOT}"/cases/large-diff-guards.md`, follow it (it may STOP the command).
Neither → proceed.

**Overview items** — never counted toward N, never entered into `comments[]`:

- title/body vague on business context → note it atop the Step 8 overview, suggest the dev add detail.
  FORBIDDEN: writing it for them.
- `headRefName` carries a ticket code but the title lacks a matching prefix → note it. No ticket in the
  branch → skip.
- "CI checks" has ≥1 `fail` line && `review_ci_status` != `false` → 1 warning sentence (check name +
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
- reading further at `<worktree>/<path>` is optional, but MUST use `Read`'s `offset`/`limit` around
  the changed region (hunk header `@@ -a,b +c,d @@` ± ~20-30 lines). FORBIDDEN: a bare `Read` of a
  file whose change is localized — i.e. not a new file or wholesale rewrite
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

`<marker>` = `<op> marker --kind finding`, verbatim, on its own line after a blank line; MUST end EVERY
finding, FILE and LINE alike.

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

Output language = `.shared.output_language`, or Step 0's override.

`<op> context --sections head` RIGHT NOW is a CHECK value, never an anchor. == "Head SHA" ⇒
`<commit_id>` = it. ≠ ⇒ the head moved mid-review ⇒ `<commit_id>` = "Head SHA", the commit every Step
read, plus 1 sentence beside the anchor — WHATEVER shape the body takes, the LGTM line included —
saying a newer commit is unreviewed. FORBIDDEN: anchoring to the checked value — no finding describes
that tree. Reuse `<commit_id>` in the overview and in Step 9's payload; never fetch it twice.

Step 6 ran → apply `re-review.md`'s early-stop gate BEFORE continuing; Step 8/9 may be dropped entirely.

FORBIDDEN in the overview: the agent's own WORK PROCESS (fetches, checkouts, compared commits, API
retries, an interruption midway) — conclusions only. Also FORBIDDEN: repeating a `comments[]` finding
or its Fix, already inline at its diff line; say ONLY what is NOT in LINE. A closing summary ("No new
issues found in this round of changes.") → **bold**, same tier as **LGTM 🌟**.

Every body anchors itself to `<commit_id>`, linked per `<op> commit-url`, and MUST convey that the
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
then the title/prefix note if any. Assessment prose is OPTIONAL, ≤3 sentences, 1 conclusion per sentence
— never one multi-clause sentence: include it ONLY to carry a conclusion no finding below does. Nothing such ⇒ stop at the title/prefix note.

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

Write the payload — `core/cli.md`'s ONE shape, `<commit_id>` from Step 8 — with a file-writing tool.

Every `line` CONFIRMED first: `<op> verify-line` per LINE finding prints the line's REAL content —
matches the finding ⇒ keep; different code ⇒ fix the number BEFORE posting, an off-by-N is a VALID
payload on unrelated code; `UNCONFIRMABLE` ⇒ the finding becomes FILE.

Then `<op> post`. Invariants on every vendor:

- exactly 1 review / 1 batch for the main PR, never split. A submodule post is a separate result for a
  DIFFERENT PR and doesn't count here.
- every LINE finding attached to its correct diff line + side

`auto_submit_review`: `true` → `<op> publish`, then `<op> post-verify` confirms it landed; `false` →
stop at whatever `post` left unpublished — a server-side draft, or (Bitbucket, which has no draft) the
payload file itself with nothing on the PR — and say it isn't published. FORBIDDEN: publishing on the
user's behalf.

Post/publish error || post-verify mismatch → `Read` `"${CLAUDE_PLUGIN_ROOT}"/cases/post-review.md`.
Happy path → skip that file.

**Then report in chat in ≤3 sentences:** the link, per-severity counts, published or still draft, plus
the worktree path and that `/open-pr:clean` removes it. FORBIDDEN: repeating a finding's description or
its Fix — the PR carries that text; removing the worktree, or asking to — the user's later call.

## Step 10 — Asked for something outside the review flow

User asks about memory, a re-scan, or the config — this run or a later PR-less chat → `Read`
`"${CLAUDE_PLUGIN_ROOT}"/cases/chat-requests.md`. Nothing asked → skip; the scheduled doctor is Step
3's job.

---

ARGUMENTS: $ARGUMENTS
