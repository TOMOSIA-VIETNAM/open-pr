# Bitbucket — post a review

`<api>`/`<curl>`/`<comments>` and the payload rule are defined in this vendor's `fetch.md`, always loaded
before this file.

Bitbucket has NO draft: a comment is visible the instant its POST returns, and the `pending` flag its
comment schema carries has no endpoint that publishes it. So the unpublished stage is the CHAT — the review
is composed there and nothing reaches the PR until "Publish the pending review".

## Post a review

Compose the review in chat, call NOTHING. 1 payload per finding, held for the publish step:

| element | payload |
|---|---|
| overview, every FILE finding inside its body | `{"content": {"raw": "<overview>"}}` |
| LINE finding | `{"content": {"raw": "<finding>"}, "inline": {"path": "<path>", "to": <line>}}` |

`inline.to` = a line in the NEW file, `inline.from` = a line in the OLD file. Exactly ONE of the two per
finding, chosen by the side it is on; both, or neither, is rejected.

Nothing is on the PR when this entry returns.

## Verify a posted review's state

`<paged>; paged "<comments>&fields=next,values.content.raw,values.deleted" '.values[] | select(.deleted
!= true and (.content.raw | contains("<finding_marker>"))) | 1' | wc -l` — `<finding_marker>` = the
FINDING marker of `core/finding-markers.md`, never the reply one. Counting across EVERY page is what
makes the number trustworthy: stopping at page 1 would read a published review as unpublished and post
it a second time.

`0` ⇒ nothing published yet. Otherwise that many findings are already on the PR, which is also what makes a
half-finished publish recoverable: matching on this plugin's own marker leaves a human's concurrent review
uncounted.

## Publish the pending review

1 POST per payload, overview FIRST:

```bash
<curl> -X POST -H "Content-Type: application/json" \
  "<api>/pullrequests/<pull_number>/comments" --data @<payload>.json
```

That `-H` is MANDATORY: without it Bitbucket reads the body as form data and answers 400.

## Commit URL

`[<first 7 of commit_id>](https://bitbucket.org/<owner>/<repo>/commits/<commit_id>)` — the commit path is
`/commits/` plural; `/commit/` 404s.

## Post-error notes

- A 400 whose `error.message` names `inline` is a bad anchor: a `path` not among the files this PR changed,
  or a `to`/`from` line the diff never touches. Fix that payload, re-post that one finding.
- Publishing is 1 request per finding, so it can fail part-way. Re-run "Verify a posted review's state" and
  re-post only the findings absent from the PR — FORBIDDEN: re-posting one already there, since Bitbucket
  has no bulk undo and a duplicate has to be deleted comment by comment.
- FORBIDDEN as a substitute for "Post a review": POSTing any comment while composing. It publishes
  immediately and destroys the only stage where `auto_submit_review: false` can hold a review back.
