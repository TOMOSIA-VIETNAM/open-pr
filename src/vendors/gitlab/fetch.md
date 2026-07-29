# GitLab — fetch

Substitute the caller's own `<owner>`/`<repo>`/`<pull_number>`/`<comment_id>`… values.

"PR" here always means a **Merge Request**: `<pull_number>` = the MR's `iid` (project-scoped, NOT the
global id), `<owner>/<repo>` = the project's namespace/path, passed to `glab api` as
`<owner>%2F<repo>` (a numeric project id also works, the encoded path avoids a lookup). Credentials
come from whatever `glab auth login` configured.

`glab api` has NO `--jq` flag (that one is `gh`'s) — pipe its JSON to `jq` instead, as below.
`glab mr view` does accept it, but ONLY together with `--output json`.


## Fetch PR basic info

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>"` (JSON, preferred when fields must
be parsed) or `glab mr view <pull_number> -R "<owner>/<repo>"` (human-readable). Field mapping: `iid` →
`pull_number`, `title` → `title`, `description` → `body`, `author.username` → `author`,
`target_branch` → `baseRefName`, `source_branch` → `headRefName`.

## Fetch PR head commit SHA

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>" | jq -r '.diff_refs.head_sha'` →
`<commit_id>`.

## Fetch PR diff — file list

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/changes" | jq -r
'.changes[] | .old_path, .new_path'`

## Fetch PR diff — full patch

`glab mr diff <pull_number> -R "<owner>/<repo>"`

## Fetch PR commits headlines

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/commits" | jq -r '.[].title'`

## Fetch PR review comments (LINE-level findings)

`glab api --paginate "projects/<owner>%2F<repo>/merge_requests/<pull_number>/discussions"`, then keep
only notes carrying a `position` object (a DiffNote). A `notes[]` entry WITHOUT `position` is
overview-level, not a LINE finding.

## Fetch PR diff size per file

**No equivalent** — no byte-size field exists, so compute from the patch: take "Fetch PR diff — full patch" (reuse it if
already fetched this run), split by file, use each hunk's text length as the proxy.

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
