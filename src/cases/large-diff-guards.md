# Large diff guards

`review.md` Step 7 arrives here with ≥1 of its 2 independent guards matched. Apply ONLY the section
whose guard actually matched; the last section applies only when both did.

## File-count guard

- `ARGUMENTS`/chat already named a strategy ("shallow review", "selective deep review", "stop") → use
  it, do NOT ask again.
- Otherwise MUST STOP and ask, exactly these 3 choices, WAIT — FORBIDDEN: picking a default yourself:
  ```
  This PR changes <N> files (> <threshold>) — a full deep review risks heavy effort/missed items.
  Pick a strategy:
  (a) Shallow review of everything — skim every file, reduced depth, only catch clear issues
      directly visible in the diff.
  (b) Selective deep review — go deep on files with real logic, skim config/generated/test files
      lightly.
  (c) Stop — state the reason, suggest the dev split the PR smaller, do not review.
  ```
- **(a)** → every Step 7 rule still applies to EVERY file, minus the optional "read more at
  `<worktree>/<path>`" — rely on the Context "Diff" alone.
- **(b)** → classify by Step 2's stack detection: files with real LOGIC get the FULL Step 7 treatment;
  config/lock/generated/test files (contextual judgment, illustrative not exhaustive) collapse into 1
  light skimmed finding, never dissected line by line.
- **(c)** → FORBIDDEN: running the review at all. Chat only: file count + threshold + suggest splitting
  the PR, then STOP the command entirely, posting nothing.

**Anti-forgotten-file checklist** — only under (a)/(b), N/A to (c):

1. `Write` `<worktree>/.review-checklist.md`, one `- [ ] <path>` line per file in "Files". INTERNAL
   bookkeeping — never appears in the PR body or in chat.
2. A file's review done (finding or not, both count) → `Edit` its line to `- [x] <path>`.
3. **MANDATORY** before writing Step 8: `Read` back `.review-checklist.md` AND `.review-skipped.md`.
   Any line still `[ ]` && absent from `.review-skipped.md` = genuinely FORGOTTEN, not a deliberate
   skip → review it IMMEDIATELY before compiling the summary. FORBIDDEN: letting it pass silently.

## Large/dump-file guard

Applies to each file in "Oversized paths" (Context) — every file whose "Diff size per file" entry exceeds
`big_file_threshold_kb` KB or reads `UNKNOWN`. Its patch is deliberately absent from the Context "Diff",
so reading it here, in bounded chunks, is the only way it is seen at all.

LIMITED peek (`Read` ~30-50 lines at the hunk start, never the whole thing) to tell
data/seed/dump/generated (repetitive structure, all literals, no control flow) from genuinely large real
logic:

- **Data/dump/generated** → FORBIDDEN: line-by-line review, or pasting dump content into the finding.
  Exactly 1 FILE-level finding, usually 📝 NOTE or 🔵 SUGGESTION: "large diff — looks like seed/dump
  data, please confirm this is intentional". Record `- <path> — <reason>` into
  `<worktree>/.review-skipped.md` (`Write` if new, `Edit` to append) — ALWAYS to the file, not just in
  context: Step 8 lists it and the checklist above cross-checks it.
- **Real logic, only incidentally large** → review normally, chunk by chunk with `offset`/`limit`.
  FORBIDDEN: `Read`ing the whole patch at once.

## Both guards matched && the user chose (a)

List EXACTLY the files matching the large/dump guard right after (a) is chosen, combined into ONE
question (never per file): peek to classify, or skip outright?

- **agrees** (all files or specific ones) → limited peek per the section above, for those files only;
  the rest of the PR stays on (a).
- **declines/unclear** → don't read them; record into `.review-skipped.md`, reason "strategy (a) +
  large size, user chose not to review — check it yourself".
- **too large to peek safely even with agreement** (far beyond the threshold, or an `UNKNOWN` that
  turns out huge) → the agent MAY decline the peek, advise skipping to avoid blowing context, and
  record it the same way.
