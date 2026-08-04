# GitLab — worktree checkout

## Check out the PR head into a worktree

`glab mr checkout` has no worktree support (glab issue #8217) — fetch the MR ref by hand:

`(cd "<worktree>" && git fetch origin
"refs/merge-requests/<pull_number>/head:refs/remotes/origin/merge-requests/<pull_number>" && git
checkout --detach "refs/remotes/origin/merge-requests/<pull_number>")` — GitLab exposes that ref for
every MR, and this is detached by construction, so no follow-up detach is needed.

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && git fetch origin
"refs/merge-requests/<n-submodule>/head:refs/remotes/origin/merge-requests/<n-submodule>" && git
checkout --detach "refs/remotes/origin/merge-requests/<n-submodule>")` — reuses what `git submodule
update --init -- <path>` already put on disk; creates no worktree. FORBIDDEN here: `glab mr checkout
--repo`, which checks out the WRONG repo's MR in this cross-repo case (glab issue #7972).
