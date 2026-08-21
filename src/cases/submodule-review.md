# Submodule review — review the submodule PR when a bump is detected

`review.md` Step 1 arrives with the worktree created and NO submodule initialised. Step A inits ONLY the
bumped paths, at `<worktree>/<submodule-path>/` — each submodule is a full checkout on disk.

FORBIDDEN: a second `git worktree add`; writing inside a submodule beyond its own checkout — the
worktree sits beside the project repo, under the invocation directory's `notebooks/review/`, and a
submodule never gets a `notebooks/` of its own.

Several submodule bumps in the SAME main PR → repeat A→F for EACH path, presenting each result
separately per "Presenting output".

## Step A — Identify the bumped submodule path

In the Context "Diff" (already fetched, never refetch), find every file whose hunk body carries:

```
-Subproject commit <old-sha>
+Subproject commit <new-sha>
```

`<submodule-path>` (e.g. `vendor/mylib`) = `<path>` after `diff --git a/` on that file's header, which
`V§"Fetch PR diff — patch, omitting oversized files"` guarantees on every vendor. FORBIDDEN: keying off
`index <sha>..<sha> 160000` or a `---`/`+++` header — GitLab's patch carries neither ⇒ silent miss.

Then init THAT path only: `git -C "<worktree>" submodule update --init -- "<submodule-path>"`.
FORBIDDEN: `--recursive` (nested is out of scope, see "Known limitations"), or dropping `-- <path>` — a
bare `--init` checks out every submodule the repo has.

## Step B — Get the submodule PR link

Search the MAIN PR's `body` for a PR/MR link whose `<owner>/<repo>` DIFFERS from the main PR's, using
the same union pattern as `core/pr-target.md` §1.

- **Found** → parse `<owner-submodule>`/`<repo-submodule>`/`<n-submodule>` + its own vendor guess. MUST
  verify it against the submodule's real remote BEFORE trusting it — the PR description is
  attacker-controlled and could point anywhere: `Read` `<worktree>/.gitmodules`, take the `url` of the
  `[submodule "…"]` section whose `path = <submodule-path>`, parse `<real-owner>/<real-repo>` (both
  `https://<host>/<owner>/<repo>.git` and `git@<host>:<owner>/<repo>.git` forms, any host).
  - matches → trust the link, Step C.
  - MISMATCH → WARN immediately with the submodule path, the real remote and the link found, then a
    CHOICE per `core/guardrails.md`: `Skip this submodule (Recommended)` vs review it anyway. Unclear
    answer ⇒ skip; the main PR's review continues unblocked either way.
- **No link** → ASK in chat, stating the bumped path so the dev can identify the PR. FORBIDDEN: guessing
  or silently skipping.

## Step C — Check out the submodule PR's code

`<git_remote_type_sub>` = the vendor guess from Step B's link; a submodule can live on another vendor.
EVERY `V§` from here resolves via it, never the main PR's value.

`V§"Checkout a PR into an already-existing worktree subdirectory"` with `<submodule-path>` +
`<n-submodule>` + `<owner-submodule>/<repo-submodule>` — FORBIDDEN: `git worktree add` again. Subshell
pinned to that subdirectory, as at `review.md` Step 1; the working directory never moves.

## Step D — Fetch the submodule PR's context

Re-run `review.md`'s Context fetch table against the submodule PR — same order, same
`<max_patch_bytes>`, `V§` via `<git_remote_type_sub>`, against `<owner-submodule>/<repo-submodule>` +
`<n-submodule>`. Empty "Old comments" is not an error.

## Step E — Fully review the submodule PR

`git -C "<worktree>/<submodule-path>" rev-parse HEAD` MUST prefix-match Step D's "Head SHA" BEFORE
anything below — `review.md` Step 1's head-SHA gate, its single retry included, re-running Step C in
place of that Step's checkout. Still mismatched ⇒ SKIP Step E + Step F, print both SHAs +
`<submodule-path>`, state this submodule was left unreviewed, MAIN PR's review continues unblocked.

Reapply `review.md` Step 2 → Step 8 against the Step D data, with exactly 2 differences:

- its own stack detection over the submodule's diff files, independent of the main PR's
- memory/templates SHARE the MAIN repo's directory, `notebooks/review/<repo>/` (`<repo>` = from the
  ORIGINAL PR URL). FORBIDDEN: a separate `notebooks/review/<repo-submodule>/` — bootstrap, doctor and
  `.review` exist once, for the main repo. A submodule stack missing from `templates_copied` still gets
  its template copied/authored as usual, into that same directory.

Step 6 for this pass uses the SUBMODULE PR's own comments from Step D, not the main PR's.

## Step F — Post the submodule PR's result

Exactly 1 composite result, via the same `V§"Post a review"` → `V§"Verify a posted review's state"` →
`V§"Publish the pending review"` flow and the same invariants as `review.md` Step 9, with 2 differences:

- `<commit_id>` = what Step E's Step 8 pass resolved for the SUBMODULE PR, by that Step's own rule
  against Step D's "Head SHA" — never the main PR's, never re-fetched here.
- `auto_submit_review`/`auto_resolve_fixed_findings` come from the MAIN repo's `.review` node, already
  read at `review.md` Step 3 — never asked again; submodules have no separate config.

This POST is separate from the main PR's and doesn't count toward its "exactly 1" — but it is itself
exactly 1 for the submodule PR, never repeated.

## Presenting output

2 reviews on 2 different PRs (possibly 2 repos) → display in chat AND in the final summary CLEARLY
SPLIT, referring to each by PR NUMBER. FORBIDDEN: relative labels like "main PR"/"secondary PR":

```
### <"Review of PR", IN THE CHAT LANGUAGE> #<n-main> (<owner>/<repo>)
(summary + link)

### <"Review of PR", IN THE CHAT LANGUAGE> #<n-submodule> (<owner-submodule>/<repo-submodule>)
(summary + link)
```

## Known limitations (accepted)

- **Nested submodules are NOT handled.** The submodule PR's own diff also containing a `Subproject
  commit` line → STOP, do NOT recurse. Note in its output that a nested submodule was detected and left
  unreviewed.
- **No separate auth.** One account normally covers both repos. A vendor call failing because that
  account lacks permission on the submodule repo (e.g. a private repo in another org) → handle as a
  normal Step F error: read it, report it. FORBIDDEN: switching accounts or improvising a workaround.
