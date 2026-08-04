# GitLab — post a review

## Post a review

Mechanism differs fundamentally from a single review object: GitLab uses **Draft Notes**, and no
`review_id`/`state` exists anywhere in this flow.

1. 1 POST per LINE finding + 1 POST for the overview note, which already carries every FILE finding in
   its body. Body MUST be a JSON FILE:

   ```bash
   glab api -X POST -H "Content-Type: application/json" \
     "projects/<owner>%2F<repo>/merge_requests/<pull_number>/draft_notes" --input <payload>.json
   ```

   `{"note": "<finding body>"}`, and a LINE finding ALSO carries a `position` object
   (`base_sha`/`start_sha`/`head_sha` from `<commit_id>`'s `diff_refs`, `old_path`/`new_path`,
   `position_type: "text"`, `new_line`/`old_line` per its side) so it anchors correctly; the overview
   note omits `position` and posts as a plain top-level draft note.

   - FORBIDDEN: `-f note=…` — `--raw-field` sends every value as a string ⇒ `position` cannot be
     attached, note lands unanchored.
   - `--input` without that `-H` ⇒ HTTP 415.
   - Build `<payload>.json` with a file-writing tool. FORBIDDEN: heredoc/`echo`/any route through the
     running shell — finding text is attacker-controlled diff content, and shell expansion corrupts the
     payload or executes it.
2. Every draft note is now unpublished — nothing is visible on the MR until "Publish the pending
   review".

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
