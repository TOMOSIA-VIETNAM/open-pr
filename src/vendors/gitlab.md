# GitLab vendor operations — `glab`/`git` command reference

Not a slash command, no frontmatter — plain reference data. Placeholders (`<owner>`, `<repo>`,
`<pull_number>`, `<comment_id>`...) MUST be substituted with the caller's OWN values, never
hardcoded in this file.

**Terminology note:** every entry NAME below keeps the word "PR" for interface consistency with
`src/vendors/github.md` (same 19 headings, copied verbatim). Internally, "PR" here always means a
GitLab **Merge Request (MR)**: `<pull_number>` = the MR's `merge_request_iid` (project-scoped, NOT
the global MR id), `<owner>/<repo>` = the project's namespace/path. `glab api` paths below use
`<owner>%2F<repo>` (URL-encoded `owner/repo`) as the project identifier, matching GitLab's own REST
API convention (a numeric project id also works, but the encoded path avoids a separate lookup).

Auth: `glab auth status`/`glab api` read credentials from whatever `glab auth login` already
configured on this machine.

## Fetch PR basic info

`glab mr view <pull_number> -R "<owner>/<repo>"` (human-readable) or
`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>"` (JSON, preferred when a caller
needs to parse specific fields). Field mapping to this plugin's common names: `iid` → `pull_number`
(already known), `title` → `title`, `description` → `body`, `author.username` → `author`,
`target_branch` → `baseRefName`, `source_branch` → `headRefName`.

## Fetch PR head commit SHA

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>" --jq '.diff_refs.head_sha'` (or
`glab mr view <pull_number> -R "<owner>/<repo>" --output json`, same field) — call the result
`<commit_id>`.

## Fetch PR diff — file list

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/changes" --jq
'.changes[] | .old_path, .new_path'`

## Fetch PR diff — full patch

`glab mr diff <pull_number> -R "<owner>/<repo>"`

## Fetch PR commits headlines

`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/commits" --jq '.[].title'`

## Fetch PR review comments (LINE-level findings)

`glab api --paginate "projects/<owner>%2F<repo>/merge_requests/<pull_number>/discussions"`, then
filter for notes carrying a `position` object (a DiffNote — GitLab's line-level note) — a
discussion's `notes[]` entries WITHOUT `position` are overview-level, not LINE findings. `--paginate`
always safe to include.

## Fetch PR diff size per file

NO byte-size field exists (same limitation as GitHub) — compute from patch text per file: fetch
"Fetch PR diff — full patch" once (do not refetch if already fetched earlier in the same run),
split by file, take each hunk's text length as the proxy size.

## Fetch CI checks

`glab ci status --merge-request <pull_number> -R "<owner>/<repo>"` (pipeline-level) or
`glab api "projects/<owner>%2F<repo>/pipelines/<pipeline_id>/jobs"` (job-level, `<pipeline_id>` =
the MR's latest pipeline id) `|| true` — harmless when the project has no CI configured, prevents
exit-on-error WHEN a job is failing/pending.

## Fetch PR reviews (FILE-level findings + review_id)

**NO direct equivalent** — GitLab has no single "review object" grouping several FILE-level
bullets under one id the way GitHub's review body does. This is the single largest structural
difference from GitHub (see "Post a review" below): every note GitLab posts (LINE or overview) is
its own individually-addressable object, never bundled under a parent id a caller could later
re-fetch as "the review". A caller relying on this entry for FILE-level finding detection has
NOTHING to parse here for this vendor — treat that whole finding category as not applicable,
LINE-level detection is unaffected.

## Fetch account running the command

`glab auth status` (shows the logged-in username) or `glab api user --jq .username`.

## Fetch review threads (id + isResolved + comment ids) via GraphQL

Heading name kept identical to `vendors/github.md` for interface consistency — GitLab does NOT
need GraphQL for this, plain REST already returns everything required:
`glab api --paginate "projects/<owner>%2F<repo>/merge_requests/<pull_number>/discussions"` — each
discussion object already has `id`, `resolved` (boolean, GitLab's own name for GitHub's
`isResolved`), and a `notes[]` array (each note's `id` = the comment id to cross-check against a
finding's `comment_id`). No separate narrower/wider variant needed like GitHub's 2 GraphQL queries
— this ONE call already carries everything needed, including backing "Resolve a review thread"
below (same discussions payload, no second call).

## Checkout a PR into a fresh worktree

`glab mr checkout` has no native worktree support (tracked upstream, glab issue #8217, still open
as of this writing) — build it manually:

1. `git worktree add "notebooks/review/<repo>/worktrees/review-pr<pull_number>-$RANDOM" --detach`
   — random name, never reused.
2. `(cd "notebooks/review/<repo>/worktrees/<name>" && git fetch origin
   "refs/merge-requests/<pull_number>/head:refs/remotes/origin/merge-requests/<pull_number>" &&
   git checkout --detach "refs/remotes/origin/merge-requests/<pull_number>")` — GitLab always
   exposes this ref for every MR (same idea as GitHub's `refs/pull/<n>/head`, just a different ref
   namespace) — already detached by construction, no extra `git checkout --detach` needed
   afterward (unlike GitHub's `gh pr checkout`, which leaves a tracking branch checked out first).

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && git fetch origin
"refs/merge-requests/<n-submodule>/head:refs/remotes/origin/merge-requests/<n-submodule>" && git
checkout --detach "refs/remotes/origin/merge-requests/<n-submodule>")` — REUSES a directory `git
submodule update --init --recursive` already put on disk; does NOT create a new worktree. Avoid
`glab mr checkout --repo` for this cross-repo case — a known bug cross-checks out the WRONG repo's
MR (glab issue #7972, still open as of this writing); the manual fetch+checkout above sidesteps it
entirely.

## Post a review (1 POST — findings + overview together)

Heading name kept identical to `vendors/github.md` for interface consistency — the mechanism
itself is COMPLETELY DIFFERENT, read carefully. GitLab has NO single "review object" (see "Fetch PR
reviews" above) — it uses **Draft Notes**
instead: each finding (LINE or overview) is POSTed as its OWN individual draft note, then ALL of
them are published together in exactly 1 separate bulk-publish call. No `review_id`/`state` field
exists anywhere in this flow (unlike GitHub's PENDING/SUBMITTED review object).

1. For EACH finding (LINE and FILE/overview alike), 1 POST each:
   `glab api -X POST "projects/<owner>%2F<repo>/merge_requests/<pull_number>/draft_notes" -f
   note="<finding body>"` — LINE findings ALSO carry a `position` object (`base_sha`, `start_sha`,
   `head_sha` from `<commit_id>`'s `diff_refs`, `old_path`/`new_path`, `position_type: "text"`,
   `new_line`/`old_line` per the LINE's side) so it anchors to the correct diff line; a FILE/
   overview finding omits `position` entirely (posts as a plain top-level draft note). MUST use the
   SAME heredoc-quoting discipline as GitHub's "Post a review" entry (finding text is
   ATTACKER-CONTROLLED, originates from the PR diff) — quote every value, never let the running
   shell expand it.
2. This step alone leaves every draft note in the PENDING equivalent — nothing is visible on the MR
   yet. Publishing them is the separate "Submit a PENDING review" entry below.

## Verify a posted review's state

No `state` field exists (unlike GitHub) — GET the draft notes list instead:
`glab api "projects/<owner>%2F<repo>/merge_requests/<pull_number>/draft_notes"`. Still contains the
notes just posted → pending (not yet visible to the MR's other viewers). Empty / notes gone →
already published (they became real discussion notes) — GitLab removes a draft note from this list
the moment `bulk_publish` runs, there's no separate "submitted" flag to read.

## Submit a PENDING review

`glab api -X POST
"projects/<owner>%2F<repo>/merge_requests/<pull_number>/draft_notes/bulk_publish"` — publishes
EVERY draft note left on this MR at once (no way to publish a subset).

## Reply on a PR

`glab mr note create <pull_number> -R "<owner>/<repo>" --reply <comment_id> -m "<content>"` for
BOTH kinds below — GitLab doesn't distinguish LINE vs FILE/overview for replying, `--reply <id>`
alone anchors the reply into the right existing discussion regardless of whether that discussion
originally carried a `position` or not:

- **LINE-level** (original finding has `path`+`line`, i.e. a DiffNote) — `comment_id` = the
  original finding note's id.
- **FILE-level / OVERVIEW-level** (a plain top-level note, no position) — GitLab HAS a real
  reply-to-discussion endpoint here (unlike GitHub, which has no reply-to-review-body concept).

**Confidence note:** the flag combination above is this file's best reconstruction from research —
`glab mr note create` also accepts `--file`/`--line` when CREATING a brand-new positioned note
(relevant to "Post a review" above, not to a reply); once `--reply <id>` targets an existing
thread, re-stating `--file`/`--line` should not be necessary, but this has not been confirmed
against a real `glab` invocation. Verify against `glab mr note --help` (or the installed `glab`
version's own docs) before depending on the exact flag names in production.

## Resolve a review thread (GraphQL)

Heading name kept identical to `vendors/github.md` for interface consistency — GitLab resolves via
plain REST, no GraphQL mutation needed:
`glab api -X PUT
"projects/<owner>%2F<repo>/merge_requests/<pull_number>/discussions/<discussion_id>?resolved=true"`
(`<discussion_id>` = the `id` from "Fetch review threads" above, matched against the finding's
`comment_id` via that discussion's `notes[].id`) — or the CLI wrapper `glab mr note resolve
<pull_number> <comment_id> -R "<owner>/<repo>"` if preferred.

## React to a PR comment

`glab api -X POST "projects/<owner>%2F<repo>/notes/<comment_id>/award_emoji" -f
name=<+1|heart|hooray|rocket|confused|eyes>` — `glab` has no dedicated wrapper for GitLab's Emoji
Reactions API, use `glab api` directly. GitLab's own param name is `name` (not `content` like
GitHub's reaction API) — same allowed emoji vocabulary otherwise.
