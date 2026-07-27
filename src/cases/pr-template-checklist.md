# PR template checklist — cross-check the description against the project's self-defined checklist (Step 7 `review.md`)

Not a slash command (lives outside `commands/`). `review.md` Step 7 `Read`s this file when
`meta.json.pr_template_paths` (read at Step 3) is non-empty — empty (the project has no PR
template at all) means skip entirely, do not read this file, do not create any finding for this
item.

Unlike the title/description and branch-ticket-prefix checks at Step 7 (overview-only, not counted
toward severity), this item DOES count as a FILE-level finding among the 3 severity levels at
Step 8, because it is a violation of a rule the project set for itself via the PR template, not
merely a style suggestion.

Read the content of the file(s) at the path(s) in `pr_template_paths` via `Read` **at
`<worktree>/<path>`** (the worktree created at Step 1 of `review.md` — NOT the direct path at pwd;
`pr_template_paths` was detected by doctor over the pwd directory tree during setup, but the ACTUAL
file content for this PR must be read from the code checked out in the worktree, in case the PR
being reviewed itself also edits the template file), and cross-check it against the PR's real
`body` (already fetched in the "Context" block). Look for leftover unfilled markers — e.g. an
unchecked `- [ ]` checkbox, or a template section still containing the original
instructions/placeholder/HTML-comment text instead of actual PR content. This is a contextual
judgment call, with NO rigid list of "which items are mandatory to fill in".

Finding ≥1 unfilled spot → combine into EXACTLY 1 CONSOLIDATED finding (list every missing item
within that single finding, do NOT split each checkbox into its own separate finding) using the
Step 7 finding format (`🟠 <short description>` + a `**Fix**` line — no "Vấn đề"/"Issue" label).
This finding is rated **🟠 SHOULD FIX**, is a **FILE**-level finding (not tied to a specific line
of code), so it goes into the Step 8 body under the `#### 🟠 SHOULD FIX` heading, NOT into
`comments[]` at Step 9.
