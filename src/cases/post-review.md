# Post-review — post/publish error or verify mismatch (Step 9 `review.md`)

Not a slash command. `review.md` Step 9 `Read`s this file ONLY WHEN: the vendor's own "Post a
review" call errors (e.g. GitHub 422) || that same vendor's own verify step reports a mismatch
against `auto_submit_review`'s expectation.

Happy path (post OK + correct state) ⇒ skip this file entirely.

## WHEN the post/publish call errors

1. MUST read the error, cross-check against Step 9's payload shape (`comments[]` missing `line`?
   `line`/`side` wrong side of diff?).
2. MUST fix payload → retry EXACTLY ONCE.
3. Still erroring → MUST STOP, report the real error to user. No other workaround.
4. FORBIDDEN: create/delete a test ("test", "isolate") review/note on the real PR to debug.
5. GitHub specifically: error = the authenticated account IS the PR's own author (GitHub's
   self-review restriction) → MUST inform user only, no workaround. Any other vendor's own
   permission-shaped error → same treatment (inform the user, no workaround), read per that
   vendor's own error message.

MUST use ONLY the vendor's own "Post a review" mechanism (`Read`
`"${CLAUDE_PLUGIN_ROOT}"/vendors/<git_remote_type>.md` if unsure) — FORBIDDEN: a shortcut that
creates a STANDALONE comment instead of going through that mechanism (each vendor file's own "Post
a review" entry names the exact shortcut command to avoid for that vendor).

## WHEN the vendor's own verify step mismatches

`Read` `"${CLAUDE_PLUGIN_ROOT}"/vendors/<git_remote_type>.md` "Verify a posted review's state" —
GitHub: `<review_id>` = from Step 9's POST response, || from the retry above if the first POST
errored; that same entry's note on the `.[-1]` race window applies here too (another review
submitted at that exact moment ⇒ `.[-1]` = someone else's review, WRONG target). A vendor with no
single review-id/state concept (GitLab) → re-run that SAME entry's own way of checking instead of
inventing a different one here.

- `auto_submit_review: true` && the vendor still reports its pending/draft state despite the
  submit/publish step already having been sent → MUST retry that SAME vendor's "Submit a PENDING
  review" entry once.
- `auto_submit_review: false` && the vendor reports something OTHER than pending/draft → MUST
  report the actual result to user. FORBIDDEN: auto APPROVE/REQUEST_CHANGES, posting another
  review.

FORBIDDEN: any other verification step (re-fetch diff, re-list comments, create a test review).
