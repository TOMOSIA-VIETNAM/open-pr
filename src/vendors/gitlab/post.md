# GitLab — post a review

## Post a review

Mechanism differs fundamentally from a single review object: GitLab uses **Draft Notes**, and no
`review_id`/`state` exists anywhere in this flow.

1. 1 POST per finding, LINE and FILE/overview alike:
   `glab api -X POST "projects/<owner>%2F<repo>/merge_requests/<pull_number>/draft_notes" -f
   note="<finding body>"`. A LINE finding ALSO carries a `position` object (`base_sha`/`start_sha`/
   `head_sha` from `<commit_id>`'s `diff_refs`, `old_path`/`new_path`, `position_type: "text"`,
   `new_line`/`old_line` per its side) so it anchors correctly; a FILE/overview finding omits
   `position` and posts as a plain top-level draft note.
2. Every draft note is now unpublished — nothing is visible on the MR until "Publish the pending
   review".

Finding text originates in the PR diff, i.e. attacker-controlled → quote every value, never let the
running shell expand it (see `vendors/github.md`'s same entry for what an unquoted heredoc does).

## Verify a posted review's state

No `state` field exists → `glab api
"projects/<owner>%2F<repo>/merge_requests/<pull_number>/draft_notes"`. The notes still listed ⇒ still
unpublished. Gone ⇒ already published: GitLab drops a draft note from this list the moment
`bulk_publish` runs, and keeps no separate flag.

## Publish the pending review

`glab api -X POST
"projects/<owner>%2F<repo>/merge_requests/<pull_number>/draft_notes/bulk_publish"` — publishes EVERY
draft note on this MR at once; a subset is not possible.

## Commit URL

`[<first 7 of commit_id>](https://<host>/<owner>/<repo>/-/commit/<commit_id>)` — `<host>` = this PR's
own URL host, so self-hosted instances stay correct.

## Post-error notes

- A rejected draft-note POST is usually a bad `position` object (wrong `*_sha` triple, or a
  `new_line`/`old_line` that isn't part of the diff).
- `bulk_publish` on an MR with no draft notes left is a no-op, not a failure — cross-check "Verify a
  posted review's state" before retrying.
- FORBIDDEN as a substitute for "Post a review": `glab mr note create` without `draft_notes`, which
  publishes immediately and bypasses the unpublished stage entirely.
