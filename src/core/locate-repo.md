# Locate the PR's own repo directory

Yields `<repo_dir>`. Users keep repos side by side under a workspace and call from it, so the invocation
directory is often not the repo — but WHAT the caller does with `<repo_dir>` is the caller's rule, not
this file's.

1. `git remote -v` at pwd names `<owner>/<repo>` → `<repo_dir>` = `.`, skip 2. Case-insensitive, both
   `https://<host>/<owner>/<repo>.git` and `git@<host>:<owner>/<repo>.git`, `<host>` = this PR's own URL
   host so self-hosted matches.
2. Else `find . -maxdepth 4 -type d -iname "$REPO" 2>&1 | grep -Ev 'node_modules'`, then
   `git -C "<candidate>" remote -v 2>/dev/null` per candidate, cross-checked against `<owner>/<repo>` — a
   matching directory NAME is never enough, the remote MUST match.
   - exactly 1 → that is `<repo_dir>`; state which in 1 short sentence
   - 0 || ≥2 → ask the user to pick or type a path; a sibling repo is invisible from inside another one,
     so suggest calling from the workspace holding them. Unresolvable → STOP:
     ```
     ❌ Could not determine the repo directory for `<owner>/<repo>` of this PR. cd into that repo, or
        into the workspace that contains it, and call this again.
     ```

FORBIDDEN: guessing by directory name, or reading a repo whose remote did not match.
