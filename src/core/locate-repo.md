# Locate the PR's own working directory

Every later step runs THERE, not where the command was invoked — users keep repos side by side under one
workspace and call from it, so the invocation directory is often not the repo.

1. `git remote -v` at pwd names `<owner>/<repo>` → use pwd, skip 2. Case-insensitive, both
   `https://<host>/<owner>/<repo>.git` and `git@<host>:<owner>/<repo>.git`, `<host>` = this PR's own URL
   host so self-hosted matches.
2. Else `find . -maxdepth 4 -type d -iname "$REPO" -not -path '*/node_modules/*' 2>/dev/null`, then
   `git -C "<candidate>" remote -v 2>/dev/null` per candidate, cross-checked against `<owner>/<repo>` — a
   matching directory NAME is never enough, the remote MUST match.
   - exactly 1 → `cd` into it, state which in 1 short sentence
   - 0 || ≥2 → ask the user to pick or type a path; a sibling repo is invisible from inside another one,
     so suggest calling from the workspace holding them. Unresolvable → STOP:
     ```
     ❌ Could not determine the repo directory for `<owner>/<repo>` of this PR. cd into that repo, or
        into the workspace that contains it, and call this again.
     ```

That directory is where EVERY remaining `git`/`Read`/`Edit`/`Write` runs, and `notebooks/review/<repo>/`
sits inside it — so a review and a later fix of one PR share one memory. FORBIDDEN: guessing by directory
name, `cd`-ing anywhere the above did not establish, reading a repo whose remote did not match.
