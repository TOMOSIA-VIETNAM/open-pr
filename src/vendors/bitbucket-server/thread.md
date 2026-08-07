# Bitbucket Data Center — thread interaction

## Reply on a PR

ONE mechanism for BOTH kinds — a reply is a comment carrying `parent`, accepted whether the parent is
anchored to a line or top-level:

```bash
<curl> -X POST -H "Content-Type: application/json" \
  "<api>/pull-requests/<pull_number>/comments" --data @<reply>.json
```

`<reply>.json` = `{"text": "<content>", "parent": {"id": <comment_id>}}`. FORBIDDEN: omitting `parent` —
the reply then lands as a new top-level comment on the PR.

## Resolve a review thread

2 calls, because an update is rejected unless it carries the comment's CURRENT version:

1. `<curl> "<api>/pull-requests/<pull_number>/comments/<comment_id>" | jq -r '.version'` → `<version>`.
2. `<curl> -X PUT -H "Content-Type: application/json"
   "<api>/pull-requests/<pull_number>/comments/<comment_id>" -d '{"version": <version>, "state":
   "RESOLVED"}'`

`<comment_id>` MUST be the thread's ROOT (`parent` absent — "Fetch review threads" says which). `-d`
inline is the exception `core/raw-http-vendor.md` allows: this body is a number and a fixed enum, with no
PR text in it. A 409 means someone edited that comment in between ⇒ re-read the version, retry once.

## React to a PR comment

```bash
<curl> -X PUT "<host>/rest/comment-likes/latest/projects/<owner>/repos/<repo>/pull-requests/<pull_number>/comments/<comment_id>/reactions/<emoticon>"
```

`<emoticon>` is this vendor's own emoji shortname, so the caller's name maps: `+1` → `thumbsup`,
`hooray` → `tada`, and `heart`/`rocket`/`confused`/`eyes` unchanged. That mapping is inferred from the
shortnames this vendor's UI uses — its API declares no list — so a 404 on this path means the shortname,
not the comment: drop the reaction, carry on with the action it was decorating, never retry in a loop.

## Finding permalink

`<host>/projects/<owner>/repos/<repo>/pull-requests/<pull_number>/overview?commentId=<comment_id>`, built
from the PR URL since a comment here carries no link of its own; `<comment_id>` per
`core/pending-review-staging.md`.
