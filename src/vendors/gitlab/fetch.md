# GitLab — fetch

Substitute the caller's own `<owner>`/`<repo>`/`<pull_number>`/`<comment_id>`… values.

"PR" here always means a **Merge Request**: `<pull_number>` = the MR's `iid` (project-scoped, NOT the
global id), `<owner>/<repo>` = the project's namespace/path, passed to `glab api` as
`<owner>%2F<repo>` (a numeric project id also works, the encoded path avoids a lookup). Credentials
come from whatever `glab auth login` configured.

`glab api` has NO `--jq` flag (that one is `gh`'s) — pipe its JSON to `jq` instead, as below.
`glab mr view` does accept it, but ONLY together with `--output json`.


## Fetch PR basic info

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>" | jq '{number: .iid, title,
body: .description, author: .author.username, baseRefName: .target_branch, headRefName:
.source_branch}'` — add or drop keys to match `<fields>`; the mapping from GitLab's own names is in
that expression.

The projection MUST stay in the call. This endpoint returns ~60 keys — assignees, labels, milestone,
pipeline, merge status, every timestamp — and all of it lands in context otherwise, for 6 fields' worth
of use.

## Fetch PR head commit SHA

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>" | jq -r '.diff_refs.head_sha'` →
`<commit_id>`.

## Fetch PR diff — file list

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/changes" | jq -r
'.changes[] | .old_path, .new_path'`

## Fetch PR diff — patch, omitting oversized files

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/changes" | jq -r --argjson m
<max_patch_bytes> '.changes[] | select(((.diff // "") | length) < $m and (.diff // "") != "") |
"diff --git a/\(.new_path) b/\(.new_path)\n\(.diff)"'` — `<max_patch_bytes>` = the caller's own
threshold in bytes. Emits a `diff --git` header per file, which plain `glab mr diff` output lacks.

Same endpoint as "Fetch PR diff size per file", one round trip for both. GitLab collapses a large diff
by itself, returning `diff: ""`; such a file is omitted here too and the size entry is what reports it.

## Fetch PR commits headlines

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/commits" | jq -r '.[].title'`

## Fetch PR review comments (LINE-level findings)

`glab api --paginate "projects/<owner>%2F<repo>/merge_requests/<pull_number>/discussions"`, then keep
only notes carrying a `position` object (a DiffNote). A `notes[]` entry WITHOUT `position` is
overview-level, not a LINE finding.

## Fetch PR diff size per file

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/changes" | jq -r '.changes[] |
if (.collapsed // false) or (.too_large // false) then "UNKNOWN(collapsed or too large — no patch
returned) \(.new_path)" else "\((.diff // "") | length) \(.new_path)" end'`

No byte-size field exists, so the patch text is the proxy — but a collapsed or too-large file comes back
with `diff: ""`, which as a length reads 0 and would put the biggest file in the PR under every
threshold. The flags MUST be checked first and reported as `UNKNOWN`, matching what GitHub returns when
it withholds a patch.

## Fetch CI checks

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/pipelines"` — returns `[]` when the
project has no CI, so it never needs `|| true`. Each entry gives `id`, `status`, `web_url`; map `status`
to the caller's bucket (`failed`/`canceled` ⇒ fail). A finding that must name the failing job takes a
second call for the latest pipeline: `glab api
"projects/<owner>%2F<repo>/pipelines/<pipeline_id>/jobs"` → `name`, `status`, `web_url`.

FORBIDDEN: `glab ci status` — it has no merge-request flag, and its `--live`/`--wait` modes block until
the pipeline finishes, which would hang the run.

## Fetch PR reviews (FILE-level findings + review_id)

**No equivalent.** GitLab has no review object grouping FILE-level bullets under one id — every note
(LINE or overview) is its own addressable object with no parent to re-fetch. A caller relying on this
entry for FILE-level detection has nothing to parse for this vendor and treats that whole category as
not applicable; LINE-level detection is unaffected.

## Fetch account running the command

`glab api user | jq -r .username` (or `glab auth status`).

## Fetch review threads (id + isResolved + comment ids)

REUSE the response of "Fetch PR review comments" above — the same one call serves this entry and
"Resolve a review thread"; FORBIDDEN: fetching it again. Each discussion carries `id`, `resolved`
(GitLab's name for `isResolved`), and `notes[]` whose `id` is the comment id to match a finding's
`comment_id` against.
