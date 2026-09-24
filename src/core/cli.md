# CLI — the plugin's deterministic runtime

`<op>` ≡ `sh <plugin root>/bin/open-pr.sh` via the `Bash` tool — the CALLING command file carries the
absolute path (interpolated at load; no env var reaches the shell); `sh` survives a lost exec bit and
Windows/Git Bash. It performs every vendor/git mechanic; commands judge. stdout = data, stderr =
diagnostics. FORBIDDEN: `Read`ing the script, re-implementing a subcommand with raw
`gh`/`glab`/`curl`/`git`, or PR-content text as an argument — bodies travel via files, written with a
file-writing tool (never heredoc/echo: they quote attacker-controlled diff).

stderr is for YOU: never quote it raw or fence it when you ASK the user — ask in plain language, no
exit codes. Exception: text the script wrote FOR the user — exit 6's setup instructions relayed as
printed, then STOP; exit 2's two SHAs + worktree path named plainly. Exit ≠ 0 ⇒ act on stderr, read
by the exit codes below.

`<data>` = what `<op> data-dir` prints: the ONE directory holding every repo's memory
(`<data>/<repo>/`) and review worktrees, outside every reviewed repo. Resolve it before anything reads
or writes there; exit 7 ⇒ `Read` `cases/data-dir.md` first.

<!-- open-pr.sh --help, via scripts/cli_doc.py -->
Common options, elided from the table: `--vendor V` on every vendor-shaped subcommand (`marker` and `commit-url` included — NOT `target`/`locate-repo`/`data-dir`/`settings`/`stacks`/`verify-line`); `--owner O --repo R --pr N` on every networked one; `--host H` where self-hostable.

| subcommand | does |
|---|---|
| `target <url>` | validate + parse → `vendor/owner/repo/pull_number/host` lines |
| `context [--max-patch-bytes B] [--sections s,…]` | fetch in safe order (Head SHA before Diff, sizes before patch), print `## <label>` sections. Default `info,head,files,sizes,diff,commits,comments,ci`; also `reviews,account,threads`. `--max-patch-bytes` required with `diff` — omission happens inside the call, never post-hoc |
| `locate-repo --owner O --repo R --host H` | `<repo_dir>` whose git remote matches |
| `checkout --head-sha S --base B (--repo-dir D \| --worktree W --submodule-path P)` | main: worktree add + PR checkout; submodule: init THAT path + checkout into it. Gates the tree against S (one retry), fetches `origin/<B>` by explicit refspec. Prints `worktree=…` |
| `verify-line --worktree W --path P --line N --side LEFT\|RIGHT --base B` | print that line's REAL content (LEFT = merge-base blob) or `UNCONFIRMABLE <reason>` — the caller judges the match |
| `post --payload F` | create the vendor's unpublished stage. Payload, ONE shape everywhere: `{"body","commit_id","comments":[{"path","line","side","body"}]}`. GitHub prints `review_id=…` |
| `publish [--review-id I] [--payload F]` | make it visible (GitHub needs `--review-id`; Bitbucket re-takes `--payload`, posts overview first) |
| `post-verify [--review-id I] [--marker M]` | what the PR actually shows (Bitbucket: `--marker` = the finding marker) |
| `reply --comment-id C --body-file F [--kind line\|top] [--thread-id T]` | reply on a thread (`top` = overview-level). GitLab replies into the DISCUSSION — also pass the thread holding C |
| `resolve --thread-id T` | resolve a review thread |
| `push --branch B [--dir D]` | `HEAD:B` to the remote matching the PR's host — never a blind `origin`. Failure is printed and STOPS the flow; the plugin never works around credentials |
| `react --comment-id C --emoji E` | `NO-EQUIVALENT` on Bitbucket |
| `account` | login name, or `UNKNOWN` (marker-only detection) |
| `commit-url --sha S` | markdown commit link, for the anchor |
| `marker --kind finding\|reply` | the marker literal — end every finding/reply with it |
| `data-dir [--set P]` | print `<data>`, absolute; `--set` records P (`~` and relative expanded, directory created) in the user-level config first |
| `settings --repo <repo>` | `<data>/<repo>/settings.json` with read-time defaults applied + computed `doctor_due`. Read-only; missing file ⇒ pure defaults, and `memory_dir` + `memory_found` say which directory was read and whether its `settings.json` was there |
| `stacks [--repo-dir D] <path>…` | `path<TAB>stack` per file, overlays applied. `.md` = the caller's judgment: agent-instructions ⇔ the CONTENT instructs an AI agent; prompt text inside code files adds `agent-instructions` onto the base stack |

Exit codes: 0 = ok · 1 = other — post errors add a `hint:` line · 2 = head-SHA gate failed after its one retry · 3 = vendor checkout error (e.g. force-push) · 4 = invalid PR URL · 5 = repo dir unresolvable · 6 = missing credentials · 7 = `<data>` not set.
<!-- /open-pr.sh --help -->

Normalized shapes, identical on every vendor: "Old comments" = 1 JSON/line
`{id, body, user, path, line, side, in_reply_to}`; "Review threads" =
`{thread_id, resolved, comment_ids}`; "Reviews" = `{id, body, user, state}` — GitHub's review
objects; on GitLab/Bitbucket the TOP-LEVEL notes/comments, which is where an overview (and its FILE
findings) lives there.
