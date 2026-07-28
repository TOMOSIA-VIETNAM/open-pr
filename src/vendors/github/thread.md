# GitHub — thread interaction

## Reply on a PR

- **LINE-level**: `gh api -X POST
  repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies -f body="<content>"` —
  `comment_id` = the ORIGINAL finding comment; omitting `{pull_number}` gives a 404.
- **FILE-level / OVERVIEW-level**: no reply-to-review-body endpoint exists → `gh api -X POST
  repos/{owner}/{repo}/issues/{pull_number}/comments -f body="<content>"`.

## Resolve a review thread

1. `<threadId>` = from "Fetch review threads" (already fetched), the thread whose `databaseId` matches
   the finding's `comment_id` — FORBIDDEN: a second query for it.
2. `gh api graphql -f
   query='mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{id isResolved}}}' -f
   t=<threadId>`

## React to a PR comment

`gh api -X POST repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions -f
content=<+1|heart|hooray|rocket|confused|eyes>`

## Finding permalink

`https://github.com/<owner>/<repo>/pull/<pull_number>#pullrequestreview-<review_id>` — `<review_id>` =
the review containing that finding ("Fetch PR reviews").
