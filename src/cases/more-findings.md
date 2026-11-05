# More findings after this run posted

Step 9's 1 review per round still holds — `Same round` adds comments, never a second review; the user
picks the round. Chat already says which ⇒ no ask.
Step 9 left nothing published (draft, Bitbucket payload file, LGTM printed in chat) ⇒ no ask: fold
the new findings into Step 8's body and run Step 9 again; `post` exit 8 on that draft →
`cases/pending-draft.md`, option `Discard it and post this review` — this run's own draft, superseded,
whatever that file pre-marks.
Else ONE CHOICE per `core/guardrails.md`, EXACTLY 2 options, `(Recommended)` on `Same round` when
`<op> context --sections head` still prints Step 8's `<commit_id>`, on `New round` when it moved:

- `Same round` — each `line` confirmed by `verify-line` as in Step 9. LINE findings: ONE
  `<op> comment --payload F`, F = `{"commit_id","comments":[…]}`, Step 8's `<commit_id>`, `comments[]`
  as in Step 9; exit 1 ⇒ the `inline=` lines it printed landed: one more `comment` with only the
  comments no `inline=` line names, never the whole payload; fails again ⇒ name the unposted ones to
  the user. Then the FILE findings + each `moved_to_overview=` one: ONE `<op> reply --kind top` on
  the posted overview — the one Step 9's `post-verify` `url=` names, never merely the newest review on
  the PR (id from "Reviews"; GitLab: its thread from "Review threads" — fetch both with
  `<op> context --sections reviews,threads`, Context did not). Body: each as `path:line` + severity +
  text, opening with the first finding — no preamble — ending with `<op> marker --kind reply`. None of
  them ⇒ no reply.
- `New round` — run this command again on the same PR URL: the posted review is then "Old comments",
  and `cases/re-review.md` keeps the new batch to what is new.
