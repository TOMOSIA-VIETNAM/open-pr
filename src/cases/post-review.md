# Post-review — POST error or verify mismatch (Step 9 `review.md`)

Not a slash command. `review.md` Step 9 `Read`s this file ONLY WHEN: POST
`.../pulls/{pull_number}/reviews` errors (e.g. 422) || verified `state` mismatches
`auto_submit_review`'s expectation.

Happy path (POST OK + correct state) ⇒ skip this file entirely.

## WHEN POST errors

1. MUST read the error, cross-check against Step 9 schema (`comments[]` missing `line`? `line`/
   `side` wrong side of diff?).
2. MUST fix payload → retry EXACTLY ONCE.
3. Still erroring → MUST STOP, report the real error to user. No other workaround.
4. FORBIDDEN: create/delete a test ("test", "isolate") review/comment on the real PR to debug.
5. Error = `gh auth` account IS the PR's own author (GitHub self-review restriction) → MUST inform
   user only, no workaround.

MUST use ONLY `POST .../pulls/{n}/reviews` — never `gh pr review --comment`, never a standalone
POST to `/pulls/{n}/comments`.

## WHEN verify mismatches

`Read` `"${CLAUDE_PLUGIN_ROOT}"/vendors/github.md` "Verify a posted review's state" (`<review_id>` =
from Step 9's POST response, || from the retry above if the first POST errored) — same file's note
on the `.[-1]` race window applies here too: another review submitted at that exact moment ⇒
`.[-1]` = someone else's review, WRONG target.

- `auto_submit_review: true` && still `PENDING` despite `event` sent → MUST submit, same vendors
  file "Submit a PENDING review".
- `auto_submit_review: false` && `state` != `PENDING` → MUST report the actual result to user.
  FORBIDDEN: auto APPROVE/REQUEST_CHANGES, posting another review.

FORBIDDEN: any other verification step (re-fetch diff, re-list comments, create a test review).
