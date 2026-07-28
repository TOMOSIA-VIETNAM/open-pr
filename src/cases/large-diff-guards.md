# Large diff guards — many files / large-dump files (Step 7 `review.md`)

Not a slash command (lives outside `commands/`). `review.md` Step 7 `Read`s this file WHEN the PR
matches AT LEAST 1 of 2 independent conditions below — matching neither ⇒ skip, Step 7 proceeds
normally, nothing here applies:

- **File-count guard**: files in "Files" (Context, `--name-only`) > `many_files_threshold` (Step 3
  `review.md`, default `30`).
- **Large/dump-file guard**: ≥1 file whose "Diff size per file" (Context) > `big_file_threshold_kb`
  KB (Step 3, default `20`), or `UNKNOWN` (GitHub dropped the patch, too large).

The 2 guards are independent — a PR may match only 1 (e.g. 5 files but 1 huge → only the
large/dump-file guard applies, "File-count guard" below is skipped entirely). "Interaction of the
2 guards" at the end needs BOTH to match at once.

## File-count guard

- `ARGUMENTS`/chat at invocation ALREADY specified a strategy (e.g. "shallow review", "selective
  deep review", "stop") → use it directly, do NOT ask again.
- Not specified → MUST STOP, ask the user in chat, exactly 3 choices, WAIT for reply, do NOT pick
  a default yourself:
  ```
  This PR changes <N> files (> <threshold>) — a full deep review risks heavy effort/missed items.
  Pick a strategy:
  (a) Shallow review of everything — skim every file, reduced depth, only catch clear issues
      directly visible in the diff.
  (b) Selective deep review — go deep on files with real logic, skim config/generated/test files
      lightly.
  (c) Stop — state the reason, suggest the dev split the PR smaller, do not review.
  ```
- **(a)** → all of Step 7 (`review.md`) still applies to EVERY file, but drop "Read more at
  `<worktree>/<path>` as needed" — rely only on the Context diff. See "Interaction of the 2 guards"
  if the PR ALSO matches the large/dump-file guard.
- **(b)** → use Step 2's stack detection to classify — files with real LOGIC (business code per
  stack) get the FULL review under every normal Step 7 rule; config/lock/generated/test files
  (contextual judgment, illustrative not exhaustive) → lump into 1 light/skimmed finding, never
  dissect line-by-line.
- **(c)** → FORBIDDEN: running Step 7 (the actual review) → go to Step 9 `review.md`. Chat-only:
  state file count + threshold, suggest splitting the PR, STOP the command entirely — post nothing
  to GitHub (same as Step 0's early-exit).

**Anti-forgotten-file checklist** (only WHEN (a)/(b) was chosen — N/A to (c), nothing is
reviewed):

1. (a)/(b) chosen → `Write` `<worktree>/.review-checklist.md`: one line `- [ ] <path>` per file in
   "Files" (Context). INTERNAL bookkeeping ONLY — never appears in the PR body or chat output.
2. File's review done (finding or not, either counts as "done") → `Edit` that line to
   `- [x] <path>`.
3. **MANDATORY, do not skip** — BEFORE writing Step 8 `review.md`: `Read` back
   `.review-checklist.md` AND `.review-skipped.md` (if present). Any line still `[ ]` && NOT in
   `.review-skipped.md` → a file genuinely FORGOTTEN (not a deliberate skip) — go back and review
   it IMMEDIATELY before compiling the summary. FORBIDDEN: letting it slip through as a silent
   omission.

## Large/dump-file guard

For EACH file matching "Large/dump-file guard" above: LIMITED peek (`Read` offset/limit ~30-50
lines at the start of the hunk, never the whole thing) to judge data/seed/dump/generated
(repetitive structure, all literals, no control flow) vs. genuinely-large real logic:

- **Data/dump/generated** → FORBIDDEN: line-by-line review, pasting the dump content back into the
  finding. Exactly 1 FILE-level finding (usually 📝 NOTE or 🔵 SUGGESTION): "large diff — looks like
  seed/dump data, please confirm this is intentional". Record `<path>` + reason into
  `<worktree>/.review-skipped.md` (`- <path> — <reason>` per line, `Write` if new / `Edit` to
  append) — ALWAYS record here, not just in context (a real anchor) — used at Step 8's list +
  cross-checked against the anti-forgotten-file checklist above.
- **Real logic (only incidentally large)** → review normally, chunk by chunk (offset/limit as
  above), FORBIDDEN: `Read`-ing the whole patch at once.

## Interaction of the 2 guards — (a) chosen AND ALSO matching the large/dump-file guard

Applies ONLY when the PR matches BOTH top-of-file conditions AND the user just chose (a). List
EXACTLY the files matching "Large/dump-file guard" right after (a) is chosen — combine into ONE
question (never per-file), asking whether the user wants a classification peek or to skip
outright:

- User agrees (all files, or specific ones) → LIMITED peek per "Large/dump-file guard" above, ONLY
  for those files; the rest of the PR still follows (a) normally.
- User declines/unclear → do not read, record into `.review-skipped.md` (see checklist above),
  reason "strategy (a) + large size, user chose not to review — check it yourself".
- File TOO large to peek safely even if the user agrees (e.g. far beyond threshold, or `UNKNOWN`
  turning out truly huge) → agent may DECLINE to peek, advise the user to skip it (avoid blowing
  context), record into `.review-skipped.md` the same way.
