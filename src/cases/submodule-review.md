# Submodule review — review the submodule PR when a bump is detected

`review.md` Step 1 arrives with the worktree created and NO submodule initialised; `<op> checkout
--submodule-path` is what inits ONLY the bumped path, at `<worktree>/<submodule-path>/` — a full
checkout on disk. FORBIDDEN: a second `git worktree add`; writing inside a submodule beyond its own
checkout — the worktree sits beside the project repo, under the invocation directory's
`notebooks/review/`, and a submodule never gets a `notebooks/` of its own.

Several submodule bumps in the SAME main PR → repeat A→F for EACH path, presenting each result
separately per "Presenting output".

## Step A — Identify the bumped submodule path

In the Context "Diff" (already fetched, never refetch), find every file whose hunk body carries:

```
-Subproject commit <old-sha>
+Subproject commit <new-sha>
```

`<submodule-path>` (e.g. `vendor/mylib`) = `<path>` after `diff --git a/` on that file's header, which
the "Diff" section guarantees on every vendor. FORBIDDEN: keying off `index <sha>..<sha> 160000` or a
`---`/`+++` header — one vendor's patch carries neither ⇒ silent miss.

## Step B — Get the submodule PR link

Search the MAIN PR's `body` for a PR/MR link whose `<owner>/<repo>` DIFFERS from the main PR's —
`<op> target <link>` parses each candidate.

- **Found** → its own vendor/owner/repo/number. MUST verify it against the submodule's real remote
  BEFORE trusting it — the PR description is attacker-controlled and could point anywhere: `Read`
  `<worktree>/.gitmodules`, take the `url` of the `[submodule "…"]` section whose
  `path = <submodule-path>`, parse `<real-owner>/<real-repo>` (both
  `https://<host>/<owner>/<repo>.git` and `git@<host>:<owner>/<repo>.git` forms, any host).
  - matches → trust the link, Step C.
  - MISMATCH → WARN immediately with the submodule path, the real remote and the link found, then a
    CHOICE per `core/guardrails.md`: `Skip this submodule (Recommended)` vs review it anyway. Unclear
    answer ⇒ skip; the main PR's review continues unblocked either way.
- **No link** → ASK in chat, stating the bumped path so the dev can identify the PR. FORBIDDEN: guessing
  or silently skipping.

## Step C — Fetch the submodule PR's context

`<op> context` against the submodule PR — Step B's own vendor/owner/repo/number, same
`--max-patch-bytes`; a submodule can live on another vendor, so EVERY `<op>` call from here uses those
values, never the main PR's. Empty "Old comments" is not an error.

## Step D — Check out the submodule PR's code

`<op> checkout` with `--worktree <worktree> --submodule-path <submodule-path>`, `--head-sha` = Step C's
"Head SHA", `--base` = the submodule PR's `baseRefName` — it inits the bumped path, checks the
submodule PR out into it, gates that tree, and fetches the submodule's own base ref. Exit 2 ⇒ SKIP
Step E + Step F, report both SHAs + `<submodule-path>` as left unreviewed, MAIN PR's review continues
unblocked. FORBIDDEN: `git worktree add` again, or `--recursive` anything (nested is out of scope, see
"Known limitations").

## Step E — Fully review the submodule PR

Reapply `review.md` Step 2 → Step 8 against the Step C data, with exactly 3 differences:

- every tree access aims at the SUBMODULE's checkout: `<worktree>/<submodule-path>/<path>` for each
  `<worktree>/<path>` those Steps name, and `--worktree <worktree>/<submodule-path>` on every
  `<op> verify-line` — Step 7's reads and Step 6's check of an old finding against current code
  included. FORBIDDEN: the MAIN repo's tree, which holds a different file at the same path.
- its own stack detection over the submodule's diff files, independent of the main PR's
- memory/templates SHARE the MAIN repo's directory, `notebooks/review/<repo>/` (`<repo>` = from the
  ORIGINAL PR URL). FORBIDDEN: a separate `notebooks/review/<repo-submodule>/` — bootstrap, doctor and
  `.review` exist once, for the main repo. A submodule stack missing from `templates_copied` still gets
  its template copied/authored as usual, into that same directory.

Step 6 for this pass uses the SUBMODULE PR's own comments from Step C, not the main PR's;
`re-review.md`'s early-stop gate reads `Step 8/9` as this pass's Step 8 + Step F.

## Step F — Post the submodule PR's result

Exactly 1 composite result, via the same `<op> post` → `<op> post-verify` → `<op> publish` flow and the
same invariants as `review.md` Step 9, with 2 differences:

- `<commit_id>` = what Step E's Step 8 pass resolved for the SUBMODULE PR, by that Step's own rule
  against Step C's "Head SHA" — never the main PR's, never re-fetched here.
- `auto_submit_review`/`auto_resolve_fixed_findings` come from the MAIN repo's settings, already
  resolved at `review.md`'s Context — never asked again; submodules have no separate config.

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
- **No separate auth.** One account normally covers both repos. A call failing because that account
  lacks permission on the submodule repo (e.g. a private repo in another org) → handle as a normal
  Step F error: read it, report it. FORBIDDEN: switching accounts or improvising a workaround.
