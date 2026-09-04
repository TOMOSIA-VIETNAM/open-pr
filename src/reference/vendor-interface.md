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
| react | reactions API | award_emoji | NO-EQUIVALENT |
| markers | HTML comments | HTML comments | link reference definitions (raw HTML is escaped there) |

Credentials: gh/glab bring their own login. Bitbucket needs `BITBUCKET_EMAIL`+`BITBUCKET_API_TOKEN`
(user identity) or `BITBUCKET_TOKEN` (workspace token, no identity); missing ⇒ exit 6 with setup
instructions. Tokens never enter argv, URLs, or output.
