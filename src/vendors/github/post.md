# GitHub — post a review

## Post a review

1 POST carrying findings + overview together:

```bash
gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/reviews \
  --input - --jq '.id' <<'EOF'
{
  "body": "<overview>",
  "commit_id": "<commit_id>",
  "comments": [
    {"path": "<file>", "line": <n>, "side": "<LEFT|RIGHT>", "body": "<LINE finding>"}
  ]
}
EOF
```

No `event` key ⇒ the review is created `PENDING`; making it visible is "Publish the pending review"
alone. `--input -` with a QUOTED heredoc (`<<'EOF'`, never bare `<<EOF`) is MANDATORY: finding text
originates in the PR diff, i.e. attacker-controlled, and an unquoted heredoc lets the running shell
expand it before `gh` sees it — a PHP `$var` corrupts the payload, a `$(cmd)` executes on the user's
machine. `--jq '.id'` takes `<review_id>` straight from the response — reuse it below, FORBIDDEN:
re-listing reviews to guess it.

## Verify a posted review's state

`gh api repos/{owner}/{repo}/pulls/{pull_number}/reviews/<review_id> --jq '{id, state}'` —
`<review_id>` from the POST response, never re-derived. FORBIDDEN: `.../reviews --jq '.[-1] | …'` to
grab "the latest review": another person's review submitted at that moment makes `.[-1]` theirs.

## Publish the pending review

`gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events -f
event="COMMENT"`

## Commit URL

`[<first 7 of commit_id>](https://github.com/<owner>/<repo>/commit/<commit_id>)`

## Post-error notes

- The authenticated account IS the PR's author → GitHub's self-review restriction blocks the POST.
  Inform the user, no workaround exists.
- A 422 usually means the payload's `comments[]` shape is wrong (missing `line`, or `line`/`side`
  pointing at the wrong side of the diff).
- FORBIDDEN as a substitute for "Post a review": `gh pr review --comment`, or a standalone POST to
  `/pulls/{pull_number}/comments` — that endpoint creates a comment outside any review object.
