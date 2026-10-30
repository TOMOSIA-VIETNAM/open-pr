# More findings after this run posted

Step 9's 1 review per round still holds; the user picks the round. Chat already says which ⇒ no ask.
Else ONE CHOICE per `core/guardrails.md`, EXACTLY 2 options, `(Recommended)` on `Same round` when
`<op> context --sections head` still prints Step 8's `<commit_id>`, on `New round` when it moved:

- `Same round` — ONE `<op> reply --kind top` on the posted overview (id from "Reviews"; GitLab: its
  thread from "Review threads"). Body: every new finding as `path:line` + severity + text, FILE and
  LINE alike, each `line` confirmed by `verify-line` as in Step 9, ending with `<op> marker --kind reply`.
- `New round` — run this command again on the same PR URL: the posted review is then "Old comments",
  and `cases/re-review.md` keeps the new batch to what is new.
