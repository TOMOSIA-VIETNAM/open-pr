# Post-review — post/publish error or verify mismatch

Reached ONLY when the post/publish call errors, || the vendor's own verify step contradicts what
`auto_submit_review` expected. The happy path never reads this file.

## The post/publish call errored

1. Read the error and cross-check the payload against `V§"Post-error notes"` for this vendor's known
   failure modes.
2. Fix the payload → retry EXACTLY ONCE.
3. Still failing → STOP and report the real error. No other workaround; a permission-shaped error
   (whatever that vendor calls it) is informational only and is never worked around.
4. FORBIDDEN: creating or deleting a "test"/"isolate" review or note on the real PR to debug.

FORBIDDEN: any shortcut posting outside `V§"Post a review"` — that vendor's "Post-error notes" entry
names the exact commands never to substitute for it.

## The verify step mismatched

Re-run `V§"Verify a posted review's state"`; that entry's own caveats apply here too (a race against
someone else's concurrent review, or a vendor with no state field at all).

- `auto_submit_review: true` && still unpublished although the publish call was already sent → retry
  `V§"Publish the pending review"` once.
- `auto_submit_review: false` && it reports anything other than unpublished → report the actual result.
  FORBIDDEN: auto APPROVE/REQUEST_CHANGES, or posting another review.

FORBIDDEN: any other verification — re-fetching the diff, re-listing comments, creating a test review.
