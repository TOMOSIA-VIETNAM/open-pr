# Bitbucket Data Center — post a review

This vendor does have pending comments of its own, but its API documents no way to CREATE one — only
reading them (`GET …/review`) and completing them (`PUT …/review`). Guessing that payload would risk
publishing a review nobody approved ⇒ `core/pending-review-staging.md` supplies the unpublished stage, and
owns the staging file, the marks, the resume rule and the verify arithmetic. Only what is this vendor's own
is below.

## Post a review

`payload` per element:

| element | `payload` |
|---|---|
| overview, every FILE finding inside its body | `{"text": "<overview>"}` |
| LINE finding | `{"text": "<finding>", "anchor": {"diffType": "EFFECTIVE", "path": "<path>", "line": <line>, "lineType": "<ADDED\|REMOVED\|CONTEXT>", "fileType": "<TO\|FROM>"}}` |

The anchor triple MUST agree with the diff, or the comment is rejected: an added line ⇒ `ADDED` + `TO`, a
removed line ⇒ `REMOVED` + `FROM`, an unchanged line quoted for context ⇒ `CONTEXT` + `TO`. `diffType:
"EFFECTIVE"` anchors against the PR's current diff, which is what a review comments on.

## Verify a posted review's state

`<curl> "<activities>" | jq -r --arg m '<finding_marker>' '[.values[] | select(.action == "COMMENTED" and
(.comment.text | contains($m)))] | length'` — `<finding_marker>` = the FINDING marker of
`core/finding-markers.md`, never the reply one.

## Publish the pending review

The POST each element goes to:

```bash
<curl> -X POST -H "Content-Type: application/json" "<api>/pull-requests/<pull_number>/comments" --data @-
```

That `-H` is MANDATORY: without it the body comes back rejected as an unsupported media type.

## Commit URL

`[<first 7 of commit_id>](<host>/projects/<owner>/repos/<repo>/commits/<commit_id>)` — `<host>` = this PR's
own URL host, so every self-hosted instance stays correct.

## Post-error notes

- A 400 naming `anchor` is a bad anchor: a `path` outside this PR's changed files, or a
  `line`/`lineType`/`fileType` triple the diff contradicts. Fix that element, re-run that index alone.
- 401 ⇒ the token is unset or expired; 403 ⇒ it is valid but carries Read only, and posting needs Write.
- FORBIDDEN as a substitute for "Publish the pending review": `PUT …/pull-requests/<pull_number>/review`.
  It publishes whatever pending threads the account already has — which this flow never creates — and
  sets a participant status (approved / needs work) nobody asked for.
