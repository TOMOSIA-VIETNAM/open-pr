# Pending review on a vendor with no server-side draft

Read by the "Post a review" / "Verify a posted review's state" / "Publish the pending review" entries of a
vendor whose API makes every comment visible the moment it is created. Such a vendor cannot hold a draft
for us, so the unpublished stage is a LOCAL file, and this atom owns everything about it except the
payload shape and the POST command — those stay in that vendor's `post.md`.

## The staging file

`notebooks/review/<repo>/worktrees/pending-review-pr<pull_number>.json`

That directory is already ignored by the memory repo, and `/open-pr:clean` deletes only directories inside
it, so the file is neither committed nor swept. `pr<pull_number>` in the name is what keeps 2 reviews
running at once from overwriting each other.

A JSON array — the overview element FIRST, then 1 element per LINE finding:

```json
[{"key": "<unique>", "posted": false, "payload": "<the vendor's own comment payload>"}]
```

| field | rule |
|---|---|
| `key` | unique inside the file: `overview`, or `<path>:<line>` for a LINE finding. The ONLY thing that makes a half-finished publish resumable |
| `posted` | `false` until published, then the comment id the vendor returned — so the mark and the proof of it are one value |
| `payload` | exactly what that vendor's POST body must be, nothing wrapped around it |

Build the file under the payload rule of `core/raw-http-vendor.md` — it holds for the staging file too,
`payload` being the exact body that later goes on the wire.

## "Post a review" ⇒ write the file, call nothing

Nothing is on the PR when that entry returns, whatever the file holds.

## "Verify …" ⇒ count what the PR shows, compare against the marks

Count the comments on the PR carrying this run's finding marker (`core/finding-markers.md`):

| count | state |
|---|---|
| 0 | still unpublished |
| == elements marked `posted` | that many published, the rest still pending → resume |
| > that | comments outside this run carry the marker ⇒ REPORT it, post nothing |

Matching on this plugin's own marker and its own `key`s is what keeps a human reviewing the same PR at the
same moment from being counted as this run.

## "Publish …" ⇒ 1 POST per unmarked element, in file order

`jq -c '.[<index>].payload' <staging file>` piped into that vendor's own comment POST, overview first.

`Edit` that element's `"posted"` to the returned id after EACH 2xx — FORBIDDEN:
posting every element and marking afterwards, which leaves a failure part-way through with no record of
what already landed.

A part-way failure resumes from the unmarked elements. FORBIDDEN: re-POSTing a marked one — there is no
bulk undo, so a duplicated finding has to be deleted comment by comment.

The overview element's recorded id outlives the run: it is the comment a FILE-level finding's permalink
addresses, since FILE findings live in the overview body on such a vendor.
