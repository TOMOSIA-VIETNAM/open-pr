# Vendor interface

Every vendor is `src/vendors/<name>/{fetch,worktree,post,thread}.md`, each file carrying the SAME entry
headings below with the text copied verbatim, so a caller only ever writes `V§"<entry>"`
(`core/pr-target.md` §3) and never names a vendor. Entry names stay vendor-neutral even where one vendor's
own terminology differs — "PR" means MR on GitLab, and a heading may describe a mechanism that isn't
literally what its name suggests for that vendor. Anything vendor-wide (terminology, id encoding, auth)
belongs in `fetch.md`, the group every run loads first.

**The size filter goes INSIDE the command.** Whatever a command prints is in the agent's context for the
rest of the run, so filtering afterwards saves nothing — an unbounded diff fetch costs more than every
prompt file in the run combined.

Reference doc for whoever adds a vendor. FORBIDDEN: `Read`ing it during a review/fix run — the group
files are the run-time artifact.

| group | entry | must return / do |
|---|---|---|
| fetch | Fetch PR basic info | the caller's requested fields, under this plugin's common names (`number`, `title`, `body`, `author`, `baseRefName`, `headRefName`) |
| fetch | Fetch PR head commit SHA | `<commit_id>` of the PR's head |
| fetch | Fetch PR diff — file list | changed paths, 1 per line |
| fetch | Fetch PR diff — patch, omitting oversized files | a unified diff of only the files whose patch is under the caller's `<max_patch_bytes>` |
| fetch | Fetch PR commits headlines | 1 subject line per commit |
| fetch | Fetch PR review comments (LINE-level findings) | line-anchored comments, with author + id + any reply linkage |
| fetch | Fetch PR diff size per file | a size proxy per file, or `UNKNOWN` when the vendor withheld or collapsed it. Never 0 for a file the vendor declined to diff |
| fetch | Fetch CI checks | every check unfiltered, each with a pass/fail bucket + name + link; never exit non-zero when there is no CI |
| fetch | Fetch PR reviews (FILE-level findings + review_id) | review bodies + their ids — or an explicit "no equivalent" when the vendor has no review object |
| fetch | Fetch account running the command | the authenticated account's login |
| fetch | Fetch review threads (id + isResolved + comment ids) | thread id, resolved flag, and the comment ids inside each thread |
| worktree | Check out the PR head into a worktree | a DETACHED checkout of the PR head into a worktree the CALLER already created (`git worktree add` is vendor-agnostic, so the caller owns it) |
| worktree | Checkout a PR into an already-existing worktree subdirectory | the same, reusing a directory `git submodule update` already created — never a new worktree |
| post | Post a review | composite: every LINE finding anchored to its line/side + the overview body, left UNPUBLISHED. May take any number of calls |
| post | Verify a posted review's state | whether "Post a review"'s result is still unpublished, without a race against someone else's concurrent review |
| post | Publish the pending review | make that result visible |
| post | Commit URL | a markdown link to one commit, label = the SHA's first 7 chars, code-styled |
| post | Post-error notes | this vendor's known failure modes for the 3 entries above, and the shortcut commands that must never substitute for them |
| thread | Reply on a PR | a reply inside an existing thread, for a LINE finding and for a FILE/overview finding |
| thread | Resolve a review thread | mark a thread resolved, given a finding's `comment_id` |
| thread | React to a PR comment | add one of `+1`/`heart`/`hooray`/`rocket`/`confused`/`eyes` to a comment |
| thread | Finding permalink | a URL addressing a FILE-level finding — or an explicit "none exists" |
