# PR template checklist — cross-check the description against the project's self-defined checklist (Step 7 `review.md`)

Not a slash command (lives outside `commands/`). `review.md` Step 7 `Read`s this file WHEN
`settings.json`'s `.review.pr_template_paths` (read at Step 3) is non-empty — empty (no PR
template at all) ⇒ skip entirely, no finding for this item.

Unlike the title/description + branch-ticket-prefix checks at Step 7 (overview-only, not counted
toward severity), this item DOES count as a FILE-level finding among the 3 severity levels at
Step 8 — it's a violation of a rule the project set for ITSELF via the PR template, not merely a
style suggestion.

MUST `Read` the file(s) at `pr_template_paths` **at `<worktree>/<path>`** (the worktree from Step
1 — NOT the direct path at pwd; `pr_template_paths` was detected by doctor over the pwd tree
during setup, but the ACTUAL content for THIS PR must come from the worktree, in case the PR
itself also edits the template file), cross-check against the PR's real `body` (Context). Look for
leftover unfilled markers — e.g. an unchecked `- [ ]` checkbox, a template section still
containing the original instructions/placeholder/HTML-comment text instead of real PR content.
Contextual judgment call, no rigid list of "which items are mandatory".

≥1 unfilled spot → combine into EXACTLY 1 CONSOLIDATED finding (list every missing item within
that single finding — FORBIDDEN: splitting each checkbox into its own finding) using the Step 7
finding format (`🟠 <short description>` + `**Fix**` line, no "Vấn đề"/"Issue" label). Rated
**🟠 SHOULD FIX**, a **FILE**-level finding (not tied to a code line) → Step 8 body under
`#### 🟠 SHOULD FIX`, NOT `comments[]` at Step 9.
