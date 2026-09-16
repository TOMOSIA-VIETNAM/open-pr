# Post-review — post/publish error or verify mismatch

Reached ONLY when `<op> post`/`<op> publish` errors, || `<op> post-verify` contradicts what
`auto_submit_review` expected. The happy path never reads this file.

## The post/publish call errored

1. Read stderr — its `hint:` line maps this vendor's known failure modes (a `comments[]` entry off the
   diff; a rejected `commit_id` = force-pushed since the "Diff" was read, no payload fix exists — report
   it, say the run must be called again).
2. A payload fix exists → fix the payload file, retry EXACTLY ONCE.
3. Still failing → STOP and report the real error. No other workaround; a permission-shaped error is
   informational only and is never worked around.
4. FORBIDDEN: creating or deleting a "test"/"isolate" review or note on the real PR to debug, or any
   posting outside `<op> post`/`publish`/`reply`.
5. A partial Bitbucket publish (1 request per part) → `<op> post-verify --marker` shows what landed;
   re-post ONLY the missing parts — a duplicate has no bulk undo.

## The verify step mismatched

Re-run `<op> post-verify` once (a race against someone else's concurrent review is possible).

- `auto_submit_review: true` && still unpublished although publish was already sent → retry
  `<op> publish` once.
- `auto_submit_review: false` && it reports anything other than unpublished → report the actual result.
  FORBIDDEN: auto APPROVE/REQUEST_CHANGES, or posting another review.

FORBIDDEN: any other verification — re-fetching the diff, re-listing comments, creating a test review.
