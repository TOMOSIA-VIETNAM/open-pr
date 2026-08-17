# Bitbucket — worktree checkout

Bitbucket publishes NO per-PR git ref, so the source BRANCH is the only route to the PR head, and a PR from a
fork lives in another repository — hence the lookup both entries start from:

`<curl>
"<api>/pullrequests/<pull_number>?fields=source.repository.full_name,source.branch.name,source.commit.hash"
| jq -r '[.source.repository.full_name, .source.branch.name, .source.commit.hash] | @tsv'` →
`<source_repo>`, `<source_branch>`, `<commit_id>`.

`<source_repo>` == `<owner>/<repo>` ⇒ the branch is on `origin`, which the user's clone already
authenticates. Anything else ⇒ a fork, fetched by URL, where git uses the user's own credential helper.

`git checkout --detach "<commit_id>"` — never the fetched branch tip — is what pins the review to the
commit the PR itself reports. git refusing that hash as unreachable means the source branch was
force-pushed since the PR data was read: STOP and say so. FORBIDDEN: checking out the tip instead, which
reviews code the PR does not show.

## Check out the PR head into a worktree

`(cd "<worktree>" && git fetch origin "<source_branch>" && git checkout --detach "<commit_id>")` for the
same-repo case; `git fetch "https://bitbucket.org/<source_repo>.git" "<source_branch>"` replaces the fetch
for a fork. Detached by construction, into a worktree the CALLER already created.

## Checkout a PR into an already-existing worktree subdirectory

`(cd "<worktree>/<submodule-path>" && git fetch origin "<source_branch-submodule>" && git checkout
--detach "<commit_id-submodule>")`, with the fork variant substituted the same way — every value read from
the SUBMODULE's own PR, never the parent's. Reuses what `git submodule update --init -- <path>` already put
on disk; creates no worktree.
