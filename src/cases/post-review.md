# Post-review — POST error or verify mismatch (Step 9 `review.md`)

Not a slash command. `review.md` Step 9 `Read`s this file ONLY when:

- the `POST .../pulls/{pull_number}/reviews` call returns an error (e.g. 422), **or**
- verified `state` mismatches the expectation set by `auto_submit_review`.

Happy path (POST OK + correct state) → do not read this file.

## When POST errors

1. Read the error message; cross-check against the Step 9 schema (`comments[]` missing `line`?
   `line`/`side` wrong side of the diff?).
2. Fix the payload → call again **exactly once**.
3. Still erroring → STOP, report the real error to the user. Do not try any other workaround.
4. FORBIDDEN to create/delete a test ("test", "isolate") review or comment on the real PR to debug.
5. Error because the `gh auth` account is the PR's own author (GitHub restricts self-review) → just
   inform the user, no workaround.

Do not use `gh pr review --comment` or a standalone POST to `/pulls/{n}/comments` — ONLY
`POST .../pulls/{n}/reviews`.

## When verify mismatches

After `gh api .../reviews/<review_id> --jq '{id, state}'` (`<review_id>` taken from the POST
response at Step 9 — or from the retry call in the section above if the first POST errored.
FORBIDDEN to switch to `.../reviews --jq '.[-1] | ...'` to "get the latest review" — if another
review was submitted at that exact moment, `.[-1]` would point to the WRONG review, someone
else's):

- `auto_submit_review: true` but still `PENDING` even though `event` was sent → submit:
  `gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events -f event="COMMENT"`.
- `auto_submit_review: false` but `state` isn't `PENDING` → report the actual result to the user;
  do not automatically APPROVE/REQUEST_CHANGES or post another review.

Do not add any other verification step (no re-fetching the diff, no re-listing comments, no
creating a test review).
