# GitHub vendor operations — `gh`/`git` command reference

Not a slash command, no frontmatter — plain reference data. Placeholders (`<owner>`, `<repo>`,
`<pull_number>`, `<comment_id>`...) MUST be substituted with the caller's OWN values, never
hardcoded in this file.

## Fetch PR basic info

`gh pr view <url> -R "<owner>/<repo>" --json <fields>` — `<fields>` is caller-supplied (only the
fields actually needed for that call).

## Fetch PR head commit SHA

`gh pr view <url> -R "<owner>/<repo>" --json headRefOid --jq .headRefOid` — call the result
`<commit_id>`.

## Fetch PR diff — file list

`gh pr diff <url> -R "<owner>/<repo>" --name-only`

## Fetch PR diff — full patch

`gh pr diff <url> -R "<owner>/<repo>"`

## Fetch PR commits headlines

`gh pr view <url> -R "<owner>/<repo>" --json commits --jq '.commits[].messageHeadline'`

## Fetch PR review comments (LINE-level findings)

`gh api repos/<owner>/<repo>/pulls/<pull_number>/comments` — add `--paginate` WHEN the PR may have
more than 1 page of comments (always safe to include).

## Fetch PR diff size per file

`gh api --paginate repos/<owner>/<repo>/pulls/<pull_number>/files --jq '.[] | if .patch == null
then "UNKNOWN(no patch — too large/binary/rename) \(.filename)" else "\(.patch|length)
\(.filename)" end'` — `--paginate` MUST stay: a PR with >30 files ⇒ GitHub paginates, missing this
flag silently drops later-page file sizes.

## Fetch CI checks

`gh pr checks <url> -R "<owner>/<repo>" --json bucket,name,link --jq '.[] | "\(.bucket) \(.name) —
\(.link)"' || true` — `|| true` is harmless when the repo has no CI, prevents exit-on-error WHEN a
check is failing/pending.

## Fetch PR reviews (FILE-level findings + review_id)

`gh api --paginate repos/<owner>/<repo>/pulls/<pull_number>/reviews`

## Fetch account running the command

`gh api user --jq .login`

## Fetch review threads (id + isResolved + comment ids) via GraphQL

`gh api graphql -f
query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id
isResolved comments(first:100){nodes{databaseId}}}}}}}' -f o="$OWNER" -f r="$REPO" -F
n="$PULL_NUMBER"`

A NARROWER variant (`id` + only the FIRST comment's `databaseId`, no `isResolved`) exists for a
different purpose — see "Resolve a review thread" below, do not conflate the two.

## Checkout a PR into a fresh worktree

1. `git worktree add "notebooks/review/<repo>/worktrees/review-pr<pull_number>-$RANDOM" --detach`
   — random name, never reused.
2. `(cd "notebooks/review/<repo>/worktrees/<name>" && gh pr checkout <pull_number> -R
   "<owner>/<repo>" && git checkout --detach)` — MUST `git checkout --detach` IMMEDIATELY AFTER
   `gh pr checkout` → that command leaves the PR's tracking branch checked out ⇒ git locks it
   against deletion in the user's own root repo (`cannot delete branch ... checked out at <path>`)
   until the worktree is removed. Detaching now releases the lock without depending on the user to
   clean up the worktree themselves.

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && gh pr checkout <n-submodule> -R
"<owner-submodule>/<repo-submodule>")` — REUSES a directory `git submodule update --init
--recursive` already put on disk; does NOT create a new worktree.

## Post a review (1 POST — findings + overview together)

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

No `event` key — this call always creates the review in `PENDING` state; whether/when it becomes
visible is entirely the separate "Submit a PENDING review" entry below, this entry has no
awareness of that decision. MUST use `--input -` + a heredoc with a QUOTED delimiter (`<<'EOF'`,
never a bare `<<EOF`) — finding text originates from the PR diff, i.e. ATTACKER-CONTROLLED data. An
unquoted heredoc lets bash expand `$var`/`` `cmd` ``/`$(...)` on the RUNNING SHELL before the
payload ever reaches `gh api` — a finding containing PHP code (`$var`) would corrupt the payload,
one containing `$(a command)` would get ACTUALLY EXECUTED on the user's machine. `--jq '.id'` grabs
`<review_id>` DIRECTLY from the POST response — reuse it for "Verify"/"Submit" below, FORBIDDEN:
re-fetching the list and guessing (race window, see "Verify a posted review's state"). FORBIDDEN:
`gh pr review --comment`, or a standalone POST to `/pulls/{pull_number}/comments` — that endpoint
creates a STANDALONE comment, not through a review object; ONLY the single endpoint above ever
creates this PR's review.

## Verify a posted review's state

`gh api repos/{owner}/{repo}/pulls/{pull_number}/reviews/<review_id> --jq '{id, state}'`
(`<review_id>` = taken from the POST response above, never re-derived another way). FORBIDDEN:
`.../reviews --jq '.[-1] | ...'` to grab "the latest review in the list" — race window: another
review (another person/bot) submitted at that exact moment ⇒ `.[-1]` points to THEIRS, not the one
just created.

## Submit a PENDING review

`gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events -f
event="COMMENT"` — publishes a review left `PENDING` by "Post a review" above.

## Reply on a PR

- **LINE-level** (original finding has `path`+`line`):
  `gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies -f
  body="<content>"` (`comment_id` = id of the ORIGINAL finding comment — omitting `{pull_number}`
  causes a 404).
- **FILE-level / OVERVIEW-level** (no path/line, lives inside a review's `body` — GitHub has no
  reply-to-review-body endpoint):
  `gh api -X POST repos/{owner}/{repo}/issues/{pull_number}/comments -f body="<content>"`.

## Resolve a review thread (GraphQL)

1. Look up `threadId`:
   `gh api graphql -f
   query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id
   comments(first:1){nodes{databaseId}}}}}}}' -f o={owner} -f r={repo} -F n={pull_number}` — take
   the `id` of the thread whose `databaseId` matches the finding's `comment_id`.
2. Resolve:
   `gh api graphql -f
   query='mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{id isResolved}}}' -f
   t=<threadId>`.

## React to a PR comment

`gh api -X POST repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions -f
content=<+1|heart|hooray|rocket|confused|eyes>`.
