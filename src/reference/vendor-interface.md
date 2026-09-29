# Vendor contract — what `bin/open-pr.sh` guarantees per vendor

Reference for contributors; FORBIDDEN to `Read` at run time — `core/cli.md` is the runtime contract.
The script is the single place vendor differences live. Adding a vendor = a branch in each subcommand
of `src/bin/open-pr.sh` + its URL shape in `target` + fixtures in `tests/test_cli.py` + atoms/scenarios
in `scripts/token_report.py`. Whatever the vendor's API lacks is handled INSIDE the script (printed as
`NO-EQUIVALENT` or `UNKNOWN`), never worked around in a prompt.

| capability | github | gitlab | bitbucket |
|---|---|---|---|
| context sections | gh CLI | glab api (MR object + /changes cached per run) | curl+jq, paged, whole-diff cut at `diff --git` |
| head SHA | `headRefOid` (40 chars) | `diff_refs.head_sha` | `source.commit.hash` (12 chars — prefix-matched, never equality) |
| PR checkout | `refs/pull/<n>/head` | `refs/merge-requests/<n>/head` | fetch source branch, detach at the PR's commit hash; unreachable hash = force-push, exit 3 |
| unpublished stage | PENDING review object | draft notes | none — the payload file is the stage; publish POSTs one comment per part, overview first |
| publish | review event COMMENT | `bulk_publish` | per-part POST |
| post-verify | review state by id | draft_notes emptied ⇔ published | marker-filtered comment scan (`--marker`) |
| FILE-level reviews | review objects | NO-EQUIVALENT | NO-EQUIVALENT |
| account | login | username | nickname, or UNKNOWN under a workspace token (401 on /user is BY DESIGN) |
| threads | GraphQL reviewThreads | discussions (`resolved` flag) | root comment + `parent` chains, `resolution` on the ROOT only |
| react (`--kind line\|top`) | reactions on the review comment (`line`) or the issue comment (`top`) — separate id spaces | award_emoji on the MR note | NO-EQUIVALENT |
| claim: list | `issues/:n/comments` + `pulls/:n/comments`, paginated | `merge_requests/:iid/discussions`, every non-system note | `pullrequests/:id/comments`, deleted skipped |
| claim: post | `line`: `pulls/:n/comments/:c/replies`; `top`: `issues/:n/comments`, opening with the request quoted (`> ` per line, 20 lines at most, then its plain URL — no thread there) | `--thread-id T`: `discussions/T/notes`; else `merge_requests/:iid/notes` | `pullrequests/:id/comments` with `parent.id` = C |
| claim: delete (lost race) | `line`: DELETE `pulls/comments/:id`; `top`: DELETE `issues/comments/:id` | DELETE `merge_requests/:iid/notes/:id` | DELETE `pullrequests/:id/comments/:id` |
| repo-target | vendor from the remote host: `github.com` | any other host (self-hosted included); `owner/repo` only, a nested group exits 5 | `bitbucket.org` |
| triggers: sources | open PRs; repo-wide issue comments (`top`) + review comments (`line`); `--since` narrows by update time | opened MRs (`updated_after`), then each MR's discussions, one row per note; system notes skipped; DiffNote/position = `line` | open PRs (`q=updated_on > <since>`), then each PR's comments; deleted skipped; `inline` = `line` |
| triggers: rate limit ⇒ exit 9 | HTTP 403/429 naming a rate limit (primary or secondary), or `X-RateLimit-Remaining: 0` | HTTP 429, the membership lookup included | HTTP 429 |
| triggers: `thread_id` | null | the note's discussion id — what `reply`/`claim --thread-id` take | null |
| triggers: `authorized` | `author_association` ∈ OWNER/MEMBER/COLLABORATOR, no extra call | `members/all/:user_id` access level ≥ 30, one call per author; 404 = `no`; any other failure = exit 1 | UNKNOWN — the permission API needs admin |
| open-prs (rate limit ⇒ exit 9, as triggers) | `pulls?state=open`, paginated | `merge_requests?state=opened`, paginated | `pullrequests?state=OPEN`, every `next` |
| markers | HTML comments | HTML comments | link reference definitions (raw HTML is escaped there) |

`triggers` prints 1 JSON per line, identical on every vendor:
`{"pr","url","comment_id","kind","thread_id","user","created_at","body","authorized"}` — `kind` =
`line|top`, what `react`/`claim --kind` takes; `authorized` = `yes|no|UNKNOWN` (write access); `--since`
is strict; `--mark-file` gets the newest `created_at` among every comment fetched, trigger or not. A
trigger is a body whose first word is the `--token` (default `/open-pr`): `/open-pr:review` and
`/open-prx` are not `/open-pr`; an `@login` token ignores case. It drops, on every vendor, any comment
carrying a finding or reply marker, or a claim marker in either form — the plugin's own posts. The
logged-in account's plain comments count: one person may be both developer and reviewer. `checkout` holds a `mkdir` lock
in the repo's git common dir around every fetch and `worktree add`, since all worktrees share that
`.git`; a lock whose pid is gone is reclaimed.

`claim` is a reply lock, the same on every vendor: a comment carrying `bot-claim:<C>` (either marker
form) means trigger C is taken. It lists first and posts nothing when one exists; else it posts, lists
again, and the earliest claim by `created_at` (compared as instants), then id, holds the lock — its own
reply counts even before the listing shows it. A loser deletes its reply; a failed delete is reported
on stderr and still prints `taken`.

Credentials: gh/glab bring their own login. Bitbucket needs `BITBUCKET_EMAIL`+`BITBUCKET_API_TOKEN`
(user identity) or `BITBUCKET_TOKEN` (workspace token, no identity); missing ⇒ exit 6 with setup
instructions. Tokens never enter argv, URLs, or output.
