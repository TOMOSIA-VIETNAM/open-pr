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

`<paged>; paged "<comments>&fields=next,values.id,values.content.raw,values.inline,values.deleted"
'.values[] | select(.deleted != true and (.content.raw | contains("<finding_marker>"))) | {id, path:
.inline.path, line: .inline.to} | @json'` — `<finding_marker>` = the "Finding marker" entry below, never
the reply one.

Nothing ⇒ nothing published yet. Otherwise each line names a finding ALREADY on the PR by path and line,
which is what makes a half-finished publish recoverable: a bare count says how many landed but not which,
and Bitbucket has no bulk undo for a duplicate. `path`/`line` are `null` for the overview. `| wc -l` gives
the count when only the count is wanted. Walking EVERY page is what makes either answer trustworthy —
stopping at page 1 reads a published review as unpublished and posts it twice.

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

## Finding marker

`[bot-finding]: #` — a link reference definition, NOT an HTML comment: Bitbucket escapes raw HTML, so
`<!-- … -->` would show up verbatim on the page.

MUST be the last line of the body with a BLANK LINE before it. A definition cannot interrupt a
paragraph, and pressed against the text above it this renders as a visible broken link.

## Post-error notes

- A 400 whose `error.message` names `inline` is a bad anchor: a `path` not among the files this PR changed,
  or a `to`/`from` line the diff never touches. Fix that payload, re-post that one finding.
- Publishing is 1 request per finding, so it can fail part-way. Re-run "Verify a posted review's state" and
  re-post only the findings absent from the PR — FORBIDDEN: re-posting one already there, since Bitbucket
  has no bulk undo and a duplicate has to be deleted comment by comment.
- FORBIDDEN as a substitute for "Post a review": POSTing any comment while composing. It publishes
  immediately and destroys the only stage where `auto_submit_review: false` can hold a review back.
