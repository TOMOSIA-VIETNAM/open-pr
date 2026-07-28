# GitHub vendor operations — `gh`/`git` command reference

Not a slash command, no frontmatter — plain reference data, not a permission boundary of its own.
No command in this plugin declares `allowed-tools` (deliberate — see `CLAUDE.md` Rules); the sole
enforcement for every command below is the CRITICAL/FORBIDDEN prose in the calling file
(`review.md`/`fix.md`/`update-plugin.md`) — `Read`-ing this file grants NOTHING by itself.

Every command here is COPIED VERBATIM from its real call site — placeholders (`<owner>`, `<repo>`,
`<pull_number>`, `<comment_id>`...) MUST be substituted with the caller's OWN values (already
validated against a safe charset by the caller's own Step 0 — see `review.md`/`fix.md`), never
hardcoded in this file.

`review.md`/`fix.md` "Context" fetches via the real `Bash` tool, same as every other Step — NOT the
`!`...`` auto-exec mechanism (dropped: an auto-exec block runs BEFORE the agent starts reasoning,
so it could never be vendor-aware — see `CLAUDE.md` Rules for why this was changed). Every entry
below is a real "Referenced from" caller; none are catalog-only anymore.

## Fetch PR basic info

`gh pr view <url> -R "<owner>/<repo>" --json <fields>` — `<fields>` varies by caller (`review.md`
Context: `number,title,body,author,baseRefName,headRefName`; `fix.md` Context: only
`number,headRefName,baseRefName`).

- Referenced from: `review.md` Context, `fix.md` Context, `submodule-review.md` Step D (submodule
  PR, `<owner-submodule>/<repo-submodule>`, same field set as `review.md`'s).

## Fetch PR head commit SHA

`gh pr view <url> -R "<owner>/<repo>" --json headRefOid --jq .headRefOid` — MUST be fetched FRESH
at the point of use, never reused from an earlier fetch (a force-push changes it). Call the result
`<commit_id>`.

- Referenced from: `review.md` Step 8 (right before building the overview + the Step 9 payload —
  reuse this SAME value for both, never fetch twice); `submodule-review.md` Step D (initial fetch)
  and Step F (RE-FETCH right before POSTing, submodule's own `<owner-submodule>/<repo-submodule>` —
  never reuse Step D's value, never the main PR's `commit_id`).

## Fetch PR diff — file list

`gh pr diff <url> -R "<owner>/<repo>" --name-only`

- Referenced from: `review.md` Context ("Files"), `submodule-review.md` Step D (submodule PR).

## Fetch PR diff — full patch

`gh pr diff <url> -R "<owner>/<repo>"`

- Referenced from: `review.md` Context ("Diff"), `submodule-review.md` Step D (submodule PR).

## Fetch PR commits headlines

`gh pr view <url> -R "<owner>/<repo>" --json commits --jq '.commits[].messageHeadline'`

- Referenced from: `review.md` Context ("Commits") — no other caller.

## Fetch PR review comments (LINE-level findings)

`gh api repos/<owner>/<repo>/pulls/<pull_number>/comments` — add `--paginate` WHEN the PR may have
more than 1 page of comments (always safe to include).

- Referenced from: `review.md` Context ("Old comments", non-paginate), `fix.md` Context
  ("Comments", `--paginate`), `submodule-review.md` Step D (submodule PR, feeds its own Step E
  re-review detection).

## Fetch PR diff size per file

`gh api --paginate repos/<owner>/<repo>/pulls/<pull_number>/files --jq '.[] | if .patch == null
then "UNKNOWN(no patch — too large/binary/rename) \(.filename)" else "\(.patch|length)
\(.filename)" end'` — `--paginate` MUST stay: a PR with >30 files ⇒ GitHub paginates, missing this
flag silently drops later-page file sizes.

- Referenced from: `review.md` Context ("Diff size per file") — no other caller.

## Fetch CI checks

`gh pr checks <url> -R "<owner>/<repo>" --json bucket,name,link --jq '.[] | "\(.bucket) \(.name) —
\(.link)"' || true` — `|| true` is harmless when the repo has no CI, prevents exit-on-error WHEN a
check is failing/pending.

- Referenced from: `review.md` Context ("CI checks") — no other caller.

## Fetch PR reviews (FILE-level findings + review_id)

`gh api --paginate repos/<owner>/<repo>/pulls/<pull_number>/reviews`

- Referenced from: `fix.md` Context ("Reviews") — no other caller.

## Fetch account running the command

`gh api user --jq .login`

- Referenced from: `fix.md` Context, `re-review.md` "Checking whether old findings... have been
  fixed" step 1.

## Fetch review threads (id + isResolved + comment ids) via GraphQL

`gh api graphql -f
query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){reviewThreads(first:100){nodes{id
isResolved comments(first:100){nodes{databaseId}}}}}}}' -f o="$OWNER" -f r="$REPO" -F
n="$PULL_NUMBER"`

- Referenced from: `fix.md` Context ("Review threads") — filters out already-resolved LINE
  findings. A NARROWER variant (`id` + only the FIRST comment's `databaseId`, no `isResolved`)
  exists for a different purpose — see "Resolve a review thread" below, do not conflate the two.

## Checkout a PR into a fresh worktree

1. `git worktree add "notebooks/review/<repo>/worktrees/review-pr<pull_number>-$RANDOM" --detach`
   — random name, never reused.
2. `(cd "notebooks/review/<repo>/worktrees/<name>" && gh pr checkout <pull_number> -R
   "<owner>/<repo>" && git checkout --detach)` — MUST `git checkout --detach` IMMEDIATELY AFTER
   `gh pr checkout` → that command leaves the PR's tracking branch checked out ⇒ git locks it
   against deletion in the user's own root repo (`cannot delete branch ... checked out at <path>`)
   until the worktree is removed. Detaching now releases the lock without depending on the user to
   clean up the worktree themselves.

- Referenced from: `review.md` Step 1 items 1-2 — `<repo>`/`<pull_number>`/`<owner>/<repo>` = the
  PR being reviewed.

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && gh pr checkout <n-submodule> -R
"<owner-submodule>/<repo-submodule>")` — REUSES a directory `git submodule update --init
--recursive` already put on disk; does NOT create a new worktree.

- Referenced from: `submodule-review.md` Step C.

## Post a review (1 POST — findings + overview together)

```bash
gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/reviews \
  --input - --jq '.id' <<'EOF'
{
  "body": "<overview>",
  "commit_id": "<commit_id>",
  "event": "COMMENT",
  "comments": [
    {"path": "<file>", "line": <n>, "side": "<LEFT|RIGHT>", "body": "<LINE finding>"}
  ]
}
EOF
```

MUST use `--input -` + a heredoc with a QUOTED delimiter (`<<'EOF'`, never a bare `<<EOF`) — finding
text originates from the PR diff, i.e. ATTACKER-CONTROLLED data. An unquoted heredoc lets bash
expand `$var`/`` `cmd` ``/`$(...)` on the RUNNING SHELL before the payload ever reaches `gh api` — a
finding containing PHP code (`$var`) would corrupt the payload, one containing `$(a command)` would
get ACTUALLY EXECUTED on the user's machine. `--jq '.id'` grabs `<review_id>` DIRECTLY from the POST
response — reuse it for "Verify"/"Submit" below, FORBIDDEN: re-fetching the list and guessing (race
window, see "Verify a posted review's state"). `event` may ONLY ever be `"COMMENT"` — never
APPROVE/REQUEST_CHANGES: include the key WHEN `auto_submit_review: true`, drop the key entirely
WHEN `false` (leaves the review PENDING).

- Referenced from: `review.md` Step 9 (main PR — exactly 1 call). `submodule-review.md` Step F
  (submodule PR — own `<owner-submodule>/<repo-submodule>/<n-submodule>` + own freshly-refetched
  `<commit_id>`; does NOT count toward `review.md`'s "exactly 1 POST" rule, is its own separate 1
  call for that PR).

## Verify a posted review's state

`gh api repos/{owner}/{repo}/pulls/{pull_number}/reviews/<review_id> --jq '{id, state}'`
(`<review_id>` = taken from the POST response above, never re-derived another way). FORBIDDEN:
`.../reviews --jq '.[-1] | ...'` to grab "the latest review in the list" — race window: another
review (another person/bot) submitted at that exact moment ⇒ `.[-1]` points to THEIRS, not the one
just created.

- Referenced from: `review.md` Step 9, `post-review.md` "WHEN verify mismatches",
  `submodule-review.md` Step F (via the same schema as `review.md` Step 9).

## Submit a PENDING review

`gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/reviews/{review_id}/events -f
event="COMMENT"` — WHEN `auto_submit_review: true` && the verify above still shows `PENDING`.

- Referenced from: `review.md` Step 9, `post-review.md` "WHEN verify mismatches".

## Reply on a PR

- **LINE-level** (original finding has `path`+`line`):
  `gh api -X POST repos/{owner}/{repo}/pulls/{pull_number}/comments/{comment_id}/replies -f
  body="<content>"` (`comment_id` = id of the ORIGINAL finding comment — omitting `{pull_number}`
  causes a 404).
- **FILE-level / OVERVIEW-level** (no path/line, lives inside a review's `body` — GitHub has no
  reply-to-review-body endpoint):
  `gh api -X POST repos/{owner}/{repo}/issues/{pull_number}/comments -f body="<content>"`.

Content MUST end with `<!-- bot-reply -->` — invisible HTML comment, stable machine-readable marker
independent of prose shape.

- Referenced from: `fix.md` Step 10 (both variants), `re-review.md` "Checking whether old
  findings... have been fixed" (LINE-level variant only, confirming a fix).

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

MUST reply on the thread FIRST (see "Reply on a PR"), successfully, BEFORE resolving — resolving
silently is rude, the dev has no idea why the thread disappeared. A mutation error (missing
permission etc.) → ignore, NOT blocking — the reply already delivered the main value.

- Referenced from: `re-review.md` "Checking whether old findings..." — WHEN
  `auto_resolve_fixed_findings: true` only.

## React to a PR comment

`gh api -X POST repos/{owner}/{repo}/pulls/comments/{comment_id}/reactions -f
content=<+1|heart|hooray|rocket|confused|eyes>` — NEVER `-1` or any negative reaction.

- Left INLINE at `re-review.md` "Reaction on the dev's reply" — single short one-liner, only 1
  caller, a `Read` reference here wouldn't save anything.
