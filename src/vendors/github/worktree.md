# GitHub — worktree checkout

## Check out the PR head into a worktree

`(cd "<worktree>" && git fetch origin "refs/pull/<pull_number>/head" && git checkout --detach
FETCH_HEAD)` — GitHub exposes that ref for every PR, fork included; detached by construction.
FORBIDDEN: `gh pr checkout`, which creates the PR's tracking branch and exits 128 (`already checked out
at <path>`) when the user's own clone sits on it.

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && git fetch origin "refs/pull/<n-submodule>/head" && git checkout
--detach FETCH_HEAD)` — `origin` = the SUBMODULE's remote. Reuses what `git submodule update --init --
<path>` already put on disk; creates no worktree.
