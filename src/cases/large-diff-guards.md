# Large diff guards — many files / large-dump files (Step 7 `review.md`)

Not a slash command (lives outside `commands/`). `review.md` Step 7 `Read`s this file when the PR
being reviewed matches AT LEAST 1 of the 2 independent conditions below — matching neither means
this file is not read, Step 7 proceeds normally, nothing in this file applies:

- **File-count guard**: number of files in "Files" (Context, `--name-only`, one file per line) >
  `many_files_threshold` (Step 3 `review.md`, default `30`).
- **Large/dump-file guard**: at least 1 file whose "Diff size per file" (Context) >
  `big_file_threshold_kb` KB (Step 3, default `20`), or `UNKNOWN` (GitHub dropped the patch for
  being too large).

The 2 guards are independent — a PR may match only 1 of the 2 (e.g. 5 files but 1 of them is
huge → only the large/dump-file guard applies, the "File-count guard" section below is skipped
entirely) — only the "Interaction of the 2 guards" section at the end needs BOTH to match at once.

## File-count guard

- `ARGUMENTS`/chat at command invocation time ALREADY specified a strategy (e.g. "shallow review",
  "selective deep review", "stop") → use it directly, do NOT ask again.
- NOT specified → STOP, ask the user right in chat, offer exactly 3 choices, WAIT for reply, do NOT
  pick a default yourself:
  ```
  This PR changes <N> files (> <threshold>) — a full deep review risks heavy effort/missed items.
  Pick a strategy:
  (a) Shallow review of everything — skim every file, reduced depth, only catch clear issues
      directly visible in the diff.
  (b) Selective deep review — go deep on files with real logic, skim config/generated/test files
      lightly.
  (c) Stop — state the reason, suggest the dev split the PR smaller, do not review.
  ```
- Choosing **(a)**: all of Step 7 (`review.md`) still applies to EVERY file, but drop the "Read
  more at `<worktree>/<path>` as needed" item — rely only on the Context diff, do not proactively
  read context beyond the diff. See "Interaction of the 2 guards" below if the PR ALSO matches the
  large/dump-file guard.
- Choosing **(b)**: use the Step 2 `review.md` result (stack detection) to classify — files with
  real LOGIC (business code per stack) get the FULL review under every normal Step 7 rule;
  config/lock/generated/test files (contextual judgment call — illustrative examples, not a closed
  checklist) → lump together into a light/skimmed finding, do not dissect line-by-line.
- Choosing **(c)**: do NOT run Step 7 (the actual review) → go to Step 9 `review.md`. Chat-only:
  state the file count + threshold, suggest the dev split the PR, STOP the command entirely — post
  nothing to GitHub (same as the early-exit at Step 0 `review.md`).

**Anti-forgotten-file checklist** (only when (a)/(b) above was chosen — does NOT apply to (c) since
nothing is reviewed):

1. As soon as (a)/(b) is chosen: `Write` `<worktree>/.review-checklist.md` — one line
   `- [ ] <path>` per file in "Files" (Context). This file is INTERNAL bookkeeping ONLY — it never
   appears in the PR body or chat output.
2. Once a file's review is done (finding or not, either counts as "done") → `Edit` that line to
   `- [x] <path>`.
3. **MANDATORY, do not skip** — BEFORE writing Step 8 `review.md`: `Read` back
   `.review-checklist.md` AND `.review-skipped.md` (if present). Any line still `[ ]` in the
   checklist AND NOT present in `.review-skipped.md` → this is a file genuinely FORGOTTEN (not a
   deliberate skip) — go back and review that file IMMEDIATELY before compiling the summary, never
   let it slip through as a silent omission.

## Large/dump-file guard

For EACH file matching the "Large/dump-file guard" condition at the top of this file: do a LIMITED
peek (`Read` offset/limit ~30-50 lines at the start of the hunk, do not read the whole thing) to
judge whether it's data/seed/dump/generated (repetitive structure, all literals, no control flow)
or genuinely-large real logic that just happens to change a lot:

- **Data/dump/generated** → do NOT review line-by-line in detail, do NOT paste the dump content
  back into the finding; exactly 1 FILE-level finding (usually 📝 NOTE or 🔵 SUGGESTION) stating
  "large diff — looks like seed/dump data, please confirm this is intentional". Record `<path>` +
  reason into `<worktree>/.review-skipped.md` (one line `- <path> — <reason>` per entry, `Write` if
  the file doesn't exist yet / `Edit` to append if it does) — ALWAYS record it in this file, not
  just in context (this is a real anchor, not something to remember in passing) — used to list at
  Step 8 `review.md` and to cross-check against the anti-forgotten-file checklist above.
- **Real logic (only incidentally large)** → review normally, keep reading chunk by chunk
  (offset/limit as above), do not `Read` the whole patch at once.

## Interaction of the 2 guards — choosing (a) AND ALSO matching the large/dump-file guard

Applies only when the PR matches BOTH conditions at the top of this file AND the user just chose
strategy (a) in "File-count guard". List EXACTLY the files matching "Large/dump-file guard" right
after the user chooses (a) — combine into ONE SINGLE question (do not ask per file separately),
asking whether the user wants to peek to classify data/dump-vs-real-logic or skip outright:

- User agrees (all files, or specifies particular ones) → LIMITED peek per the "Large/dump-file
  guard" rule above, ONLY for those files; the rest of the PR still follows (a) normally.
- User declines/doesn't answer clearly → do not read, record into `.review-skipped.md` (see
  checklist above) with reason "strategy (a) + large size, user chose not to review — check it
  yourself".
- File TOO large to peek safely even if the user agrees (e.g. size far beyond the threshold, or
  `UNKNOWN` that turns out to be truly huge) → the agent may DECLINE to peek, advise the user to
  skip it to avoid blowing context, record into `.review-skipped.md` the same way.
