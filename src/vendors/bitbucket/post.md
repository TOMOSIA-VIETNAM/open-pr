# Bitbucket Cloud — post a review

Cloud publishes a comment the instant its POST returns, and the `pending` flag its comment schema carries
has no endpoint that publishes it ⇒ `core/pending-review-staging.md` supplies the unpublished stage, and
owns the staging file, the marks, the resume rule and the verify arithmetic. Only what is Cloud's own is
below.

## Post a review

`payload` per element:

| element | `payload` |
|---|---|
| overview, every FILE finding inside its body | `{"content": {"raw": "<overview>"}}` |
| LINE finding | `{"content": {"raw": "<finding>"}, "inline": {"path": "<path>", "to": <line>}}` |

`inline.to` = a line in the NEW file, `inline.from` = a line in the OLD file. Exactly ONE of the two per
element, chosen by the side the finding is on; both, or neither, is rejected.

## Verify a posted review's state

`<curl> "<comments>&fields=next,values.content.raw,values.deleted" | jq -r --arg m '<finding_marker>'
'[.values[] | select(.deleted != true and (.content.raw | contains($m)))] | length'` — `<finding_marker>` =
the FINDING marker of `core/finding-markers.md`, never the reply one.

## Publish the pending review

The POST each element goes to:

```bash
<curl> -X POST -H "Content-Type: application/json" "<api>/pullrequests/<pull_number>/comments" --data @-
```

That `-H` is MANDATORY: without it Cloud reads the body as form data and answers 400.

## Commit URL

`[<first 7 of commit_id>](https://bitbucket.org/<owner>/<repo>/commits/<commit_id>)` — Cloud's commit path
is `/commits/` plural; `/commit/` 404s.

## Post-error notes

- A 400 whose `error.message` names `inline` is a bad anchor: a `path` not among the files this PR changed,
  or a `to`/`from` line the diff never touches. Fix that element, re-run that index alone.
- FORBIDDEN as a substitute for "Post a review": POSTing any comment while composing. It publishes
  immediately and destroys the only stage where `auto_submit_review: false` can hold a review back.
