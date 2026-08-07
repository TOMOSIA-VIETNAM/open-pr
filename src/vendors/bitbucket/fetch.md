# Bitbucket Cloud — fetch

Atlassian ships no CLI, so `core/raw-http-vendor.md` rules every group here — `curl` flags, credentials,
payloads, diff pipelines. The rest of this file is Cloud's own.

"PR" means a **Pull Request**; `<owner>` = the workspace slug, `<repo>` = the repository slug,
`<pull_number>` = the PR id, each exactly as the PR URL spells it. Substitute the caller's own
`<comment_id>`/`<commit_id>`/`<fields>`/`<max_patch_bytes>` the same way. 4 shorthands, valid in EVERY
group of this vendor:

| shorthand | expands to |
|---|---|
| `<api>` | `https://api.bitbucket.org/2.0/repositories/<owner>/<repo>` |
| `<curl>` | `curl -sS --fail-with-body <auth>` |
| `<comments>` | `<api>/pullrequests/<pull_number>/comments?pagelen=100` — 3 entries read it, each with its own `&fields=` |
| `<diff_cmd>` | `<curl> -L "<api>/pullrequests/<pull_number>/diff"` — `-L` MANDATORY, that path redirects to the repository diff and without it the body is empty |

`<auth>` — resolve ONCE, before the first fetch of a run:

| env set | `<auth>` | what it is |
|---|---|---|
| `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` | `-u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN"` | an Atlassian API token, belonging to a user |
| `BITBUCKET_TOKEN` | `-H "Authorization: Bearer $BITBUCKET_TOKEN"` | a repository/workspace access token, scoped to one repo/workspace, NO user identity behind it |

Neither set ⇒ the STOP of `core/raw-http-vendor.md`, naming the first pair, an API token created under
Atlassian account settings → Security → API tokens (app: Bitbucket), and the scopes
`read:pullrequest:bitbucket` + `write:pullrequest:bitbucket` + `read:account`.

**Pagination.** A list endpoint answers `{"values": […], "next": "<url>"}`. Every entry below that ends
in `.values[]` MUST follow `next` until it is absent — a full first page is not evidence of a last page.

## Fetch PR basic info

`<curl>
"<api>/pullrequests/<pull_number>?fields=id,title,description,author.nickname,source.branch.name,destination.branch.name"
| jq '{number: .id, title, body: .description, author: .author.nickname, baseRefName:
.destination.branch.name, headRefName: .source.branch.name}'` — add or drop keys to match `<fields>`,
narrowing `?fields=` by the same keys; the mapping from Bitbucket's own names is in that expression.

Both projections MUST stay. Unnarrowed, this endpoint returns the description rendered to HTML a second
time plus ~20 link objects, and all of it lands in context for 6 fields' worth of use.

## Fetch PR head commit SHA

`<curl> "<api>/pullrequests/<pull_number>?fields=source.commit.hash" | jq -r '.source.commit.hash'` →
`<commit_id>`.

## Fetch PR diff — file list

`<curl> "<api>/pullrequests/<pull_number>/diffstat?pagelen=100&fields=next,values.old.path,values.new.path"
| jq -r '.values[] | (.old.path // empty), (.new.path // empty)'`

## Fetch PR diff — patch, omitting oversized files

`<diff_cmd>` piped into the patch pipeline of `core/raw-http-vendor.md`, with the caller's
`<max_patch_bytes>`.

## Fetch PR commits headlines

`<curl> "<api>/pullrequests/<pull_number>/commits?pagelen=100&fields=next,values.message" | jq -r
'.values[].message | split("\n")[0]'` — Bitbucket returns the whole message, so the subject is its
first line.

## Fetch PR review comments (LINE-level findings)

`<curl>
"<comments>&fields=next,values.id,values.content.raw,values.user.nickname,values.inline,values.parent.id,values.deleted"
| jq '[.values[] | select(.deleted != true and .inline != null)]'` — a comment carrying an `inline`
object IS a LINE finding; one without it is overview-level and belongs to no line. `parent.id` present
⇒ the comment is a reply, which is the linkage a caller matches threads on. A deleted comment stays in
the list as a tombstone with its content gone, hence the `deleted` filter.

`inline.to` = the line in the NEW file, `inline.from` = the line in the OLD file; exactly one of them
is set per comment and that is what names the side.

## Fetch PR diff size per file

`<diff_cmd>` piped into the bytes-per-file pipeline of `core/raw-http-vendor.md`, whose `UNKNOWN` rule
covers the files Cloud returns no chunk for — a diffstat path missing from this output is `UNKNOWN`,
never 0.

## Fetch CI checks

`<curl> "<api>/pullrequests/<pull_number>/statuses?pagelen=100&fields=next,values.state,values.name,values.url"
| jq -r '.values[] | "\(.state) \(.name) — \(.url)"'` — answers `values: []` when the repo has no CI,
so it never needs `|| true`. `state` maps to the caller's bucket: `SUCCESSFUL` ⇒ pass, `FAILED` and
`STOPPED` ⇒ fail, `INPROGRESS` ⇒ pending. Covers Bitbucket Pipelines and any external CI alike, since
both report through this one endpoint.

## Fetch PR reviews (FILE-level findings + review_id)

**No equivalent.** A comment here is anchored to a line or it is top-level, and either way its own id is
the only handle on it — no object groups several under one `review_id`. So this vendor answers nothing for
FILE-level detection and the caller drops that category, while LINE-level detection carries on unchanged.

## Fetch account running the command

`<curl> "https://api.bitbucket.org/2.0/user?fields=nickname" | jq -r .nickname`

Under `BITBUCKET_TOKEN` it answers 401 by design — the no-person case of `core/raw-http-vendor.md`, so
`UNKNOWN` is the result. FORBIDDEN: re-running it under the other `<auth>` form.

## Fetch review threads (id + isResolved + comment ids)

`<curl> "<comments>&fields=next,values.id,values.parent.id,values.resolution,values.deleted" | jq
'[.values[] | select(.deleted != true) | {id, parent: .parent.id, resolved: (.resolution != null)}]'` —
the LINE-findings endpoint again under a narrower projection, so a second round trip buys 1 small object
per comment instead of re-reading the finding bodies.

Cloud has no thread object: a thread IS a comment with `parent` absent, plus every comment whose
`parent.id` chains back to it. That root's `id` is the thread id "Resolve a review thread" takes, and
`resolution` (an object once resolved, `null` before) is Cloud's name for `isResolved`.
