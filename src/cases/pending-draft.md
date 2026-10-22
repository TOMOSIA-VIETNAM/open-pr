# Pending draft — `<op> post` exit 8

Reached ONLY on that exit: an unpublished review of the caller's own already sits on this PR, and
nothing of this run was posted. Its stdout: `draft_id=<I>`, `commit=<C>` (`UNKNOWN` possible),
`ours=true|false`.

- `ours=false` — a person's own pending review. FORBIDDEN: publishing or discarding it, by any
  means. STOP: tell the user it blocks this review — submit or discard it on the PR, then run again.
- `ours=true` — ONE question naming `<C>` (short), first option (Recommended):

  | `<C>` vs Step 8's `<commit_id>` | first | second |
  |---|---|---|
  | same | `Publish the existing draft` | `Discard it and post this review` |
  | differs, `UNKNOWN` | `Discard it and post this review` | `Publish the existing draft` |

  - Publish → `<op> publish --review-id <I>`, then `<op> post-verify --review-id <I>`. This run's
    payload is never posted. Report it as Step 9 does, saying the published review is the earlier
    draft at `<C>`; watch session: `commit` = `<C>`, `counts` = this run's (the draft's are not read).
  - Discard → `<op> discard --draft-id <I>`, then `<op> post` again and go on with Step 9.
