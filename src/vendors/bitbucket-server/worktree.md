# Bitbucket Data Center — worktree checkout

`<api>`, `<curl>` and the auth variable are defined in this vendor's `fetch.md`, always loaded before this
file. Neither entry here calls the API: this vendor publishes a git ref per PR, so git alone reaches the
head, including when the PR comes from a fork.

## Check out the PR head into a worktree

`(cd "<worktree>" && git fetch origin
"refs/pull-requests/<pull_number>/from:refs/remotes/origin/pull-requests/<pull_number>" && git checkout
--detach "refs/remotes/origin/pull-requests/<pull_number>")` — detached by construction, into a worktree
the CALLER already created, so no follow-up detach is needed.

The ref is `/from`, the PR's own head. FORBIDDEN: `/merge`, which is a merge preview commit that exists in
no branch and would have the review report lines nobody wrote.

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && git fetch origin
"refs/pull-requests/<n-submodule>/from:refs/remotes/origin/pull-requests/<n-submodule>" && git checkout
--detach "refs/remotes/origin/pull-requests/<n-submodule>")` — `<n-submodule>` = the SUBMODULE's own PR.
Reuses what `git submodule update --init -- <path>` already put on disk; creates no worktree.
