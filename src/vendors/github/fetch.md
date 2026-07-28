# GitHub — fetch

Substitute the caller's own `<owner>`/`<repo>`/`<pull_number>`/`<comment_id>`… values.

## Fetch PR basic info

`gh pr view <url> -R "<owner>/<repo>" --json <fields>` — `<fields>` caller-supplied.

## Fetch PR head commit SHA

`gh pr view <url> -R "<owner>/<repo>" --json headRefOid --jq .headRefOid` → `<commit_id>`.

## Fetch PR diff — file list

`gh pr diff <url> -R "<owner>/<repo>" --name-only`

## Fetch PR diff — full patch

`gh pr diff <url> -R "<owner>/<repo>"`

## Fetch PR commits headlines

`gh pr view <url> -R "<owner>/<repo>" --json commits --jq '.commits[].messageHeadline'`

## Fetch PR review comments (LINE-level findings)

`gh api repos/<owner>/<repo>/pulls/<pull_number>/comments` — add `--paginate` when the PR may exceed 1
page (always safe).

## Fetch PR diff size per file

`gh api --paginate repos/<owner>/<repo>/pulls/<pull_number>/files --jq '.[] | if .patch == null
then "UNKNOWN(no patch — too large/binary/rename) \(.filename)" else "\(.patch|length)
\(.filename)" end'` — `--paginate` MUST stay: >30 files paginates, and without it later-page sizes are
silently lost.

## Fetch CI checks

`gh pr checks <url> -R "<owner>/<repo>" --json bucket,name,link --jq '.[] | "\(.bucket) \(.name) —
\(.link)"' || true` — `|| true` keeps a failing/pending check (or no CI at all) from exiting non-zero.

## Fetch PR reviews (FILE-level findings + review_id)

`gh api --paginate repos/<owner>/<repo>/pulls/<pull_number>/reviews`

## Fetch account running the command

`gh api user --jq .login`

## Fetch review threads (id + isResolved + comment ids)

`gh api graphql -f
query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id
isResolved comments(first:100){nodes{databaseId}}}}}}}' -f o="$OWNER" -f r="$REPO" -F
n="$PULL_NUMBER"`
