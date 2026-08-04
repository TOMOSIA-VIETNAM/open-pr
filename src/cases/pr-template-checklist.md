# PR template checklist

Unlike the title/description and branch-prefix notes at Step 7, this one DOES count as a FILE-level
finding among the severity levels: it violates a rule the project set for ITSELF, not a style
preference.

`Read` each `pr_template_paths` file **at `<worktree>/<path>`**, not at pwd — doctor detected those
paths over the pwd tree, but the content for THIS PR must come from the worktree, in case the PR edits
the template too. Cross-check against the PR's real `body`: look for leftover unfilled markers — an
unchecked `- [ ]`, or a section still holding the template's own instructions/placeholder/HTML comment
instead of real content. Contextual judgment; there is no fixed list of mandatory items.

≥1 unfilled spot → EXACTLY 1 CONSOLIDATED finding listing every missing item (FORBIDDEN: one finding
per checkbox), in the Step 7 finding format, rated **🟠 SHOULD FIX**, FILE-level ⇒ the Step 8 body under
`#### 🟠 SHOULD FIX`, never `comments[]`.
