# Bitbucket Data Center — fetch

No CLI exists for this product either, so `core/raw-http-vendor.md` rules every group here — `curl`
flags, credentials, payloads, diff pipelines. The rest of this file is Data Center's own.

"PR" means a **Pull Request**; `<owner>` = the PROJECT KEY (`~<username>` for a personal repo), `<repo>` =
the repository slug, `<pull_number>` = the PR id, each exactly as the PR URL spells it, and `<host>` = the
scheme+host of that same URL since every instance is self-hosted. Substitute the caller's own
`<comment_id>`/`<commit_id>`/`<fields>`/`<max_patch_bytes>` the same way. 4 shorthands, valid in EVERY
group of this vendor:

| shorthand | expands to |
|---|---|
| `<api>` | `<host>/rest/api/latest/projects/<owner>/repos/<repo>` |
| `<curl>` | `curl -sS --fail-with-body -H "Authorization: Bearer $BITBUCKET_SERVER_TOKEN"` |
| `<activities>` | `<api>/pull-requests/<pull_number>/activities?limit=100` — this vendor's only list of every comment on a PR, read by 3 entries |
| `<diff_cmd>` | `<curl> "<api>/pull-requests/<pull_number>.diff?contextLines=3"` — the `.diff` suffix is what returns `text/plain`; the sibling `/diff` path returns hunks as JSON, far larger for the same content. `contextLines=3` MUST stay: the default is 10, and 7 extra unchanged lines per hunk is pure context cost |

Reactions and build status live under sibling REST namespaces of the same `<host>`, spelled out where they
are used.

`BITBUCKET_SERVER_TOKEN` = an HTTP access token, created under the instance's Profile → Manage account →
HTTP access tokens, with Read permission on the repository and Write to post. Unset ⇒ the STOP of
`core/raw-http-vendor.md`, naming that variable.

**Pagination.** A list endpoint answers `{"values": […], "isLastPage": bool, "nextPageStart": N}`. Every
entry below that reads `.values[]` MUST re-request with `?start=<nextPageStart>` until `isLastPage` is
true; a full page is not evidence of a last page.

**Confidence.** These commands are verified against the official Bitbucket Data Center OpenAPI
specification, NOT against a live instance. If the server rejects something, the 2 places to check first
are the `anchor` object that anchors a LINE comment (`post.md`) and the `version` that every comment
update must carry (`thread.md`) — the rest is plain REST with no payload of its own.

## Fetch PR basic info

`<curl> "<api>/pull-requests/<pull_number>" | jq '{number: .id, title, body: .description, author:
.author.user.name, baseRefName: .toRef.displayId, headRefName: .fromRef.displayId}'` — add or drop keys
to match `<fields>`; the mapping from this vendor's own names is in that expression.

The projection MUST stay in the call: unprojected, this endpoint also returns the description rendered
to HTML, every reviewer with their own approval state, and both refs' full repository objects.

## Fetch PR head commit SHA

`<curl> "<api>/pull-requests/<pull_number>" | jq -r '.fromRef.latestCommit'` → `<commit_id>`.

## Fetch PR diff — file list

`<curl> "<api>/pull-requests/<pull_number>/changes?limit=1000" | jq -r '.values[] | (.path.toString //
empty), (.srcPath.toString // empty)'` — `srcPath` is set only for a rename or copy, and is that file's
old path.

## Fetch PR diff — patch, omitting oversized files

`<diff_cmd>` piped into the patch pipeline of `core/raw-http-vendor.md`, with the caller's
`<max_patch_bytes>`.

## Fetch PR commits headlines

`<curl> "<api>/pull-requests/<pull_number>/commits?limit=100" | jq -r '.values[].message | split("\n")[0]'`
— the whole message comes back, so the subject is its first line.

## Fetch PR review comments (LINE-level findings)

`<curl> "<activities>" | jq '[.values[] | select(.action == "COMMENTED" and .commentAnchor != null) |
{id: .comment.id, text: .comment.text, author: .comment.author.name, anchor: .commentAnchor, parent:
.comment.parent.id}]'`

Comments arrive as activity entries, not from a list of their own: `/comments` on this vendor requires a
`path` query and so cannot answer "every comment on this PR". `commentAnchor` present ⇒ the comment is
anchored, and `commentAnchor.line` with `fileType` names the line and the side; absent ⇒ overview-level.

## Fetch PR diff size per file

`<diff_cmd>` piped into the bytes-per-file pipeline of `core/raw-http-vendor.md`, whose `UNKNOWN` rule
covers the files this vendor returns no chunk for — a `/changes` path missing from this output is
`UNKNOWN`, never 0.

## Fetch CI checks

`<curl> "<host>/rest/build-status/latest/commits/<commit_id>?limit=100" | jq -r '.values[] | "\(.state)
\(.name // .key) — \(.url)"'` — keyed by COMMIT, not by PR, so it takes `<commit_id>`; answers `values:
[]` when nothing ever reported a build, so it never needs `|| true`. `state` maps to the caller's bucket:
`SUCCESSFUL` ⇒ pass, `FAILED` ⇒ fail, `INPROGRESS` ⇒ pending.

## Fetch PR reviews (FILE-level findings + review_id)

**No equivalent.** Completing a review leaves nothing addressable behind: its threads turn into ordinary
comments and its verdict into a participant status, and no id ties those two together. So this vendor
answers nothing for FILE-level detection and the caller drops that category; LINE level is unaffected.

## Fetch account running the command

`<curl> -D - -o /dev/null "<api>/pull-requests/<pull_number>" | awk 'tolower($1) ==
"x-ausername:"{gsub(/\r/,"",$2); print $2}'` — this vendor has no "current user" endpoint; it returns the
authenticated username in that response header instead. `-D -` dumps RESPONSE headers only, which is why
it is allowed where `-i` is not.

Header absent ⇒ a repository-scoped token — the no-person case of `core/raw-http-vendor.md`, so `UNKNOWN`
is the result.

## Fetch review threads (id + isResolved + comment ids)

`<curl> "<activities>" | jq '[.values[] | select(.action == "COMMENTED") | {id: .comment.id, parent:
.comment.parent.id, resolved: .comment.threadResolved}]'` — the same endpoint, deliberately WITHOUT the
anchor filter the LINE-findings entry applies: an overview comment can be resolved too, so restricting
this to anchored ones would hide half the threads.

`threadResolved` is this vendor's name for `isResolved` and is true on every comment of a resolved
thread. A thread has no object of its own: its id is the id of the comment with no `parent`, and every
comment whose `parent.id` chains back to that one belongs to it.
