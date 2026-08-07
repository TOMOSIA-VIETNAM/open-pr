# Bitbucket — fetch

Substitute the caller's own `<owner>`/`<repo>`/`<pull_number>`/`<comment_id>`… values.

"PR" means a **Pull Request**; `<owner>` = the workspace slug, `<repo>` = the repository slug, each
exactly as the PR URL spells it. Atlassian ships NO CLI ⇒ every entry of every group is `curl` + `jq`,
built from these shorthands:

| shorthand | expands to |
|---|---|
| `<api>` | `https://api.bitbucket.org/2.0/repositories/<owner>/<repo>` |
| `<curl>` | `curl -sS --fail-with-body <auth>` |
| `<comments>` | `<api>/pullrequests/<pull_number>/comments?pagelen=100` — 3 entries read it, each with its own `&fields=` |
| `<diff_cmd>` | `<curl> -L "<api>/pullrequests/<pull_number>/diff"` — `-L` MANDATORY, that path redirects to the repository diff and without it the body is empty |
| `<patch_pipe>` | `awk -v m=<max_patch_bytes> '/^diff --git /{if(n&&s<m)printf "%s",b; b=""; s=0; n=1} n{b=b $0 "\n"; s+=length($0)+1} END{if(n&&s<m)printf "%s",b}'` |
| `<size_pipe>` | `awk '/^diff --git /{if(n)print s" "p; p=substr($0,index($0," b/")+3); s=0; n=1} n{s+=length($0)+1} END{if(n)print s" "p}'` |
| `<paged>` | `paged() { next="$1"; while [ -n "$next" ]; do page=$(<curl> "$next"); printf '%s' "$page" \| jq -r "$2"; next=$(printf '%s' "$page" \| jq -r '.next // empty'); done; }` |

No per-file patch endpoint exists, so the 2 diff entries cut ONE whole-diff response at `diff --git`
boundaries — hence the 2 pipelines. Both run under `LC_ALL=C`: `awk`'s `length` counts CHARACTERS, and a
UTF-8 locale would size a patch full of accented or CJK text well under its real byte count.

`--fail-with-body` = a non-zero exit on an HTTP error AND the response body, whose `error.message` is the
only place Atlassian states what it rejected. FORBIDDEN: `-f` alone (discards that body), `-v`/`-i` (dump
the `Authorization` header into context).

**Credential.** `<auth>`, resolved ONCE before the first fetch:

| env set | `<auth>` | what it is |
|---|---|---|
| `BITBUCKET_EMAIL` + `BITBUCKET_API_TOKEN` | `-u "$BITBUCKET_EMAIL:$BITBUCKET_API_TOKEN"` | an Atlassian API token, belonging to a user |
| `BITBUCKET_TOKEN` | `-H "Authorization: Bearer $BITBUCKET_TOKEN"` | a repository/workspace access token, scoped to one repo/workspace, NO user identity behind it |

Neither set ⇒ STOP before any call and print: the first pair, an API token created under Atlassian account
settings → Security → API tokens (app: Bitbucket) with scopes `read:pullrequest:bitbucket` +
`write:pullrequest:bitbucket` + `read:account`, and the `env` block of `~/.claude/settings.json` as the
place that sets them for every session. Only the NAME of a variable ever enters context. FORBIDDEN:
printing or echoing either variable, asking the user to paste a token into chat, reading one out of a file,
putting one in a URL (a URL reaches the access log, the shell history and every proxy between).

**Any JSON payload** (this group and every other): written to a file with a file-writing tool and sent with
`--data @<file>`, or piped straight out of `jq` with `--data @-`. FORBIDDEN: a heredoc, `echo`, `-d` with
interpolated text, or any other route through the running shell — finding and reply text quotes the PR's
own diff, i.e. attacker-controlled input, and shell expansion there corrupts the payload or executes it.

**Pagination.** A list endpoint answers `{"values": […], "next": "<url>"}` and caps a page at 100, so any
entry reading `.values[]` MUST walk every page: `<paged>` defines the walk, then `paged "<url>" '<jq>'`
runs it, printing `<jq>` raw per page. A `@json` at the end of `<jq>` emits an object as one line.

Every such entry below is written that way and MUST be run that way — a PR over 100 comments, files or
commits silently loses everything past page 1 otherwise, which reads as "no finding there". `"$next"` and
`"$page"` stay QUOTED: both come from Bitbucket, and an unquoted URL splits on its own `&`.

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

`<paged>; paged "<api>/pullrequests/<pull_number>/diffstat?pagelen=100&fields=next,values.old.path,values.new.path"
'.values[] | (.old.path // empty), (.new.path // empty)'`

## Fetch PR diff — patch, omitting oversized files

`LC_ALL=C <diff_cmd> | <patch_pipe>` — whole `diff --git` chunks, dropping any that reaches
`<max_patch_bytes>`, the caller's own threshold in bytes.

## Fetch PR commits headlines

`<paged>; paged "<api>/pullrequests/<pull_number>/commits?pagelen=100&fields=next,values.message"
'.values[].message | split("\n")[0]'` — Bitbucket returns the whole message, so the subject is its first
line.

## Fetch PR review comments (LINE-level findings)

`<paged>; paged
"<comments>&fields=next,values.id,values.content.raw,values.user.nickname,values.inline,values.parent.id,values.deleted"
'.values[] | select(.deleted != true and .inline != null) | @json'` — a comment carrying an `inline`
object IS a LINE finding; one without it is overview-level and belongs to no line. `parent.id` present
⇒ the comment is a reply, which is the linkage a caller matches threads on. A deleted comment stays in
the list as a tombstone with its content gone, hence the `deleted` filter.

`inline.to` = the line in the NEW file, `inline.from` = the line in the OLD file; exactly one of them
is set per comment and that is what names the side.

## Fetch PR diff size per file

`LC_ALL=C <diff_cmd> | <size_pipe>` — exact patch bytes per file.

A path that "Fetch PR diff — file list" returned but this never printed is `UNKNOWN`, NEVER 0: the chunk
is omitted entirely for a binary file and for a diff Bitbucket declines to generate, and reading that
absence as 0 bytes would slip the largest file in the PR under every threshold, so it would be neither
reviewed nor reported as skipped.

## Fetch CI checks

`<paged>; paged "<api>/pullrequests/<pull_number>/statuses?pagelen=100&fields=next,values.state,values.name,values.url"
'.values[] | "\(.state) \(.name) — \(.url)"'` — answers `values: []` when the repo has no CI,
so it never needs `|| true`. `state` maps to the caller's bucket: `SUCCESSFUL` ⇒ pass, `FAILED` and
`STOPPED` ⇒ fail, `INPROGRESS` ⇒ pending. Covers Bitbucket Pipelines and any external CI alike, since
both report through this one endpoint.

## Fetch PR reviews (FILE-level findings + review_id)

**No equivalent.** A comment here is anchored to a line or it is top-level, and either way its own id is
the only handle on it — no object groups several under one `review_id`. So this vendor answers nothing for
FILE-level detection and the caller drops that category, while LINE-level detection carries on unchanged.

## Fetch account running the command

`<curl> "https://api.bitbucket.org/2.0/user?fields=nickname" | jq -r .nickname`

Under `BITBUCKET_TOKEN` this answers 401 by design — such a token acts as the repository, not as a person,
so there is no account to name. That 401 is the ANSWER: print `UNKNOWN`, and `core/finding-markers.md`
falls back to the marker. FORBIDDEN: reporting it as an auth failure, or re-running it under the other
`<auth>` form.

## Fetch review threads (id + isResolved + comment ids)

`<paged>; paged "<comments>&fields=next,values.id,values.parent.id,values.resolution,values.deleted"
'.values[] | select(.deleted != true) | {id, parent: .parent.id, resolved: (.resolution != null)} |
@json'` — the LINE-findings endpoint again under a narrower projection, so a second pass buys 1 small
object per comment instead of re-reading the finding bodies.

Bitbucket has no thread object: a thread IS a comment with `parent` absent, plus every comment whose
`parent.id` chains back to it. That root's `id` is the thread id "Resolve a review thread" takes, and
`resolution` (an object once resolved, `null` before) is Bitbucket's name for `isResolved`.
