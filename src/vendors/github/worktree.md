# GitHub — worktree checkout

## Check out the PR head into a worktree

`(cd "<worktree>" && gh pr checkout <pull_number> -R "<owner>/<repo>" && git checkout --detach)` — the
`git checkout --detach` MUST follow immediately: `gh pr checkout` leaves the PR's tracking branch
checked out, which git then locks against deletion in the user's own root repo (`cannot delete branch …
checked out at <path>`) until the worktree goes away. Detaching releases that lock without depending on
the user cleaning up.

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && gh pr checkout <n-submodule> -R
"<owner-submodule>/<repo-submodule>")` — reuses what `git submodule update --init -- <path>` already
put on disk; creates no worktree.
