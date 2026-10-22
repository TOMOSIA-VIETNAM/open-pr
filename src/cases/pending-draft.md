# Pending draft — `<op> post` exit 8

Reached ONLY on that exit: an unpublished review of the caller's own already sits on this PR, and
nothing of this run was posted. Its stdout: `draft_id=<I>`, `commit=<C>` (`UNKNOWN` possible),
`ours=true|false`, `overview=true|false` (the plugin's overview is in it).

- `ours=false` — a person's own pending review. FORBIDDEN: publishing or discarding it, by any
  means. STOP: tell the user it blocks this review — submit or discard it on the PR, then run again.
- `ours=true` — ONE question naming `<C>` (short), first option (Recommended):

  | draft | first | second |
  |---|---|---|
  | `overview=false` | `Discard it and post this review` | `Publish the existing draft` |
  | `<C>` = Step 8's `<commit_id>` | `Publish the existing draft` | `Discard it and post this review` |
  | other `<C>`, `UNKNOWN` | `Discard it and post this review` | `Publish the existing draft` |

  - Publish → `<op> publish --review-id <I>`, then `<op> post-verify --review-id <I>`; its `url=` line
    is the link, its `counts=` line the counts. This run's payload is never posted. Report: the earlier
    draft (at `<C>`) was published + the link + counts; watch session: `commit` = `<C>`, `counts` = that
    JSON — no `counts=` line ⇒ `null`, `note` saying they could not be counted.
  - Discard → `<op> discard --draft-id <I>`, then `<op> post` again and go on with Step 9.
