# Bitbucket Cloud — thread interaction

## Reply on a PR

ONE mechanism for BOTH kinds — a reply is a comment carrying `parent`, and Cloud accepts that whether the
parent is anchored to a line or top-level:

```bash
<curl> -X POST -H "Content-Type: application/json" \
  "<api>/pullrequests/<pull_number>/comments" --data @<reply>.json
```

`<reply>.json` = `{"content": {"raw": "<content>"}, "parent": {"id": <comment_id>}}`. FORBIDDEN: omitting
`parent` — the reply then lands as a new top-level comment on the PR.

## Resolve a review thread

`<curl> -X POST "<api>/pullrequests/<pull_number>/comments/<comment_id>/resolve"` — `<comment_id>` MUST be
the thread's ROOT (`parent` absent). A finding's own comment IS that root unless "Fetch review threads"
shows it has a `parent`, in which case follow `parent.id` up first. `DELETE` on the same path unresolves.

## React to a PR comment

**No equivalent.** Cloud exposes no reactions endpoint — the emoji picker in its UI has no public API behind
it. A caller reacting as an ADDITION to some other action still performs that other action, and adds
nothing here.

## Finding permalink

`<curl> "<api>/pullrequests/<pull_number>/comments/<comment_id>?fields=links.html.href" | jq -r
'.links.html.href'`, `<comment_id>` per `core/pending-review-staging.md`.
